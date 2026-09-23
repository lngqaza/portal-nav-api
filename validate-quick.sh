#!/bin/bash
# Quick validation (no pip install) - assumes deps already installed

echo "🔍 Portal Nav API - Quick Validation"
echo "====================================="

# Clean
echo "📦 Cleaning..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete

# Syntax check
echo "🔧 Checking Python syntax..."
python -m py_compile routes/*.py core/*.py models/*.py 2>/dev/null && echo "  ✓ Syntax OK" || echo "  ✗ Syntax errors found"

# Check imports
echo "📋 Checking imports..."
python -c "import routes; import core; import models" 2>/dev/null && echo "  ✓ Imports OK" || echo "  ✗ Import errors found"

# Check code quality
echo "🔨 Code quality checks..."
python -m py_compile handlers/*.py services/*.py 2>/dev/null && echo "  ✓ All files compile" || echo "  ⚠ Some files have issues"

echo ""
echo "✅ Quick validation complete"
echo "   For full test suite: ./validate.sh (includes pytest)"
