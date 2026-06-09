#!/usr/bin/env bash
# seed-index.sh — Populate nav_index and nav_hot_paths with representative portal pages.
# Usage:
#   NAV_ADMIN_TOKEN="..." ./scripts/seed-index.sh
#   or: ./scripts/seed-index.sh  (reads from env; must match Lambda API_KEYS / ADMIN_TOKEN)
#
# Idempotent — safe to re-run; existing paths are updated in place.

set -euo pipefail

BASE_URL="${NAV_BASE_URL:-https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com}"
ADMIN_TOKEN="${NAV_ADMIN_TOKEN:?NAV_ADMIN_TOKEN must be set}"

post_index() {
  local path="$1" label="$2" description="$3" tags="$4"
  local body
  body=$(printf '{"path":"%s","label":"%s","description":"%s","tags":%s}' \
    "$path" "$label" "$description" "$tags")
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/admin/index" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$body")
  printf "  [%s] %s → %s\n" "$status" "$path" "$label"
}

post_hot_path() {
  local path="$1" label="$2" aliases="$3"
  local body
  body=$(printf '{"path":"%s","label":"%s","aliases":%s,"pinned":false}' \
    "$path" "$label" "$aliases")
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/admin/hot-paths" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$body")
  printf "  [%s] hot-path %s\n" "$status" "$path"
}

echo "=== Seeding nav_index ==="

# ── Claims ─────────────────────────────────────────────────────────────────
post_index "/claims/submit"   "Submit a Claim"          "File and submit a new insurance claim online"                  '["claims","forms"]'
post_index "/claims/status"   "Check Claim Status"      "Track the progress of an existing claim"                       '["claims","tracking"]'
post_index "/claims/history"  "Claim History"           "View all past and current claims on your policy"               '["claims","history"]'
post_index "/claims/documents" "Upload Claim Documents" "Attach supporting documents to an open claim"                  '["claims","documents","upload"]'

# ── Policy ─────────────────────────────────────────────────────────────────
post_index "/policy/renew"    "Renew My Policy"         "Renew or extend your existing insurance policy"                '["policy","renewal"]'
post_index "/policy/details"  "Policy Details"          "View coverage details, limits, and exclusions"                 '["policy","coverage"]'
post_index "/policy/upgrade"  "Upgrade Coverage"        "Add extra cover or increase your existing benefit limits"      '["policy","upgrade","cover"]'
post_index "/policy/cancel"   "Cancel Policy"           "Request cancellation of an active policy"                      '["policy","cancel"]'
post_index "/policy/documents" "Policy Documents"       "Download your policy schedule, wording, and certificate"       '["policy","documents","download"]'

# ── Payments ───────────────────────────────────────────────────────────────
post_index "/payments/make"      "Make a Payment"        "Pay a premium, excess, or outstanding balance"                '["payments","billing"]'
post_index "/payments/history"   "Payment History"       "View all past transactions and receipts"                      '["payments","history","receipts"]'
post_index "/payments/debit"     "Manage Debit Order"    "Update or cancel your recurring premium debit order"          '["payments","debit","banking"]'
post_index "/payments/statement" "Account Statement"     "Download a full account statement for any date range"         '["payments","statement","download"]'

# ── Account ────────────────────────────────────────────────────────────────
post_index "/account/profile"    "Edit Profile"          "Update personal details, address, and contact information"    '["account","profile","settings"]'
post_index "/account/password"   "Change Password"       "Update your login password or PIN"                            '["account","security","password"]'
post_index "/account/beneficiary" "Manage Beneficiaries" "Add, update, or remove nominated beneficiaries"              '["account","beneficiary","estate"]'
post_index "/account/documents"  "My Documents"          "Access all correspondence, notices, and uploaded files"       '["account","documents"]'

# ── Support ────────────────────────────────────────────────────────────────
post_index "/support/contact"    "Contact Us"            "Reach customer support by phone, email, or live chat"         '["support","contact","help"]'
post_index "/support/faq"        "FAQs"                  "Browse frequently asked questions and self-service guides"    '["support","faq","help"]'
post_index "/support/complaint"  "Lodge a Complaint"     "Submit a formal complaint about a product or service"         '["support","complaint","ombudsman"]'
post_index "/support/chat"       "Live Chat"             "Start a real-time chat session with a support agent"          '["support","chat","live"]'

# ── Benefits ───────────────────────────────────────────────────────────────
post_index "/benefits/health"    "Health Benefits"       "View and manage your medical aid and wellness benefits"       '["benefits","health","medical"]'
post_index "/benefits/life"      "Life Cover"            "Manage life insurance policies and beneficiaries"             '["benefits","life","insurance"]'
post_index "/benefits/vehicle"   "Vehicle Insurance"     "Manage your motor vehicle cover and roadside assistance"      '["benefits","vehicle","motor"]'
post_index "/benefits/home"      "Home Insurance"        "Manage your building and home contents insurance"             '["benefits","home","contents"]'

# ── Reports ────────────────────────────────────────────────────────────────
post_index "/reports/annual"     "Annual Report"         "Download your annual policy and benefit summary"              '["reports","annual","download"]'
post_index "/reports/tax"        "Tax Certificate"       "Download a tax certificate for medical aid contributions"     '["reports","tax","certificate"]'

echo ""
echo "=== Seeding nav_hot_paths (top-10 high-traffic paths) ==="

post_hot_path "/claims/submit"    "Submit a Claim"    '["file a claim","new claim","log a claim","insurance claim"]'
post_hot_path "/claims/status"    "Check Claim Status" '["claim progress","where is my claim","track claim"]'
post_hot_path "/policy/renew"     "Renew My Policy"   '["renew policy","policy renewal","extend cover"]'
post_hot_path "/payments/make"    "Make a Payment"    '["pay now","pay premium","outstanding payment","settle balance"]'
post_hot_path "/account/profile"  "Edit Profile"      '["update details","change address","personal info","my details"]'
post_hot_path "/support/contact"  "Contact Us"        '["call us","email support","get help","help me"]'
post_hot_path "/support/faq"      "FAQs"              '["how do i","questions","self service","help articles"]'
post_hot_path "/account/password" "Change Password"   '["reset password","forgot password","change pin","update password"]'
post_hot_path "/payments/history" "Payment History"   '["past payments","receipts","transaction history","payment record"]'
post_hot_path "/benefits/health"  "Health Benefits"   '["medical aid","wellness","health cover","gap cover"]'

echo ""
echo "=== Verification ==="
INDEXED=$(curl -s "$BASE_URL/admin/index" -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'pages in index')")
HOT=$(curl -s "$BASE_URL/admin/hot-paths" -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'hot paths')")
echo "  $INDEXED"
echo "  $HOT"
echo ""
echo "Done. Test a query:"
echo "  curl -s $BASE_URL/query -H 'x-api-key: \$NAV_API_KEY' -H 'Content-Type: application/json' -d '{\"query\":\"submit a claim\"}'"
