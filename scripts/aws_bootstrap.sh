#!/usr/bin/env bash
# Bootstrap the AWS side of the real-substrate arm (W-2), then emit a .env to download.
#
#   Run this in AWS CloudShell (us-east-1). It creates:
#     * one S3 bucket        -- the real namespace the ladder is measured against
#     * one ECR repository   -- a real OCI registry, the Tier 2 substrate
#     * one IAM user + policy scoped to exactly those two resources, plus
#       bedrock:InvokeModel for the behavioural arm
#     * one access key, written into a .env you download from CloudShell
#
# Least privilege on purpose. The policy names the bucket and the repository
# explicitly rather than granting s3:* or ecr:*, so a leaked key from this file
# can touch the experiment's own resources and nothing else in the account.
#
# Nothing here needs a model. The capacity ladder is measured with no inference
# calls at all, so this half cannot be blocked by a Bedrock quota.

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
STAMP="$(date +%Y%m%d)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"

USER_NAME="covert-channel-substrate"
POLICY_NAME="CovertChannelSubstrateAccess"
BUCKET="covert-channel-substrate-${ACCOUNT}"
REPO="covert-channel-cache"
OUT="$HOME/covert-channel.env"

echo "account : $ACCOUNT"
echo "region  : $REGION"
echo "bucket  : $BUCKET"
echo "repo    : $REPO"
echo

# ---------------------------------------------------------------- substrates
echo "== S3 bucket =="
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "   exists, reusing"
else
  # us-east-1 is the one region that rejects a LocationConstraint.
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
  # The substrate must never be public: it holds encoded payloads during a run.
  aws s3api put-public-access-block --bucket "$BUCKET" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  echo "   created, public access blocked"
fi

echo "== ECR repository =="
if aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1; then
  echo "   exists, reusing"
else
  aws ecr create-repository --repository-name "$REPO" --region "$REGION" >/dev/null
  echo "   created"
fi

# ---------------------------------------------------------------- iam
echo "== IAM policy =="
POLICY_DOC=$(cat <<JSON
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
        "ecr:DescribeImages", "ecr:BatchDeleteImage"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BehaviouralArmModels",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:ListFoundationModels"],
      "Resource": "*"
    }
  ]
}
JSON
)

POLICY_ARN="arn:aws:iam::${ACCOUNT}:policy/${POLICY_NAME}"
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  echo "   exists, reusing $POLICY_ARN"
else
  aws iam create-policy --policy-name "$POLICY_NAME" \
    --policy-document "$POLICY_DOC" >/dev/null
  echo "   created $POLICY_ARN"
fi

echo "== IAM user =="
if aws iam get-user --user-name "$USER_NAME" >/dev/null 2>&1; then
  echo "   exists, reusing"
else
  aws iam create-user --user-name "$USER_NAME" >/dev/null
  echo "   created"
fi
aws iam attach-user-policy --user-name "$USER_NAME" --policy-arn "$POLICY_ARN"
echo "   policy attached"

# An IAM user may hold at most two access keys. Retire the old ones so this
# script stays re-runnable and so a key that has been sitting around is not
# left valid indefinitely.
for k in $(aws iam list-access-keys --user-name "$USER_NAME" \
           --query 'AccessKeyMetadata[].AccessKeyId' --output text); do
  echo "   deleting previous key $k"
  aws iam delete-access-key --user-name "$USER_NAME" --access-key-id "$k"
done

echo "== access key =="
KEY_JSON=$(aws iam create-access-key --user-name "$USER_NAME")
AK=$(echo "$KEY_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["AccessKey"]["AccessKeyId"])')
SK=$(echo "$KEY_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["AccessKey"]["SecretAccessKey"])')
echo "   created ${AK:0:8}..."

# ---------------------------------------------------------------- .env
cat > "$OUT" <<ENV
# Real-substrate arm (W-2) -- generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Scoped to one bucket and one repository; see policy $POLICY_NAME.
# LOCAL ONLY. Do not commit, paste into a chat, or screenshot.

AWS_ACCESS_KEY_ID=$AK
AWS_SECRET_ACCESS_KEY=$SK
AWS_DEFAULT_REGION=$REGION
AWS_REGION=$REGION

# Substrates the ladder is measured against
ARS_S3_BUCKET=$BUCKET
ARS_ECR_REPO=$REPO
ARS_ECR_REGISTRY=${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com

# Behavioural arm (optional; needs model access enabled in the Bedrock console)
BEDROCK_MODEL_ID=amazon.nova-pro-v1:0
ENV
chmod 600 "$OUT"

echo
echo "=================================================================="
echo " wrote $OUT"
echo
echo " Download it:  CloudShell menu (top right) > Actions > Download file"
echo "               path:  covert-channel.env"
echo
echo " Then save it as  project-v2/.env.aws  on your machine."
echo
echo " NOTE: Nova needs one manual step -- Bedrock console > Model access"
echo "       > enable Amazon Nova. IAM permission alone is not enough."
echo "=================================================================="
