#!/usr/bin/env bash
# Deploy the nav-widget CloudFront Function (header injection) to a distribution.
#
# Usage:
#   bash cloudfront-injection/deploy.sh \
#     <DISTRIBUTION_ID> \
#     <API_KEY> \
#     <API_URL> \
#     <WIDGET_URL>
#
# Example (Lumo demo):
#   bash cloudfront-injection/deploy.sh \
#     E1KJRIM4W6FY0A \
#     nav-d240be1101a43aa295f1dc26fe77e7e7 \
#     https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com \
#     https://d6kupsfl5u4c6.cloudfront.net/assets/nav-widget.js
#
# For full body injection (Lambda@Edge), see the comments in
# inject-widget-lambda-edge.js — that requires a separate Lambda deployment
# in us-east-1 and is outside the scope of this script.

set -euo pipefail

DIST_ID="${1:?Usage: deploy.sh <DIST_ID> <API_KEY> <API_URL> <WIDGET_URL>}"
API_KEY="${2:?API_KEY required}"
API_URL="${3:?API_URL required}"
WIDGET_URL="${4:?WIDGET_URL required}"

FUNCTION_NAME="nav-widget-inject-${DIST_ID}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Substitute placeholders in the function source
FUNCTION_CODE=$(sed \
  -e "s|__API_KEY__|${API_KEY}|g" \
  -e "s|__API_URL__|${API_URL}|g" \
  -e "s|__WIDGET_URL__|${WIDGET_URL}|g" \
  "${SCRIPT_DIR}/inject-widget.js")

echo "Deploying CloudFront Function: ${FUNCTION_NAME}"

# Check if function already exists
if aws cloudfront describe-function --name "${FUNCTION_NAME}" --region us-east-1 &>/dev/null; then
    # Get current ETag for update
    ETAG=$(aws cloudfront describe-function --name "${FUNCTION_NAME}" --region us-east-1 \
           --query 'ETag' --output text)
    aws cloudfront update-function \
        --name "${FUNCTION_NAME}" \
        --if-match "${ETAG}" \
        --function-config '{"Comment":"nav-widget header injector","Runtime":"cloudfront-js-2.0"}' \
        --function-code "$(echo "${FUNCTION_CODE}" | base64 -w0)" \
        --region us-east-1 \
        --query 'FunctionSummary.FunctionMetadata.FunctionARN' --output text
    echo "Updated existing function."
else
    ARN=$(aws cloudfront create-function \
        --name "${FUNCTION_NAME}" \
        --function-config '{"Comment":"nav-widget header injector","Runtime":"cloudfront-js-2.0"}' \
        --function-code "$(echo "${FUNCTION_CODE}" | base64 -w0)" \
        --region us-east-1 \
        --query 'FunctionSummary.FunctionMetadata.FunctionARN' --output text)
    echo "Created function: ${ARN}"
fi

# Publish the function
ETAG=$(aws cloudfront describe-function --name "${FUNCTION_NAME}" --region us-east-1 \
       --query 'ETag' --output text)
aws cloudfront publish-function \
    --name "${FUNCTION_NAME}" \
    --if-match "${ETAG}" \
    --region us-east-1 \
    --query 'FunctionSummary.Status' --output text

echo "Published. Associate this function with distribution ${DIST_ID}:"
echo "  CloudFront console → Behaviors → Edit → Function associations"
echo "  Event: viewer-response, Function ARN: (see above)"
echo ""
echo "Or run the association programmatically:"
echo "  aws cloudfront get-distribution-config --id ${DIST_ID} > /tmp/dist.json"
echo "  # Add FunctionAssociations to the default cache behavior, then:"
echo "  aws cloudfront update-distribution --id ${DIST_ID} --if-match <ETAG> --distribution-config file:///tmp/dist.json"
