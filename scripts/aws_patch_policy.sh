#!/usr/bin/env bash
# Patch the substrate policy with the permissions the first pass missed.
#
#   Run this in AWS CloudShell, NOT with the key in .env.aws.
#   That key belongs to the scoped user, which deliberately cannot modify IAM --
#   a user that can rewrite its own policy is not scoped.
#
# Adds, over the original:
#   * ecr:DescribeRepositories / DescribeImages / GetDownloadUrlForLayer
#       -- the first pass granted push and list but not describe, so the
#          registry probe could not read back what it wrote.
#   * bedrock:ListInferenceProfiles / GetInferenceProfile
#       -- several Nova models are only invocable through an inference profile,
#          and the profile id cannot be discovered without these.
#   * elasticfilesystem:DescribeFileSystems / DescribeMountTargets
#       -- read-only, for the EFS arm. Creating the filesystem stays an admin
#          action; this only lets the experiment see what exists.
#
# It creates a new policy VERSION and sets it default, so the change is
# reversible: the previous version stays listed and can be restored.

set -euo pipefail

POLICY_NAME="CovertChannelSubstrateAccess"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
POLICY_ARN="arn:aws:iam::${ACCOUNT}:policy/${POLICY_NAME}"
BUCKET="covert-channel-substrate-${ACCOUNT}"

echo "account : $ACCOUNT"
echo "policy  : $POLICY_ARN"
echo

DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SubstrateBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::${BUCKET}"
    },
    {
      "Sid": "SubstrateObjects",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:GetObjectAttributes"],
      "Resource": "arn:aws:s3:::${BUCKET}/*"
    },
    {
      "Sid": "SubstrateRegistry",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken", "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload", "ecr:BatchGetImage", "ecr:ListImages",
        "ecr:DescribeImages", "ecr:BatchDeleteImage",
        "ecr:DescribeRepositories", "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BehaviouralArmModels",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel", "bedrock:ListFoundationModels",
        "bedrock:ListInferenceProfiles", "bedrock:GetInferenceProfile"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ElasticFileSystemReadOnly",
      "Effect": "Allow",
      "Action": ["elasticfilesystem:DescribeFileSystems", "elasticfilesystem:DescribeMountTargets"],
      "Resource": "*"
    }
  ]
}
JSON
)

# A managed policy holds at most five versions. Drop the oldest non-default
# ones so this stays re-runnable rather than failing on the sixth edit.
VERSIONS=$(aws iam list-policy-versions --policy-arn "$POLICY_ARN" \
           --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text)
COUNT=$(echo "$VERSIONS" | wc -w)
if [ "$COUNT" -ge 4 ]; then
  for v in $VERSIONS; do
    echo "   pruning old version $v"
    aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$v" || true
  done
fi

echo "== creating new default version =="
NEW=$(aws iam create-policy-version --policy-arn "$POLICY_ARN" \
      --policy-document "$DOC" --set-as-default \
      --query 'PolicyVersion.VersionId' --output text)
echo "   now default: $NEW"

echo
echo "=================================================================="
echo " Policy updated. No new key needed -- the existing one in"
echo " .env.aws picks this up immediately."
echo
echo " Verify from your PC:"
echo "   aws ecr describe-repositories --profile covert"
echo "=================================================================="
