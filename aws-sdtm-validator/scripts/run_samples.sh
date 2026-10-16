#!/usr/bin/env bash
# Upload every file in sample_data/ and print the status of each QC report.
set -euo pipefail

STACK=${STACK:-sdtm-csv-validator}
REGION=${AWS_REGION:-$(aws configure get region || echo eu-north-1)}
cd "$(dirname "$0")/.."

BUCKET=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)

for f in sample_data/*.csv; do
  aws s3 cp --region "$REGION" "$f" "s3://$BUCKET/incoming/$(basename "$f")" --only-show-errors
  echo "uploaded $(basename "$f")"
done

echo "Waiting for Lambda to write reports..."
sleep 10

printf "\n%-24s %-20s %7s %7s %9s\n" FILE STATUS RECORDS ERRORS WARNINGS
for f in sample_data/*.csv; do
  stem=$(basename "$f" .csv)
  aws s3 cp --region "$REGION" "s3://$BUCKET/reports/$stem.qc.json" - 2>/dev/null \
    | python3 -c "import json,sys; r=json.load(sys.stdin); s=r['summary']; print(f\"{r['file']:<24} {r['status']:<20} {s['records']:>7} {s['errors']:>7} {s['warnings']:>9}\")" \
    || echo "$stem: report not ready yet - rerun in a few seconds"
done

echo
echo "Open an HTML report (link valid 1 hour):"
aws s3 presign --region "$REGION" "s3://$BUCKET/reports/dm_with_errors.qc.html" --expires-in 3600
