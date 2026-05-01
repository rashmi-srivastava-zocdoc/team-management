# Project Tracker Design

## Overview

A webpage that tracks all projects across teams, consolidating documents, links, Slack channels, and SDLC status in one place. Integrates with Jira, Slack, and email via Glean to automatically enrich project data.

## Goals

- Single source of truth for all active projects
- Track projects from early ideation (before Jira) through completion
- Consolidate all related documents in one place
- Surface recent Slack activity summaries
- Show SDLC progress at a glance

## Page Layout

### Location

`projects.html` — accessible via navigation alongside Team Directory and Scorecard.

### Structure

**Header:** Matches existing pages with logo, nav links (Directory | Scorecard | Projects), team dropdown.

**Filters:**
- Team dropdown (All / Provider Onboarding / Pterodactyl / Billing)
- SDLC stage filter (All / Discovery / Planning / Development / Testing / Rollout / Metrics / Complete)

**Main content:** Table with expandable rows.

### Table Columns

| Column | Description |
|--------|-------------|
| Project | Project name (clickable to expand) |
| Team | Owning team |
| Lead(s) | Project lead name(s) |
| Stage | SDLC stage badge |
| Jira | Epic key or "—" if none |
| Updated | Last data refresh timestamp |

### Expanded Row Detail

Two-column layout that appears below the clicked row:

**Left column:**
- Summary: One-paragraph project description
- Slack Summary: AI-generated digest of last 5 days from project Slack channel

**Right column:**
- Documents: List of links with icons by type (Confluence, Google Doc, Figma, Looker, etc.)
- Links: Slack channel link, Jira epic link with progress (e.g., "12/18 done")

## Data Model

### File: `projects/data.json`

```json
{
  "lastUpdated": "2026-04-30T10:00:00Z",
  "projects": [
    {
      "id": "provider-self-service",
      "name": "Provider Self-Service Onboarding",
      "summary": "Enable providers to complete onboarding without CSM assistance",
      "team": "provider-onboarding",
      "leads": ["alexander.gorowara@zocdoc.com"],
      "stage": "development",
      "slackChannels": ["#proj-self-service"],
      "jiraEpics": ["PROVGRO-123"],
      "documents": [
        {
          "name": "Tech Spec",
          "url": "https://zocdoc.atlassian.net/wiki/...",
          "type": "confluence"
        },
        {
          "name": "PRD",
          "url": "https://docs.google.com/...",
          "type": "gdoc"
        },
        {
          "name": "Designs",
          "url": "https://figma.com/...",
          "type": "figma"
        },
        {
          "name": "Metrics Dashboard",
          "url": "https://looker.zocdoc.com/...",
          "type": "looker"
        }
      ],
      "slackSummary": "",
      "discoveredDocs": [],
      "jiraStats": {
        "total": 0,
        "done": 0,
        "inProgress": 0
      }
    }
  ]
}
```

### Field Descriptions

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| id | string | Manual | Unique identifier (kebab-case) |
| name | string | Manual | Display name |
| summary | string | Manual | One-paragraph description |
| team | string | Manual | Team key matching `docs/teams.md` |
| leads | string[] | Manual | Email addresses of project leads |
| stage | string | Manual | SDLC stage key |
| slackChannels | string[] | Manual | Project-specific Slack channels |
| jiraEpics | string[] | Manual | Jira epic keys |
| documents | object[] | Manual | Curated document links |
| slackSummary | string | Script | AI-generated 5-day summary |
| discoveredDocs | object[] | Script | Auto-discovered docs from email/Slack |
| jiraStats | object | Script | Ticket counts from Jira API |

## SDLC Stages

| Key | Display Name | Description |
|-----|--------------|-------------|
| discovery | Discovery/Ideation | Early exploration, no Jira yet |
| planning | Planning/Design | Specs, tech design, requirements |
| development | Development | Active coding, has Jira epic(s) |
| testing | Testing/QA | In QA review |
| rollout | Rollout | Deploying, feature flags, monitoring |
| metrics | Metrics/Analytics | Measuring success, analyzing data |
| complete | Complete | Shipped and done |

## Scripts

### Main Orchestrator: `scripts/refresh-projects.py`

Coordinates all data enrichment and writes final `projects/data.json`.

**Process:**
1. Load `projects/data.json`
2. For each project with Jira epics: fetch stats
3. For each project with Slack channels: generate 5-day summary
4. For each project: search for related documents
5. Write updated `projects/data.json`
6. Update `lastUpdated` timestamp

### Jira Enrichment: `scripts/fetch-jira-project-stats.py`

**Input:** Jira epic key(s)
**Output:** Ticket counts (total, done, in progress)
**API:** Jira REST API via existing auth

### Slack Summary: `scripts/fetch-slack-summary.py`

**Input:** Slack channel name
**Output:** AI-generated summary of last 5 days
**API:** Glean chat API with channel context

### Document Discovery: `scripts/fetch-project-docs.py`

**Input:** Project name, keywords
**Output:** List of discovered document links
**API:** Glean search across email and Slack

## Refresh Schedule

**Daily:** GitHub Action runs `scripts/refresh-projects.sh` each morning.

**Manual:** Run `./scripts/refresh-projects.sh` locally for immediate refresh.

### GitHub Action: `.github/workflows/refresh-projects.yml`

```yaml
name: Refresh Projects
on:
  schedule:
    - cron: '0 10 * * *'  # 10 AM UTC daily
  workflow_dispatch:  # Manual trigger
```

## UI Components

### Stage Badge Colors

| Stage | Background | Text |
|-------|------------|------|
| discovery | #e3f2fd | #1565c0 |
| planning | #fff3e0 | #e65100 |
| development | #e8f5e9 | #2e7d32 |
| testing | #f3e5f5 | #7b1fa2 |
| rollout | #fce4ec | #c2185b |
| metrics | #e0f2f1 | #00695c |
| complete | #eceff1 | #546e7a |

### Document Type Icons

| Type | Icon |
|------|------|
| confluence | 📄 |
| gdoc | 📝 |
| figma | 🎨 |
| looker | 📊 |
| slack | 💬 |
| jira | 🎫 |
| other | 🔗 |

## Navigation

Add "Projects" link to existing nav in `index.html` and `scorecard.html`:

```html
<div class="nav-links">
    <a href="index.html">Directory</a>
    <a href="scorecard.html">Scorecard</a>
    <a href="projects.html" class="active">Projects</a>
</div>
```

## Manual Project Management

To add a new project, edit `projects/data.json` directly:

1. Add new object to `projects` array
2. Fill in manual fields (id, name, summary, team, leads, stage)
3. Optionally add slackChannels, jiraEpics, documents
4. Run `./scripts/refresh-projects.sh` to enrich with Jira/Slack data

To update SDLC stage: edit the `stage` field in `projects/data.json`.

## Dependencies

- Existing Jira API access (used by scorecard)
- Glean MCP server (for Slack summary and document discovery)
- GitHub Actions (for scheduled refresh)
