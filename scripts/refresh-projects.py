#!/usr/bin/env python3
"""Refresh project data from external sources.

Orchestrates data enrichment:
1. Loads projects/data.json
2. For each project with Jira epics: fetches ticket stats
3. Updates lastUpdated timestamp
4. Writes updated data.json

Usage:
    python3 refresh-projects.py [--skip-jira] [--skip-glean]

Slack summaries and document discovery require Glean MCP and are
typically run interactively or via a separate agent workflow.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECTS_FILE = Path(__file__).parent.parent / "projects" / "data.json"


def load_projects() -> dict:
    """Load projects data from JSON file."""
    if not PROJECTS_FILE.exists():
        print(f"Error: {PROJECTS_FILE} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(PROJECTS_FILE.read_text())


def save_projects(data: dict):
    """Save projects data to JSON file."""
    data["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
    PROJECTS_FILE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated {PROJECTS_FILE}")


def fetch_jira_stats(epic_keys: list[str]) -> dict:
    """Fetch Jira stats for multiple epics."""
    if not epic_keys:
        return {}

    try:
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "fetch-jira-project-stats.py")] + epic_keys,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Jira fetch warning: {result.stderr}", file=sys.stderr)
            return {}
    except Exception as e:
        print(f"Jira fetch error: {e}", file=sys.stderr)
        return {}


def main():
    parser = argparse.ArgumentParser(description="Refresh project data")
    parser.add_argument("--skip-jira", action="store_true", help="Skip Jira stats fetch")
    parser.add_argument("--skip-glean", action="store_true", help="Skip Glean-based enrichment")
    args = parser.parse_args()

    print("=" * 40)
    print("  REFRESH PROJECT DATA")
    print("=" * 40)

    data = load_projects()
    projects = data.get("projects", [])

    if not args.skip_jira:
        print("\n[1/2] Fetching Jira epic stats...")
        all_epics = []
        epic_to_project = {}

        for project in projects:
            for epic in project.get("jiraEpics", []):
                all_epics.append(epic)
                epic_to_project[epic] = project["id"]

        if all_epics:
            stats = fetch_jira_stats(all_epics)
            for epic_key, epic_stats in stats.items():
                project_id = epic_to_project.get(epic_key)
                for project in projects:
                    if project["id"] == project_id:
                        project["jiraStats"] = epic_stats
                        print(f"  ✓ {epic_key}: {epic_stats['done']}/{epic_stats['total']} done")
                        break
        else:
            print("  No Jira epics to fetch")
    else:
        print("\n[1/2] Skipping Jira (--skip-jira)")

    if not args.skip_glean:
        print("\n[2/2] Glean enrichment...")
        print("  ℹ Slack summaries and doc discovery require Glean MCP")
        print("  ℹ Run interactively or use agent workflow for Glean features")
    else:
        print("\n[2/2] Skipping Glean (--skip-glean)")

    print("\nSaving data...")
    save_projects(data)

    print("\n" + "=" * 40)
    print("  DONE")
    print("=" * 40)
    print(f"\nView: open projects.html")


if __name__ == "__main__":
    main()
