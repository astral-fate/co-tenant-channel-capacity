#!/usr/bin/env bash
# Measure the capacity ladder on a real network filesystem (W-2), then tear the machine down.
#
#   Run in AWS CloudShell. Needs admin identity: the scoped key in .env.aws holds read-only
#   EFS by design, so it can observe this infrastructure but not create it.
#
# Why EFS and not S3
# ------------------
# The S3 probe established that an object store cannot host this measurement: its key space is
# flat, so `dirname` is not separable from `filename` and two rungs of the ladder collapse into
# one. EFS is a real POSIX mount -- real directories, settable timestamps, real entry limits --
# which is the substrate class the synthetic model was standing in for. Measuring there is what
# L3 concedes has not been done.
#
# Shape of the run
# ----------------
# Nothing interactive. An EC2 instance boots, mounts the filesystem, pulls the code from S3,
# probes the mount's real limits, measures the ladder against it, uploads both artifacts back to
# S3, and terminates itself. No SSH, no key pair, no open inbound port -- the security group
# admits NFS from itself only, so the mount is reachable from the instance and from nothing else.
#
# Cost is a few cents: one t3.micro for the minutes it runs, plus EFS storage measured in
# megabytes. The self-terminate is what keeps it that way, so it is deliberately the last line
# of user-data rather than a manual step.

set -euo pipefail

REGION="${AWS_REGION:-eu-north-1}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="covert-channel-substrate-${ACCOUNT}"
NAME="covert-channel-efs"
ROLE="covert-channel-efs-runner"

echo "account $ACCOUNT / region $REGION / bucket $BUCKET"

# ---------------------------------------------------------------- network
VPC=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true \
      --query 'Vpcs[0].VpcId' --output text)
SUBNET=$(aws ec2 describe-subnets --region "$REGION" --filters Name=vpc-id,Values="$VPC" \
         --query 'Subnets[0].SubnetId' --output text)
AZ=$(aws ec2 describe-subnets --region "$REGION" --subnet-ids "$SUBNET" \
     --query 'Subnets[0].AvailabilityZone' --output text)
echo "vpc $VPC / subnet $SUBNET / az $AZ"

