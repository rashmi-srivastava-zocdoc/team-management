#!/usr/bin/env bash
# Fetch code coverage data from TeamCity using the CLI
# Requires: teamcity CLI authenticated
# Output: scorecard/teamcity-coverage.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_FILE="$REPO_ROOT/scorecard/teamcity-coverage.json"
TEMP_DIR=$(mktemp -d)

cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

log() { echo "$@" >&2; }

log "Fetching TeamCity coverage data via CLI..."
log "Output: $OUTPUT_FILE"
log ""

# Check if teamcity CLI is available
if ! command -v teamcity &> /dev/null; then
    log "ERROR: teamcity CLI not found. Install from: https://jb.gg/tc/docs"
    exit 1
fi

# Check auth
if ! teamcity auth status &>/dev/null; then
    log "ERROR: teamcity CLI not authenticated. Run: teamcity auth login"
    exit 1
fi

fetch_coverage() {
    local svc_name="$1"
    local project_prefix="$2"
    local build_type="${project_prefix}_${project_prefix}_PantsCICoverageReport"

    log "  Fetching: $svc_name..."
    log "    Build type: $build_type"

    # Find the latest successful coverage build (use --plain for tab-separated output)
    local build_info
    build_info=$(teamcity run list --limit 1 --job "$build_type" --status success --plain --no-header 2>/dev/null | head -1 || echo "")

    if [[ -z "$build_info" ]]; then
        log "    -> No builds found"
        echo "{\"classes_pct\": null, \"methods_pct\": null, \"lines_pct\": null, \"branches_pct\": null, \"web_url\": \"\", \"error\": \"No builds found for $build_type\"}"
        return
    fi

    # Extract build ID (second tab-separated column: STATUS\tID\tJOB\t...)
    local build_id
    build_id=$(echo "$build_info" | cut -f2)
    local build_status
    build_status=$(echo "$build_info" | cut -f1)

    if [[ -z "$build_id" ]] || [[ "$build_id" == "#" ]]; then
        log "    -> Could not parse build ID"
        echo "{\"classes_pct\": null, \"methods_pct\": null, \"lines_pct\": null, \"branches_pct\": null, \"web_url\": \"\", \"error\": \"Could not parse build ID\"}"
        return
    fi

    log "    -> Found build: $build_id (status: $build_status)"

    # Get build URL
    local web_url
    web_url=$(teamcity run view "$build_id" 2>/dev/null | grep "View in browser:" | sed 's/View in browser: //' || echo "")

    # Download coverage artifact (try cobertura.zip first, then coverage.zip)
    # Note: TeamCity CLI creates a directory at -o path, with artifact inside
    local download_dir="$TEMP_DIR/download_${svc_name}"
    local artifact_name=""
    if teamcity run download "$build_id" -a "cobertura.zip" -o "$download_dir" &>/dev/null; then
        artifact_name="cobertura.zip"
    elif teamcity run download "$build_id" -a "coverage.zip" -o "$download_dir" &>/dev/null; then
        artifact_name="coverage.zip"
    else
        log "    -> No coverage artifact"
        echo "{\"classes_pct\": null, \"methods_pct\": null, \"lines_pct\": null, \"branches_pct\": null, \"web_url\": \"$web_url\", \"build_id\": $build_id, \"error\": \"No coverage artifact\"}"
        return
    fi

    # Extract and parse cobertura XML
    local cobertura_dir="$TEMP_DIR/cobertura_${svc_name}"
    mkdir -p "$cobertura_dir"
    unzip -q "$download_dir/$artifact_name" -d "$cobertura_dir" 2>/dev/null || true

    local cobertura_xml
    cobertura_xml=$(find "$cobertura_dir" -name "*.xml" -type f 2>/dev/null | head -1)

    if [[ -z "$cobertura_xml" ]] || [[ ! -f "$cobertura_xml" ]]; then
        log "    -> No XML found in cobertura.zip"
        echo "{\"classes_pct\": null, \"methods_pct\": null, \"lines_pct\": null, \"branches_pct\": null, \"web_url\": \"$web_url\", \"build_id\": $build_id, \"error\": \"No XML in cobertura.zip\"}"
        return
    fi

    # Parse coverage from cobertura XML
    local line_rate branch_rate
    line_rate=$(grep -o 'line-rate="[0-9.]*"' "$cobertura_xml" 2>/dev/null | head -1 | grep -o '[0-9.]*' || echo "")
    branch_rate=$(grep -o 'branch-rate="[0-9.]*"' "$cobertura_xml" 2>/dev/null | head -1 | grep -o '[0-9.]*' || echo "")

    # Convert to percentages
    local lines_pct="null" branches_pct="null"
    if [[ -n "$line_rate" ]]; then
        lines_pct=$(echo "scale=1; $line_rate * 100" | bc 2>/dev/null || echo "null")
    fi
    if [[ -n "$branch_rate" ]]; then
        branches_pct=$(echo "scale=1; $branch_rate * 100" | bc 2>/dev/null || echo "null")
    fi

    if [[ "$lines_pct" == "null" ]]; then
        log "    -> Could not parse coverage"
        echo "{\"classes_pct\": null, \"methods_pct\": null, \"lines_pct\": null, \"branches_pct\": null, \"web_url\": \"$web_url\", \"build_id\": $build_id, \"error\": \"Could not parse coverage\"}"
    else
        log "    -> Coverage: L:${lines_pct}% B:${branches_pct}%"
        local fetched_at
        fetched_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        echo "{\"classes_pct\": $lines_pct, \"methods_pct\": $lines_pct, \"lines_pct\": $lines_pct, \"branches_pct\": $branches_pct, \"web_url\": \"$web_url\", \"build_id\": $build_id, \"build_type\": \"$build_type\", \"fetched_at\": \"$fetched_at\"}"
    fi
}

# Build the JSON file
# TeamCity project naming patterns vary:
#   - Poomba_X_Poomba_X_PantsCICoverageReport (provider-grouping)
#   - X_X_PantsCICoverageReport (practice-user-permissions)
#   - Provider_X_Provider_X_PantsCICoverageReport (provider services)
{
    echo "{"
    echo "  \"provider-grouping\": $(fetch_coverage "provider-grouping" "Poomba_ProviderGrouping"),"
    echo "  \"practice-user-permissions\": $(fetch_coverage "practice-user-permissions" "PracticeUserPermissions"),"
    echo "  \"practice-authorization-proxy\": $(fetch_coverage "practice-authorization-proxy" "PracticeAuthorizationProxy"),"
    echo "  \"provider-join-service\": $(fetch_coverage "provider-join-service" "Provider_ProviderJoinService"),"
    echo "  \"provider-setup-service\": $(fetch_coverage "provider-setup-service" "Provider_ProviderSetupService")"
    echo "}"
} > "$OUTPUT_FILE"

log ""
log "Done! Coverage data written to: $OUTPUT_FILE"
log ""
log "Contents:"
cat "$OUTPUT_FILE" >&2
