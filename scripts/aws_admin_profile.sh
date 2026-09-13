#!/usr/bin/env bash
# Create a second, broader profile so the infrastructure can be driven from your own machine
# instead of CloudShell -- without putting account-root credentials on a laptop.
#
#   Run once in AWS CloudShell. Writes covert-admin.env for you to download.
#
# Why not just use the console/root key
# -------------------------------------
# Root or full-admin keys on a workstation are the failure this repo has already had once: the
# project's other .env records a key that had to be rotated because it reached a chat transcript.
# A key that can do everything turns any leak into an account-wide incident. This one is bounded
# to the resources this experiment actually touches, so the blast radius of a leak is the
# experiment.
#
# What it can do: create and tear down the EFS/EC2 substrate arm, read instance state, read logs.
# What it deliberately cannot do: touch IAM outside this project's own role names, create users,
# attach policies to anything else, or reach any S3 bucket but this one.
#
# The IAM statement is the one worth reading before you run this. `iam:CreateRole` plus
# `iam:PassRole` is, in general, a privilege-escalation path -- a principal that can mint a role
# and hand it to a machine can grant itself whatever that role holds. It is scoped here by name
# to `covert-channel-*`, and PassRole is restricted to the EC2 service, which is what keeps it a
# bounded capability rather than a general one.

set -euo pipefail

REGION="${AWS_REGION:-eu-north-1}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="covert-channel-substrate-${ACCOUNT}"
USER_NAME="covert-channel-operator"
POLICY_NAME="CovertChannelOperator"
POLICY_ARN="arn:aws:iam::${ACCOUNT}:policy/${POLICY_NAME}"
OUT="$HOME/covert-admin.env"

echo "account $ACCOUNT / region $REGION"

DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadEverythingWeDiagnose",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*", "elasticfilesystem:Describe*",
        "iam:GetRole", "iam:GetPolicy", "iam:GetPolicyVersion", "iam:ListPolicyVersions",
        "iam:ListRoles", "iam:ListInstanceProfiles",
        "ssm:GetParameter", "ssm:GetParameters",
        "logs:DescribeLogGroups", "logs:DescribeLogStreams", "logs:GetLogEvents",
        "bedrock:List*", "bedrock:Get*", "ecr:Describe*", "ecr:List*",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BuildTheSubstrateArm",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances", "ec2:CreateTags",
        "ec2:CreateSecurityGroup", "ec2:AuthorizeSecurityGroupIngress",
        "elasticfilesystem:CreateFileSystem", "elasticfilesystem:CreateMountTarget",
        "elasticfilesystem:CreateTags", "elasticfilesystem:TagResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DestroyOnlyWhatThisProjectTagged",
      "Effect": "Allow",
      "Action": [
        "ec2:TerminateInstances", "ec2:DeleteSecurityGroup",
        "elasticfilesystem:DeleteFileSystem", "elasticfilesystem:DeleteMountTarget"
      ],
      "Resource": "*",
      "Condition": {
        "StringLike": {"aws:ResourceTag/Name": "covert-channel*"}
      }
    },
    {
      "Sid": "ProjectRolesOnly",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole", "iam:DeleteRole", "iam:PutRolePolicy", "iam:DeleteRolePolicy",
        "iam:CreateInstanceProfile", "iam:DeleteInstanceProfile",
        "iam:AddRoleToInstanceProfile", "iam:RemoveRoleFromInstanceProfile"
      ],
      "Resource": [
        "arn:aws:iam::${ACCOUNT}:role/covert-channel-*",
        "arn:aws:iam::${ACCOUNT}:instance-profile/covert-channel-*"
      ]
    },
    {
      "Sid": "PassOnlyProjectRolesAndOnlyToEC2",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::${ACCOUNT}:role/covert-channel-*",
      "Condition": {"StringEquals": {"iam:PassedToService": "ec2.amazonaws.com"}}
    },
    {
      "Sid": "TheExperimentBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::${BUCKET}"
    },
    {
      "Sid": "TheExperimentObjects",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:GetObjectAttributes"],
      "Resource": "arn:aws:s3:::${BUCKET}/*"
    },
    {
      "Sid": "Inference",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "*"
    }
  ]
}
JSON
)

if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  for v in $(aws iam list-policy-versions --policy-arn "$POLICY_ARN" \
             --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text); do
    aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$v" || true
  done
  aws iam create-policy-version --policy-arn "$POLICY_ARN" --policy-document "$DOC" \
      --set-as-default >/dev/null
  echo "policy updated"
else
  aws iam create-policy --policy-name "$POLICY_NAME" --policy-document "$DOC" >/dev/null
  echo "policy created"
fi

aws iam get-user --user-name "$USER_NAME" >/dev/null 2>&1 || \
  aws iam create-user --user-name "$USER_NAME" >/dev/null
aws iam attach-user-policy --user-name "$USER_NAME" --policy-arn "$POLICY_ARN"

# Retire old keys: a user may hold two, and a stale one left valid is a liability.
for k in $(aws iam list-access-keys --user-name "$USER_NAME" \
           --query 'AccessKeyMetadata[].AccessKeyId' --output text); do
  echo "  retiring previous key $k"
  aws iam delete-access-key --user-name "$USER_NAME" --access-key-id "$k"
done

KEY_JSON=$(aws iam create-access-key --user-name "$USER_NAME")
AK=$(echo "$KEY_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["AccessKey"]["AccessKeyId"])')
SK=$(echo "$KEY_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["AccessKey"]["SecretAccessKey"])')

cat > "$OUT" <<ENV
# Operator profile -- can build and tear down the substrate arm, and read state.
# Bounded to this project's resources. NOT account admin, and not a root key.
# LOCAL ONLY. Do not commit, paste into a chat, or screenshot.

AWS_ACCESS_KEY_ID=$AK
AWS_SECRET_ACCESS_KEY=$SK
AWS_DEFAULT_REGION=$REGION
AWS_REGION=$REGION
ARS_S3_BUCKET=$BUCKET
ENV
chmod 600 "$OUT"

echo
echo "=================================================================="
echo " wrote $OUT"
echo " Download: Actions > Download file > covert-admin.env"
echo " Save as:  project-v2/.env.admin"
echo
echo " If it ever leaks, revoke with:"
echo "   aws iam delete-access-key --user-name $USER_NAME --access-key-id $AK"
echo "=================================================================="
