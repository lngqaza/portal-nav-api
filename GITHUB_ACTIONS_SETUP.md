# GitHub Actions Auto-Deployment Setup

Complete manual setup for automatic Lambda deployment on every push to `master`.

---

## **Step 1: Create AWS IAM Role (Via Console)**

Go to: https://console.aws.amazon.com/iam/home#/roles

1. Click **Create role**
2. Select **Custom trust policy**
3. Paste this trust policy:

```json
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
```

4. Click **Next**
5. Click **Create policy** (to add inline policy)
6. Name: `github-actions-portal-nav`
7. Click **Create role**

---

## **Step 2: Add Inline Policy**

1. Go to the role you just created: https://console.aws.amazon.com/iam/home#/roles/github-actions-portal-nav
2. Click **Add permissions** → **Create inline policy**
3. Choose **JSON**
4. Paste this policy:

```json
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
```

5. Name: `deploy-policy`
6. Click **Create policy**

---

## **Step 3: Add GitHub Secrets**

Go to: https://github.com/lngqaza/portal-nav-api/settings/secrets/actions

Click **New repository secret** and add these **4 secrets**:

### Secret 1: `AWS_ROLE_ARN`
```
arn:aws:iam::684756697968:role/github-actions-portal-nav
```

### Secret 2: `AWS_ACCOUNT_ID`
```
684756697968
```

### Secret 3: `API_GATEWAY_ID`
```
3jz6sk8vt7
```

### Secret 4: `NAV_API_KEY`
Get from:
```bash
aws lambda get-function-configuration \
  --function-name portal-nav-api \
  --query 'Environment.Variables.API_KEYS' \
  --region eu-west-1 \
  --output text
```
Then paste the first API key (before the colon)

### Secret 5: `NAV_ADMIN_TOKEN`
```bash
aws lambda get-function-configuration \
  --function-name portal-nav-api \
  --query 'Environment.Variables.ADMIN_TOKEN' \
  --region eu-west-1 \
  --output text
```

---

## **Step 4: Test the deployment**

1. Make a small change (e.g., edit README.md):
   ```bash
   cd /c/dev/work/portal-nav-api
   echo "# Auto-deployment test" >> README.md
   git add README.md
   git commit -m "test: trigger auto-deployment"
   git push origin master
   ```

2. Go to: https://github.com/lngqaza/portal-nav-api/actions
3. Watch the workflow run
4. Check if Lambda was updated:
   ```bash
   aws lambda get-function-configuration \
     --function-name portal-nav-api \
     --region eu-west-1 \
     | grep LastModified
   ```

---

## **How it works**

Every push to `master`:

```
git push origin master
    ↓
GitHub detects commit
    ↓
Triggers .github/workflows/deploy.yml
    ↓
GitHub Actions uses AWS role to:
  - Assume role via OIDC token
  - Build Docker image
  - Push to ECR
  - Update Lambda function
  - Run smoke test (/health)
    ↓
✅ Done (no manual steps)
```

---

## **Monitoring deployments**

**GitHub Actions:**
- Repo → **Actions** tab → see workflow runs
- Click run to see logs

**Lambda:**
```bash
aws lambda get-function-configuration \
  --function-name portal-nav-api \
  --region eu-west-1 \
  | grep -E "LastModified|CodeSha256"
```

**Live API:**
```bash
curl -s https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com/health \
  | jq .
```

---

## **Troubleshooting**

### Workflow fails: "AssumeRoleUnauthorizedOperation"
- Check: IAM role trust policy has correct OIDC provider ARN
- Check: `repo:lngqaza/portal-nav-api:*` matches your repo

### Workflow fails: "Permission denied" on ECR
- Check: Inline policy has ECR permissions
- Check: `deploy-policy` is attached to the role

### Workflow fails: "Lambda function not found"
- Check: `NAV_ADMIN_TOKEN` secret is correct
- Check: Lambda function name is `portal-nav-api`

### Workflow runs but Lambda doesn't update
- Check: GitHub Actions has the AWS secrets configured
- Check: Lambda function has CloudWatch logs enabled

---

Once complete, **push to `master` and your changes deploy automatically. No manual Lambda updates needed.**
