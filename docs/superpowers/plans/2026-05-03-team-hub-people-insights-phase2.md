# Team Hub & People Insights - Phase 2: Data Collection Scripts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create Python scripts to fetch metrics from GitHub/Jira, store in people-insights, and publish aggregated data to team-hub.

**Architecture:** Three scripts - refresh.py (daily data collection), publish-to-hub.py (aggregate and push), backfill.py (historical data). All scripts live in people-insights/scripts/.

**Tech Stack:** Python 3.11+, httpx, GitPython

---

## File Structure

```
people-insights/scripts/
├── refresh.py           # Daily data collection
├── publish_to_hub.py    # Aggregate and push to team-hub
├── backfill.py          # Historical data collection
└── utils/
    ├── __init__.py
    ├── github_client.py # GitHub API wrapper
    ├── jira_client.py   # Jira API wrapper
    └── config.py        # Shared configuration
```

---

### Task 1: Create Shared Configuration Module

**Files:**
- Create: `people-insights/scripts/utils/__init__.py`
- Create: `people-insights/scripts/utils/config.py`

- [ ] **Step 1: Create utils directory**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights/scripts
mkdir -p utils
touch utils/__init__.py
```

- [ ] **Step 2: Create config.py**

```bash
cat > utils/config.py << 'PYEOF'
"""Shared configuration for data collection scripts."""
import os
from pathlib import Path

# Paths
PEOPLE_INSIGHTS_ROOT = Path(__file__).parent.parent.parent
TEAM_HUB_ROOT = PEOPLE_INSIGHTS_ROOT.parent / "team-hub"
CONFIG_DIR = PEOPLE_INSIGHTS_ROOT / "config"
DATA_DIR = PEOPLE_INSIGHTS_ROOT / "data"

# Team configuration
TEAMS_YAML = CONFIG_DIR / "teams.yaml"

# API credentials from environment
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_ORG = os.environ.get("GITHUB_ORG", "Zocdoc")
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://zocdoc.atlassian.net")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")

# Team definitions
TEAMS = {
    "peacock": {
        "name": "Peacock (Provider Onboarding)",
        "jira_project": "PROVGRO",
        "repos": ["provider-setup-service"],
    },
    "pterodactyl": {
        "name": "Pterodactyl (Account & User Setup)",
        "jira_project": "PTERODACTL",
        "repos": [
            "practice-user-permissions",
            "practice-authorization-proxy",
            "provider-grouping",
            "provider-join-service",
        ],
    },
    "billing": {
        "name": "Billing",
        "jira_project": "BILL",
        "repos": [],  # To be discovered
    },
}
PYEOF
```

- [ ] **Step 3: Verify config imports**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
PYTHONPATH=scripts python3 -c "from utils.config import TEAMS, DATA_DIR; print(f'Teams: {list(TEAMS.keys())}'); print(f'Data dir: {DATA_DIR}')"
```

Expected: `Teams: ['peacock', 'pterodactyl', 'billing']` and data dir path

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
git add scripts/utils/
git commit -m "feat: add shared configuration module for scripts

Defines paths, API credentials, and team configurations.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 2: Create GitHub Client Wrapper

**Files:**
- Create: `people-insights/scripts/utils/github_client.py`

- [ ] **Step 1: Create github_client.py**

```bash
cat > scripts/utils/github_client.py << 'PYEOF'
"""GitHub API client for fetching PR data."""
import json
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import urllib.error

from .config import GITHUB_TOKEN, GITHUB_ORG


def _make_request(url: str) -> dict:
    """Make authenticated GitHub API request."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TeamMetrics/1.0",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"GitHub API error: {e.code} {e.reason}")
        return {}


def fetch_merged_prs(
    repo: str,
    start_date: datetime,
    end_date: datetime,
    org: str = GITHUB_ORG,
) -> list[dict]:
    """Fetch merged PRs for a repo in date range."""
    prs = []
    page = 1
    
    while True:
        url = (
            f"https://api.github.com/repos/{org}/{repo}/pulls"
            f"?state=closed&sort=updated&direction=desc&per_page=100&page={page}"
        )
        data = _make_request(url)
        
        if not data:
            break
            
        for pr in data:
            if not pr.get("merged_at"):
                continue
                
            merged_at = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
            
            if merged_at < start_date:
                return prs  # Past our date range
                
            if merged_at <= end_date:
                prs.append({
                    "number": pr["number"],
                    "title": pr["title"],
                    "author": pr["user"]["login"],
                    "merged_at": pr["merged_at"],
                    "url": pr["html_url"],
                })
        
        if len(data) < 100:
            break
        page += 1
    
    return prs


def fetch_prs_for_team(
    repos: list[str],
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Fetch PRs for all repos belonging to a team."""
    all_prs = []
    for repo in repos:
        prs = fetch_merged_prs(repo, start_date, end_date)
        for pr in prs:
            pr["repo"] = repo
        all_prs.extend(prs)
    
    return {
        "prs": all_prs,
        "total": len(all_prs),
        "by_author": _count_by_author(all_prs),
    }


def _count_by_author(prs: list[dict]) -> dict[str, int]:
    """Count PRs by author."""
    counts = {}
    for pr in prs:
        author = pr["author"]
        counts[author] = counts.get(author, 0) + 1
    return counts
PYEOF
```

