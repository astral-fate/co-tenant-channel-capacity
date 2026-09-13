#!/usr/bin/env bash
# Launch the EFS ladder run from this machine, with a failure that can be diagnosed.
#
#   bash scripts/efs_ladder_run.sh          # uses profile covert-admin
#
# What changed from the CloudShell version, and why
# -------------------------------------------------
# The first attempt hung for thirteen minutes and produced nothing. It could not be diagnosed
# because the log was uploaded once, at the end, and the instance self-terminated -- so a hang
# before that line destroyed the only evidence of itself. Three changes make the same failure
# legible:
#
#   * the log is shipped after every phase, so a hang leaves a trail up to the point it hung;
#   * `mount` runs under `timeout`, because a wedged NFS mount blocks forever rather than
#     failing, which is the most likely cause of a silent hang on this path;
#   * a background watchdog force-uploads and terminates after 12 minutes, so the box cannot
#     sit running and billing after the run has stopped making progress.
#
# The mount also falls back to plain nfs4 if `amazon-efs-utils` is unavailable, which is a real
# possibility on AL2023 in some regions and would otherwise present as the same silent hang.

set -euo pipefail

PROFILE="${AWS_PROFILE_OVERRIDE:-covert-admin}"
AWS="/c/Program Files/Amazon/AWSCLIV2/aws.exe"
[ -x "$AWS" ] || AWS="aws"

REGION=$("$AWS" configure get region --profile "$PROFILE")
ACCOUNT=$("$AWS" sts get-caller-identity --profile "$PROFILE" --query Account --output text)
BUCKET="covert-channel-substrate-${ACCOUNT}"
NAME="covert-channel-efs"
ROLE="covert-channel-efs-runner"

FS=$("$AWS" efs describe-file-systems --profile "$PROFILE" \
     --query "FileSystems[?Name=='${NAME}'].FileSystemId | [0]" --output text)
SG=$("$AWS" ec2 describe-security-groups --profile "$PROFILE" \
     --filters Name=group-name,Values="$NAME" --query 'SecurityGroups[0].GroupId' --output text)
SUBNET=$("$AWS" efs describe-mount-targets --profile "$PROFILE" --file-system-id "$FS" \
         --query 'MountTargets[0].SubnetId' --output text)
# Git Bash rewrites a leading "/" into a Windows path, so the parameter name arrives as
# "C:/Program Files/Git/aws/service/..." and returns as an InvalidParameter rather than an
# error. MSYS_NO_PATHCONV disables that conversion for this call.
AMI=$(MSYS_NO_PATHCONV=1 "$AWS" ssm get-parameters --profile "$PROFILE" \
      --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
      --query 'Parameters[0].Value' --output text)
# Fail here rather than let RunInstances reject "None" -- a malformed id is a lookup bug, and
# the message from RunInstances hides which lookup produced it.
[ -n "$AMI" ] && [ "$AMI" != "None" ] || { echo "AMI lookup failed: '$AMI'" >&2; exit 1; }

echo "region $REGION / fs $FS / sg $SG / subnet $SUBNET"
echo "ami $AMI"

USERDATA=$(cat <<EOF
#!/bin/bash
exec > /var/log/ladder.log 2>&1
set -x
S3=s3://${BUCKET}/efs-run/results
ship() { aws s3 cp /var/log/ladder.log \$S3/ladder.log --region ${REGION} 2>/dev/null || true; }

# Force an exit even if something below wedges, so the box cannot bill indefinitely.
( sleep 720
  echo "WATCHDOG: 12 minutes elapsed, forcing upload and shutdown"
  ship
  shutdown -h now ) &

echo "PHASE install"; ship
dnf install -y python3 unzip >/dev/null 2>&1 || true
dnf install -y amazon-efs-utils >/dev/null 2>&1 || echo "efs-utils unavailable, will use nfs4"
ship

echo "PHASE mount"; ship
mkdir -p /mnt/efs
# A wedged NFS mount blocks forever. Bound it, and fall back to plain nfs4.
if ! timeout 90 mount -t efs -o tls ${FS}:/ /mnt/efs; then
  echo "efs-utils mount failed or timed out, trying nfs4"
  timeout 90 mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2 \
    ${FS}.efs.${REGION}.amazonaws.com:/ /mnt/efs || echo "MOUNT FAILED"
fi
mount | grep -i efs || echo "NO EFS MOUNT PRESENT"
ship

echo "PHASE code"; ship
mkdir -p /mnt/efs/substrate /opt/run/results/real-substrate /opt/run/results/capacity
cd /opt/run
aws s3 cp s3://${BUCKET}/efs-run/code.zip code.zip --region ${REGION}
unzip -q -o code.zip
export PYTHONPATH=/opt/run/src:/opt/run/real
ship

echo "PHASE probe"; ship
timeout 300 python3 real/probe_limits.py /mnt/efs/substrate || echo "PROBE FAILED"
cp -f results/real-substrate/*.json /opt/run/results/real-substrate/ 2>/dev/null || true
ship

echo "PHASE ladder"; ship
timeout 900 python3 src/capacity.py --root /mnt/efs/substrate \
  --json /opt/run/results/capacity/capacity-efs.json || echo "LADDER FAILED"
ship

echo "PHASE upload"
mount > /opt/run/results/real-substrate/mount-evidence.txt 2>&1 || true
df -h /mnt/efs >> /opt/run/results/real-substrate/mount-evidence.txt 2>&1 || true
aws s3 cp /opt/run/results \$S3/ --recursive --region ${REGION} || true
ship
echo "PHASE done"; ship
shutdown -h now
EOF
)

IID=$("$AWS" ec2 run-instances --profile "$PROFILE" --image-id "$AMI" --instance-type t3.micro \
      --subnet-id "$SUBNET" --security-group-ids "$SG" \
      --iam-instance-profile Name="$ROLE" \
      --instance-initiated-shutdown-behavior terminate \
      --user-data "$USERDATA" \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME-runner}]" \
      --query 'Instances[0].InstanceId' --output text)

echo
echo "instance $IID"
echo "log ships after every phase to s3://${BUCKET}/efs-run/results/ladder.log"
echo "watchdog forces shutdown at 12 minutes"
