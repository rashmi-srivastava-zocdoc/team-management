#!/usr/bin/env python3
"""Build the Q2 Production Standards scorecard (21 checks) for Peacock and Pterodactyl teams.

Adapted from PRM team's harden-scorecard skill (by Avinash).
Outputs JSON for GitHub Pages (no Confluence publishing).
"""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / "Desktop/github"
OUTPUT_DIR = BASE_DIR / "team-management/scorecard"
OUTPUT_FILE = OUTPUT_DIR / "data.json"

# Team and service definitions
TEAMS = {
    "peacock": {
        "name": "Peacock",
        "repo_base": BASE_DIR / "_team_provider-peacock-team",
        "services": [
            {"name": "provider-setup-service", "repo": "provider-setup-service"},
        ]
    },
    "pterodactyl": {
        "name": "Pterodactyl",
        "repo_base": BASE_DIR / "_team_user-permissions",
        "services": [
            {"name": "practice-user-permissions", "repo": "practice-user-permissions"},
            {"name": "practice-authorization-proxy", "repo": "practice-authorization-proxy"},
            {"name": "provider-grouping", "repo": "provider-grouping"},
            {"name": "provider-join-service", "repo": "provider-join-service", "repo_override": BASE_DIR / "_team_provider-peacock-team/provider-join-service"},
        ]
    }
}

# Q2 Production Standards - All 21 scored checks across 4 pillars
# Source: Infrastructure Scorecard.xlsx (Q2 2026)
CHECK_DEFINITIONS = {
    # === DEPLOYMENT SAFETY (6 checks) ===
    "blueGreen": {
        "name": "Blue/Green Enabled",
        "pillar": "Deployment Safety",
        "priority": "P1",
        "tier1": "blue_green_enabled = true",
        "sor": "Repo Scanner"
    },
    "sloGate": {
        "name": "SLO Deployment Gate Enabled",
        "pillar": "Deployment Safety",
        "priority": "P2",
        "tier1": "GitHub check blocks deploy on SLO breach",
        "sor": "GitHub / Datadog"
    },
    "prSize": {
        "name": "Average PR Size Within Threshold",
        "pillar": "Deployment Safety",
        "priority": "P1",
        "tier1": "<= 400 lines (30d avg)",
        "sor": "GitHub"
    },
    "changeFailureRate": {
        "name": "Prod Change Failure Rate Within Threshold",
        "pillar": "Deployment Safety",
        "priority": "P3",
        "tier1": "< 15%",
        "sor": "DX Metrics"
    },
    "rollbackTime": {
        "name": "Rollback Times Within Threshold",
        "pillar": "Deployment Safety",
        "priority": "P2",
        "tier1": "< 10 min",
        "sor": "DX Metrics"
    },
    "deployPipeline": {
        "name": "Production Deploy Pipelines Within Threshold",
        "pillar": "Deployment Safety",
        "priority": "P3",
        "tier1": "p90 < 30 min",
        "sor": "DX Metrics"
    },

    # === CODE QUALITY (6 checks) ===
    "coverage": {
        "name": "Code Coverage Meets Threshold",
        "pillar": "Code Quality",
        "priority": "P1",
        "tier1": ">= 80%",
        "sor": "TeamCity"
    },
    "complexity": {
        "name": "Cyclomatic Complexity p95 Within Threshold",
        "pillar": "Code Quality",
        "priority": "P3",
        "tier1": "< 15",
        "sor": "Roadie"
    },
    "methodSize": {
        "name": "Method Size p95 Within Threshold",
        "pillar": "Code Quality",
        "priority": "P2",
        "tier1": "< 50 lines",
        "sor": "Roadie"
    },
    "mutedTests": {
        "name": "No Muted/Ignored Critical Tests",
        "pillar": "Code Quality",
        "priority": "P1",
        "tier1": "count = 0",
        "sor": "TeamCity / Repo"
    },
    "testFailureRate": {
        "name": "Test Failure Rate",
        "pillar": "Code Quality",
        "priority": "P1",
        "tier1": "< 1%",
        "sor": "CI Metrics"
    },
    "eol": {
        "name": "EOL Framework/Version not being used",
        "pillar": "Code Quality",
        "priority": "P1",
        "tier1": "eol_days < 90",
        "sor": "Repo Scanner"
    },

    # === OBSERVABILITY (5 checks) ===
    "slo": {
        "name": "SLO Defined in Datadog",
        "pillar": "Observability",
        "priority": "P1",
        "tier1": "slo_count >= 1",
        "sor": "Datadog / Roadie"
    },
    "burnRate": {
        "name": "SLO Burn Rate Alerting Configured",
        "pillar": "Observability",
        "priority": "P1",
        "tier1": "monitor_count >= 1",
        "sor": "Datadog / Roadie"
    },
    "smokeTests": {
        "name": "Smoke Tests Passing",
        "pillar": "Observability",
        "priority": "P2",
        "tier1": "100% pass rate",
        "sor": "Roadie"
    },
    "sentry": {
        "name": "Sentry Hygiene",
        "pillar": "Observability",
        "priority": "P1",
        "tier1": "0 unresolved, 0 permanently muted",
        "sor": "Sentry"
    },
    "incidentMetric": {
        "name": "Metric to auto trigger incidents identified",
        "pillar": "Observability",
        "priority": "P2",
        "tier1": "5xx/error monitor wired to PD",
        "sor": "CDK / Datadog"
    },

    # === TOOLING STANDARDIZATION (4 checks) ===
    "deployable": {
        "name": "Deployable (Recent Prod Deploy)",
        "pillar": "Tooling",
        "priority": "P1",
        "tier1": "<= 90 days since prod deploy",
        "sor": "TeamCity / GitHub"
    },
    "plinth": {
        "name": "On Plinth",
        "pillar": "Tooling",
        "priority": "P3",
        "tier1": "service on Plinth framework",
        "sor": "Repo Scanner"
    },
    "cdkNoAnsible": {
        "name": "On CDK, Off Ansible",
        "pillar": "Tooling",
        "priority": "P1",
        "tier1": "iac_system = cdk AND ansible_present = false",
        "sor": "Repo Scanner"
    },
    "pagerduty": {
        "name": "PagerDuty Configured Correctly",
        "pillar": "Tooling",
        "priority": "P1",
        "tier1": "poc != soc AND off_hours_escalation",
        "sor": "PagerDuty / CDK"
    },
}