- [ ] **Step 2: Verify imports**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
PYTHONPATH=scripts python3 -c "from utils.github_client import fetch_prs_for_team; print('GitHub client OK')"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/utils/github_client.py
git commit -m "feat: add GitHub client for PR data collection

Fetches merged PRs by date range, aggregates by author.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 3: Create Jira Client Wrapper

**Files:**
- Create: `people-insights/scripts/utils/jira_client.py`

- [ ] **Step 1: Create jira_client.py**

```bash
cat > scripts/utils/jira_client.py << 'PYEOF'
"""Jira API client for fetching sprint data."""
import base64
import json
from datetime import datetime
from typing import Optional
import urllib.request
import urllib.error

from .config import JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN


def _get_auth_header() -> str:
    """Get Basic auth header for Jira."""
    credentials = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def _make_request(url: str) -> dict:
    """Make authenticated Jira API request."""
    headers = {
        "Authorization": _get_auth_header(),
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"Jira API error: {e.code} {e.reason}")
        return {}


def fetch_board_id(project_key: str) -> Optional[int]:
    """Get the board ID for a project."""
    url = f"{JIRA_BASE_URL}/rest/agile/1.0/board?projectKeyOrId={project_key}"
    data = _make_request(url)
    boards = data.get("values", [])
    if boards:
        return boards[0]["id"]
    return None


def fetch_sprints(board_id: int, state: str = "active,closed") -> list[dict]:
    """Fetch sprints for a board."""
    url = f"{JIRA_BASE_URL}/rest/agile/1.0/board/{board_id}/sprint?state={state}"
    data = _make_request(url)
    return data.get("values", [])


def fetch_sprint_issues(sprint_id: int) -> list[dict]:
    """Fetch issues in a sprint."""
    url = (
        f"{JIRA_BASE_URL}/rest/agile/1.0/sprint/{sprint_id}/issue"
        f"?maxResults=200&fields=summary,status,assignee,issuetype,customfield_10016"
    )
    data = _make_request(url)
    
    issues = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        assignee = fields.get("assignee") or {}
        issues.append({
            "key": issue["key"],
            "summary": fields.get("summary", ""),
            "status": fields.get("status", {}).get("name", ""),
            "assignee": assignee.get("emailAddress", "unassigned"),
            "assignee_name": assignee.get("displayName", "Unassigned"),
            "type": fields.get("issuetype", {}).get("name", ""),
            "points": fields.get("customfield_10016") or 0,
        })
    
    return issues


def fetch_sprint_data(project_key: str) -> dict:
    """Fetch sprint data for a project."""
    board_id = fetch_board_id(project_key)
    if not board_id:
        return {"error": f"No board found for {project_key}"}
    
    sprints = fetch_sprints(board_id)
    if not sprints:
        return {"error": f"No sprints found for board {board_id}"}
    
    # Get most recent closed sprint or active sprint
    recent_sprint = None
    for sprint in reversed(sprints):
        if sprint.get("state") in ("active", "closed"):
            recent_sprint = sprint
            break
    
    if not recent_sprint:
        return {"error": "No active or closed sprint found"}
    
    issues = fetch_sprint_issues(recent_sprint["id"])
    
    # Calculate metrics
    total_points = sum(i["points"] for i in issues)
    done_points = sum(i["points"] for i in issues if i["status"] == "Done")
    done_count = sum(1 for i in issues if i["status"] == "Done")
    
    return {
        "sprint_id": recent_sprint["id"],
        "sprint_name": recent_sprint["name"],
        "state": recent_sprint["state"],
        "start_date": recent_sprint.get("startDate"),
        "end_date": recent_sprint.get("endDate"),
        "total_issues": len(issues),
        "done_issues": done_count,
        "total_points": total_points,
        "done_points": done_points,
        "completion_rate": round(done_points / total_points * 100, 1) if total_points > 0 else 0,
        "issues": issues,  # Full detail for private storage
    }
PYEOF
```