SG=$(aws ec2 describe-security-groups --region "$REGION" \
     --filters Name=group-name,Values="$NAME" Name=vpc-id,Values="$VPC" \
     --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG" = "None" ] || [ -z "$SG" ]; then
  SG=$(aws ec2 create-security-group --region "$REGION" --group-name "$NAME" \
       --description "NFS between the ladder runner and its EFS mount" --vpc-id "$VPC" \
       --query 'GroupId' --output text)
  # NFS from this group to this group only. No inbound from the internet at any point.
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG" \
      --protocol tcp --port 2049 --source-group "$SG" >/dev/null
  echo "security group $SG created (NFS self-referencing only)"
else
  echo "security group $SG reused"
fi

# ---------------------------------------------------------------- filesystem
FS=$(aws efs describe-file-systems --region "$REGION" \
     --query "FileSystems[?Name=='${NAME}'].FileSystemId | [0]" --output text 2>/dev/null || echo "None")
if [ "$FS" = "None" ] || [ -z "$FS" ]; then
  FS=$(aws efs create-file-system --region "$REGION" --performance-mode generalPurpose \
       --throughput-mode bursting --tags Key=Name,Value="$NAME" \
       --query 'FileSystemId' --output text)
  echo "efs $FS creating ..."
  until [ "$(aws efs describe-file-systems --region "$REGION" --file-system-id "$FS" \
             --query 'FileSystems[0].LifeCycleState' --output text)" = "available" ]; do
    sleep 5
  done
  echo "efs $FS available"
else
  echo "efs $FS reused"
fi

if [ -z "$(aws efs describe-mount-targets --region "$REGION" --file-system-id "$FS" \
           --query 'MountTargets[0].MountTargetId' --output text 2>/dev/null | grep -v None)" ]; then
  aws efs create-mount-target --region "$REGION" --file-system-id "$FS" \
      --subnet-id "$SUBNET" --security-groups "$SG" >/dev/null
  echo "mount target creating ..."
  until [ "$(aws efs describe-mount-targets --region "$REGION" --file-system-id "$FS" \
             --query 'MountTargets[0].LifeCycleState' --output text)" = "available" ]; do
    sleep 10
  done
fi
echo "mount target available"

# ---------------------------------------------------------------- instance role
# The instance needs S3 for the code in and the results out, and nothing else.
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},
                  "Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam put-role-policy --role-name "$ROLE" --policy-name s3-run-artifacts \
    --policy-document "{
      \"Version\":\"2012-10-17\",
      \"Statement\":[{\"Effect\":\"Allow\",
        \"Action\":[\"s3:GetObject\",\"s3:PutObject\"],
        \"Resource\":\"arn:aws:s3:::${BUCKET}/efs-run/*\"}]}" >/dev/null
  aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE" >/dev/null
  echo "instance role $ROLE created; waiting for propagation"
  sleep 15
else
  echo "instance role $ROLE reused"
fi

AMI=$(aws ssm get-parameters --region "$REGION" \
      --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
      --query 'Parameters[0].Value' --output text)
echo "ami $AMI"

# ---------------------------------------------------------------- the run
USERDATA=$(cat <<EOF
#!/bin/bash
exec > /var/log/ladder.log 2>&1
set -x
dnf install -y python3 python3-pip amazon-efs-utils unzip
mkdir -p /mnt/efs
mount -t efs -o tls ${FS}:/ /mnt/efs
mkdir -p /mnt/efs/substrate /opt/run/results/real-substrate /opt/run/results/capacity
cd /opt/run
aws s3 cp s3://${BUCKET}/efs-run/code.zip code.zip --region ${REGION}
unzip -q code.zip
export PYTHONPATH=/opt/run/src:/opt/run/real

# Real limits of the mount, then the ladder measured ON it. The probe is what makes the
# ladder's search ceilings properties of this filesystem rather than of our declarations.
python3 real/probe_limits.py /mnt/efs/substrate || true
python3 src/capacity.py --root /mnt/efs/substrate --json /opt/run/results/capacity/capacity-efs.json || true

mount | grep efs > /opt/run/results/real-substrate/mount-evidence.txt || true
df -h /mnt/efs >> /opt/run/results/real-substrate/mount-evidence.txt || true

aws s3 cp /opt/run/results s3://${BUCKET}/efs-run/results/ --recursive --region ${REGION} || true
aws s3 cp /var/log/ladder.log s3://${BUCKET}/efs-run/results/ladder.log --region ${REGION} || true

# Terminate self. This is why the run costs cents rather than whatever it costs to forget.
TOKEN=\$(curl -sX PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
IID=\$(curl -s -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids \$IID --region ${REGION}
EOF
)

IID=$(aws ec2 run-instances --region "$REGION" --image-id "$AMI" --instance-type t3.micro \
      --subnet-id "$SUBNET" --security-group-ids "$SG" \
      --iam-instance-profile Name="$ROLE" \
      --instance-initiated-shutdown-behavior terminate \
      --user-data "$USERDATA" \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME-runner}]" \
      --query 'Instances[0].InstanceId' --output text)

echo
echo "=================================================================="
echo " instance   : $IID"
echo " filesystem : $FS"
echo
echo " It mounts EFS, probes it, measures the ladder against it, uploads"
echo " to s3://${BUCKET}/efs-run/results/, then terminates itself."
echo " Expect ~5 minutes."
echo
echo " Watch:    aws ec2 describe-instances --instance-ids $IID \\"
echo "             --query 'Reservations[].Instances[].State.Name' --region $REGION"
echo " Results:  aws s3 ls s3://${BUCKET}/efs-run/results/ --region $REGION"
echo "=================================================================="
