#!/usr/bin/env python3
"""Fetch ticket statistics for Jira epics.

Usage:
    python3 fetch-jira-project-stats.py EPIC-123 EPIC-456

Requires:
    JIRA_EMAIL and JIRA_API_TOKEN environment variables
    Or: ~/.config/jira-credentials.json with {"email": "...", "api_token": "..."}

Output:
    JSON object mapping epic keys to stats: {"EPIC-123": {"total": 10, "done": 5, "inProgress": 3}}
"""
import base64
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

JIRA_BASE_URL = "https://zocdoc.atlassian.net"
JIRA_API_URL = f"{JIRA_BASE_URL}/rest/api/3"


def get_credentials():
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


def fetch_epic_stats(epic_key: str, email: str, token: str) -> dict:
    """Fetch ticket counts for an epic."""
    jql = f'"Epic Link" = {epic_key} OR parent = {epic_key}'
    url = f"{JIRA_API_URL}/search?jql={jql}&maxResults=100&fields=status"

    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    req = Request(url, headers={
        "Authorization": f"Basic {auth}",
        "Accept": "application/json"
    })

    try:
        with urlopen(req) as response:
            data = json.loads(response.read())
    except HTTPError as e:
        print(f"Error fetching {epic_key}: {e}", file=sys.stderr)
        return {"total": 0, "done": 0, "inProgress": 0, "error": str(e)}

    total = data.get("total", 0)
    done = 0
    in_progress = 0

    for issue in data.get("issues", []):
        status = issue.get("fields", {}).get("status", {}).get("statusCategory", {}).get("key", "")
        if status == "done":
            done += 1
        elif status == "indeterminate":
            in_progress += 1

    return {"total": total, "done": done, "inProgress": in_progress}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fetch-jira-project-stats.py EPIC-123 [EPIC-456 ...]", file=sys.stderr)
        sys.exit(1)

    epic_keys = sys.argv[1:]
    email, token = get_credentials()

    if not email or not token:
        print("Error: Jira credentials not found", file=sys.stderr)
        print("Set JIRA_EMAIL and JIRA_API_TOKEN env vars", file=sys.stderr)
        sys.exit(1)

    results = {}
    for key in epic_keys:
        results[key] = fetch_epic_stats(key, email, token)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