- [ ] **Step 2: Verify imports**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
PYTHONPATH=scripts python3 -c "from utils.jira_client import fetch_sprint_data; print('Jira client OK')"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/utils/jira_client.py
git commit -m "feat: add Jira client for sprint data collection

Fetches sprints, issues, calculates velocity metrics.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 4: Create Main Refresh Script

**Files:**
- Create: `people-insights/scripts/refresh.py`

- [ ] **Step 1: Create refresh.py**

```bash
cat > scripts/refresh.py << 'PYEOF'
#!/usr/bin/env python3
"""Daily data collection script.

Fetches metrics from GitHub and Jira for all teams,
stores in people-insights/data/ with full individual detail.

Usage:
    python3 refresh.py [--date YYYY-MM-DD]
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from utils.config import TEAMS, DATA_DIR
from utils.github_client import fetch_prs_for_team
from utils.jira_client import fetch_sprint_data


def load_json(path: Path) -> dict:
    """Load JSON file or return empty dict."""
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_json(path: Path, data: dict) -> None:
    """Save data to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  Saved: {path}")


def refresh_prs(date_str: str) -> None:
    """Fetch PR data for all teams."""
    print("\n[1/2] Fetching PR data...")
    
    prs_file = DATA_DIR / "prs.json"
    prs_data = load_json(prs_file)
    
    # Date range: 7 days ending on target date
    end_date = datetime.fromisoformat(date_str)
    start_date = end_date - timedelta(days=7)
    
    day_data = {"fetched_at": datetime.now().isoformat(), "teams": {}}
    
    for team_id, team_config in TEAMS.items():
        repos = team_config.get("repos", [])
        if not repos:
            print(f"  {team_id}: No repos configured, skipping")
            continue
            
        print(f"  {team_id}: Fetching from {len(repos)} repos...")
        team_prs = fetch_prs_for_team(repos, start_date, end_date)
        day_data["teams"][team_id] = team_prs
        print(f"    Found {team_prs['total']} PRs")
    
    prs_data[date_str] = day_data
    save_json(prs_file, prs_data)


def refresh_sprints(date_str: str) -> None:
    """Fetch sprint data for all teams."""
    print("\n[2/2] Fetching sprint data...")
    
    sprints_file = DATA_DIR / "sprints.json"
    sprints_data = load_json(sprints_file)
    
    day_data = {"fetched_at": datetime.now().isoformat(), "teams": {}}
    
    for team_id, team_config in TEAMS.items():
        project_key = team_config.get("jira_project")
        if not project_key:
            print(f"  {team_id}: No Jira project configured, skipping")
            continue
            
        print(f"  {team_id}: Fetching sprint for {project_key}...")
        sprint_data = fetch_sprint_data(project_key)
        
        if "error" in sprint_data:
            print(f"    Error: {sprint_data['error']}")
        else:
            day_data["teams"][team_id] = sprint_data
            print(f"    Sprint: {sprint_data['sprint_name']} ({sprint_data['completion_rate']}% complete)")
    
    sprints_data[date_str] = day_data
    save_json(sprints_file, sprints_data)


def main():
    parser = argparse.ArgumentParser(description="Refresh team metrics data")
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Target date (default: today)",
    )
    args = parser.parse_args()
    
    print("=" * 50)
    print(f"  REFRESH TEAM METRICS - {args.date}")
    print("=" * 50)
    
    refresh_prs(args.date)
    refresh_sprints(args.date)
    
    print("\n" + "=" * 50)
    print("  DONE")
    print("=" * 50)
    print(f"\nData saved to: {DATA_DIR}")
    print("Next: Run publish_to_hub.py to push aggregated data")


if __name__ == "__main__":
    main()
PYEOF
chmod +x scripts/refresh.py
```

- [ ] **Step 2: Test script runs (dry run without API calls)**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
PYTHONPATH=scripts python3 scripts/refresh.py --help
```

Expected: Shows usage help

- [ ] **Step 3: Commit**

```bash
git add scripts/refresh.py
git commit -m "feat: add daily refresh script for metrics collection

