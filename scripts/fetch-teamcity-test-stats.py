#!/usr/bin/env python3
"""Fetch test failure rate from TeamCity build statistics.

Calculates failure rate = FailedTestCount / (FailedTestCount + PassedTestCount) * 100
for recent CI builds per service.

Tier thresholds (from tier-thresholds.json):
- Tier 1: < 1%
- Tier 2: < 2%
- Tier 3: < 5%
"""
import json
import subprocess
import sys
from pathlib import Path

OUTPUT_DIR = Path.home() / "Desktop/Github/team-management/scorecard"

# Service -> TeamCity build type IDs for test execution
# Use PantsCIUnitTests and PantsCIIntegrationTests builds where tests actually run
CI_BUILD_TYPES = {
    "provider-setup-service": [
        "Provider_ProviderSetupService_Provider_ProviderSetupService_PantsCIUnitTests",
        "Provider_ProviderSetupService_Provider_ProviderSetupService_PantsCIIntegrationTests",
    ],
    "practice-user-permissions": [
        "PracticeUserPermissions_PracticeUserPermissions_PantsCIUnitTests",
        "PracticeUserPermissions_PracticeUserPermissions_PantsCIIntegrationTests",
    ],
    "practice-authorization-proxy": [
        "PracticeAuthorizationProxy_PracticeAuthorizationProxy_PantsCIUnitTests",
        "PracticeAuthorizationProxy_PracticeAuthorizationProxy_PantsCIIntegrationTests",
    ],
    "provider-grouping": [
        "Poomba_ProviderGrouping_Poomba_ProviderGrouping_PantsCIUnitTests",
        "Poomba_ProviderGrouping_Poomba_ProviderGrouping_PantsCIIntegrationTests",
    ],
    "provider-join-service": [
        "Provider_ProviderJoinService_Provider_ProviderJoinService_PantsCIUnitTests",
        "Provider_ProviderJoinService_Provider_ProviderJoinService_PantsCIIntegrationTests",
    ],
}


def api(path):
    """Call TeamCity API via CLI."""
    r = subprocess.run(["teamcity", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def get_test_failure_rate(build_types, lookback_builds=10):
    """Get test failure rate from recent CI builds.

    Args:
        build_types: List of TeamCity build type IDs to query
        lookback_builds: Number of recent builds to check per build type

    Returns dict with:
    - failure_rate_pct: float or None
    - failed_count: int
    - passed_count: int
    - total_builds: int
    - tier: str (t1, t2, t3, below_t3, unknown)
    """
    if not build_types:
        return {"error": "no CI build type configured", "tier": "unknown"}

    total_failed = 0
    total_passed = 0
    builds_with_tests = 0

    for build_type in build_types:
        # Query recent builds with statistics
        data = api(
            f"/app/rest/builds?locator=buildType:{build_type},branch:default:true,count:{lookback_builds}"
            f"&fields=build(id,number,status,buildTypeId,statistics(property))"
        )

        if not data or not data.get("build"):
            continue

        for build in data["build"]:
            props = {p["name"]: p["value"] for p in build.get("statistics", {}).get("property", [])}

            # TeamCity doesn't include FailedTestCount when it's 0
            # Calculate from TotalTestCount - PassedTestCount - IgnoredTestCount
            total_count = props.get("TotalTestCount")
            passed = props.get("PassedTestCount")
            ignored = props.get("IgnoredTestCount", "0")
            failed_explicit = props.get("FailedTestCount")

            if total_count is not None and passed is not None:
                if failed_explicit is not None:
                    failed = int(failed_explicit)
                else:
                    # Calculate failed = total - passed - ignored
                    failed = int(total_count) - int(passed) - int(ignored)

                total_failed += failed
                total_passed += int(passed)
                builds_with_tests += 1

    if builds_with_tests == 0:
        return {"error": "no CI builds found", "tier": "unknown", "total_builds": 0}

    total_tests = total_failed + total_passed
    if total_tests == 0:
        return {"error": "no tests ran", "tier": "unknown", "total_builds": builds_with_tests}

    failure_rate = (total_failed / total_tests) * 100

    # Determine tier based on thresholds
    if failure_rate < 1:
        tier = "t1"
    elif failure_rate < 2:
        tier = "t2"
    elif failure_rate < 5:
        tier = "t3"
    else:
        tier = "below_t3"

    return {
        "failure_rate_pct": round(failure_rate, 1),
        "failed_count": total_failed,
        "passed_count": total_passed,
        "total_builds": builds_with_tests,
        "tier": tier,
    }


def main():
    results = {}

    for svc, build_types in CI_BUILD_TYPES.items():
        print(f"Fetching test stats for {svc}...", file=sys.stderr)
        results[svc] = get_test_failure_rate(build_types)

    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "teamcity-test-stats.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print(f"\n{'Service':<35} {'Tier':<8} {'Rate':<8} {'Failed':<8} {'Passed':<10} {'Builds'}")
    print("-" * 85)

    for svc, r in results.items():
        if "error" in r:
            print(f"{svc:<35} {'?':<8} {r['error']}")
            continue

        tier_display = r["tier"].upper().replace("_", " ")
        rate = f"{r['failure_rate_pct']}%"
        print(f"{svc:<35} {tier_display:<8} {rate:<8} {r['failed_count']:<8} {r['passed_count']:<10} {r['total_builds']}")

    print(f"\nWrote {output_file}")


if __name__ == "__main__":
    main()
