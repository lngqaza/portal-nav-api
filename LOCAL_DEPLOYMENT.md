# Local Deployment Strategy (LXP Pattern)

**Enforce this before every push to master.**

## Pre-Push Validation Gate

Before pushing code to master, run local validation to ensure it's safe to deploy:

```bash
./validate.sh
```

This script:
- ✅ Installs dev dependencies
- ✅ Runs all pytest tests  
- ✅ Checks Python syntax (linting)
- ✅ Reports pass/fail status

**Only push if validation passes.**

## What This Validates

| Check | Purpose | Blocks Push? |
|-------|---------|-------------|
| Dependencies | Ensure all packages install | ❌ No |
| Tests | Verify logic correctness | ✅ Yes |
| Linting | Check Python syntax | ❌ No |

## Workflow

```
1. Code change
   ↓
2. Run: ./validate.sh
   ↓
3. If ✅ passes:
   - git push origin master
   - GitHub Actions auto-deploys to Lambda
   ↓
4. If ❌ fails:
   - Fix local issues
   - Re-run ./validate.sh
```

## Cost-First Deployment

**Per CLAUDE.md LXP pattern:**
- Use lowest-cost validation option (Python tests, not Docker)
- Docker/WSL on this machine is unreliable → avoided
- Local unit tests are free (embedded)
- Real database tests only run in CI (avoid local DB setup)

## One-Time Setup

```bash
# Create virtual environment (optional, but recommended)
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install dev dependencies once
pip install -r requirements-dev.txt
```

Then for future changes:
```bash
./validate.sh
git push origin master
```

## CI/CD Pipeline Parity

The local `./validate.sh` runs the **same checks** as GitHub Actions:
- ✅ Pytest tests (like CI)
- ✅ Python syntax validation (like CI)
- ❌ Docker build (skipped locally per LXP — only in CI)
- ❌ AWS Lambda deployment (skipped locally — only in CI)

After push, GitHub Actions will:
1. Build Docker image
2. Push to ECR
3. Update Lambda function
4. Run smoke test (health check)
5. Auto-deploy (no manual step needed)

## Troubleshooting

**Tests fail locally but pass in CI?**
- Likely DB connection issue (tests mock the DB locally)
- Check that pytest fixtures are running
- Run: `pytest tests/ -v` for detailed output

**Validation times out?**
- First run installs many packages (~2 min)
- Subsequent runs are faster (~30 sec)
- Press Ctrl+C to cancel and fix issues manually

**Want to skip validation?**
- Don't. This is a **safety gate**, not optional.
- Pushing broken code triggers Lambda revert via rollback workflow.
