#!/usr/bin/env bash
# deploy.sh — Deploy mock portal to S3 static website hosting.
# Creates bucket if it doesn't exist, syncs all files, prints the public URL.
#
# Usage: ./mock-portal/deploy.sh
# Requires: aws CLI configured for eu-west-1

set -euo pipefail

REGION="eu-west-1"
BUCKET="portal-nav-api-mock-$(aws sts get-caller-identity --query Account --output text)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "→ Deploying mock portal to s3://$BUCKET ..."

# Create bucket if it doesn't exist
aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null || \
  aws s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION"

# Disable block public access (needed for static website)
aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Allow public read via bucket policy
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [{
    \"Sid\": \"PublicRead\",
    \"Effect\": \"Allow\",
    \"Principal\": \"*\",
    \"Action\": \"s3:GetObject\",
    \"Resource\": \"arn:aws:s3:::${BUCKET}/*\"
  }]
}"

# Enable static website hosting
aws s3 website "s3://$BUCKET" \
  --index-document index.html \
  --error-document index.html

# Sync all files
aws s3 sync "$SCRIPT_DIR" "s3://$BUCKET" \
  --delete \
  --exclude "*.sh" \
  --exclude "_layout.html" \
  --cache-control "max-age=60"

# Set correct content types
aws s3 cp "s3://$BUCKET/assets/nav-widget.js" "s3://$BUCKET/assets/nav-widget.js" \
  --content-type "application/javascript" \
  --metadata-directive REPLACE --cache-control "max-age=60"

URL="http://${BUCKET}.s3-website-${REGION}.amazonaws.com"
echo ""
echo "✅ Mock portal live at:"
echo "   $URL"
echo ""
echo "Test queries to try in the widget (Ctrl+K):"
echo "  - 'submit a claim'"
echo "  - 'update banking details'"
echo "  - 'view my policy'"
echo "  - 'make a payment'"
echo "  - 'forgot password'"
echo "  - 'download tax certificate'"
