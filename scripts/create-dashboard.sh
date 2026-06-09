#!/usr/bin/env bash
# create-dashboard.sh — Create or update the portal-nav-api CloudWatch dashboard.
# Idempotent — safe to re-run; overwrites existing dashboard with same name.
#
# Usage: ./scripts/create-dashboard.sh
# Requires: aws CLI, region eu-west-1

set -euo pipefail

REGION="eu-west-1"
FUNCTION="portal-nav-api"
API_ID="3jz6sk8vt7"
DASHBOARD_NAME="portal-nav-api"

BODY=$(cat <<DASHBOARD
{
  "widgets": [
    {
      "type": "text",
      "x": 0, "y": 0, "width": 24, "height": 1,
      "properties": {
        "markdown": "## portal-nav-api — Observability Dashboard\nRegion: eu-west-1 | Lambda: portal-nav-api | API GW: ${API_ID}"
      }
    },

    {
      "type": "metric",
      "x": 0, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Invocations & Errors (1h)",
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "period": 60,
        "stat": "Sum",
        "metrics": [
          ["AWS/Lambda", "Invocations", "FunctionName", "${FUNCTION}", {"label": "Invocations", "color": "#1f77b4"}],
          ["AWS/Lambda", "Errors",      "FunctionName", "${FUNCTION}", {"label": "Errors",      "color": "#d62728"}],
          ["AWS/Lambda", "Throttles",   "FunctionName", "${FUNCTION}", {"label": "Throttles",   "color": "#ff7f0e"}]
        ]
      }
    },

    {
      "type": "metric",
      "x": 8, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Duration p50 / p95 / p99 (ms)",
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "period": 60,
        "metrics": [
          ["AWS/Lambda", "Duration", "FunctionName", "${FUNCTION}", {"stat": "p50", "label": "p50",  "color": "#2ca02c"}],
          ["AWS/Lambda", "Duration", "FunctionName", "${FUNCTION}", {"stat": "p95", "label": "p95",  "color": "#ff7f0e"}],
          ["AWS/Lambda", "Duration", "FunctionName", "${FUNCTION}", {"stat": "p99", "label": "p99",  "color": "#d62728"}],
          ["AWS/Lambda", "Duration", "FunctionName", "${FUNCTION}", {"stat": "Maximum", "label": "Max", "color": "#9467bd"}]
        ]
      }
    },

    {
      "type": "metric",
      "x": 16, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Cold Starts & Concurrent Executions",
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "period": 60,
        "metrics": [
          ["AWS/Lambda", "InitDuration",           "FunctionName", "${FUNCTION}", {"stat": "Sum",     "label": "Cold starts (count)", "color": "#e377c2"}],
          ["AWS/Lambda", "ConcurrentExecutions",   "FunctionName", "${FUNCTION}", {"stat": "Maximum", "label": "Max concurrent",      "color": "#17becf"}]
        ]
      }
    },

    {
      "type": "metric",
      "x": 0, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "API Gateway — Request Count (1h)",
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "period": 60,
        "stat": "Sum",
        "metrics": [
          ["AWS/ApiGateway", "Count", "ApiId", "${API_ID}", {"label": "Total requests", "color": "#1f77b4"}]
        ]
      }
    },

    {
      "type": "metric",
      "x": 8, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "API Gateway — 4xx / 5xx Error Rate",
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "period": 60,
        "metrics": [
          ["AWS/ApiGateway", "4xx", "ApiId", "${API_ID}", {"stat": "Sum",     "label": "4xx",       "color": "#ff7f0e"}],
          ["AWS/ApiGateway", "5xx", "ApiId", "${API_ID}", {"stat": "Sum",     "label": "5xx",       "color": "#d62728"}],
          ["AWS/ApiGateway", "4xx", "ApiId", "${API_ID}", {"stat": "Average", "label": "4xx rate",  "color": "#ffbb78", "yAxis": "right"}],
          ["AWS/ApiGateway", "5xx", "ApiId", "${API_ID}", {"stat": "Average", "label": "5xx rate",  "color": "#ff9896", "yAxis": "right"}]
        ],
        "yAxis": {
          "right": { "label": "Rate (0–1)", "min": 0, "max": 1 }
        }
      }
    },

    {
      "type": "metric",
      "x": 16, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "API Gateway — Latency p50 / p95 (ms)",
        "view": "timeSeries",
        "stacked": false,
        "region": "${REGION}",
        "period": 60,
        "metrics": [
          ["AWS/ApiGateway", "Latency", "ApiId", "${API_ID}", {"stat": "p50", "label": "p50",  "color": "#2ca02c"}],
          ["AWS/ApiGateway", "Latency", "ApiId", "${API_ID}", {"stat": "p95", "label": "p95",  "color": "#ff7f0e"}],
          ["AWS/ApiGateway", "Latency", "ApiId", "${API_ID}", {"stat": "p99", "label": "p99",  "color": "#d62728"}]
        ]
      }
    },

    {
      "type": "text",
      "x": 0, "y": 13, "width": 24, "height": 1,
      "properties": {
        "markdown": "### Runbook\n[AppSec runbook](https://github.com/lngqaza/portal-nav-api/blob/master/docs/governance/appsec-runbook.md) | [README](https://github.com/lngqaza/portal-nav-api/blob/master/README.md) | Logs: CloudWatch Log groups: /aws/lambda/portal-nav-api"
      }
    }
  ]
}
DASHBOARD
)

echo "Creating/updating CloudWatch dashboard: $DASHBOARD_NAME ..."
aws cloudwatch put-dashboard \
  --region "$REGION" \
  --dashboard-name "$DASHBOARD_NAME" \
  --dashboard-body "$BODY"

echo "Dashboard URL:"
echo "  https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_NAME}"
