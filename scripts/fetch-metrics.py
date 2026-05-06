#!/usr/bin/env python3
"""Fetch PR and Sprint metrics for all teams.

Usage:
    python3 fetch-metrics.py [--skip-prs] [--skip-sprints]

Requires:
    GH_TOKEN or GITHUB_TOKEN for PR data
    JIRA_EMAIL and JIRA_API_TOKEN for sprint data

Output:
    Updates data/prs.json and data/sprints.json
"""
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"

JIRA_BASE_URL = "https://zocdoc.atlassian.net"

TEAM_CONFIG = {
    "peacock": {
        "jiraProject": "PROVGRO",
        "githubTeam": "provider-peacock-team",
    },
    "pterodactyl": {
        "jiraProject": "PTERODACTL",
        "githubTeam": "pterodactyl-team",
    },
    "billing": {
        "jiraProject": "BILL",
        "githubTeam": "billing-team",
    },
}


def get_jira_credentials():
    """Get Jira credentials from env vars or config file."""
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if email and token:
        return email, token

    config_path = Path.home() / ".config" / "jira-credentials.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        return config.get("email"), config.get("api_token")

    return None, None


def fetch_sprint_data(project_key: str, email: str, token: str) -> dict:
    """Fetch active sprint stats for a Jira project."""
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}

    # Get board ID for project
    boards_url = f"{JIRA_BASE_URL}/rest/agile/1.0/board?projectKeyOrId={project_key}"
    try:
        req = Request(boards_url, headers=headers)
        with urlopen(req) as resp:
            boards = json.loads(resp.read())
    except HTTPError as e:
        return {"error": f"Failed to get boards: {e}"}

    if not boards.get("values"):
        return {"error": "No boards found"}

    # Prefer scrum boards over kanban for sprint data
    scrum_boards = [b for b in boards["values"] if b.get("type") == "scrum"]
    if scrum_boards:
        board_id = scrum_boards[0]["id"]
    else:
        board_id = boards["values"][0]["id"]

    # Get active sprint
    sprints_url = f"{JIRA_BASE_URL}/rest/agile/1.0/board/{board_id}/sprint?state=active"
    try:
        req = Request(sprints_url, headers=headers)
        with urlopen(req) as resp:
            sprints = json.loads(resp.read())
    except HTTPError as e:
        return {"error": f"Failed to get sprints: {e}"}

    if not sprints.get("values"):
        return {"error": "No active sprint"}

    sprint = sprints["values"][0]
    sprint_id = sprint["id"]
    sprint_name = sprint["name"]

    # Get sprint issues
    issues_url = f"{JIRA_BASE_URL}/rest/agile/1.0/sprint/{sprint_id}/issue?maxResults=200&fields=status,customfield_10004"
    try:
        req = Request(issues_url, headers=headers)
        with urlopen(req) as resp:
            issues_data = json.loads(resp.read())
    except HTTPError as e:
        return {"error": f"Failed to get issues: {e}"}

    total = issues_data.get("total", 0)
    done = 0
    total_points = 0
    done_points = 0

    for issue in issues_data.get("issues", []):
        fields = issue.get("fields", {})
        status_cat = fields.get("status", {}).get("statusCategory", {}).get("key", "")
        points = fields.get("customfield_10004") or 0

        total_points += points
        if status_cat == "done":
            done += 1
            done_points += points

    return {
        "sprint_name": sprint_name,
        "state": "active",
        "total_issues": total,
        "done_issues": done,
        "total_points": total_points,
        "done_points": done_points,
        "completion_rate": round(done_points / total_points * 100) if total_points > 0 else 0,
    }


def fetch_pr_data(team_slug: str) -> dict:
    """Fetch PR counts for a GitHub team (last 7 days)."""
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        return {"error": "No GitHub token"}

    # Search for PRs by team members in last 7 days
    # Using gh CLI for simplicity
    try:
        result = subprocess.run(
            [
                "gh", "api", "graphql", "-f", f"""query={{
                    search(query: "org:Zocdoc is:pr created:>=$(date -d '7 days ago' +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d) team:Zocdoc/{team_slug}", type: ISSUE, first: 100) {{
                        issueCount
                    }}
                }}"""
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return {"total_prs": data.get("data", {}).get("search", {}).get("issueCount", 0)}
    except Exception as e:
        pass

    # Fallback: use REST API to search recent PRs
    try:
        cmd = ["gh", "pr", "list", "--repo", "Zocdoc/provider-fe-monorepo", "--state", "all", "--limit", "50", "--json", "author,createdAt"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            prs = json.loads(result.stdout)
            # Count unique authors as proxy
            authors = set(pr.get("author", {}).get("login", "") for pr in prs)
            return {"total_prs": len(prs), "unique_authors": len(authors)}
    except Exception:
        pass

    return {"total_prs": 0, "unique_authors": 0}


def main():
    skip_prs = "--skip-prs" in sys.argv
    skip_sprints = "--skip-sprints" in sys.argv

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Load existing data
    prs_file = DATA_DIR / "prs.json"
    sprints_file = DATA_DIR / "sprints.json"

    prs_data = json.loads(prs_file.read_text()) if prs_file.exists() else {}
    sprints_data = json.loads(sprints_file.read_text()) if sprints_file.exists() else {}

    # Fetch sprint data
    if not skip_sprints:
        email, token = get_jira_credentials()
        if email and token:
            print("Fetching sprint data from Jira...")
            today_sprints = {"teams": {}}
            for team_id, config in TEAM_CONFIG.items():
                print(f"  {team_id}...", end=" ", flush=True)
                data = fetch_sprint_data(config["jiraProject"], email, token)
                today_sprints["teams"][team_id] = data
                if "error" in data:
                    print(f"error: {data['error']}")
                else:
                    print(f"{data['done_issues']}/{data['total_issues']} done")

            sprints_data[today] = today_sprints
            sprints_data["lastUpdated"] = now_iso

            # Keep only last 30 days
            dates = sorted([k for k in sprints_data.keys() if k.startswith("202")])
            for old_date in dates[:-30]:
                del sprints_data[old_date]

            sprints_file.write_text(json.dumps(sprints_data, indent=2))
            print(f"Updated {sprints_file}")
        else:
            print("Skipping sprints: no Jira credentials")

    # Fetch PR data
    if not skip_prs:
        gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if gh_token:
            print("Fetching PR data from GitHub...")
            today_prs = {"teams": {}}
            for team_id, config in TEAM_CONFIG.items():
                print(f"  {team_id}...", end=" ", flush=True)
                data = fetch_pr_data(config["githubTeam"])
                today_prs["teams"][team_id] = data
                print(f"{data.get('total_prs', 0)} PRs")

            prs_data[today] = today_prs
            prs_data["lastUpdated"] = now_iso

            # Keep only last 30 days
            dates = sorted([k for k in prs_data.keys() if k.startswith("202")])
            for old_date in dates[:-30]:
                del prs_data[old_date]

            prs_file.write_text(json.dumps(prs_data, indent=2))
            print(f"Updated {prs_file}")
        else:
            print("Skipping PRs: no GitHub token")

    print("Done!")


if __name__ == "__main__":
    main()
