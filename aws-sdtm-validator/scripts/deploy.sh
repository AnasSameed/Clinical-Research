#!/usr/bin/env bash
# Deploy (or update) the stack and upload the validator code.
# Run from the project folder in AWS CloudShell:   bash scripts/deploy.sh
set -euo pipefail

STACK=${STACK:-sdtm-csv-validator}
PROJECT=${PROJECT:-sdtm-csv-validator}
REGION=${AWS_REGION:-$(aws configure get region || echo eu-north-1)}
cd "$(dirname "$0")/.."

echo "==> Deploying CloudFormation stack '$STACK' in $REGION"
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file template.yaml \
  --parameter-overrides ProjectName="$PROJECT" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

echo "==> Packaging Lambda code"
BUILD=$(mktemp -d)
cp src/validator.py src/lambda_function.py "$BUILD/"
(cd "$BUILD" && zip -q function.zip validator.py lambda_function.py)

echo "==> Uploading code to Lambda function '$PROJECT'"
aws lambda update-function-code --region "$REGION" \
  --function-name "$PROJECT" --zip-file "fileb://$BUILD/function.zip" >/dev/null
aws lambda wait function-updated --region "$REGION" --function-name "$PROJECT"
rm -rf "$BUILD"

BUCKET=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)
echo
echo "Deployed. Bucket: $BUCKET"
echo "Try it:  bash scripts/run_samples.sh"
