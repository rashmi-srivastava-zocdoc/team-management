#!/bin/bash
# Refresh all scorecard data locally
# Usage: ./scripts/refresh-scorecard.sh [--skip-teamcity] [--skip-jira]

set -e
cd "$(dirname "$0")/.."

SKIP_TEAMCITY=false
SKIP_JIRA=false

for arg in "$@"; do
    case $arg in
        --skip-teamcity) SKIP_TEAMCITY=true ;;
        --skip-jira) SKIP_JIRA=true ;;
        --help|-h)
            echo "Usage: ./scripts/refresh-scorecard.sh [options]"
            echo ""
            echo "Options:"
            echo "  --skip-teamcity  Skip TeamCity coverage fetch"
            echo "  --skip-jira      Skip Jira epic tickets fetch"
            echo "  --help           Show this help"
            exit 0
            ;;
    esac
done

echo "========================================"
echo "  REFRESH SCORECARD DATA"
echo "========================================"

# Step 1: TeamCity coverage and test stats
if [ "$SKIP_TEAMCITY" = false ]; then
    echo ""
    echo "[1/5] Fetching TeamCity coverage..."
    python3 scripts/fetch-teamcity-coverage.py
    echo ""
    echo "[1.5/5] Fetching TeamCity test failure rates..."
    python3 scripts/fetch-teamcity-test-stats.py
else
    echo ""
    echo "[1/5] Skipping TeamCity data (--skip-teamcity)"
fi

# Step 2: Jira epic tickets
if [ "$SKIP_JIRA" = false ]; then
    echo ""
    echo "[2/5] Fetching Jira epic tickets..."
    if python3 scripts/fetch-epic-tickets.py 2>/dev/null; then
        echo "  ✓ Epic tickets updated"
    else
        echo "  ⚠ Jira fetch failed (credentials missing?) - using hardcoded tickets"
    fi
else
    echo ""
    echo "[2/5] Skipping Jira fetch (--skip-jira)"
fi

# Step 3: Parse tier thresholds from Excel
echo ""
echo "[3/5] Parsing tier thresholds from Excel..."
if [ -f "data/Infrastructure Scorecard.xlsx" ]; then
    python3 scripts/parse-tier-thresholds.py
else
    echo "  ⚠ Excel file not found - using existing tier-thresholds.json"
fi

# Step 5: Build scorecard
echo ""
echo "[5/5] Building scorecard..."
python3 scripts/build-scorecard.py

echo ""
echo "========================================"
echo "  DONE"
echo "========================================"
echo ""
echo "View locally: open scorecard/scorecard.html"
echo "After push:   https://rashmi-srivastava-zocdoc.github.io/team-management/scorecard.html"
