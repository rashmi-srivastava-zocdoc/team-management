#!/usr/bin/env python3
"""Build the Q2 Production Standards scorecard with tiered compliance levels.

Adapted from PRM team's harden-scorecard skill (by Avinash).
Outputs JSON for GitHub Pages with T1/T2/T3 tier status per check.

Usage:
    python3 build-scorecard.py              # Use local repos
    python3 build-scorecard.py --use-github # Clone fresh from GitHub main branch
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / "Desktop/github"
# In CI (GitHub Actions), use GITHUB_WORKSPACE; locally use ~/Desktop/github/team-management
if os.environ.get("GITHUB_WORKSPACE"):
    OUTPUT_DIR = Path(os.environ["GITHUB_WORKSPACE"]) / "scorecard"
else:
    OUTPUT_DIR = BASE_DIR / "team-management/scorecard"
OUTPUT_FILE = OUTPUT_DIR / "data.json"
TIER_THRESHOLDS_FILE = OUTPUT_DIR / "tier-thresholds.json"
GITHUB_ORG = "Zocdoc"

# Mapping from tier-thresholds.json slugs to internal check IDs
# This allows us to use the Excel-derived thresholds while keeping existing check functions
SLUG_TO_CHECK_ID = {
    "blue_green_enabled": "blueGreen",
    "slo_deployment_gate_enabled": "sloGate",
    "average_pr_size_within_threshold": "prSize",
    "prod_change_failure_rate_within_threshold": "changeFailureRate",
    "rollback_times_within_threshold": "rollbackTime",
    "production_deploy_pipelines_within_threshold": "deployPipeline",
    "code_coverage_meets_threshold": "coverage",
    "cyclomatic_complexity_p95_within_threshold": "complexity",
    "method_size_p95_within_threshold": "methodSize",
    "no_muted_ignored_critical_tests": "mutedTests",
    "test_failure_rate": "testFailureRate",
    "eol_framework_version_not_being_used": "eol",
    "slo_defined_in_datadog": "slo",
    "slo_burn_rate_alerting_configured": "burnRate",
    "smoke_tests_passing": "smokeTests",
    "sentry_hygiene": "sentry",
    "metric_to_auto_trigger_incidents_identified": "incidentMetric",
    "deployable_recent_prod_deploy": "deployable",
    "on_plinth": "plinth",
    "on_cdk_off_ansible": "cdkNoAnsible",
    "pagerduty_configured_correctly": "pagerduty",
    "defining_core_user_journeys": "coreJourneys",
    "qa_iterations_per_app_cycle": "qaIterations",
    "branch_preview_enabled": "branchPreview",
}

CHECK_ID_TO_SLUG = {v: k for k, v in SLUG_TO_CHECK_ID.items()}

# Roadie check mapping: Roadie check name -> scorecard check ID
ROADIE_CHECK_MAP = {
    # Sentry
    "Sentry Issues Not Looked At": "sentry",
    "Sentry Issues Unassigned": "sentry",
    # PagerDuty
    "Pagerduty Configuration": "pagerduty",
    "Pagerduty Long Time to First Ack": "pagerduty",
    "Pagerduty High Total Incidents": "pagerduty",
    # Security / EOL
    "No Critical or High Dependabot Findings": "eol",
    "Zero High Severity Code Findings": "eol",
    "Repository Scanned by Semgrep (past 30 days)": "eol",
}

ROADIE_SCORES_FILE = OUTPUT_DIR / "roadie-scores.json"

# TeamCity project IDs for muted tests API
# Query: teamcity api "/app/rest/mutes?locator=project:(id:PROJECT_ID)"
TEAMCITY_PROJECT_IDS = {
    "provider-setup-service": "Provider_ProviderSetupService",
    "practice-user-permissions": "PracticeUserPermissions",
    "practice-authorization-proxy": "PracticeAuthorizationProxy",
    "provider-grouping": "Poomba_ProviderGrouping",
    "provider-join-service": "Provider_ProviderJoinService",
}

TEAMS = {
    "provider-onboarding": {
        "name": "Provider Onboarding",
        "repo_base": BASE_DIR / "_team_provider-peacock-team",
        "epic": {
            "key": "PROVGRO-6335",
            "url": "https://zocdoc.atlassian.net/browse/PROVGRO-6335",
            "summary": "Q2 2026 - Infrastructure Hardening"
        },
        "services": [
            {"name": "provider-setup-service", "repo": "provider-setup-service", "github_repo": "provider-setup-service"},
        ]
    },
    "account-user-setup": {
        "name": "Account & User Setup",
        "repo_base": BASE_DIR / "_team_user-permissions",
        "epic": {
            "key": "PTERODACTL-1880",
            "url": "https://zocdoc.atlassian.net/browse/PTERODACTL-1880",
            "summary": "Q2 2026 [2x] - Infrastructure Hardening"
        },
        "services": [
            {"name": "practice-user-permissions", "repo": "practice-user-permissions", "github_repo": "practice-user-permissions"},
            {"name": "practice-authorization-proxy", "repo": "practice-authorization-proxy", "github_repo": "practice-authorization-proxy"},
            {"name": "provider-grouping", "repo": "provider-grouping", "github_repo": "provider-grouping"},
            {"name": "provider-join-service", "repo": "provider-join-service", "repo_override": BASE_DIR / "_team_provider-peacock-team/provider-join-service", "github_repo": "provider-join-service"},
        ]
    },
    "billing": {
        "name": "Billing",
        "repo_base": BASE_DIR / "_team_billing",
        "services": [
            # Add billing services here when available
        ]
    }
}

# Ticket mappings: team -> check -> [tickets with service info]
# Tickets are grouped by check type, with optional service for filtering in detail view
TEAM_TICKETS = {
    "provider-onboarding": {
        "blueGreen": [
            {"key": "PROVGRO-6301", "summary": "Implement smoke tests for blue/green deployment validation", "status": "To Do", "service": "provider-setup-service"},
        ],
        "plinth": [
            {"key": "PROVGRO-6189", "summary": "[plinth] add missing auth-policies", "status": "In Review", "service": "provider-setup-service"},
        ],
        "coverage": [
            {"key": "PROVGRO-6264", "summary": "[Test Coverage] PartnerNetwork tasks + SKU definitions", "status": "To Do", "service": "provider-setup-service"},
            {"key": "PROVGRO-6265", "summary": "[Test Coverage] Intake tasks + SKU definition", "status": "To Do", "service": "provider-setup-service"},
            {"key": "PROVGRO-6266", "summary": "[Test Coverage] Activation & setup tasks + PartnerSyndication SKU", "status": "To Do", "service": "provider-setup-service"},
            {"key": "PROVGRO-6267", "summary": "[Test Coverage] Remaining misc task definitions + ClaimYourProfile SKU", "status": "To Do", "service": "provider-setup-service"},
            {"key": "PROVGRO-6268", "summary": "[Test Coverage] Authorization handlers", "status": "To Do", "service": "provider-setup-service"},
            {"key": "PROVGRO-6269", "summary": "[Test Coverage] AlertHandlerImpl + alert definitions", "status": "To Do", "service": "provider-setup-service"},
            {"key": "PROVGRO-6270", "summary": "[Test Coverage] MilestonesImpl unit tests", "status": "To Do", "service": "provider-setup-service"},
            {"key": "PROVGRO-6271", "summary": "[Test Coverage] Lambda entry points", "status": "To Do", "service": "provider-setup-service"},
            {"key": "PROVGRO-6272", "summary": "[Test Coverage] Utilities, extensions & mappers", "status": "To Do", "service": "provider-setup-service"},
        ],
    },
    "account-user-setup": {
        "blueGreen": [
            {"key": "PTERODACTL-1882", "summary": "Enable ECS blue/green deployment for POGS", "status": "To Do", "service": "provider-grouping"},
            {"key": "PTERODACTL-1883", "summary": "Implement smoke tests for POGS blue/green deployment", "status": "To Do", "service": "provider-grouping"},
            {"key": "PTERODACTL-1884", "summary": "Enable ECS blue/green deployment for PUP", "status": "To Do", "service": "practice-user-permissions"},
            {"key": "PTERODACTL-1885", "summary": "Implement smoke tests for PUP blue/green deployment", "status": "To Do", "service": "practice-user-permissions"},
            {"key": "PTERODACTL-1886", "summary": "Enable ECS blue/green deployment for PAP", "status": "To Do", "service": "practice-authorization-proxy"},
            {"key": "PTERODACTL-1887", "summary": "Implement smoke tests for PAP blue/green deployment", "status": "To Do", "service": "practice-authorization-proxy"},
        ],
    },
}

USE_GITHUB = False
TEMP_DIR = None

def load_tier_thresholds():
    """Load tier thresholds from tier-thresholds.json and convert to CHECK_DEFINITIONS format."""
    if not TIER_THRESHOLDS_FILE.exists():
        print(f"Warning: {TIER_THRESHOLDS_FILE} not found, using fallback definitions")
        return None

    with open(TIER_THRESHOLDS_FILE) as f:
        data = json.load(f)

    check_defs = {}
    for slug, check in data.get("checks", {}).items():
        check_id = SLUG_TO_CHECK_ID.get(slug)
        if not check_id:
            continue

        check_defs[check_id] = {
            "name": check.get("name", slug),
            "pillar": check.get("pillar", "Unknown"),
            "priority": check.get("priority", "P3"),
            "tier1": check.get("tier1", {}).get("threshold", ""),
            "tier2": check.get("tier2", {}).get("threshold", ""),
            "tier3": check.get("tier3", {}).get("threshold", ""),
            "sor": check.get("sor", ""),
            "data_provider": check.get("data_provider", ""),
            "description": check.get("description", ""),
        }

    print(f"Loaded {len(check_defs)} check definitions from tier-thresholds.json")
    return check_defs


def load_roadie_scores():
    """Load Roadie Tech Insights scores if available."""
    if not ROADIE_SCORES_FILE.exists():
        return {}

    with open(ROADIE_SCORES_FILE) as f:
        data = json.load(f)

    # Transform to per-service, per-check format
    scores = {}
    for service, info in data.items():
        scores[service] = {
            "passing_count": info.get("passing_count", 0),
            "failing_count": info.get("failing_count", 0),
            "failing_checks": {},  # check_id -> [roadie check names]
        }

        # Map failing Roadie checks to scorecard check IDs
        for failing in info.get("failing", []):
            roadie_check = failing.get("check", "")
            check_id = ROADIE_CHECK_MAP.get(roadie_check)
            if check_id:
                if check_id not in scores[service]["failing_checks"]:
                    scores[service]["failing_checks"][check_id] = []
                scores[service]["failing_checks"][check_id].append(roadie_check)

    print(f"Loaded Roadie scores for {len(scores)} services")
    return scores


def clone_repo(github_repo):
    """Clone a repo from GitHub to temp directory, return path."""
    global TEMP_DIR
    if TEMP_DIR is None:
        TEMP_DIR = Path(tempfile.mkdtemp(prefix="scorecard_"))
        print(f"Using temp directory: {TEMP_DIR}")

    repo_path = TEMP_DIR / github_repo
    if repo_path.exists():
        return repo_path

    url = f"https://github.com/{GITHUB_ORG}/{github_repo}.git"
    print(f"  Cloning {github_repo} from main branch...")
    result = subprocess.run(
        ["gh", "repo", "clone", f"{GITHUB_ORG}/{github_repo}", str(repo_path), "--", "--depth=1", "--branch=main"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Warning: Failed to clone {github_repo}: {result.stderr}")
        return None
    return repo_path

def cleanup_temp():
    """Clean up temp directory."""
    global TEMP_DIR
    if TEMP_DIR and TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        print(f"Cleaned up temp directory: {TEMP_DIR}")

# Q2 Production Standards - loaded from tier-thresholds.json
# Fallback definitions used only if JSON doesn't exist
CHECK_DEFINITIONS_FALLBACK = {
    "blueGreen": {"name": "Blue/Green Enabled", "pillar": "Deployment Safety", "priority": "P1"},
    "sloGate": {"name": "SLO Deployment Gate Enabled", "pillar": "Deployment Safety", "priority": "P2"},
    "prSize": {"name": "Average PR Size Within Threshold", "pillar": "Deployment Safety", "priority": "P1"},
    "changeFailureRate": {"name": "Prod Change Failure Rate Within Threshold", "pillar": "Deployment Safety", "priority": "P3"},
    "rollbackTime": {"name": "Rollback Times Within Threshold", "pillar": "Deployment Safety", "priority": "P2"},
    "deployPipeline": {"name": "Production Deploy Pipelines Within Threshold", "pillar": "Deployment Safety", "priority": "P3"},
    "coverage": {"name": "Code Coverage Meets Threshold", "pillar": "Code Quality", "priority": "P1"},
    "complexity": {"name": "Cyclomatic Complexity p95 Within Threshold", "pillar": "Code Quality", "priority": "P3"},
    "methodSize": {"name": "Method Size p95 Within Threshold", "pillar": "Code Quality", "priority": "P2"},
    "mutedTests": {"name": "No Muted/Ignored Critical Tests", "pillar": "Code Quality", "priority": "P1"},
    "testFailureRate": {"name": "Test Failure Rate", "pillar": "Code Quality", "priority": "P1"},
    "eol": {"name": "EOL Framework/Version not being used", "pillar": "Code Quality", "priority": "P1"},
    "slo": {"name": "SLO Defined in Datadog", "pillar": "Observability", "priority": "P1"},
    "burnRate": {"name": "SLO Burn Rate Alerting Configured", "pillar": "Observability", "priority": "P1"},
    "smokeTests": {"name": "Smoke Tests Passing", "pillar": "Observability", "priority": "P2"},
    "sentry": {"name": "Sentry Hygiene", "pillar": "Observability", "priority": "P1"},
    "incidentMetric": {"name": "Metric to auto trigger incidents identified", "pillar": "Observability", "priority": "P2"},
    "deployable": {"name": "Deployable (Recent Prod Deploy)", "pillar": "Tooling Standardization", "priority": "P1"},
    "plinth": {"name": "On Plinth", "pillar": "Tooling Standardization", "priority": "P3"},
    "cdkNoAnsible": {"name": "On CDK, Off Ansible", "pillar": "Tooling Standardization", "priority": "P1"},
    "pagerduty": {"name": "PagerDuty Configured Correctly", "pillar": "Tooling Standardization", "priority": "P1"},
}

# Will be populated at runtime from tier-thresholds.json
CHECK_DEFINITIONS = None

def run_cmd(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=30)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", 1

# === CHECK FUNCTIONS (return tier: t1, t2, t3, below_t3, unknown, dx_metric) ===

def check_blue_green(repo_path):
    out, rc = run_cmd(
        "grep -rE 'BLUE_GREEN|blueGreen|blue-green|deploymentStrategy|blueGreenDeployment' "
        "cdk/ infrastructure/cdk/ 2>/dev/null | head -1",
        cwd=repo_path
    )
    if out:
        return {"tier": "t1", "status": "pass", "notes": "B/G enabled in CDK"}
    # Check if CDK directory exists (either location)
    out, rc = run_cmd("test -d cdk || test -d infrastructure/cdk && echo exists", cwd=repo_path)
    if out:
        # CDK exists but no blue-green - check if it's even an ECS service
        # Include zd-cdk patterns: HttpService, LoadBalancedHttpService, CronService, WorkerService
        out2, _ = run_cmd(
            "grep -rE 'EcsService|FargateService|Ec2Service|ecs\\.HttpService|LoadBalancedHttpService|ecs\\.CronService|ecs\\.WorkerService' "
            "cdk/ infrastructure/cdk/ 2>/dev/null | head -1",
            cwd=repo_path
        )
        if out2:
            return {"tier": "below_t3", "status": "fail", "notes": "ECS service without B/G"}
        return {"tier": "n/a", "status": "n/a", "notes": "Not an ECS service (Lambda only)"}
    return {"tier": "unknown", "status": "unknown", "notes": "No CDK directory"}

def check_slo_gate(repo_path):
    out, rc = run_cmd("grep -r 'sloGate\\|SloGate\\|deployment.*gate' cdk/ .github/ 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t1", "status": "pass", "notes": "SLO gate found"}
    return {"tier": "unknown", "status": "unknown", "notes": "Depends on SLO definition first"}

def check_pr_size(repo_path):
    out, rc = run_cmd("""
        SINCE=$(date -u -v-30d '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -d '30 days ago' '+%Y-%m-%dT%H:%M:%SZ')
        gh pr list --state merged --limit 50 --json additions,deletions,mergedAt 2>/dev/null | \
        jq --arg since "$SINCE" '[.[] | select(.mergedAt >= $since) | .additions + .deletions] | if length == 0 then 0 else (add / length | floor) end'
    """, cwd=repo_path)
    try:
        avg = int(out)
        if avg <= 400:
            tier = "t1"
        elif avg <= 600:
            tier = "t2"
        elif avg <= 800:
            tier = "t3"
        else:
            tier = "below_t3"
        status = "pass" if tier == "t1" else "warning" if tier in ("t2", "t3") else "fail"
        return {"tier": tier, "status": status, "value": avg, "notes": f"{avg} lines avg (30d)"}
    except (ValueError, TypeError):
        return {"tier": "dx_metric", "status": "dx_metric", "notes": "DX-tracked metric"}

def check_change_failure_rate(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "DX/Roadie metric — not per-svc"}

def check_rollback_time(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "DX/Roadie metric"}

def check_deploy_pipeline(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "DX metric — p90 time-to-deploy"}

def check_coverage(repo_path, tc_coverage, svc_name):
    tc_data = tc_coverage.get(svc_name, {})
    if "error" in tc_data:
        return {"tier": "unknown", "status": "unknown", "value": None, "target": 80, "notes": tc_data["error"]}
    if tc_data.get("lines_pct") is not None:
        pct = tc_data["lines_pct"]
        if pct >= 80:
            tier = "t1"
        elif pct >= 70:
            tier = "t2"
        elif pct >= 60:
            tier = "t3"
        else:
            tier = "below_t3"
        status = "pass" if tier == "t1" else "warning" if tier in ("t2", "t3") else "fail"
        return {
            "tier": tier,
            "status": status,
            "value": pct,
            "target": 80,
            "notes": f"Lines:{pct}% (C:{tc_data.get('classes_pct', '?')}% M:{tc_data.get('methods_pct', '?')}% B:{tc_data.get('branches_pct', '?')}%)",
            "build_url": tc_data.get("web_url", "")
        }
    return {"tier": "unknown", "status": "unknown", "value": None, "target": 80, "notes": "No TeamCity data"}

def check_complexity(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "Roadie — not currently scored"}

def check_method_size(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "Roadie — not currently scored"}

def check_muted_tests(tc_muted_tests, svc_name):
    """Check muted tests count from TeamCity API.

    Per Excel guidance: Tier 1 = muted_tests_count = 0
    Data source: TeamCity test occurrence data (mutes API)
    """
    tc_data = tc_muted_tests.get(svc_name, {})
    if "error" in tc_data:
        return {"tier": "unknown", "status": "unknown", "count": None, "notes": tc_data["error"]}

    count = tc_data.get("count", 0)
    project_id = tc_data.get("project_id", "")

    if count == 0:
        return {"tier": "t1", "status": "pass", "count": 0, "notes": "No muted tests in TeamCity"}
    else:
        return {
            "tier": "below_t3",
            "status": "fail",
            "count": count,
            "notes": f"{count} muted tests in TeamCity",
            "project_id": project_id
        }

def check_test_failure_rate(tc_test_stats, svc_name):
    """Check test failure rate from TeamCity build statistics."""
    tc_data = tc_test_stats.get(svc_name, {})
    if "error" in tc_data:
        return {"tier": "unknown", "status": "unknown", "notes": tc_data["error"]}

    failure_rate = tc_data.get("failure_rate_pct")
    if failure_rate is None:
        return {"tier": "unknown", "status": "unknown", "notes": "No test failure data"}

    tier = tc_data.get("tier", "unknown")
    failed = tc_data.get("failed_count", 0)
    passed = tc_data.get("passed_count", 0)
    builds = tc_data.get("total_builds", 0)

    if tier == "t1":
        status = "pass"
    elif tier in ("t2", "t3"):
        status = "warning"
    else:
        status = "fail"

    return {
        "tier": tier,
        "status": status,
        "value": failure_rate,
        "target": 1,  # Tier 1 target: < 1%
        "notes": f"{failure_rate}% ({failed}/{failed+passed} tests, {builds} builds)"
    }

def check_eol(repo_path):
    out, rc = run_cmd("grep -r 'net8.0\\|net9.0' . --include='*.csproj' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t1", "status": "pass", "notes": ".NET 8+ LTS"}
    out, rc = run_cmd("grep -r 'net7.0' . --include='*.csproj' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t2", "status": "warning", "notes": ".NET 7 — upgrade within 6mo"}
    out, rc = run_cmd("grep -r 'net6.0' . --include='*.csproj' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t3", "status": "warning", "notes": ".NET 6 — upgrade within 12mo"}
    out, rc = run_cmd("grep -r 'TargetFramework' . --include='*.csproj' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "below_t3", "status": "fail", "notes": "Legacy framework — urgent upgrade needed"}
    return {"tier": "unknown", "status": "unknown", "notes": "No .csproj found"}

def check_slo(repo_path):
    out, rc = run_cmd("grep -ri 'new.*Slo\\|SloDefinition\\|createSlo' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t1", "status": "pass", "count": 1, "notes": "SLO found in CDK"}
    out, rc = run_cmd("grep -ri 'slo' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t2", "status": "warning", "count": 0, "notes": "SLO reference found, verify definition"}
    return {"tier": "below_t3", "status": "fail", "count": 0, "notes": "No SLO detected"}

def check_burn_rate(repo_path):
    out, rc = run_cmd("grep -ri 'burn.*rate\\|burnRate\\|BurnRate' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t1", "status": "pass", "notes": "Burn rate found in CDK"}
    return {"tier": "below_t3", "status": "fail", "notes": "No burn rate alerting — depends on SLO"}

def check_smoke_tests(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "Roadie surfaces; no active gap"}

def check_sentry(repo_path):
    out, rc = run_cmd("grep -ri 'sentry\\|Sentry' . --include='*.cs' --include='*.json' --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "unknown", "status": "unknown", "unresolved": None, "notes": "Sentry configured — hygiene unchecked (needs API)"}
    return {"tier": "below_t3", "status": "fail", "unresolved": None, "notes": "No Sentry config found"}

def check_incident_metric(repo_path):
    out, rc = run_cmd("grep -ri 'alarmWebhook\\|pagerDuty.*5xx\\|5xx.*pagerDuty' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t1", "status": "pass", "notes": "5xx monitor wired to PD"}
    out, rc = run_cmd("grep -ri '5xx\\|error.*monitor\\|alarm.*5' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t2", "status": "warning", "notes": "5xx/error monitor found, verify PD wiring"}
    return {"tier": "below_t3", "status": "fail", "notes": "No incident trigger metric detected"}

def check_deployable(repo_path):
    out, rc = run_cmd("git log --oneline -1 --format='%ci' origin/main 2>/dev/null || git log --oneline -1 --format='%ci' origin/master 2>/dev/null", cwd=repo_path)
    if out:
        from datetime import datetime
        try:
            commit_date = datetime.strptime(out[:10], "%Y-%m-%d")
            days_ago = (datetime.now() - commit_date).days
            if days_ago <= 30:
                tier = "t1"
            elif days_ago <= 60:
                tier = "t2"
            elif days_ago <= 90:
                tier = "t3"
            else:
                tier = "below_t3"
            status = "pass" if tier == "t1" else "warning" if tier in ("t2", "t3") else "fail"
            return {"tier": tier, "status": status, "days_ago": days_ago, "notes": f"Last commit: {out[:10]} ({days_ago}d ago)"}
        except:
            pass
    return {"tier": "unknown", "status": "unknown", "notes": "Could not get last commit date"}

def check_plinth(repo_path):
    out, rc = run_cmd("grep -ri 'plinth\\|Plinth' . --include='*.csproj' --include='*.cs' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t1", "status": "pass", "notes": "On Plinth"}
    out, rc = run_cmd("ls src/ 2>/dev/null && ls cdk/ 2>/dev/null", cwd=repo_path)
    if rc == 0:
        return {"tier": "t1", "status": "pass", "notes": "Plinth-style structure"}
    return {"tier": "unknown", "status": "unknown", "notes": "Could not determine"}

def check_cdk_no_ansible(repo_path):
    has_cdk = False
    has_ansible = False

    out, rc = run_cmd("ls cdk/cdk.json cdk/ 2>/dev/null | head -1", cwd=repo_path)
    if rc == 0 and out:
        has_cdk = True

    out, rc = run_cmd("ls ansible/ playbooks/ 2>/dev/null", cwd=repo_path)
    if rc == 0 and out:
        has_ansible = True

    if has_cdk and not has_ansible:
        return {"tier": "t1", "status": "pass", "notes": "CDK only"}
    elif has_cdk and has_ansible:
        return {"tier": "t2", "status": "warning", "notes": "CDK present but ansible/ still exists"}
    elif not has_cdk and has_ansible:
        return {"tier": "below_t3", "status": "fail", "notes": "Ansible only — needs CDK migration"}
    else:
        return {"tier": "unknown", "status": "unknown", "notes": "No CDK or Ansible found"}

def check_pagerduty(repo_path):
    out, rc = run_cmd("grep -ri 'alarmWebhook' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        out2, rc2 = run_cmd("grep -ri 'offHours\\|off_hours\\|escalation' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
        if out2:
            return {"tier": "t1", "status": "pass", "notes": "alarmWebhook + off-hours escalation"}
        return {"tier": "t2", "status": "warning", "notes": "alarmWebhook wired, no off-hours config"}
    out, rc = run_cmd("grep -ri 'pagerduty\\|PagerDuty\\|pagerDutyIntegration' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"tier": "t2", "status": "warning", "notes": "PagerDuty config found, verify alarmWebhook"}
    return {"tier": "below_t3", "status": "fail", "notes": "alarmWebhook not wired"}

def load_teamcity_coverage():
    coverage_file = OUTPUT_DIR / "teamcity-coverage.json"
    if coverage_file.exists():
        try:
            with open(coverage_file) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {coverage_file}: {e}")
            return {}
    return {}


def load_teamcity_test_stats():
    """Load test failure rate data from teamcity-test-stats.json."""
    test_stats_file = OUTPUT_DIR / "teamcity-test-stats.json"
    if test_stats_file.exists():
        try:
            with open(test_stats_file) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {test_stats_file}: {e}")
            return {}
    return {}


def load_teamcity_muted_tests():
    """Fetch muted test counts from TeamCity using the CLI."""
    results = {}
    for svc_name, project_id in TEAMCITY_PROJECT_IDS.items():
        try:
            r = subprocess.run(
                ["teamcity", "api", f"/app/rest/mutes?locator=project:(id:{project_id})"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                count = data.get("count", 0)
                results[svc_name] = {"count": count, "project_id": project_id}
            else:
                results[svc_name] = {"error": f"TeamCity API error: {r.stderr[:100]}"}
        except subprocess.TimeoutExpired:
            results[svc_name] = {"error": "TeamCity API timeout"}
        except json.JSONDecodeError:
            results[svc_name] = {"error": "Invalid JSON from TeamCity"}
        except FileNotFoundError:
            results[svc_name] = {"error": "teamcity CLI not found"}
            break
        except Exception as e:
            results[svc_name] = {"error": str(e)[:100]}

    print(f"Loaded muted tests for {len([r for r in results.values() if 'count' in r])} services from TeamCity")
    return results

def analyze_service(team_id, service, repo_base, tc_coverage, tc_muted_tests, tc_test_stats, roadie_scores=None):
    svc_name = service["name"]
    check_defs = CHECK_DEFINITIONS or CHECK_DEFINITIONS_FALLBACK
    roadie = roadie_scores.get(svc_name, {}) if roadie_scores else {}

    if USE_GITHUB:
        github_repo = service.get("github_repo", service["repo"])
        repo_path = clone_repo(github_repo)
        if repo_path is None:
            return {
                "name": svc_name,
                "repo": service["repo"],
                "error": f"Failed to clone {github_repo} from GitHub",
                "checks": {k: {"tier": "unknown", "status": "unknown", "notes": "Clone failed"} for k in check_defs}
            }
    else:
        repo_path = service.get("repo_override") or (repo_base / service["repo"])
        if not repo_path.exists():
            return {
                "name": svc_name,
                "repo": service["repo"],
                "error": f"Repo not found at {repo_path}",
                "checks": {k: {"tier": "unknown", "status": "unknown", "notes": "Repo not found"} for k in check_defs}
            }

    checks = {}

    # Deployment Safety
    checks["blueGreen"] = check_blue_green(repo_path)
    checks["sloGate"] = check_slo_gate(repo_path)
    checks["prSize"] = check_pr_size(repo_path)
    checks["changeFailureRate"] = check_change_failure_rate(repo_path)
    checks["rollbackTime"] = check_rollback_time(repo_path)
    checks["deployPipeline"] = check_deploy_pipeline(repo_path)

    # Code Quality
    checks["coverage"] = check_coverage(repo_path, tc_coverage, svc_name)
    checks["complexity"] = check_complexity(repo_path)
    checks["methodSize"] = check_method_size(repo_path)
    checks["mutedTests"] = check_muted_tests(tc_muted_tests, svc_name)
    checks["testFailureRate"] = check_test_failure_rate(tc_test_stats, svc_name)
    checks["eol"] = check_eol(repo_path)

    # Observability
    checks["slo"] = check_slo(repo_path)
    checks["burnRate"] = check_burn_rate(repo_path)
    checks["smokeTests"] = check_smoke_tests(repo_path)
    checks["sentry"] = check_sentry(repo_path)
    checks["incidentMetric"] = check_incident_metric(repo_path)

    # Tooling
    checks["deployable"] = check_deployable(repo_path)
    checks["plinth"] = check_plinth(repo_path)
    checks["cdkNoAnsible"] = check_cdk_no_ansible(repo_path)
    checks["pagerduty"] = check_pagerduty(repo_path)

    # Override with Roadie data if available
    roadie_failing = roadie.get("failing_checks", {})
    if roadie_failing:
        # Sentry - Roadie has actual hygiene data
        if "sentry" in roadie_failing:
            failing_checks = roadie_failing["sentry"]
            checks["sentry"] = {
                "tier": "below_t3",
                "status": "fail",
                "notes": f"Roadie: {', '.join(failing_checks)}",
                "roadie_source": True
            }
        elif checks["sentry"].get("status") == "unknown":
            # No sentry failures in Roadie = passing
            checks["sentry"] = {
                "tier": "t1",
                "status": "pass",
                "notes": "Roadie: Sentry hygiene passing",
                "roadie_source": True
            }

        # PagerDuty - Roadie has config and incident data
        if "pagerduty" in roadie_failing:
            failing_checks = roadie_failing["pagerduty"]
            checks["pagerduty"] = {
                "tier": "below_t3",
                "status": "fail",
                "notes": f"Roadie: {', '.join(failing_checks)}",
                "roadie_source": True
            }

    return {
        "name": svc_name,
        "repo": service["repo"],
        "checks": checks
    }

def load_existing_data():
    """Load existing data.json to preserve tickets and epics."""
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None

def add_ticket_url(ticket):
    """Add Jira URL to a ticket dict."""
    if "url" not in ticket:
        ticket["url"] = f"https://zocdoc.atlassian.net/browse/{ticket['key']}"
    return ticket

def load_epic_tickets():
    """Load tickets from epic-tickets.json if it exists."""
    epic_tickets_file = OUTPUT_DIR / "epic-tickets.json"
    if epic_tickets_file.exists():
        try:
            with open(epic_tickets_file) as f:
                data = json.load(f)
                return data.get("ticketsByTeam", {})
        except (json.JSONDecodeError, IOError):
            pass
    return None

def apply_team_tickets(scorecard):
    """Apply tickets to team level, grouped by check.

    Priority: epic-tickets.json > TEAM_TICKETS hardcoded fallback
    """
    # Try to load from epic-tickets.json first
    epic_tickets = load_epic_tickets()

    for team_id, team in scorecard["teams"].items():
        # Use epic-tickets.json if available, otherwise fall back to hardcoded
        if epic_tickets and team_id in epic_tickets:
            team_ticket_config = epic_tickets[team_id]
            print(f"  Using epic-tickets.json for {team_id}")
        else:
            team_ticket_config = TEAM_TICKETS.get(team_id, {})
            if team_ticket_config:
                print(f"  Using hardcoded TEAM_TICKETS for {team_id}")

        if team_ticket_config:
            tickets_by_check = {}
            for check_id, tickets in team_ticket_config.items():
                tickets_by_check[check_id] = [add_ticket_url(dict(t)) for t in tickets]
            team["ticketsByCheck"] = tickets_by_check

def apply_team_epics(scorecard):
    """Apply epic info from TEAMS config to the scorecard."""
    for team_id, team in scorecard["teams"].items():
        team_config = TEAMS.get(team_id, {})
        if "epic" in team_config:
            team["epic"] = team_config["epic"]

def build_scorecard():
    global CHECK_DEFINITIONS

    # Load check definitions from tier-thresholds.json
    CHECK_DEFINITIONS = load_tier_thresholds()
    if CHECK_DEFINITIONS is None:
        print("Using fallback check definitions")
        CHECK_DEFINITIONS = CHECK_DEFINITIONS_FALLBACK

    tc_coverage = load_teamcity_coverage()
    tc_muted_tests = load_teamcity_muted_tests()
    tc_test_stats = load_teamcity_test_stats()
    roadie_scores = load_roadie_scores()

    teams_data = {}
    for team_id, team_config in TEAMS.items():
        services = []
        for service in team_config["services"]:
            result = analyze_service(team_id, service, team_config["repo_base"], tc_coverage, tc_muted_tests, tc_test_stats, roadie_scores)
            services.append(result)

        teams_data[team_id] = {
            "name": team_config["name"],
            "services": services
        }

    scorecard = {
        "lastUpdated": datetime.now().isoformat(),
        "teams": teams_data,
        "checkDefinitions": CHECK_DEFINITIONS
    }

    # Apply epics and tickets from stable config
    apply_team_epics(scorecard)
    apply_team_tickets(scorecard)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(scorecard, f, indent=2, default=str)

    return scorecard

def print_summary(scorecard):
    print("\n" + "=" * 80)
    print("      Q2 INFRASTRUCTURE SCORECARD (21 checks, tiered)")
    print("=" * 80)

    tier_counts = {"t1": 0, "t2": 0, "t3": 0, "below_t3": 0, "unknown": 0, "dx_metric": 0}
    p1_t1 = 0
    p1_total = 0

    for team_id, team in scorecard["teams"].items():
        print(f"\n{'='*80}")
        print(f" {team['name'].upper()}")
        print(f"{'='*80}")

        for service in team["services"]:
            if "error" in service:
                print(f"\n  {service['name']}: ERROR - {service['error']}")
                continue

            print(f"\n  {service['name']}")
            print(f"  {'-'*50}")

            checks = service["checks"]
            for check_id, check in checks.items():
                tier = check.get("tier", "unknown")
                tier_counts[tier] = tier_counts.get(tier, 0) + 1

                defn = CHECK_DEFINITIONS.get(check_id, {})
                if defn.get("priority") == "P1" and tier != "dx_metric":
                    p1_total += 1
                    if tier == "t1":
                        p1_t1 += 1

                icon = {"t1": "T1", "t2": "T2", "t3": "T3", "below_t3": "<T3", "unknown": "??", "dx_metric": "DX"}.get(tier, "??")
                print(f"    [{icon:>3}] {defn.get('name', check_id)}: {check.get('notes', '')}")

    print("\n" + "=" * 80)
    print(" TIER SUMMARY")
    print("=" * 80)
    print(f"  T1 (best):    {tier_counts['t1']}")
    print(f"  T2:           {tier_counts['t2']}")
    print(f"  T3:           {tier_counts['t3']}")
    print(f"  <T3 (gaps):   {tier_counts['below_t3']}")
    print(f"  Unknown:      {tier_counts['unknown']}")
    print(f"  DX Metric:    {tier_counts['dx_metric']}")
    print("=" * 80)
    compliance = round(100 * p1_t1 / p1_total) if p1_total > 0 else 0
    print(f" P1 Tier 1 Compliance: {compliance}% ({p1_t1}/{p1_total})")
    print("=" * 80)
    print(f"\nUpdated: {OUTPUT_FILE}")
    print(f"View at: https://rashmi-srivastava-zocdoc.github.io/team-management/scorecard.html")

def main():
    global USE_GITHUB

    parser = argparse.ArgumentParser(description="Build Q2 Infrastructure Scorecard")
    parser.add_argument("--use-github", action="store_true",
                        help="Clone repos fresh from GitHub main branch instead of using local copies")
    args = parser.parse_args()

    USE_GITHUB = args.use_github
    if USE_GITHUB:
        print("Mode: Cloning from GitHub main branch (fresh data)")
    else:
        print("Mode: Using local repos (may be stale)")

    try:
        scorecard = build_scorecard()
        print_summary(scorecard)
    finally:
        if USE_GITHUB:
            cleanup_temp()

if __name__ == "__main__":
    main()
