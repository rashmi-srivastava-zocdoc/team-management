# Team Hub & People Insights Architecture Design

**Date:** 2026-05-03  
**Status:** Approved  
**Goal:** Separate public team metrics (GitHub Pages) from private individual metrics (local only)

---

## Overview

Split EM-Dashboard into two distinct tools:
- **team-hub/** — Public GitHub Pages site showing team directory, scorecard, projects, and aggregated team metrics
- **people-insights/** — Private local tool for individual performance analysis, gap analysis, and detailed metrics

## Repository Structure

```
EM-Dashboard/
├── people-insights/          # PRIVATE - all data collection, individual analysis
│   ├── config/
│   │   └── teams.yaml        # Team definitions, Jira keys, repos
│   ├── data/
│   │   ├── sprints.json      # Full sprint data with individual breakdown
│   │   ├── prs.json          # All PRs with author info
│   │   ├── slack.json        # Slack activity
│   │   ├── incidents.json    # PagerDuty incidents
│   │   └── individuals/
│   │       ├── gap-analysis/
│   │       └── activity-reports/
│   ├── scripts/
│   │   ├── refresh.py        # Daily data collection from all sources
│   │   ├── publish-to-hub.py # Aggregate & push to team-hub
│   │   └── backfill.py       # Historical data collection
│   ├── frontend/             # React app (migrated from TeamMetrics)
│   └── backend/              # FastAPI (migrated from TeamMetrics)
│
├── team-hub/                 # PUBLIC - GitHub Pages
│   ├── data/
│   │   ├── teams.json        # Team roster (no individual metrics)
│   │   ├── sprints.json      # Team-level velocity only
│   │   ├── prs.json          # Team PR counts only
│   │   └── projects.json     # Project status
│   ├── index.html            # Team directory
│   ├── scorecard.html        # Compliance scorecard
│   ├── projects.html         # Project tracker
│   └── metrics.html          # NEW: Team sprint/shipping metrics
│
└── docs/
    └── superpowers/
        └── specs/            # Design documents
```

## Data Flow

### Daily Refresh (6 AM via Claude Code Scheduled Routine)

1. `cd ~/Desktop/Github/EM-Dashboard/people-insights`
2. `python scripts/refresh.py`
   - Fetch GitHub PRs for all 3 teams and their repos
   - Fetch Jira sprint data (PROVGRO, PTERODACTL, BILL)
   - Fetch Slack activity (if token available)
   - Fetch PagerDuty incidents
   - Save to `data/*.json` with full individual breakdown
3. `python scripts/publish-to-hub.py`
   - Read `people-insights/data/*.json`
   - Aggregate to team level (strip individual identifiers)
   - Write to `team-hub/data/*.json`
   - Git commit + push to team-hub
4. GitHub Pages auto-deploys team-hub

### Data Retention

- Each day appends to JSON files (no overwrites)
- Structure: `{ "2026-05-03": {...}, "2026-05-04": {...} }`
- Enables trend charts over time

## JSON Schemas

### Private: people-insights/data/sprints.json

```json
{
  "2026-05-03": {
    "teams": {
      "peacock": {
        "sprint_name": "Sprint 23",
        "velocity": 42,
        "committed": 50,
        "completed": 42,
        "tickets": [
          {
            "key": "PROVGRO-123",
            "assignee": "sydney.morton@zocdoc.com",
            "points": 3,
            "status": "Done"
          }
        ]
      }
    }
  }
}
```

### Public: team-hub/data/sprints.json

```json
{
  "2026-05-03": {
    "teams": {
      "peacock": {
        "sprint_name": "Sprint 23",
        "velocity": 42,
        "committed": 50,
        "completion_rate": 84,
        "ticket_count": 15
      }
    }
  }
}
```

### PR Data (same pattern)

- **Private**: includes author, review times per person, individual counts
- **Public**: team totals only (PRs merged, avg review time)

## Teams Covered

| Team | Jira Project | Repositories |
|------|--------------|--------------|
| Peacock (Provider Onboarding) | PROVGRO | provider-setup-service |
| Pterodactyl (Account & User Setup) | PTERODACTL | practice-user-permissions, practice-authorization-proxy, provider-grouping, provider-join-service |
| Billing | BILL | (to be discovered - not listed in teams.md) |

## Backfill Strategy

### Phase 1: Current Sprint (validate first)
- Run `refresh.py` to capture current sprint
- Validate data correctness
- Test `publish-to-hub.py` aggregation

### Phase 2: Historical Backfill (2026-01-01 to 2026-05-02)
- `python scripts/backfill.py --start 2026-01-01 --end 2026-05-02`
- Iterates week by week:
  - GitHub PRs: Full history available
  - Jira sprints: Full history available
  - Slack: Limited to 90 days (free tier)
  - PagerDuty: Check retention policy
- Rate-limit friendly (1 second delay between API calls)
- Estimated time: 10-15 minutes for 18 weeks

## Migration Plan

| Current Location | Action | New Location |
|------------------|--------|--------------|
| `TeamMetrics/` | Rename + restructure | `people-insights/frontend/` + `backend/` |
| `TeamMetrics/backend/config/teams.yaml` | Move | `people-insights/config/teams.yaml` |
| `TeamMetrics/backend/data/*.json` | Move | `people-insights/data/` |
| `people-management/` | Merge | `people-insights/data/individuals/` |
| `people-management/reports/` | Move | `people-insights/data/individuals/reports/` |
| `team-management/` | Rename | `team-hub/` |

## Git Strategy

- **team-hub/**: Git repo, pushes to GitHub (public, GitHub Pages)
- **people-insights/**: Local-only git repo (private, not pushed)

## New Skill

Create `/rs-refresh-metrics` skill to:
- Run the daily refresh manually
- Schedule via `/schedule` for 6 AM daily execution

## Public vs Private Data Summary

| Data Type | team-hub (Public) | people-insights (Private) |
|-----------|-------------------|---------------------------|
| Team roster | ✅ Names, roles | ✅ Full contact info |
| Projects | ✅ Status, epics | ✅ Same |
| Scorecard | ✅ Compliance % | ✅ Same |
| Sprint velocity | ✅ Team totals | ✅ + Individual breakdown |
| PRs merged | ✅ Team counts | ✅ + Per-person counts |
| Gap analysis | ❌ | ✅ |
| Peer comparisons | ❌ | ✅ |
| Activity reports | ❌ | ✅ |
