#!/usr/bin/env python3
"""Fetch tickets from Jira epics and categorize them for the scorecard.

Reads epic keys from TEAMS config, fetches child tickets via Jira API,
and categorizes them under scorecard checks based on summary/description.

Usage:
    python3 fetch-epic-tickets.py                    # Fetch all team epics
    python3 fetch-epic-tickets.py --team provider-onboarding  # Fetch one team

    # Stdin mode - categorize pre-fetched JSON (e.g., from Atlassian MCP):
    python3 fetch-epic-tickets.py --stdin --team provider-onboarding < tickets.json
    cat tickets.json | python3 fetch-epic-tickets.py --stdin --team account-user-setup

Requires (for API mode):
    JIRA_EMAIL and JIRA_API_TOKEN environment variables
    Or: ~/.config/jira-credentials.json with {"email": "...", "api_token": "..."}
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import base64

# Jira configuration
JIRA_BASE_URL = "https://zocdoc.atlassian.net"
JIRA_API_URL = f"{JIRA_BASE_URL}/rest/api/3"

# Output file for categorized tickets
OUTPUT_FILE = Path(__file__).parent.parent / "scorecard" / "epic-tickets.json"

# Team epics - must match TEAMS in build-scorecard.py
TEAM_EPICS = {
    "provider-onboarding": {
        "epic_key": "PROVGRO-6335",
        "default_service": "provider-setup-service",
    },
    "account-user-setup": {
        "epic_key": "PTERODACTL-1880",
        "default_service": None,  # Must detect from ticket
    },
}

# Service detection patterns
SERVICE_PATTERNS = [
    (r"\bPSS\b|provider-setup-service|provider setup service", "provider-setup-service"),
    (r"\bPUP\b|practice-user-permissions|user permissions", "practice-user-permissions"),
    (r"\bPAP\b|practice-authorization-proxy|authorization proxy", "practice-authorization-proxy"),
    (r"\bPOGS\b|provider-grouping|provider grouping", "provider-grouping"),
    (r"\bPJS\b|provider-join-service|provider join", "provider-join-service"),
]

# Check categorization rules (order matters - first match wins)
# Format: (pattern, check_id, exclude_pattern)
CHECK_PATTERNS = [
    # Blue/green related (including smoke tests FOR blue/green)
    (r"blue[/-]?green|ecs deployment|deployment validation", "blueGreen", None),
    (r"smoke test.*blue[/-]?green|blue[/-]?green.*smoke test", "blueGreen", None),

    # SLO gate
    (r"slo gate|deployment gate|slo block", "sloGate", None),

    # Coverage
    (r"\[test coverage\]|\[coverage\]|unit test|test coverage|coverage", "coverage", None),

    # Muted tests
    (r"muted test|ignored test|skip test", "mutedTests", None),

    # EOL
    (r"\beol\b|end of life|framework upgrade|\.net upgrade", "eol", None),

    # SLO
    (r"\bslo\b|service level|latency target|availability target", "slo", r"slo gate|burn rate"),

    # Burn rate
    (r"burn rate|error budget|slo alert", "burnRate", None),

    # Smoke tests (generic - NOT blue/green related)
    (r"smoke test", "smokeTests", r"blue[/-]?green"),

    # Sentry
    (r"sentry|error tracking", "sentry", None),

    # Incident metric
    (r"incident|pagerduty|5xx|alerting", "incidentMetric", r"pagerduty config"),

    # Plinth / auth
    (r"plinth|auth-policies|authorization", "plinth", None),

    # CDK
    (r"\bcdk\b|ansible|infrastructure", "cdkNoAnsible", None),

    # PagerDuty config
    (r"pagerduty config|on-call config", "pagerduty", None),

    # PR size
    (r"pr size|pull request size", "prSize", None),

    # Deployable
    (r"\bdeploy\b|ci/cd|pipeline", "deployable", r"blue[/-]?green|smoke test"),
]


def get_jira_credentials():
    """Get Jira credentials from env vars or config file."""
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")

    if email and token:
        return email, token

    # Try config file
    config_file = Path.home() / ".config" / "jira-credentials.json"
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
            return config.get("email"), config.get("api_token")

    return None, None


def jira_request(endpoint, email, token):
    """Make authenticated request to Jira API."""
    url = f"{JIRA_API_URL}/{endpoint}"
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()

    req = Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        print(f"  Error fetching {endpoint}: {e.code} {e.reason}")
        return None


def fetch_epic_children(epic_key, email, token):
    """Fetch all child issues of an epic."""
    # JQL to find issues in the epic
    jql = f'"Epic Link" = {epic_key} OR parent = {epic_key}'
    jql_encoded = jql.replace(' ', '%20').replace('=', '%3D').replace('"', '%22')
    endpoint = f"search?jql={jql_encoded}&maxResults=100&fields=key,summary,status,description"

    result = jira_request(endpoint, email, token)
    if not result:
        return []

    tickets = []
    for issue in result.get("issues", []):
        fields = issue.get("fields", {})

        # Extract description text (Jira uses Atlassian Document Format)
        description = ""
        desc_field = fields.get("description")
        if desc_field and isinstance(desc_field, dict):
            # Parse ADF content
            for content in desc_field.get("content", []):
                for item in content.get("content", []):
                    if item.get("type") == "text":
                        description += item.get("text", "") + " "
        elif isinstance(desc_field, str):
            description = desc_field

        tickets.append({
            "key": issue.get("key"),
            "summary": fields.get("summary", ""),
            "status": fields.get("status", {}).get("name", "Unknown"),
            "description": description[:500],  # Truncate for matching
        })

    return tickets


def detect_service(text, default_service):
    """Detect service from ticket text."""
    text_lower = text.lower()

    for pattern, service in SERVICE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return service

    return default_service


def categorize_ticket(ticket, default_service):
    """Categorize a ticket under a scorecard check."""
    text = f"{ticket['summary']} {ticket.get('description', '')}".lower()

    for pattern, check_id, exclude_pattern in CHECK_PATTERNS:
        # Check if pattern matches
        if re.search(pattern, text, re.IGNORECASE):
            # Check if exclude pattern also matches (skip if so)
            if exclude_pattern and re.search(exclude_pattern, text, re.IGNORECASE):
                continue

            service = detect_service(text, default_service)
            return check_id, service

    # No match - return None for uncategorized
    return None, detect_service(text, default_service)


def fetch_and_categorize(team_id, team_config, email, token):
    """Fetch and categorize tickets for a team."""
    epic_key = team_config["epic_key"]
    default_service = team_config["default_service"]

    print(f"\nFetching tickets from {epic_key}...")
    tickets = fetch_epic_children(epic_key, email, token)
    print(f"  Found {len(tickets)} tickets")

    # Categorize tickets
    categorized = {}
    uncategorized = []

    for ticket in tickets:
        check_id, service = categorize_ticket(ticket, default_service)

        if check_id:
            if check_id not in categorized:
                categorized[check_id] = []

            categorized[check_id].append({
                "key": ticket["key"],
                "summary": ticket["summary"],
                "status": ticket["status"],
                "service": service,
            })
            print(f"  {ticket['key']}: {check_id} ({service})")
        else:
            uncategorized.append(ticket)
            print(f"  {ticket['key']}: UNCATEGORIZED - {ticket['summary'][:50]}...")

    if uncategorized:
        print(f"\n  ⚠ {len(uncategorized)} tickets could not be categorized")

    return categorized, uncategorized


def parse_stdin_tickets(raw_json, default_service):
    """Parse tickets from stdin JSON (Atlassian MCP format or raw Jira API response)."""
    data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json

    # Handle MCP wrapper format: [{"type": "text", "text": "{...}"}]
    if isinstance(data, list) and len(data) > 0 and "type" in data[0]:
        data = json.loads(data[0]["text"])

    # Extract issues array
    issues = data.get("issues", [])

    tickets = []
    for issue in issues:
        fields = issue.get("fields", {})

        # Extract description text
        description = ""
        desc_field = fields.get("description")
        if isinstance(desc_field, str):
            description = desc_field
        elif isinstance(desc_field, dict):
            # ADF format - extract text content
            for content in desc_field.get("content", []):
                for item in content.get("content", []):
                    if item.get("type") == "text":
                        description += item.get("text", "") + " "

        # Get status name
        status = "Unknown"
        status_field = fields.get("status")
        if isinstance(status_field, dict):
            status = status_field.get("name", "Unknown")
        elif isinstance(status_field, str):
            status = status_field

        tickets.append({
            "key": issue.get("key"),
            "summary": fields.get("summary", ""),
            "status": status,
            "description": description[:500],
        })

    return tickets


def categorize_tickets_from_list(tickets, default_service):
    """Categorize a list of tickets."""
    categorized = {}
    uncategorized = []

    for ticket in tickets:
        check_id, service = categorize_ticket(ticket, default_service)

        if check_id:
            if check_id not in categorized:
                categorized[check_id] = []

            categorized[check_id].append({
                "key": ticket["key"],
                "summary": ticket["summary"],
                "status": ticket["status"],
                "service": service,
            })
            print(f"  {ticket['key']}: {check_id} ({service})")
        else:
            uncategorized.append(ticket)
            print(f"  {ticket['key']}: UNCATEGORIZED - {ticket['summary'][:50]}...")

    return categorized, uncategorized


def main():
    parser = argparse.ArgumentParser(description="Fetch and categorize epic tickets for scorecard")
    parser.add_argument("--team", help="Team ID to fetch (default: all teams)")
    parser.add_argument("--dry-run", action="store_true", help="Print results without saving")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin instead of fetching from Jira API")
    args = parser.parse_args()

    # Stdin mode - categorize pre-fetched JSON
    if args.stdin:
        if not args.team:
            print("Error: --stdin requires --team to specify which team the tickets belong to")
            sys.exit(1)

        if args.team not in TEAM_EPICS:
            print(f"Error: Unknown team '{args.team}'. Valid teams: {', '.join(TEAM_EPICS.keys())}")
            sys.exit(1)

        team_config = TEAM_EPICS[args.team]
        default_service = team_config["default_service"]

        print(f"Reading tickets from stdin for {args.team}...")
        raw_json = sys.stdin.read()

        tickets = parse_stdin_tickets(raw_json, default_service)
        print(f"  Found {len(tickets)} tickets")

        categorized, uncategorized = categorize_tickets_from_list(tickets, default_service)

        # Load existing data and merge
        all_tickets = {}
        all_uncategorized = {}

        if OUTPUT_FILE.exists():
            with open(OUTPUT_FILE) as f:
                existing = json.load(f)
                all_tickets = existing.get("ticketsByTeam", {})
                all_uncategorized = existing.get("uncategorized", {})

        all_tickets[args.team] = categorized
        if uncategorized:
            all_uncategorized[args.team] = uncategorized

        # Save
        if not args.dry_run:
            output = {
                "ticketsByTeam": all_tickets,
                "uncategorized": all_uncategorized,
            }
            os.makedirs(OUTPUT_FILE.parent, exist_ok=True)
            with open(OUTPUT_FILE, "w") as f:
                json.dump(output, f, indent=2)
            print(f"\n✓ Saved to {OUTPUT_FILE}")
        else:
            print("\n(Dry run - results not saved)")

        return

    # API mode - fetch from Jira
    email, token = get_jira_credentials()
    if not email or not token:
        print("Error: Jira credentials not found.")
        print("Set JIRA_EMAIL and JIRA_API_TOKEN environment variables, or create ~/.config/jira-credentials.json")
        sys.exit(1)

    # Determine which teams to fetch
    teams_to_fetch = {}
    if args.team:
        if args.team not in TEAM_EPICS:
            print(f"Error: Unknown team '{args.team}'. Valid teams: {', '.join(TEAM_EPICS.keys())}")
            sys.exit(1)
        teams_to_fetch[args.team] = TEAM_EPICS[args.team]
    else:
        teams_to_fetch = TEAM_EPICS

    print("=" * 60)
    print("  FETCH EPIC TICKETS FOR SCORECARD")
    print("=" * 60)

    # Load existing data if updating a single team
    all_tickets = {}
    all_uncategorized = {}

    if OUTPUT_FILE.exists() and args.team:
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)
            all_tickets = existing.get("ticketsByTeam", {})
            all_uncategorized = existing.get("uncategorized", {})

    # Fetch and categorize for each team
    for team_id, team_config in teams_to_fetch.items():
        print(f"\n{'='*60}")
        print(f"  {team_id.upper()}")
        print(f"{'='*60}")

        categorized, uncategorized = fetch_and_categorize(team_id, team_config, email, token)
        all_tickets[team_id] = categorized
        if uncategorized:
            all_uncategorized[team_id] = uncategorized

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")

    for team_id, checks in all_tickets.items():
        total = sum(len(tickets) for tickets in checks.values())
        print(f"\n{team_id}:")
        for check_id, tickets in sorted(checks.items()):
            print(f"  {check_id}: {len(tickets)} tickets")
        uncat_count = len(all_uncategorized.get(team_id, []))
        if uncat_count:
            print(f"  UNCATEGORIZED: {uncat_count} tickets")

    # Save results
    if not args.dry_run:
        output = {
            "ticketsByTeam": all_tickets,
            "uncategorized": all_uncategorized,
        }

        os.makedirs(OUTPUT_FILE.parent, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\n✓ Saved to {OUTPUT_FILE}")
        print("\nNext: Run 'python3 scripts/build-scorecard.py' to rebuild scorecard")
    else:
        print("\n(Dry run - results not saved)")


if __name__ == "__main__":
    main()