Fetches PR and sprint data for all teams, stores with individual detail.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 5: Create Publish to Hub Script

**Files:**
- Create: `people-insights/scripts/publish_to_hub.py`

- [ ] **Step 1: Create publish_to_hub.py**

```bash
cat > scripts/publish_to_hub.py << 'PYEOF'
#!/usr/bin/env python3
"""Publish aggregated metrics to team-hub.

Reads detailed data from people-insights/data/,
aggregates to team level (strips individual info),
writes to team-hub/data/, commits and pushes.

Usage:
    python3 publish_to_hub.py [--no-push]
"""
import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

from utils.config import DATA_DIR, TEAM_HUB_ROOT, TEAMS


def load_json(path: Path) -> dict:
    """Load JSON file or return empty dict."""
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_json(path: Path, data: dict) -> None:
    """Save data to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  Saved: {path}")


def aggregate_prs() -> dict:
    """Aggregate PR data to team level."""
    print("\n[1/2] Aggregating PR data...")
    
    source = load_json(DATA_DIR / "prs.json")
    aggregated = {"lastUpdated": datetime.now().isoformat()}
    
    for date_str, day_data in source.items():
        if date_str == "lastUpdated":
            continue
            
        aggregated[date_str] = {"teams": {}}
        
        for team_id, team_data in day_data.get("teams", {}).items():
            # Strip individual author info, keep only totals
            aggregated[date_str]["teams"][team_id] = {
                "total_prs": team_data.get("total", 0),
                "unique_authors": len(team_data.get("by_author", {})),
            }
    
    return aggregated


def aggregate_sprints() -> dict:
    """Aggregate sprint data to team level."""
    print("[2/2] Aggregating sprint data...")
    
    source = load_json(DATA_DIR / "sprints.json")
    aggregated = {"lastUpdated": datetime.now().isoformat()}
    
    for date_str, day_data in source.items():
        if date_str == "lastUpdated":
            continue
            
        aggregated[date_str] = {"teams": {}}
        
        for team_id, team_data in day_data.get("teams", {}).items():
            # Strip individual issue assignments, keep only aggregates
            aggregated[date_str]["teams"][team_id] = {
                "sprint_name": team_data.get("sprint_name"),
                "state": team_data.get("state"),
                "total_issues": team_data.get("total_issues", 0),
                "done_issues": team_data.get("done_issues", 0),
                "total_points": team_data.get("total_points", 0),
                "done_points": team_data.get("done_points", 0),
                "completion_rate": team_data.get("completion_rate", 0),
            }
    
    return aggregated


def git_commit_and_push(no_push: bool = False) -> None:
    """Commit and push changes to team-hub."""
    print("\n[3/3] Committing to team-hub...")
    
    hub_data = TEAM_HUB_ROOT / "data"
    
    # Check for changes
    result = subprocess.run(
        ["git", "diff", "--quiet", "data/"],
        cwd=TEAM_HUB_ROOT,
        capture_output=True,
    )
    
    if result.returncode == 0:
        print("  No changes to commit")
        return
    
    # Commit
    subprocess.run(["git", "add", "data/"], cwd=TEAM_HUB_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore: update metrics data {datetime.now().strftime('%Y-%m-%d')}\n\nGenerated with AI\n\nCo-Authored-By: Claude Code"],
        cwd=TEAM_HUB_ROOT,
        check=True,
    )
    print("  Committed")
    
    if no_push:
        print("  Skipping push (--no-push)")
        return
    
    # Push
    subprocess.run(["git", "push"], cwd=TEAM_HUB_ROOT, check=True)
    print("  Pushed to remote")


def main():
    parser = argparse.ArgumentParser(description="Publish metrics to team-hub")
    parser.add_argument("--no-push", action="store_true", help="Don't push to remote")
    args = parser.parse_args()
    
    print("=" * 50)
    print("  PUBLISH TO TEAM-HUB")
    print("=" * 50)
    
    hub_data = TEAM_HUB_ROOT / "data"
    
    # Aggregate and save
    prs = aggregate_prs()
    save_json(hub_data / "prs.json", prs)
    
    sprints = aggregate_sprints()
    save_json(hub_data / "sprints.json", sprints)
    
    # Commit and push
    git_commit_and_push(args.no_push)
    
    print("\n" + "=" * 50)
    print("  DONE")
    print("=" * 50)


if __name__ == "__main__":
    main()
PYEOF
chmod +x scripts/publish_to_hub.py
```

