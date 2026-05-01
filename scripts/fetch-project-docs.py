#!/usr/bin/env python3
"""Discover documents related to a project using Glean search.

Searches email and Slack for document links (Confluence, Google Docs,
Figma, Looker) related to a project.

Usage:
    python3 fetch-project-docs.py "Project Name" "keyword1" "keyword2"

Output:
    JSON array of discovered documents on stdout.
    Each doc: {"name": "...", "url": "...", "type": "confluence|gdoc|figma|looker|other"}

Note:
    This script outputs search parameters. In production, refresh-projects.py
    calls Glean MCP directly. This script serves as documentation.
"""
import json
import re
import sys


DOC_PATTERNS = [
    (r"zocdoc\.atlassian\.net/wiki", "confluence"),
    (r"docs\.google\.com", "gdoc"),
    (r"figma\.com", "figma"),
    (r"looker\.zocdoc\.com|lookerstudio\.google\.com", "looker"),
]


def classify_url(url: str) -> str:
    """Classify a URL by document type."""
    for pattern, doc_type in DOC_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return doc_type
    return "other"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fetch-project-docs.py 'Project Name' [keywords...]", file=sys.stderr)
        sys.exit(1)

    project_name = sys.argv[1]
    keywords = sys.argv[2:] if len(sys.argv) > 2 else []

    search_query = f"{project_name} {' '.join(keywords)}".strip()

    search_config = {
        "query": search_query,
        "datasources": ["slack", "gmail"],
        "filters": {
            "updated": "past_month"
        },
        "extract_urls": True,
        "url_patterns": [p[0] for p in DOC_PATTERNS]
    }

    print(json.dumps(search_config, indent=2))


if __name__ == "__main__":
    main()
