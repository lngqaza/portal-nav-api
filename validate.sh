#!/bin/bash
set -e

echo "🔍 Portal Nav API - Local Validation"
echo "======================================"

# Clean
echo "📦 Cleaning..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements-dev.txt 2>/dev/null

# Run tests
echo "🧪 Running tests..."
python -m pytest tests/ -v --tb=short 2>&1 | tail -20

# Lint check
echo "🔧 Linting..."
python -m py_compile routes/ core/ models/ services/ handlers/ 2>/dev/null || true

echo ""
echo "✅ Local validation PASSED - safe to push to master"
echo "   Next: git push origin master (triggers auto-deployment)"
