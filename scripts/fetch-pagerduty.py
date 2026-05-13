#!/usr/bin/env python3
"""Fetch PagerDuty configuration data and check compliance for scorecard.

Checks:
1. Escalation policy has 2+ levels (primary and secondary)
2. Primary ≠ Secondary on-call person
3. Off-hours coverage configured (schedule has layers)

Requires PAGERDUTY_API_TOKEN environment variable.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "scorecard"

TOKEN = os.environ.get("PAGERDUTY_API_TOKEN")
BASE = "https://api.pagerduty.com"

# Team -> Service configuration
# Each team has a PagerDuty service with an escalation policy
TEAMS = {
    "provider-onboarding": {
        "name": "Provider Onboarding (Peacock)",
        "service_id": "PJS4NXI",
        "primary_schedule_id": "P7KGUO1",
        "secondary_schedule_id": "P8SP532",
    },
    "account-user-setup": {
        "name": "Account & User Setup (Pterodactyl)",
        "service_id": "PKRZBAN",  # Practice User Permissions Service
        "primary_schedule_id": "P9ITG6M",  # Pterodactyl On Call
        "secondary_schedule_id": "PH9VS8X",  # Pterodactyl Secondary On Call
    },
    "billing": {
        "name": "Billing",
        "service_id": "PP0E0W7",  # Appointment Accounting (uses Billing On Call escalation)
        "primary_schedule_id": "PDP20HZ",  # Billing Primary On-call
        "secondary_schedule_id": "PKG6K5E",  # Billing Secondary On-Call
    },
}


def get(endpoint):
    """Make authenticated GET request to PagerDuty API."""
    url = f"{BASE}{endpoint}"
    result = subprocess.run(
        [
            "curl", "-sS",
            "-H", f"Authorization: Token token={TOKEN}",
            "-H", "Accept: application/vnd.pagerduty+json;version=2",
            "-H", "Content-Type: application/json",
            url
        ],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise Exception(f"curl failed: {result.stderr}")
    return json.loads(result.stdout)


def get_service(service_id):
    """Get PagerDuty service details including escalation policy."""
    return get(f"/services/{service_id}?include[]=escalation_policy")


def get_escalation_policy(policy_id):
    """Get escalation policy with all rules/levels."""
    return get(f"/escalation_policies/{policy_id}")


def get_schedule(schedule_id):
    """Get schedule details including layers."""
    return get(f"/schedules/{schedule_id}")


def get_oncalls(schedule_ids):
    """Get current on-call users for given schedules."""
    params = "&".join([f"schedule_ids[]={sid}" for sid in schedule_ids if sid])
    return get(f"/oncalls?{params}")


def check_team_config(team_id, config):
    """Check PagerDuty configuration for a team."""
    result = {
        "team": config["name"],
        "checks": {
            "escalation_levels": {"status": "unknown", "details": ""},
            "distinct_oncalls": {"status": "unknown", "details": ""},
            "offhours_coverage": {"status": "unknown", "details": ""},
        },
        "passing": False,
        "errors": [],
    }

    try:
        # Check 1: Escalation policy has 2+ levels
        if config.get("service_id"):
            svc_data = get_service(config["service_id"])
            svc = svc_data.get("service", {})
            policy = svc.get("escalation_policy", {})
            policy_id = policy.get("id")

            if policy_id:
                policy_data = get_escalation_policy(policy_id)
                ep = policy_data.get("escalation_policy", {})
                rules = ep.get("escalation_rules", [])
                num_levels = len(rules)

                if num_levels >= 2:
                    result["checks"]["escalation_levels"] = {
                        "status": "pass",
                        "details": f"{num_levels} escalation levels configured"
                    }
                else:
                    result["checks"]["escalation_levels"] = {
                        "status": "fail",
                        "details": f"Only {num_levels} level(s), need 2+ for primary/secondary"
                    }
            else:
                result["checks"]["escalation_levels"]["details"] = "No escalation policy found"
        else:
            result["checks"]["escalation_levels"]["details"] = "No service ID configured"

        # Check 2: Primary ≠ Secondary on-call
        schedule_ids = [
            config.get("primary_schedule_id"),
            config.get("secondary_schedule_id"),
        ]
        schedule_ids = [s for s in schedule_ids if s]

        if len(schedule_ids) >= 2:
            oncalls_data = get_oncalls(schedule_ids)
            oncalls = oncalls_data.get("oncalls", [])

            # Group by schedule
            by_schedule = {}
            for oc in oncalls:
                sched_id = oc.get("schedule", {}).get("id")
                user_id = oc.get("user", {}).get("id")
                user_name = oc.get("user", {}).get("summary", "Unknown")
                if sched_id and user_id:
                    by_schedule.setdefault(sched_id, []).append({
                        "id": user_id,
                        "name": user_name
                    })

            primary_users = set(u["id"] for u in by_schedule.get(config["primary_schedule_id"], []))
            secondary_users = set(u["id"] for u in by_schedule.get(config["secondary_schedule_id"], []))

            primary_names = [u["name"] for u in by_schedule.get(config["primary_schedule_id"], [])]
            secondary_names = [u["name"] for u in by_schedule.get(config["secondary_schedule_id"], [])]

            if primary_users and secondary_users:
                if primary_users.isdisjoint(secondary_users):
                    result["checks"]["distinct_oncalls"] = {
                        "status": "pass",
                        "details": f"Primary: {', '.join(primary_names)}; Secondary: {', '.join(secondary_names)}"
                    }
                else:
                    overlap = primary_users & secondary_users
                    result["checks"]["distinct_oncalls"] = {
                        "status": "fail",
                        "details": f"Same person on primary and secondary"
                    }
            else:
                missing = []
                if not primary_users:
                    missing.append("primary")
                if not secondary_users:
                    missing.append("secondary")
                result["checks"]["distinct_oncalls"]["details"] = f"No on-call for: {', '.join(missing)}"
        elif len(schedule_ids) == 1:
            result["checks"]["distinct_oncalls"]["details"] = "Only one schedule configured"
        else:
            result["checks"]["distinct_oncalls"]["details"] = "No schedules configured"

        # Check 3: Off-hours coverage (schedule has layers or rotation)
        if config.get("primary_schedule_id"):
            sched_data = get_schedule(config["primary_schedule_id"])
            sched = sched_data.get("schedule", {})
            layers = sched.get("schedule_layers", [])

            if layers:
                # Check if there are restrictions (off-hours handling)
                has_restrictions = any(
                    layer.get("restrictions")
                    for layer in layers
                )

                if has_restrictions:
                    result["checks"]["offhours_coverage"] = {
                        "status": "pass",
                        "details": f"{len(layers)} layer(s) with time restrictions"
                    }
                else:
                    # No restrictions means 24/7 coverage - still a pass
                    result["checks"]["offhours_coverage"] = {
                        "status": "pass",
                        "details": f"{len(layers)} layer(s), 24/7 coverage"
                    }
            else:
                result["checks"]["offhours_coverage"] = {
                    "status": "fail",
                    "details": "No schedule layers configured"
                }
        else:
            result["checks"]["offhours_coverage"]["details"] = "No primary schedule configured"

    except Exception as e:
        result["errors"].append(str(e))

    # Overall pass/fail
    check_statuses = [c["status"] for c in result["checks"].values()]
    result["passing"] = all(s == "pass" for s in check_statuses)

    return result


def main():
    if not TOKEN:
        print("ERROR: PAGERDUTY_API_TOKEN environment variable not set", file=sys.stderr)
        print("\nTo get a token:", file=sys.stderr)
        print("  1. Go to PagerDuty > User Settings > Create API User Token", file=sys.stderr)
        print("  2. Or create a read-only API key in Integrations > API Access Keys", file=sys.stderr)
        print("  3. export PAGERDUTY_API_TOKEN='your-token'", file=sys.stderr)
        sys.exit(1)

    print("Checking PagerDuty configuration...", file=sys.stderr)

    results = {}
    for team_id, config in TEAMS.items():
        print(f"\nChecking {config['name']}...", file=sys.stderr)
        results[team_id] = check_team_config(team_id, config)

    # Output JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = OUTPUT_DIR / "pagerduty-scores.json"
    with open(output_file, "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "teams": results,
        }, f, indent=2)

    # Human-readable summary
    print("\n" + "="*60)
    print("PagerDuty Configuration Check Results")
    print("="*60)

    for team_id, data in results.items():
        status = "✅ PASS" if data["passing"] else "❌ FAIL"
        print(f"\n{data['team']}: {status}")
        for check_name, check_data in data["checks"].items():
            icon = "✅" if check_data["status"] == "pass" else "❌" if check_data["status"] == "fail" else "⚠️"
            print(f"  {icon} {check_name}: {check_data['details']}")
        if data["errors"]:
            print(f"  Errors: {data['errors']}")

    print(f"\nWrote {output_file}")


if __name__ == "__main__":
    main()
