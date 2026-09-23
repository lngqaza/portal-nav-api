#!/bin/bash
# Start demo site HTTP server

cd "$(dirname "$0")/demo-site"

echo "🚀 Starting SafeGuard Insurance Demo Site"
echo "=========================================="
echo ""
echo "Site will be available at: http://localhost:8000"
echo "Admin Console: http://localhost:8000/../admin-console.html"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python -m http.server 8000 --bind 127.0.0.1
