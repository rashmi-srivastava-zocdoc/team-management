#!/usr/bin/env python3
"""Generate a 5-day summary of Slack channel activity using Glean.

This script is designed to be called by refresh-projects.py with Glean
MCP available, or manually with the channel name.

Usage:
    python3 fetch-slack-summary.py "#channel-name" "Project Name"

Output:
    A short summary string (1-3 sentences) on stdout.
    Empty string if no activity or Glean unavailable.

Note:
    This script outputs a prompt for Glean. In production, refresh-projects.py
    calls Glean MCP directly. This script serves as documentation and fallback.
"""
import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 fetch-slack-summary.py '#channel' 'Project Name'", file=sys.stderr)
        sys.exit(1)

    channel = sys.argv[1]
    project_name = sys.argv[2]

    prompt = f"""Summarize the last 5 days of activity in the Slack channel {channel}
for the project "{project_name}".

Focus on:
- Key decisions made
- Blockers or issues raised
- Progress updates
- Upcoming milestones mentioned

Keep the summary to 2-3 sentences. If there's no recent activity, say so briefly."""

    print(prompt)


if __name__ == "__main__":
    main()
