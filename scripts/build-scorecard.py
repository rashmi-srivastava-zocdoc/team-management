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
GITHUB_ORG = "Zocdoc"

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

# Ticket mappings: team -> [tickets]
# All tickets for infrastructure hardening work, displayed in team summary tab
TEAM_TICKETS = {
    "provider-onboarding": [
        {"key": "PROVGRO-6189", "summary": "[plinth] add missing auth-policies", "status": "In Review"},
        {"key": "PROVGRO-6301", "summary": "Implement smoke tests for blue/green deployment validation", "status": "To Do"},
        {"key": "PROVGRO-6264", "summary": "[Test Coverage] PartnerNetwork tasks + SKU definitions", "status": "To Do"},
        {"key": "PROVGRO-6265", "summary": "[Test Coverage] Intake tasks + SKU definition", "status": "To Do"},
        {"key": "PROVGRO-6266", "summary": "[Test Coverage] Activation & setup tasks + PartnerSyndication SKU", "status": "To Do"},
        {"key": "PROVGRO-6267", "summary": "[Test Coverage] Remaining misc task definitions + ClaimYourProfile SKU", "status": "To Do"},
        {"key": "PROVGRO-6268", "summary": "[Test Coverage] Authorization handlers", "status": "To Do"},
        {"key": "PROVGRO-6269", "summary": "[Test Coverage] AlertHandlerImpl + alert definitions", "status": "To Do"},
        {"key": "PROVGRO-6270", "summary": "[Test Coverage] MilestonesImpl unit tests", "status": "To Do"},
        {"key": "PROVGRO-6271", "summary": "[Test Coverage] Lambda entry points", "status": "To Do"},
        {"key": "PROVGRO-6272", "summary": "[Test Coverage] Utilities, extensions & mappers", "status": "To Do"},
    ],
    "account-user-setup": [
        {"key": "PTERODACTL-1882", "summary": "Enable ECS blue/green deployment for POGS", "status": "To Do"},
        {"key": "PTERODACTL-1883", "summary": "Implement smoke tests for POGS blue/green deployment", "status": "To Do"},
        {"key": "PTERODACTL-1884", "summary": "Enable ECS blue/green deployment for PUP", "status": "To Do"},
        {"key": "PTERODACTL-1885", "summary": "Implement smoke tests for PUP blue/green deployment", "status": "To Do"},
        {"key": "PTERODACTL-1886", "summary": "Enable ECS blue/green deployment for PAP", "status": "To Do"},
        {"key": "PTERODACTL-1887", "summary": "Implement smoke tests for PAP blue/green deployment", "status": "To Do"},
    ],
}

USE_GITHUB = False
TEMP_DIR = None

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

