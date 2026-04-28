#!/usr/bin/env python3
"""Pull code-coverage stats from the latest successful PantsCICoverageReport build per service.

Adapted from PRM team's harden-scorecard skill.

Stat property mapping (pants pipeline):
    CodeCoverageC -> Classes %
    CodeCoverageM -> Methods %
    CodeCoverageS -> Lines %       (NOT Statements)
    CodeCoverageR -> Branches %    (NOT Regions)
"""
import json
import subprocess
import os

OUTPUT_DIR = os.path.expanduser("~/Desktop/github/team-management/scorecard")

# service -> PantsCICoverageReport buildType ID
# TODO: Verify these build type IDs in TeamCity
# Pattern: {Category}_{ServiceName}_{Category}_{ServiceName}_PantsCICoverageReport
COVERAGE_BUILD_TYPES = {
    # Peacock
    "provider-setup-service": "Provider_ProviderSetupService_Provider_ProviderSetupService_PantsCICoverageReport",
    # Pterodactyl
    "practice-user-permissions": "Provider_PracticeUserPermissions_Provider_PracticeUserPermissions_PantsCICoverageReport",
    "practice-authorization-proxy": "Provider_PracticeAuthorizationProxy_Provider_PracticeAuthorizationProxy_PantsCICoverageReport",
    "provider-grouping": "Provider_ProviderGrouping_Provider_ProviderGrouping_PantsCICoverageReport",
    "provider-join-service": "Provider_ProviderJoinService_Provider_ProviderJoinService_PantsCICoverageReport",
}

def api(path):
    """Call TeamCity API via the teamcity CLI."""
    r = subprocess.run(["teamcity", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None

def latest_coverage(build_type):
    """Get coverage stats from the latest successful build."""
    if not build_type:
        return None
    data = api(f"/app/rest/builds?locator=buildType:{build_type},branch:default:true,status:SUCCESS,count:1"
               f"&fields=build(id,number,buildTypeId,webUrl,finishDate,statistics(property))")
    if not data or not data.get("build"):
        return None
    b = data["build"][0]
    props = {p["name"]: p["value"] for p in b.get("statistics", {}).get("property", [])}

    def pct_direct(key):
        v = props.get(key)
        return round(float(v), 1) if v is not None else None

    def pct_from_abs(covered_k, total_k):
        c, t = props.get(covered_k), props.get(total_k)
        if c is None or t is None or float(t) == 0:
            return None
        return round(100.0 * float(c) / float(t), 1)

    return {
        "build_id": b["id"],
        "build_number": b["number"],
        "buildTypeId": b["buildTypeId"],
        "web_url": b["webUrl"],
        "finish_date": b["finishDate"],
        "classes_pct": pct_direct("CodeCoverageC") or pct_from_abs("CodeCoverageAbsCCovered", "CodeCoverageAbsCTotal"),
        "methods_pct": pct_direct("CodeCoverageM") or pct_from_abs("CodeCoverageAbsMCovered", "CodeCoverageAbsMTotal"),
        "lines_pct": pct_direct("CodeCoverageS") or pct_from_abs("CodeCoverageAbsSCovered", "CodeCoverageAbsSTotal"),
        "branches_pct": pct_direct("CodeCoverageR") or pct_from_abs("CodeCoverageAbsRCovered", "CodeCoverageAbsRTotal"),
    }

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}
    for svc, bt in COVERAGE_BUILD_TYPES.items():
        r = latest_coverage(bt)
        results[svc] = r or {"error": "no PantsCICoverageReport build (build type not found or coverlet not wired)"}

    output_path = os.path.join(OUTPUT_DIR, "teamcity-coverage.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    def fmt(v):
        return f"{v}%" if v is not None else "—"

    print(f"\n{'Service':<35} {'Build':<8} {'Classes':<9} {'Methods':<9} {'Lines':<9} {'Branches':<9}")
    print("-" * 95)
    for svc, r in results.items():
        if "error" in r:
            print(f"{svc:<35} ERROR: {r['error']}")
            continue
        print(f"{svc:<35} #{r['build_number']:<7} "
              f"{fmt(r.get('classes_pct')):<9} "
              f"{fmt(r.get('methods_pct')):<9} "
              f"{fmt(r.get('lines_pct')):<9} "
              f"{fmt(r.get('branches_pct')):<9}")

    print(f"\nWrote {output_path}")

if __name__ == "__main__":
    main()
