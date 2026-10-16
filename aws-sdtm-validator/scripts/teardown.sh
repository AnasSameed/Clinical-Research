#!/usr/bin/env bash
# Delete everything this project created so nothing keeps costing money.
set -euo pipefail

STACK=${STACK:-sdtm-csv-validator}
REGION=${AWS_REGION:-$(aws configure get region || echo eu-north-1)}

BUCKET=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)

echo "==> Emptying s3://$BUCKET"
aws s3 rm --region "$REGION" "s3://$BUCKET" --recursive --only-show-errors

echo "==> Deleting stack $STACK"
aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK"
echo "All resources removed."