# Q2 Production Standards - 21 checks with tiered thresholds
# Tiers: t1 (best), t2, t3, below_t3 (worst), unknown, dx_metric
CHECK_DEFINITIONS = {
    # === DEPLOYMENT SAFETY (6 checks) ===
    "blueGreen": {
        "name": "Blue/Green Enabled",
        "pillar": "Deployment Safety",
        "priority": "P1",
        "tier1": "blue_green_enabled = true",
        "tier2": None,
        "tier3": None,
        "sor": "Repo Scanner",
        "binary": True
    },
    "sloGate": {
        "name": "SLO Deployment Gate Enabled",
        "pillar": "Deployment Safety",
        "priority": "P2",
        "tier1": "GitHub check blocks deploy on SLO breach",
        "tier2": "Gate configured but not blocking",
        "tier3": None,
        "sor": "GitHub / Datadog",
        "binary": True
    },
    "prSize": {
        "name": "Average PR Size Within Threshold",
        "pillar": "Deployment Safety",
        "priority": "P1",
        "tier1": "<= 400 lines",
        "tier2": "<= 600 lines",
        "tier3": "<= 800 lines",
        "sor": "GitHub",
        "thresholds": {"t1": 400, "t2": 600, "t3": 800}
    },
    "changeFailureRate": {
        "name": "Prod Change Failure Rate Within Threshold",
        "pillar": "Deployment Safety",
        "priority": "P3",
        "tier1": "< 15%",
        "tier2": "< 25%",
        "tier3": "< 35%",
        "sor": "DX Metrics",
        "dx_metric": True
    },
    "rollbackTime": {
        "name": "Rollback Times Within Threshold",
        "pillar": "Deployment Safety",
        "priority": "P2",
        "tier1": "< 10 min",
        "tier2": "< 15 min",
        "tier3": "< 30 min",
        "sor": "DX Metrics",
        "dx_metric": True
    },
    "deployPipeline": {
        "name": "Production Deploy Pipelines Within Threshold",
        "pillar": "Deployment Safety",
        "priority": "P3",
        "tier1": "p90 < 30 min",
        "tier2": "p90 < 45 min",
        "tier3": "p90 < 60 min",
        "sor": "DX Metrics",
        "dx_metric": True
    },

    # === CODE QUALITY (6 checks) ===
    "coverage": {
        "name": "Code Coverage Meets Threshold",
        "pillar": "Code Quality",
        "priority": "P1",
        "tier1": ">= 80%",
        "tier2": ">= 70%",
        "tier3": ">= 60%",
        "sor": "TeamCity",
        "thresholds": {"t1": 80, "t2": 70, "t3": 60}
    },
    "complexity": {
        "name": "Cyclomatic Complexity p95 Within Threshold",
        "pillar": "Code Quality",
        "priority": "P3",
        "tier1": "< 15",
        "tier2": "< 20",
        "tier3": "< 30",
        "sor": "Roadie",
        "dx_metric": True
    },
    "methodSize": {
        "name": "Method Size p95 Within Threshold",
        "pillar": "Code Quality",
        "priority": "P2",
        "tier1": "< 50 lines",
        "tier2": "< 75 lines",
        "tier3": "< 100 lines",
        "sor": "Roadie",
        "dx_metric": True
    },
    "mutedTests": {
        "name": "No Muted/Ignored Critical Tests",
        "pillar": "Code Quality",
        "priority": "P1",
        "tier1": "count = 0",
        "tier2": "count <= 2",
        "tier3": "count <= 5",
        "sor": "TeamCity / Repo",
        "thresholds": {"t1": 0, "t2": 2, "t3": 5}
    },
    "testFailureRate": {
        "name": "Test Failure Rate",
        "pillar": "Code Quality",
        "priority": "P1",
        "tier1": "< 1%",
        "tier2": "< 3%",
        "tier3": "< 5%",
        "sor": "CI Metrics",
        "dx_metric": True
    },
    "eol": {
        "name": "EOL Framework/Version not being used",
        "pillar": "Code Quality",
        "priority": "P1",
        "tier1": ".NET 8+ LTS",
        "tier2": ".NET 7 (upgrade within 6mo)",
        "tier3": ".NET 6 (upgrade within 12mo)",
        "sor": "Repo Scanner",
        "binary": True
    },

    # === OBSERVABILITY (5 checks) ===
    "slo": {
        "name": "SLO Defined in Datadog",
        "pillar": "Observability",
        "priority": "P1",
        "tier1": "slo_count >= 1",
        "tier2": None,
        "tier3": None,
        "sor": "Datadog / Roadie",
        "binary": True
    },
    "burnRate": {
        "name": "SLO Burn Rate Alerting Configured",
        "pillar": "Observability",
        "priority": "P1",
        "tier1": "monitor_count >= 1",
        "tier2": None,
        "tier3": None,
        "sor": "Datadog / Roadie",
        "binary": True
    },
    "smokeTests": {
        "name": "Smoke Tests Passing",
        "pillar": "Observability",
        "priority": "P2",
        "tier1": "100% pass rate",
        "tier2": ">= 95% pass rate",
        "tier3": ">= 90% pass rate",
        "sor": "Roadie",
        "dx_metric": True
    },
    "sentry": {
        "name": "Sentry Hygiene",
        "pillar": "Observability",
        "priority": "P1",
        "tier1": "0 unresolved, 0 permanently muted",
        "tier2": "<= 5 unresolved",
        "tier3": "<= 10 unresolved",
        "sor": "Sentry",
        "binary": True
    },
    "incidentMetric": {
        "name": "Metric to auto trigger incidents identified",
        "pillar": "Observability",
        "priority": "P2",
        "tier1": "5xx/error monitor wired to PD",
        "tier2": "Monitor exists but not wired to PD",
        "tier3": None,
        "sor": "CDK / Datadog",
        "binary": True
    },

    # === TOOLING STANDARDIZATION (4 checks) ===
    "deployable": {
        "name": "Deployable (Recent Prod Deploy)",
        "pillar": "Tooling",
        "priority": "P1",
        "tier1": "<= 30 days since prod deploy",
        "tier2": "<= 60 days",
        "tier3": "<= 90 days",
        "sor": "TeamCity / GitHub",
        "thresholds": {"t1": 30, "t2": 60, "t3": 90}
    },
    "plinth": {
        "name": "On Plinth",
        "pillar": "Tooling",
        "priority": "P3",
        "tier1": "service on Plinth framework",
        "tier2": None,
        "tier3": None,
        "sor": "Repo Scanner",
        "binary": True
    },
    "cdkNoAnsible": {
        "name": "On CDK, Off Ansible",
        "pillar": "Tooling",
        "priority": "P1",
        "tier1": "CDK only, no Ansible",
        "tier2": "CDK present, Ansible remnants",
        "tier3": None,
        "sor": "Repo Scanner",
        "binary": True
    },
    "pagerduty": {
        "name": "PagerDuty Configured Correctly",
        "pillar": "Tooling",
        "priority": "P1",
        "tier1": "alarmWebhook wired, off-hours escalation",
        "tier2": "alarmWebhook wired, no off-hours",
        "tier3": None,
        "sor": "PagerDuty / CDK",
        "binary": True
    },
}

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
        out2, _ = run_cmd("grep -rE 'EcsService|FargateService|Ec2Service' cdk/ infrastructure/cdk/ 2>/dev/null | head -1", cwd=repo_path)
        if out2:
            return {"tier": "below_t3", "status": "fail", "notes": "ECS service without B/G"}
        return {"tier": "n/a", "status": "n/a", "notes": "Not an ECS service (Lambda/Worker)"}
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
    if tc_data.get("classes_pct") is not None:
        pct = tc_data["classes_pct"]
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
            "notes": f"C:{pct}% M:{tc_data.get('methods_pct', '?')}% L:{tc_data.get('lines_pct', '?')}% B:{tc_data.get('branches_pct', '?')}%",
            "build_url": tc_data.get("web_url", "")
        }
    return {"tier": "unknown", "status": "unknown", "value": None, "target": 80, "notes": "No TeamCity data"}

