# Admin Console & Auto-Deployment Setup

Two new features to manage portal-nav-api:

1. **Admin Console** — Web UI to manage configuration, index, and hot paths
2. **Auto-Deploy** — Automatic deployment to Lambda on every push to `master`

---

## **Part 1: Admin Console**

### Quick Start

1. **Open the console:**
   - Copy `admin-console.html` to your web server (or open locally)
   - Or access directly: `file:///path/to/admin-console.html`

2. **Enter your credentials:**
   - **API URL:** `https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com` (no trailing slash)
   - **Admin Token:** The `NAV_ADMIN_TOKEN` from Lambda env vars
   - Click **Test Connection**

3. **Manage the system:**

#### **Configuration Tab** ⚙️
- View/update thresholds in real-time (no Lambda restart needed)
  - `HOT_PATH_THRESHOLD` (Layer 0 fuzzy match) — default 0.75
  - `L1_THRESHOLD` (embedding search) — default 0.65
  - `L2_THRESHOLD` (re-ranker) — default 0.50
  - `MAX_HOT_PATHS` (top N pages in Layer 0) — default 70
- **Re-embed All Pages** — regenerate embeddings for entire index (takes minutes)

#### **Statistics Tab** 📊
- View 24-hour analytics:
  - Total queries
  - MISS rate (% of searches with no good match)
  - Layer hit distribution (L0/L1/L2 usage)
  - Indexed pages count

#### **Hot Paths Tab** ⚡
- View/manage the top 70 frequently-used pages
- Add custom hot paths (for pages that should always be found quickly)
- See hit counts and last-used timestamps
- Pin important pages (always included in top 70)

#### **Index Tab** 🔍
- View index statistics (total pages, embedded count)
- Manually add a page to the index (for content not auto-discovered)
- Provide: path, label, description, tags

### Credentials

The console stores your API URL and token in **localStorage** (browser only, not sent anywhere):
- Safe on your local machine
- Clear it in DevTools if needed

To get credentials:

1. **API URL:** Your API Gateway endpoint
   ```
   https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
   ```

2. **Admin Token:** From Lambda environment variables
   ```bash
   aws lambda get-function-configuration \
     --function-name portal-nav-api \
     --query 'Environment.Variables.ADMIN_TOKEN' \
     --region eu-west-1
   ```

---

## **Part 2: Auto-Deploy**

### Setup (One-time)

The `.github/workflows/deploy.yml` file is already in the repo. To enable auto-deployment:

#### **1. Create AWS IAM Role for GitHub Actions**

```bash
# Create a trust policy (save as trust-policy.json)
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::684756697968:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:lngqaza/portal-nav-api:*"
        }
      }
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name github-actions-portal-nav \
  --assume-role-policy-document file://trust-policy.json
```

#### **2. Attach permissions**

```bash
# Create inline policy (save as permissions.json)
cat > permissions.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:eu-west-1:684756697968:repository/portal-nav-api"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode"
      ],
      "Resource": "arn:aws:lambda:eu-west-1:684756697968:function:portal-nav-api"
    }
  ]
}
EOF

# Attach the policy
aws iam put-role-policy \
  --role-name github-actions-portal-nav \
  --policy-name deploy-policy \
  --policy-document file://permissions.json
```

#### **3. Add GitHub Secrets**

In your repo, go to **Settings → Secrets and variables → Actions** and add:

```
AWS_ROLE_ARN = arn:aws:iam::684756697968:role/github-actions-portal-nav
AWS_ACCOUNT_ID = 684756697968
API_GATEWAY_ID = 3jz6sk8vt7
NAV_API_KEY = (your test API key for smoke tests)
NAV_ADMIN_TOKEN = (your admin token)
```

### How it works

1. **Push to master**
   ```bash
   git commit -m "fix: improve search thresholds"
   git push origin master
   ```

2. **GitHub Actions triggers automatically:**
   - ✅ Checks out code
   - ✅ Builds Docker image
   - ✅ Pushes to ECR
   - ✅ Updates Lambda function
   - ✅ Runs smoke test (checks `/health`)
   - ✅ Done (no manual step)

3. **Check status:**
   - Go to repo → **Actions** tab
   - Click the latest workflow run
   - See build logs

### Rollback (if something breaks)

1. **Revert the commit:**
   ```bash
   git revert HEAD
   git push origin master
   ```

2. **GitHub Actions runs again** → Lambda reverts to previous version

---

## **Day-to-day use**

### Monitoring

**Check search health in Admin Console:**
1. Open admin-console.html
2. Go to **Statistics** tab
3. Look at MISS rate:
   - **< 5%** → Healthy
   - **5-15%** → Monitor (might need index updates)
   - **> 15%** → Problem (adjust thresholds or check index coverage)

### Tuning thresholds

**If MISS rate is high:**
1. Admin Console → **Configuration**
2. Lower `L1_THRESHOLD` or `L2_THRESHOLD` (makes matches easier)
3. Click **Save Changes** (takes effect immediately)
4. Check stats again

**If getting false positives (wrong pages):**
1. Raise thresholds to be more strict
2. Save and monitor

### Adding new pages

**Option A: Auto-discover** (widget crawls site)
- Happens automatically with `data-discover="on"`
- New pages added to index within 1-2 visits

**Option B: Manual index** (Admin Console)
1. Go to **Index** tab
2. Click **Index Page**
3. Fill in path, label, description, tags
4. Save

---

## **Troubleshooting**

### Admin Console won't connect

- [ ] Is the API URL correct? (no trailing slash)
- [ ] Is the admin token correct?
- [ ] Can you access the API directly? `curl https://... /health`
- [ ] Check browser console for CORS errors

### Auto-deploy fails

1. **Check GitHub Actions logs:**
   - Repo → Actions → latest run
   - Click the failed step
   - Read the error

2. **Common issues:**
   - IAM role doesn't have ECR permissions → fix permissions.json
   - Docker build fails → check Dockerfile / code
   - Lambda env vars missing → check AWS Lambda console

### MISS rate is high

1. **Check index coverage:**
   - Admin Console → **Index** → view count
   - Is it empty? Run auto-discovery or manually add pages

2. **Lower thresholds temporarily:**
   - Configuration → lower L1/L2 thresholds
   - Observe MISS rate
   - Gradually increase thresholds back

3. **Check query logs:**
   ```bash
   aws logs tail /aws/lambda/portal-nav-api --region eu-west-1 --follow
   ```

---

## **What's next?**

Once this is working:

1. ✅ **Admin Console** — manage config without touching code
2. ✅ **Auto-Deploy** — `git push` → Lambda update (no manual steps)
3. 🎯 **Next:** Add a monitoring dashboard (CloudWatch metrics in the console)
4. 🎯 **Next:** Add user feedback / MISS reporting

---

Questions? Check the RUNBOOK.md for on-call procedures.
