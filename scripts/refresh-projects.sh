#!/bin/bash
# Refresh all project data locally
# Usage: ./scripts/refresh-projects.sh [--skip-jira] [--skip-glean]

set -e
cd "$(dirname "$0")/.."

echo "========================================"
echo "  REFRESH PROJECTS DATA"
echo "========================================"

python3 scripts/refresh-projects.py "$@"

echo ""
echo "View locally: open projects.html"
echo "After push:   https://rashmi-srivastava-zocdoc.github.io/team-management/projects.html"