- [ ] **Step 2: Test script runs**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
PYTHONPATH=scripts python3 scripts/publish_to_hub.py --help
```

- [ ] **Step 3: Commit**

```bash
git add scripts/publish_to_hub.py
git commit -m "feat: add publish script to aggregate and push to team-hub

Strips individual data, commits aggregated metrics to public repo.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 6: Create Backfill Script

**Files:**
- Create: `people-insights/scripts/backfill.py`

- [ ] **Step 1: Create backfill.py**

```bash
cat > scripts/backfill.py << 'PYEOF'
#!/usr/bin/env python3
"""Backfill historical data.

Fetches metrics for a date range, week by week.

Usage:
    python3 backfill.py --start 2026-01-01 --end 2026-05-02
    python3 backfill.py --weeks 1  # Last N weeks
"""
import argparse
import time
from datetime import datetime, timedelta

from refresh import refresh_prs, refresh_sprints


def backfill_range(start_date: datetime, end_date: datetime) -> None:
    """Backfill data for a date range."""
    current = start_date
    week_num = 1
    total_weeks = ((end_date - start_date).days // 7) + 1
    
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n{'='*50}")
        print(f"  BACKFILL Week {week_num}/{total_weeks}: {date_str}")
        print(f"{'='*50}")
        
        refresh_prs(date_str)
        refresh_sprints(date_str)
        
        current += timedelta(days=7)
        week_num += 1
        
        # Rate limit friendly
        if current <= end_date:
            print("\n  Sleeping 2 seconds (rate limit)...")
            time.sleep(2)
    
    print(f"\n{'='*50}")
    print(f"  BACKFILL COMPLETE - {week_num - 1} weeks")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Backfill historical metrics")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--weeks", type=int, help="Backfill last N weeks")
    args = parser.parse_args()
    
    if args.weeks:
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=args.weeks)
    elif args.start and args.end:
        start_date = datetime.fromisoformat(args.start)
        end_date = datetime.fromisoformat(args.end)
    else:
        parser.error("Provide --start and --end, or --weeks")
    
    print(f"Backfilling from {start_date.date()} to {end_date.date()}")
    backfill_range(start_date, end_date)


if __name__ == "__main__":
    main()
PYEOF
chmod +x scripts/backfill.py
```

- [ ] **Step 2: Test script runs**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
PYTHONPATH=scripts python3 scripts/backfill.py --help
```

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill.py
git commit -m "feat: add backfill script for historical data

Fetches metrics week by week with rate limiting.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 7: Test Full Pipeline with Last Week's Data

**Files:**
- None (testing only)

- [ ] **Step 1: Load environment variables**

Ensure `.env` has the required tokens:

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
cat backend/.env | grep -E "^(GITHUB_TOKEN|JIRA)" | head -3
```

If tokens exist, source them:

```bash
source backend/.env
```

- [ ] **Step 2: Run refresh for last week**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
PYTHONPATH=scripts python3 scripts/refresh.py --date $(date -v-7d +%Y-%m-%d)
```

Expected: Fetches PR and sprint data, saves to `data/prs.json` and `data/sprints.json`

- [ ] **Step 3: Check data files**

```bash
cat data/prs.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'PR dates: {list(d.keys())}')"
cat data/sprints.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Sprint dates: {list(d.keys())}')"
```

- [ ] **Step 4: Run publish (no push)**

```bash
PYTHONPATH=scripts python3 scripts/publish_to_hub.py --no-push
```

- [ ] **Step 5: Verify team-hub data**

```bash
cat ../team-hub/data/sprints.json | python3 -m json.tool | head -30
```

- [ ] **Step 6: Commit test data**

```bash
git add data/
git commit -m "chore: add initial metrics data from test run

Generated with AI

Co-Authored-By: Claude Code"
```

---

## Summary

After Phase 2:
- ✅ `scripts/utils/config.py` - Shared configuration
- ✅ `scripts/utils/github_client.py` - GitHub API wrapper
- ✅ `scripts/utils/jira_client.py` - Jira API wrapper
- ✅ `scripts/refresh.py` - Daily data collection
- ✅ `scripts/publish_to_hub.py` - Aggregate and push to team-hub
- ✅ `scripts/backfill.py` - Historical data collection
- ✅ Pipeline tested with last week's data

**Next:** Phase 3 - Team Metrics UI (metrics.html page for team-hub)