def check_complexity(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "Roadie — not currently scored"}

def check_method_size(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "Roadie — not currently scored"}

def check_muted_tests(repo_path):
    out, rc = run_cmd("grep -rn '\\[Ignore\\]\\|\\[Skip\\]\\|\\[Explicit\\]' tests/ --include='*.cs' 2>/dev/null | wc -l", cwd=repo_path)
    try:
        count = int(out.strip())
    except ValueError:
        count = 0
    if count == 0:
        return {"tier": "t1", "status": "pass", "count": 0, "notes": "No muted tests"}
    elif count <= 2:
        return {"tier": "t2", "status": "warning", "count": count, "notes": f"{count} muted tests"}
    elif count <= 5:
        return {"tier": "t3", "status": "warning", "count": count, "notes": f"{count} muted tests"}
    else:
        return {"tier": "below_t3", "status": "fail", "count": count, "notes": f"{count} muted tests"}

def check_test_failure_rate(repo_path):
    return {"tier": "dx_metric", "status": "dx_metric", "notes": "CI-level metric — no per-svc data"}

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

def analyze_service(team_id, service, repo_base, tc_coverage):
    svc_name = service["name"]

    if USE_GITHUB:
        github_repo = service.get("github_repo", service["repo"])
        repo_path = clone_repo(github_repo)
        if repo_path is None:
            return {
                "name": svc_name,
                "repo": service["repo"],
                "error": f"Failed to clone {github_repo} from GitHub",
                "checks": {k: {"tier": "unknown", "status": "unknown", "notes": "Clone failed"} for k in CHECK_DEFINITIONS}
            }
    else:
        repo_path = service.get("repo_override") or (repo_base / service["repo"])
        if not repo_path.exists():
            return {
                "name": svc_name,
                "repo": service["repo"],
                "error": f"Repo not found at {repo_path}",
                "checks": {k: {"tier": "unknown", "status": "unknown", "notes": "Repo not found"} for k in CHECK_DEFINITIONS}
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
    checks["mutedTests"] = check_muted_tests(repo_path)
    checks["testFailureRate"] = check_test_failure_rate(repo_path)
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

def apply_team_tickets(scorecard):
    """Apply tickets from TEAM_TICKETS to team level in the scorecard."""
    for team_id, team in scorecard["teams"].items():
        team_tickets = TEAM_TICKETS.get(team_id, [])
        if team_tickets:
            team["tickets"] = [add_ticket_url(dict(t)) for t in team_tickets]

def apply_team_epics(scorecard):
    """Apply epic info from TEAMS config to the scorecard."""
    for team_id, team in scorecard["teams"].items():
        team_config = TEAMS.get(team_id, {})
        if "epic" in team_config:
            team["epic"] = team_config["epic"]

def build_scorecard():
    tc_coverage = load_teamcity_coverage()

    teams_data = {}
    for team_id, team_config in TEAMS.items():
        services = []
        for service in team_config["services"]:
            result = analyze_service(team_id, service, team_config["repo_base"], tc_coverage)
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
