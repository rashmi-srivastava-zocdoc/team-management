#!/usr/bin/env python3
"""Hit Roadie Tech Insights and output a per-check matrix for Peacock/Pterodactyl services.

Adapted from PRM team's harden-scorecard skill.

Requires ROADIE_API_TOKEN environment variable.
"""
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path

OUTPUT_DIR = Path.home() / "Desktop/github/team-management/scorecard"

TOKEN = os.environ.get("ROADIE_API_TOKEN")
BASE = "https://api.roadie.so/api"

# Services to check
SERVICES = [
    # Peacock
    "provider-setup-service",
    # Pterodactyl
    "practice-user-permissions",
    "practice-authorization-proxy",
    "provider-grouping",
    "provider-join-service",
]

def get(url):
    """Make authenticated GET request to Roadie API."""
    import subprocess
    # Use curl to avoid sandbox urllib issues
    result = subprocess.run(
        ["curl", "-sS", "-H", f"Authorization: bearer {TOKEN}", "-H", "Accept: application/json", url],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise Exception(f"curl failed: {result.stderr}")
    return json.loads(result.stdout)

def main():
    if not TOKEN:
        print("ERROR: ROADIE_API_TOKEN environment variable not set", file=sys.stderr)
        print("\nTo get a token:", file=sys.stderr)
        print("  1. Go to Roadie's API section in your org settings", file=sys.stderr)
        print("  2. Generate a personal access token", file=sys.stderr)
        print("  3. export ROADIE_API_TOKEN='your-token'", file=sys.stderr)
        sys.exit(1)

    try:
        # Get scorecards and checks metadata
        scs = get(f"{BASE}/tech-insights/v1/scorecards")
        checks_meta = get(f"{BASE}/tech-insights/v1/checks")

        # checks_meta might be dict or list
        if isinstance(checks_meta, dict):
            for v in checks_meta.values():
                if isinstance(v, list):
                    checks_meta = v
                    break
        name_by_id = {c["id"]: c.get("name") or c["id"] for c in checks_meta}
        print(f"Found {len(scs)} scorecards, {len(name_by_id)} checks", file=sys.stderr)

        by_card = {}
        for sc in scs:
            title = sc.get("title")
            by_card[title] = [(c["id"], name_by_id.get(c["id"], c["id"]), "") for c in sc.get("checks", [])]

        # For each check, pull results
        refs = {s: f"component:default/{s}" for s in SERVICES}
        per_check = {}  # check_id -> {entity: bool}
        for cid in {cid for lst in by_card.values() for cid, _, _ in lst}:
            try:
                data = get(f"{BASE}/tech-insights/v1/check-results/{cid}")
            except Exception as e:
                print(f"  check {cid} error {e}", file=sys.stderr)
                continue
            results = {}
            for item in data.get("items", []):
                ent = item.get("entity", "")
                results[ent] = item.get("result") == "true"
            per_check[cid] = results

        # Render per-service results
        out = {}
        for svc, ref in refs.items():
            failing = []
            passing = []
            for card_title, checks in by_card.items():
                for cid, ctitle, cdesc in checks:
                    res = per_check.get(cid, {}).get(ref)
                    if res is None:
                        continue
                    (passing if res else failing).append({
                        "card": card_title,
                        "check": ctitle,
                        "desc": cdesc,
                        "id": cid
                    })
            out[svc] = {
                "failing": failing,
                "passing_count": len(passing),
                "failing_count": len(failing)
            }

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_file = OUTPUT_DIR / "roadie-scores.json"
        with open(output_file, "w") as f:
            json.dump(out, f, indent=2)

        # Human-readable summary
        for svc, d in out.items():
            total = d['passing_count'] + d['failing_count']
            if total == 0:
                print(f"\n=== {svc}  (no Roadie data) ===")
                continue
            print(f"\n=== {svc}  ({d['passing_count']}/{total} passing) ===")
            by_card_fail = {}
            for f_item in d["failing"]:
                by_card_fail.setdefault(f_item["card"], []).append(f_item["check"])
            for card, items in by_card_fail.items():
                print(f"  [{card}] FAILING:")
                for c in items:
                    print(f"    - {c}")

        print(f"\nWrote {output_file}")

    except HTTPError as e:
        print(f"ERROR: Roadie API returned {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"ERROR: Could not connect to Roadie API: {e.reason}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
