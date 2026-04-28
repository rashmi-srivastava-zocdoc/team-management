#!/usr/bin/env python3
"""Add Jira epic and ticket tracking to scorecard data."""

import json
from datetime import datetime

DATA_FILE = "scorecard/data.json"

# Epic info for Provider Onboarding
PROVIDER_ONBOARDING_EPIC = {
    "key": "PROVGRO-6335",
    "url": "https://zocdoc.atlassian.net/browse/PROVGRO-6335",
    "summary": "[Q2 2026] Infrastructure Hardening"
}

# Tickets from the epic, mapped to checks
# Status: "To Do", "In Progress", "In Review", "Done"
TICKETS = {
    "coverage": [
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
    "blueGreen": [
        {"key": "PROVGRO-6301", "summary": "Implement smoke tests for blue/green deployment validation", "status": "To Do"},
    ],
    "sloGate": [
        {"key": "PROVGRO-6189", "summary": "[plinth] add missing auth-policies", "status": "In Review"},
    ],
}

def calculate_completion(tickets):
    """Calculate completion percentage based on ticket statuses."""
    if not tickets:
        return None
    done_count = sum(1 for t in tickets if t["status"] == "Done")
    return round((done_count / len(tickets)) * 100)

def add_ticket_url(ticket):
    """Add URL to ticket."""
    ticket["url"] = f"https://zocdoc.atlassian.net/browse/{ticket['key']}"
    return ticket

def main():
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # Add epic to Provider Onboarding team
    if "provider-onboarding" in data["teams"]:
        team = data["teams"]["provider-onboarding"]
        team["epic"] = PROVIDER_ONBOARDING_EPIC

        # Update checks with ticket info
        for service in team.get("services", []):
            for check_id, check in service.get("checks", {}).items():
                if check_id in TICKETS:
                    tickets = [add_ticket_url(t.copy()) for t in TICKETS[check_id]]
                    check["tickets"] = tickets
                    check["completion"] = calculate_completion(tickets)
                else:
                    check["tickets"] = []
                    check["completion"] = None

    # Update timestamp
    data["lastUpdated"] = datetime.now().isoformat()

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {DATA_FILE}")
    print(f"  - Added epic: {PROVIDER_ONBOARDING_EPIC['key']}")
    print(f"  - Added tickets to {len(TICKETS)} checks")

if __name__ == "__main__":
    main()