def run_cmd(cmd, cwd=None):
    """Run a shell command and return stdout."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=30)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", 1

# === CHECK FUNCTIONS ===

def check_blue_green(repo_path):
    """Check if blue/green deployment is enabled."""
    out, rc = run_cmd("grep -r 'deploymentStrategy\\|blue_green\\|BlueGreen\\|blueGreenDeployment' cdk/ 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "pass", "notes": "B/G enabled in CDK"}
    out, rc = run_cmd("ls cdk/ 2>/dev/null", cwd=repo_path)
    if rc == 0:
        return {"status": "fail", "notes": "CDK present but B/G not detected"}
    return {"status": "unknown", "notes": "No CDK directory"}

def check_slo_gate(repo_path):
    """Check for SLO deployment gate."""
    out, rc = run_cmd("grep -r 'sloGate\\|SloGate\\|deployment.*gate' cdk/ .github/ 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "pass", "notes": "SLO gate found"}
    return {"status": "unknown", "notes": "Depends on SLO definition first"}

def check_pr_size(repo_path):
    """Check average PR size (30d). Requires gh CLI."""
    out, rc = run_cmd("""
        SINCE=$(date -u -v-30d '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -d '30 days ago' '+%Y-%m-%dT%H:%M:%SZ')
        gh pr list --state merged --limit 50 --json additions,deletions,mergedAt 2>/dev/null | \
        jq --arg since "$SINCE" '[.[] | select(.mergedAt >= $since) | .additions + .deletions] | if length == 0 then 0 else (add / length | floor) end'
    """, cwd=repo_path)
    try:
        avg = int(out)
        status = "pass" if avg <= 400 else "warning" if avg <= 600 else "fail"
        return {"status": status, "value": avg, "notes": f"{avg} lines avg"}
    except (ValueError, TypeError):
        return {"status": "dx_metric", "notes": "DX-tracked metric"}

def check_change_failure_rate(repo_path):
    """Check prod change failure rate - DX metric."""
    return {"status": "dx_metric", "notes": "DX/Roadie metric — not per-svc"}

def check_rollback_time(repo_path):
    """Check rollback time - DX metric."""
    return {"status": "dx_metric", "notes": "DX/Roadie metric"}

def check_deploy_pipeline(repo_path):
    """Check deploy pipeline time - DX metric."""
    return {"status": "dx_metric", "notes": "DX metric — p90 time-to-deploy"}

def check_coverage(repo_path, tc_coverage, svc_name):
    """Check code coverage from TeamCity."""
    tc_data = tc_coverage.get(svc_name, {})
    if "error" in tc_data:
        return {"status": "unknown", "value": None, "target": 80, "notes": tc_data["error"]}
    if tc_data.get("classes_pct") is not None:
        pct = tc_data["classes_pct"]
        status = "pass" if pct >= 80 else "warning" if pct >= 70 else "fail"
        return {
            "status": status,
            "value": pct,
            "target": 80,
            "notes": f"C:{pct}% M:{tc_data.get('methods_pct', '?')}% L:{tc_data.get('lines_pct', '?')}% B:{tc_data.get('branches_pct', '?')}%",
            "build_url": tc_data.get("web_url", "")
        }
    return {"status": "unknown", "value": None, "target": 80, "notes": "No TeamCity data"}

def check_complexity(repo_path):
    """Check cyclomatic complexity - Roadie metric."""
    return {"status": "dx_metric", "notes": "Roadie — not currently scored"}

def check_method_size(repo_path):
    """Check method size - Roadie metric."""
    return {"status": "dx_metric", "notes": "Roadie — not currently scored"}

def check_muted_tests(repo_path):
    """Count muted/ignored tests."""
    out, rc = run_cmd("grep -rn '\\[Ignore\\]\\|\\[Skip\\]\\|\\[Explicit\\]' tests/ --include='*.cs' 2>/dev/null | wc -l", cwd=repo_path)
    try:
        count = int(out.strip())
    except ValueError:
        count = 0
    if count == 0:
        return {"status": "pass", "count": 0, "notes": ""}
    return {"status": "fail", "count": count, "notes": f"{count} muted tests"}

def check_test_failure_rate(repo_path):
    """Check test failure rate - CI metric."""
    return {"status": "dx_metric", "notes": "CI-level metric — no per-svc data"}

def check_eol(repo_path):
    """Check for EOL frameworks."""
    out, rc = run_cmd("grep -r 'net8.0\\|net9.0' . --include='*.csproj' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "pass", "notes": ".NET 8+ LTS"}
    out, rc = run_cmd("grep -r 'net6.0\\|net7.0' . --include='*.csproj' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "warning", "notes": ".NET 6/7 — upgrade soon"}
    out, rc = run_cmd("grep -r 'TargetFramework' . --include='*.csproj' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "unknown", "notes": "Check framework version"}
    return {"status": "unknown", "notes": "No .csproj found"}

def check_slo(repo_path):
    """Check for SLO definition."""
    out, rc = run_cmd("grep -ri 'new.*Slo\\|SloDefinition\\|createSlo' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "pass", "count": 1, "notes": "SLO found in CDK"}
    out, rc = run_cmd("grep -ri 'slo' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "warning", "count": 0, "notes": "SLO reference found, verify definition"}
    return {"status": "fail", "count": 0, "notes": "No SLO detected"}

def check_burn_rate(repo_path):
    """Check for burn rate alerting."""
    out, rc = run_cmd("grep -ri 'burn.*rate\\|burnRate\\|BurnRate' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "pass", "notes": "Burn rate found in CDK"}
    return {"status": "fail", "notes": "No burn rate alerting — depends on SLO"}

def check_smoke_tests(repo_path):
    """Check smoke tests - Roadie metric."""
    return {"status": "dx_metric", "notes": "Roadie surfaces; no active gap"}

def check_sentry(repo_path):
    """Check Sentry configuration."""
    out, rc = run_cmd("grep -ri 'sentry\\|Sentry' . --include='*.cs' --include='*.json' --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "unknown", "unresolved": None, "notes": "Sentry configured — hygiene unchecked (needs API)"}
    return {"status": "fail", "unresolved": None, "notes": "No Sentry config found"}

def check_incident_metric(repo_path):
    """Check for incident trigger metric."""
    out, rc = run_cmd("grep -ri '5xx\\|error.*monitor\\|alarm.*5' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "pass", "notes": "5xx/error monitor found"}
    return {"status": "warning", "notes": "No incident trigger metric detected"}

def check_deployable(repo_path):
    """Check recent deploy (via git commit on main/master)."""
    out, rc = run_cmd("git log --oneline -1 --format='%ci' origin/main 2>/dev/null || git log --oneline -1 --format='%ci' origin/master 2>/dev/null", cwd=repo_path)
    if out:
        return {"status": "pass", "notes": f"Last commit: {out[:10]}"}
    return {"status": "unknown", "notes": "Could not get last commit date"}

def check_plinth(repo_path):
    """Check if service is on Plinth."""
    out, rc = run_cmd("grep -ri 'plinth\\|Plinth' . --include='*.csproj' --include='*.cs' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "pass", "notes": "On Plinth"}
    out, rc = run_cmd("ls src/ 2>/dev/null && ls cdk/ 2>/dev/null", cwd=repo_path)
    if rc == 0:
        return {"status": "pass", "notes": "Plinth-style structure"}
    return {"status": "unknown", "notes": "Could not determine"}

def check_cdk_no_ansible(repo_path):
    """Check if on CDK and off Ansible."""
    has_cdk = False
    has_ansible = False

    out, rc = run_cmd("ls cdk/cdk.json cdk/ 2>/dev/null | head -1", cwd=repo_path)
    if rc == 0 and out:
        has_cdk = True

    out, rc = run_cmd("ls ansible/ playbooks/ 2>/dev/null", cwd=repo_path)
    if rc == 0 and out:
        has_ansible = True

    if has_cdk and not has_ansible:
        return {"status": "pass", "notes": "CDK only"}
    elif has_cdk and has_ansible:
        return {"status": "warning", "notes": "CDK present but ansible/ still exists"}
    elif not has_cdk and has_ansible:
        return {"status": "fail", "notes": "Ansible only — needs CDK migration"}
    else:
        return {"status": "unknown", "notes": "No CDK or Ansible found"}

def check_pagerduty(repo_path):
    """Check for PagerDuty configuration."""
    out, rc = run_cmd("grep -ri 'pagerduty\\|PagerDuty\\|alarmWebhook\\|pagerDutyIntegration' cdk/ --include='*.ts' 2>/dev/null | head -1", cwd=repo_path)
    if out:
        return {"status": "pass", "notes": "PagerDuty config found in CDK"}
    return {"status": "fail", "notes": "alarmWebhook not wired"}

def load_teamcity_coverage():
    """Load TeamCity coverage data if available."""
    coverage_file = OUTPUT_DIR / "teamcity-coverage.json"
    if coverage_file.exists():
        with open(coverage_file) as f:
            return json.load(f)
    return {}

def analyze_service(team_id, service, repo_base, tc_coverage):
    """Run all 21 checks for a service."""
    # Support repo_override for services cloned in different directories
    repo_path = service.get("repo_override") or (repo_base / service["repo"])
    svc_name = service["name"]

    if not repo_path.exists():
        return {
            "name": svc_name,
            "repo": service["repo"],
            "error": f"Repo not found at {repo_path}",
            "checks": {k: {"status": "unknown", "notes": "Repo not found"} for k in CHECK_DEFINITIONS}
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

def build_scorecard():
    """Build the full scorecard."""
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

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(scorecard, f, indent=2)

    return scorecard

def print_summary(scorecard):
    """Print a terminal summary of the scorecard."""
    print("\n" + "=" * 80)
    print("      Q2 INFRASTRUCTURE SCORECARD (21 checks)")
    print("=" * 80)

    total_checks = 0
    passing = 0
    failing = 0
    dx_metric = 0

    pillars = ["Deployment Safety", "Code Quality", "Observability", "Tooling"]

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

            for pillar in pillars:
                pillar_checks = [k for k, v in CHECK_DEFINITIONS.items() if v["pillar"] == pillar]
                line = f"    {pillar}: "
                statuses = []

                for check_id in pillar_checks:
                    check = checks.get(check_id, {})
                    status = check.get("status", "unknown")
                    total_checks += 1

                    if status == "pass":
                        passing += 1
                        statuses.append("✓")
                    elif status == "fail":
                        failing += 1
                        statuses.append("✗")
                    elif status == "warning":
                        statuses.append("!")
                    elif status == "dx_metric":
                        dx_metric += 1
                        statuses.append("◆")
                    else:
                        statuses.append("?")

                print(f"{line}{' '.join(statuses)}")

    print("\n" + "=" * 80)
    print(" LEGEND: ✓=pass  ✗=fail  !=warning  ◆=DX/Roadie metric  ?=unknown")
    print("=" * 80)
    actionable = total_checks - dx_metric
    pct = round(100 * passing / actionable) if actionable > 0 else 0
    print(f" Services: {sum(len(t['services']) for t in scorecard['teams'].values())}")
    print(f" Checks: {total_checks} total ({dx_metric} DX-tracked, {actionable} actionable)")
    print(f" Passing: {passing}/{actionable} actionable ({pct}%)")
    print(f" Gaps: {failing}")
    print("=" * 80)
    print(f"\nUpdated: {OUTPUT_FILE}")
    print(f"View at: https://rashmi-srivastava-zocdoc.github.io/team-management/scorecard.html")

def main():
    scorecard = build_scorecard()
    print_summary(scorecard)

if __name__ == "__main__":
    main()
