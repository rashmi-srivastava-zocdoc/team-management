# Project Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a project tracking page that consolidates documents, links, Slack summaries, and SDLC status for ~20 projects across teams.

**Architecture:** Static HTML page (`projects.html`) loads JSON data (`projects/data.json`). Python scripts enrich data from Jira and Glean. Daily GitHub Action keeps data fresh.

**Tech Stack:** HTML/CSS/JavaScript (matching existing pages), Python 3 for scripts, Jira REST API, Glean MCP.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `projects/data.json` | Project data (manual + enriched) |
| `projects.html` | Table view with expandable rows |
| `scripts/fetch-jira-project-stats.py` | Fetch epic ticket counts from Jira |
| `scripts/fetch-slack-summary.py` | Generate 5-day summary via Glean |
| `scripts/fetch-project-docs.py` | Discover docs from email/Slack via Glean |
| `scripts/refresh-projects.py` | Main orchestrator that calls other scripts |
| `scripts/refresh-projects.sh` | Shell wrapper for local/CI use |
| `.github/workflows/refresh-projects.yml` | Daily scheduled refresh |

---

### Task 1: Create Initial Data File

**Files:**
- Create: `projects/data.json`

- [ ] **Step 1: Create projects directory**

```bash
mkdir -p projects
```

- [ ] **Step 2: Create data.json with sample projects**

Create `projects/data.json`:

```json
{
  "lastUpdated": "2026-04-30T10:00:00Z",
  "projects": [
    {
      "id": "provider-self-service",
      "name": "Provider Self-Service Onboarding",
      "summary": "Enable providers to complete onboarding steps without CSM assistance",
      "team": "provider-onboarding",
      "leads": ["alexander.gorowara@zocdoc.com"],
      "stage": "development",
      "slackChannels": [],
      "jiraEpics": [],
      "documents": [],
      "slackSummary": "",
      "discoveredDocs": [],
      "jiraStats": {
        "total": 0,
        "done": 0,
        "inProgress": 0
      }
    },
    {
      "id": "role-bundles-v2",
      "name": "Role Bundles v2",
      "summary": "Redesigned role bundle system with improved UX and granular permissions",
      "team": "account-user-setup",
      "leads": ["mayank.choudhary@zocdoc.com"],
      "stage": "planning",
      "slackChannels": [],
      "jiraEpics": [],
      "documents": [],
      "slackSummary": "",
      "discoveredDocs": [],
      "jiraStats": {
        "total": 0,
        "done": 0,
        "inProgress": 0
      }
    },
    {
      "id": "billing-portal-redesign",
      "name": "Billing Portal Redesign",
      "summary": "Modernize the billing portal with improved invoice management",
      "team": "billing",
      "leads": ["dave.ramirez@zocdoc.com"],
      "stage": "discovery",
      "slackChannels": [],
      "jiraEpics": [],
      "documents": [],
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

- [ ] **Step 3: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open('projects/data.json')); print('Valid JSON')"
```

Expected: `Valid JSON`

- [ ] **Step 4: Commit**

```bash
git add projects/data.json
git commit -m "feat: add initial projects data structure

Sample projects for Provider Onboarding, Pterodactyl, and Billing teams.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 2: Create Projects Page HTML Structure

**Files:**
- Create: `projects.html`

- [ ] **Step 1: Create projects.html with header and filters**

Create `projects.html` with the header matching existing pages, team dropdown, and stage filter:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Tracker</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #ffffff;
            color: #172b4d;
            line-height: 1.6;
        }
        .header {
            background: #ffffff;
            border-bottom: 1px solid #dfe1e6;
            padding: 1rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .logo {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 600;
            font-size: 1.25rem;
            color: #172b4d;
            text-decoration: none;
        }
        .logo-icon {
            width: 32px;
            height: 32px;
            background: #FFE14D;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #172b4d;
        }
        .nav-links {
            display: flex;
            gap: 1rem;
        }
        .nav-links a {
            color: #5e6c84;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            transition: all 0.2s;
        }
        .nav-links a:hover {
            background: #f4f5f7;
            color: #172b4d;
        }
        .nav-links a.active {
            background: #FFE14D;
            color: #172b4d;
        }
        .header-right {
            display: flex;
            align-items: center;
            gap: 2rem;
        }
        .filters {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        .filters label {
            font-weight: 500;
            color: #5e6c84;
            font-size: 0.875rem;
        }
        .filter-dropdown {
            padding: 0.5rem 2rem 0.5rem 0.75rem;
            font-size: 0.9rem;
            border: 1px solid #dfe1e6;
            border-radius: 6px;
            background: #ffffff;
            color: #172b4d;
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23666' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 0.75rem center;
            min-width: 160px;
        }
        .filter-dropdown:hover {
            border-color: #0065ff;
        }
        .filter-dropdown:focus {
            outline: none;
            border-color: #0065ff;
            box-shadow: 0 0 0 2px rgba(0, 101, 255, 0.2);
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        .page-title {
            font-size: 1.75rem;
            font-weight: 500;
            color: #172b4d;
            margin-bottom: 0.5rem;
        }
        .page-meta {
            color: #5e6c84;
            font-size: 0.875rem;
            margin-bottom: 1.5rem;
        }
    </style>
</head>
<body>
    <header class="header">
        <a href="index.html" class="logo">
            <div class="logo-icon">T</div>
            Team Hub
        </a>
        <div class="nav-links">
            <a href="index.html">Directory</a>
            <a href="scorecard.html">Scorecard</a>
            <a href="projects.html" class="active">Projects</a>
        </div>
        <div class="header-right">
            <div class="filters">
                <label for="team-filter">Team:</label>
                <select id="team-filter" class="filter-dropdown">
                    <option value="all">All Teams</option>
                    <option value="provider-onboarding">Provider Onboarding</option>
                    <option value="account-user-setup">Account & User Setup</option>
                    <option value="billing">Billing</option>
                </select>
                <label for="stage-filter">Stage:</label>
                <select id="stage-filter" class="filter-dropdown">
                    <option value="all">All Stages</option>
                    <option value="discovery">Discovery</option>
                    <option value="planning">Planning</option>
                    <option value="development">Development</option>
                    <option value="testing">Testing</option>
                    <option value="rollout">Rollout</option>
                    <option value="metrics">Metrics</option>
                    <option value="complete">Complete</option>
                </select>
            </div>
        </div>
    </header>
    <main class="container">
        <h1 class="page-title">Project Tracker</h1>
        <p class="page-meta">Last updated: <span id="last-updated">Loading...</span></p>
        <div id="projects-table"></div>
    </main>
</body>
</html>
```

- [ ] **Step 2: Open in browser to verify header renders**

```bash
open projects.html
```

Expected: Page loads with header, nav links, team dropdown, stage dropdown.

- [ ] **Step 3: Commit**

```bash
git add projects.html
git commit -m "feat: add projects page header and filters

Matches existing page styling with team and SDLC stage filters.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 3: Add Projects Table Styles

**Files:**
- Modify: `projects.html`

- [ ] **Step 1: Add table and row styles to the `<style>` block**

Add these styles before the closing `</style>` tag in `projects.html`:

```css
        /* Table styles */
        .projects-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .projects-table th {
            text-align: left;
            padding: 1rem;
            background: #f4f5f7;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            color: #5e6c84;
            border-bottom: 2px solid #dfe1e6;
        }
        .projects-table td {
            padding: 1rem;
            border-bottom: 1px solid #ebecf0;
            vertical-align: top;
        }
        .projects-table tr:hover {
            background: #f8f9fa;
        }
        .projects-table tr.expanded {
            background: #fffde7;
        }
        .project-name {
            font-weight: 600;
            color: #172b4d;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .project-name:hover {
            color: #0065ff;
        }
        .expand-icon {
            font-size: 0.75rem;
            transition: transform 0.2s;
        }
        .expanded .expand-icon {
            transform: rotate(90deg);
        }
        .stage-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        .stage-discovery { background: #e3f2fd; color: #1565c0; }
        .stage-planning { background: #fff3e0; color: #e65100; }
        .stage-development { background: #e8f5e9; color: #2e7d32; }
        .stage-testing { background: #f3e5f5; color: #7b1fa2; }
        .stage-rollout { background: #fce4ec; color: #c2185b; }
        .stage-metrics { background: #e0f2f1; color: #00695c; }
        .stage-complete { background: #eceff1; color: #546e7a; }
        .jira-link {
            color: #0065ff;
            text-decoration: none;
        }
        .jira-link:hover {
            text-decoration: underline;
        }
        .no-jira {
            color: #97a0af;
        }
```

- [ ] **Step 2: Verify styles compile (open page)**

```bash
open projects.html
```

Expected: Page still loads without errors.

- [ ] **Step 3: Commit**

```bash
git add projects.html
git commit -m "feat: add projects table styles

Stage badge colors, hover states, and expanded row styling.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 4: Add Expanded Row Detail Styles

**Files:**
- Modify: `projects.html`

- [ ] **Step 1: Add expanded detail styles to the `<style>` block**

Add these styles before the closing `</style>` tag:

```css
        /* Expanded row detail */
        .project-detail {
            display: none;
            background: #fafbfc;
            border-bottom: 2px solid #FFE14D;
        }
        .project-detail.visible {
            display: table-row;
        }
        .project-detail td {
            padding: 1.5rem;
        }
        .detail-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }
        .detail-section {
            margin-bottom: 1rem;
        }
        .detail-section:last-child {
            margin-bottom: 0;
        }
        .detail-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            color: #5e6c84;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .detail-text {
            font-size: 0.9rem;
            color: #172b4d;
        }
        .slack-summary {
            background: #f4f5f7;
            padding: 0.75rem 1rem;
            border-radius: 6px;
            font-style: italic;
            font-size: 0.875rem;
            color: #42526e;
        }
        .slack-summary.empty {
            color: #97a0af;
            font-style: normal;
        }
        .doc-list {
            list-style: none;
        }
        .doc-list li {
            margin-bottom: 0.5rem;
        }
        .doc-list a {
            color: #0065ff;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .doc-list a:hover {
            text-decoration: underline;
        }
        .doc-icon {
            font-size: 1rem;
        }
        .link-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        .link-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.25rem 0.75rem;
            background: #e3f2fd;
            border-radius: 12px;
            font-size: 0.8rem;
            color: #0065ff;
            text-decoration: none;
        }
        .link-chip:hover {
            background: #bbdefb;
        }
        .link-chip.slack {
            background: #e8f5e9;
            color: #2e7d32;
        }
        .link-chip.jira {
            background: #e3f2fd;
            color: #0065ff;
        }
        .jira-progress {
            font-size: 0.75rem;
            color: #5e6c84;
            margin-left: 0.25rem;
        }
```

- [ ] **Step 2: Verify styles compile (open page)**

```bash
open projects.html
```

Expected: Page still loads without errors.

- [ ] **Step 3: Commit**

```bash
git add projects.html
git commit -m "feat: add expanded row detail styles

Two-column layout for summary, Slack digest, documents, and links.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 5: Add JavaScript Data Loading and Table Rendering

**Files:**
- Modify: `projects.html`

- [ ] **Step 1: Add JavaScript before closing `</body>` tag**

Add this script block before `</body>`:

```html
    <script>
        const TEAM_NAMES = {
            'provider-onboarding': 'Provider Onboarding',
            'account-user-setup': 'Account & User Setup',
            'billing': 'Billing'
        };

        const STAGE_NAMES = {
            'discovery': 'Discovery',
            'planning': 'Planning',
            'development': 'Development',
            'testing': 'Testing',
            'rollout': 'Rollout',
            'metrics': 'Metrics',
            'complete': 'Complete'
        };

        const DOC_ICONS = {
            'confluence': '📄',
            'gdoc': '📝',
            'figma': '🎨',
            'looker': '📊',
            'slack': '💬',
            'jira': '🎫',
            'other': '🔗'
        };

        let projectsData = null;

        async function loadProjects() {
            try {
                const response = await fetch('projects/data.json');
                projectsData = await response.json();
                document.getElementById('last-updated').textContent = 
                    new Date(projectsData.lastUpdated).toLocaleString();
                renderTable(projectsData.projects);
            } catch (error) {
                console.error('Failed to load projects:', error);
                document.getElementById('projects-table').innerHTML = 
                    '<p style="color: #de350b;">Failed to load projects data.</p>';
            }
        }

        function getLeadName(email) {
            if (!email) return '—';
            const name = email.split('@')[0].split('.').map(
                part => part.charAt(0).toUpperCase() + part.slice(1)
            ).join(' ');
            return name;
        }

        function renderTable(projects) {
            const teamFilter = document.getElementById('team-filter').value;
            const stageFilter = document.getElementById('stage-filter').value;

            const filtered = projects.filter(p => {
                if (teamFilter !== 'all' && p.team !== teamFilter) return false;
                if (stageFilter !== 'all' && p.stage !== stageFilter) return false;
                return true;
            });

            if (filtered.length === 0) {
                document.getElementById('projects-table').innerHTML = 
                    '<p style="color: #5e6c84; padding: 2rem;">No projects match the selected filters.</p>';
                return;
            }

            let html = `
                <table class="projects-table">
                    <thead>
                        <tr>
                            <th>Project</th>
                            <th>Team</th>
                            <th>Lead(s)</th>
                            <th>Stage</th>
                            <th>Jira</th>
                            <th>Updated</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            filtered.forEach(project => {
                const leadNames = (project.leads || []).map(getLeadName).join(', ') || '—';
                const jiraLinks = (project.jiraEpics || []).map(key => 
                    `<a href="https://zocdoc.atlassian.net/browse/${key}" class="jira-link" target="_blank">${key}</a>`
                ).join(', ') || '<span class="no-jira">—</span>';

                html += `
                    <tr class="project-row" data-id="${project.id}">
                        <td>
                            <div class="project-name" onclick="toggleDetail('${project.id}')">
                                <span class="expand-icon">▶</span>
                                ${project.name}
                            </div>
                        </td>
                        <td>${TEAM_NAMES[project.team] || project.team}</td>
                        <td>${leadNames}</td>
                        <td><span class="stage-badge stage-${project.stage}">${STAGE_NAMES[project.stage] || project.stage}</span></td>
                        <td>${jiraLinks}</td>
                        <td>${new Date(projectsData.lastUpdated).toLocaleDateString()}</td>
                    </tr>
                    <tr class="project-detail" data-detail-id="${project.id}">
                        <td colspan="6">
                            ${renderDetail(project)}
                        </td>
                    </tr>
                `;
            });

            html += '</tbody></table>';
            document.getElementById('projects-table').innerHTML = html;
        }

        function renderDetail(project) {
            const docs = [...(project.documents || []), ...(project.discoveredDocs || [])];
            const docListHtml = docs.length > 0 
                ? `<ul class="doc-list">${docs.map(doc => `
                    <li>
                        <a href="${doc.url}" target="_blank">
                            <span class="doc-icon">${DOC_ICONS[doc.type] || DOC_ICONS.other}</span>
                            ${doc.name}
                        </a>
                    </li>
                `).join('')}</ul>`
                : '<p style="color: #97a0af; font-size: 0.875rem;">No documents linked yet</p>';

            const slackChannels = (project.slackChannels || []).map(ch => 
                `<a href="https://zocdoc.slack.com/channels/${ch.replace('#', '')}" class="link-chip slack" target="_blank">💬 ${ch}</a>`
            ).join('');

            const jiraChips = (project.jiraEpics || []).map(key => {
                const stats = project.jiraStats || {};
                const progress = stats.total > 0 ? `<span class="jira-progress">(${stats.done}/${stats.total})</span>` : '';
                return `<a href="https://zocdoc.atlassian.net/browse/${key}" class="link-chip jira" target="_blank">🎫 ${key}${progress}</a>`;
            }).join('');

            const slackSummary = project.slackSummary 
                ? `<div class="slack-summary">"${project.slackSummary}"</div>`
                : '<div class="slack-summary empty">No recent Slack activity</div>';

            return `
                <div class="detail-content">
                    <div class="detail-left">
                        <div class="detail-section">
                            <div class="detail-label">Summary</div>
                            <div class="detail-text">${project.summary || 'No summary provided'}</div>
                        </div>
                        <div class="detail-section">
                            <div class="detail-label">Slack (5-day summary)</div>
                            ${slackSummary}
                        </div>
                    </div>
                    <div class="detail-right">
                        <div class="detail-section">
                            <div class="detail-label">Documents</div>
                            ${docListHtml}
                        </div>
                        <div class="detail-section">
                            <div class="detail-label">Links</div>
                            <div class="link-list">
                                ${slackChannels}
                                ${jiraChips}
                                ${!slackChannels && !jiraChips ? '<span style="color: #97a0af; font-size: 0.875rem;">No links yet</span>' : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        function toggleDetail(projectId) {
            const row = document.querySelector(`tr[data-id="${projectId}"]`);
            const detail = document.querySelector(`tr[data-detail-id="${projectId}"]`);
            
            row.classList.toggle('expanded');
            detail.classList.toggle('visible');
        }

        // Filter handlers
        document.getElementById('team-filter').addEventListener('change', () => {
            if (projectsData) renderTable(projectsData.projects);
        });
        document.getElementById('stage-filter').addEventListener('change', () => {
            if (projectsData) renderTable(projectsData.projects);
        });

        // Load on page ready
        loadProjects();
    </script>
```

- [ ] **Step 2: Test page loads and displays projects**

```bash
open projects.html
```

Expected: Table shows 3 sample projects with stage badges. Clicking a project name expands the detail row.

- [ ] **Step 3: Test filters work**

Change team dropdown to "Provider Onboarding" — should show only that project.
Change stage dropdown to "Planning" — should show only Role Bundles project.

- [ ] **Step 4: Commit**

```bash
git add projects.html
git commit -m "feat: add projects table rendering with expandable details

Loads JSON data, renders table with filters, expands rows on click.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 6: Update Navigation in Existing Pages

**Files:**
- Modify: `index.html`
- Modify: `scorecard.html`

- [ ] **Step 1: Update nav-links in index.html**

Find the `.nav-links` div in `index.html` and update to include Projects:

```html
        <div class="nav-links">
            <a href="index.html" class="active">Directory</a>
            <a href="scorecard.html">Scorecard</a>
            <a href="projects.html">Projects</a>
        </div>
```

- [ ] **Step 2: Update nav-links in scorecard.html**

Find the `.nav-links` div in `scorecard.html` and update to include Projects:

```html
        <div class="nav-links">
            <a href="index.html">Directory</a>
            <a href="scorecard.html" class="active">Scorecard</a>
            <a href="projects.html">Projects</a>
        </div>
```

- [ ] **Step 3: Test navigation works**

```bash
open index.html
```

Click "Projects" link — should navigate to projects.html.
Click "Directory" link — should navigate back.

- [ ] **Step 4: Commit**

```bash
git add index.html scorecard.html
git commit -m "feat: add Projects link to navigation

Accessible from Directory and Scorecard pages.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 7: Create Jira Stats Fetcher Script

**Files:**
- Create: `scripts/fetch-jira-project-stats.py`

- [ ] **Step 1: Create the script**

Create `scripts/fetch-jira-project-stats.py`:

```python
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/fetch-jira-project-stats.py
```

- [ ] **Step 3: Test with a known epic (if credentials available)**

```bash
python3 scripts/fetch-jira-project-stats.py PROVGRO-6335
```

Expected: JSON output with ticket counts, or error message if no credentials.

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch-jira-project-stats.py
git commit -m "feat: add Jira epic stats fetcher

Fetches ticket counts (total, done, in progress) for epic keys.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 8: Create Slack Summary Fetcher Script

**Files:**
- Create: `scripts/fetch-slack-summary.py`

- [ ] **Step 1: Create the script**

Create `scripts/fetch-slack-summary.py`:

```python
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/fetch-slack-summary.py
```

- [ ] **Step 3: Test it outputs a prompt**

```bash
python3 scripts/fetch-slack-summary.py "#proj-test" "Test Project"
```

Expected: Outputs a Glean prompt for summarizing the channel.

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch-slack-summary.py
git commit -m "feat: add Slack summary prompt generator

Generates Glean prompt for 5-day channel summary.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 9: Create Document Discovery Script

**Files:**
- Create: `scripts/fetch-project-docs.py`

- [ ] **Step 1: Create the script**

Create `scripts/fetch-project-docs.py`:

```python
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/fetch-project-docs.py
```

- [ ] **Step 3: Test it outputs search config**

```bash
python3 scripts/fetch-project-docs.py "Provider Self-Service" onboarding
```

Expected: JSON search configuration for Glean.

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch-project-docs.py
git commit -m "feat: add document discovery search config generator

Generates Glean search parameters for finding project docs.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 10: Create Main Refresh Orchestrator

**Files:**
- Create: `scripts/refresh-projects.py`

- [ ] **Step 1: Create the script**

Create `scripts/refresh-projects.py`:

```python
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/refresh-projects.py
```

- [ ] **Step 3: Test it runs without errors**

```bash
python3 scripts/refresh-projects.py --skip-jira --skip-glean
```

Expected: Loads data, updates timestamp, saves file.

- [ ] **Step 4: Commit**

```bash
git add scripts/refresh-projects.py
git commit -m "feat: add project data refresh orchestrator

Coordinates Jira stats fetch and updates timestamp.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 11: Create Shell Wrapper Script

**Files:**
- Create: `scripts/refresh-projects.sh`

- [ ] **Step 1: Create the script**

Create `scripts/refresh-projects.sh`:

```bash
#!/bin/bash
# Refresh all project data locally
# Usage: ./scripts/refresh-projects.sh [--skip-jira] [--skip-glean]

set -e
cd "$(dirname "$0")/.."

echo "========================================"
echo "  REFRESH PROJECTS DATA"
echo "========================================"

python3 scripts/refresh-projects.py "$@"

echo ""
echo "View locally: open projects.html"
echo "After push:   https://rashmi-srivastava-zocdoc.github.io/team-management/projects.html"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/refresh-projects.sh
```

- [ ] **Step 3: Test it runs**

```bash
./scripts/refresh-projects.sh --skip-jira
```

Expected: Runs refresh-projects.py and shows output.

- [ ] **Step 4: Commit**

```bash
git add scripts/refresh-projects.sh
git commit -m "feat: add refresh-projects shell wrapper

Convenience script for local and CI use.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 12: Create GitHub Action for Daily Refresh

**Files:**
- Create: `.github/workflows/refresh-projects.yml`

- [ ] **Step 1: Create the workflow file**

Create `.github/workflows/refresh-projects.yml`:

```yaml
name: Refresh Projects Data

on:
  schedule:
    # Run daily at 10am UTC (6am ET)
    - cron: '0 10 * * *'
  workflow_dispatch:
    # Manual trigger
    inputs:
      skip_jira:
        description: 'Skip Jira stats fetch'
        required: false
        default: 'false'
        type: boolean

permissions:
  contents: write

jobs:
  refresh-projects:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Refresh project data
        env:
          JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
        run: |
          ARGS=""
          if [[ "${{ github.event.inputs.skip_jira }}" == "true" ]] || [[ -z "$JIRA_EMAIL" ]]; then
            ARGS="--skip-jira"
          fi
          python3 scripts/refresh-projects.py $ARGS --skip-glean

      - name: Check for changes
        id: changes
        run: |
          if git diff --quiet projects/data.json; then
            echo "changed=false" >> $GITHUB_OUTPUT
          else
            echo "changed=true" >> $GITHUB_OUTPUT
          fi

      - name: Commit and push changes
        if: steps.changes.outputs.changed == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add projects/data.json
          git commit -m "chore: refresh projects data

          Generated with AI

          Co-Authored-By: Claude Code"
          git push

      - name: Summary
        run: |
          echo "## Projects Data Refresh" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          if [[ "${{ steps.changes.outputs.changed }}" == "true" ]]; then
            echo "✅ Projects data updated and committed" >> $GITHUB_STEP_SUMMARY
          else
            echo "ℹ️ No changes to projects data" >> $GITHUB_STEP_SUMMARY
          fi
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "View: https://rashmi-srivastava-zocdoc.github.io/team-management/projects.html" >> $GITHUB_STEP_SUMMARY
```

- [ ] **Step 2: Verify YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/refresh-projects.yml')); print('Valid YAML')"
```

Expected: `Valid YAML` (or install pyyaml if needed: `pip install pyyaml`)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/refresh-projects.yml
git commit -m "feat: add daily projects refresh GitHub Action

Runs at 10am UTC, fetches Jira stats, commits changes.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 13: Add Sample Data with Real Project Details

**Files:**
- Modify: `projects/data.json`

- [ ] **Step 1: Update data.json with more realistic sample data**

Update `projects/data.json` with richer sample data:

```json
{
  "lastUpdated": "2026-04-30T10:00:00Z",
  "projects": [
    {
      "id": "provider-self-service",
      "name": "Provider Self-Service Onboarding",
      "summary": "Enable providers to complete onboarding steps without CSM assistance, including credential verification, NPI validation, and scheduling configuration.",
      "team": "provider-onboarding",
      "leads": ["alexander.gorowara@zocdoc.com"],
      "stage": "development",
      "slackChannels": [],
      "jiraEpics": [],
      "documents": [
        {
          "name": "Tech Spec",
          "url": "https://zocdoc.atlassian.net/wiki/spaces/TECH/pages/123456/Provider+Self-Service+Tech+Spec",
          "type": "confluence"
        }
      ],
      "slackSummary": "",
      "discoveredDocs": [],
      "jiraStats": {
        "total": 0,
        "done": 0,
        "inProgress": 0
      }
    },
    {
      "id": "role-bundles-v2",
      "name": "Role Bundles v2",
      "summary": "Redesigned role bundle system with improved UX, granular permissions, and better admin controls for practice user management.",
      "team": "account-user-setup",
      "leads": ["mayank.choudhary@zocdoc.com"],
      "stage": "planning",
      "slackChannels": [],
      "jiraEpics": [],
      "documents": [
        {
          "name": "PRD",
          "url": "https://docs.google.com/document/d/abc123/edit",
          "type": "gdoc"
        },
        {
          "name": "Designs",
          "url": "https://figma.com/file/xyz789",
          "type": "figma"
        }
      ],
      "slackSummary": "",
      "discoveredDocs": [],
      "jiraStats": {
        "total": 0,
        "done": 0,
        "inProgress": 0
      }
    },
    {
      "id": "billing-portal-redesign",
      "name": "Billing Portal Redesign",
      "summary": "Modernize the billing portal with improved invoice management, payment history, and self-service billing adjustments.",
      "team": "billing",
      "leads": ["dave.ramirez@zocdoc.com"],
      "stage": "discovery",
      "slackChannels": [],
      "jiraEpics": [],
      "documents": [],
      "slackSummary": "",
      "discoveredDocs": [],
      "jiraStats": {
        "total": 0,
        "done": 0,
        "inProgress": 0
      }
    },
    {
      "id": "provider-grouping-migration",
      "name": "Provider Grouping Migration",
      "summary": "Migrate legacy provider grouping data to the new provider-grouping service architecture.",
      "team": "account-user-setup",
      "leads": ["garon.smith@zocdoc.com"],
      "stage": "testing",
      "slackChannels": [],
      "jiraEpics": [],
      "documents": [
        {
          "name": "Migration Runbook",
          "url": "https://zocdoc.atlassian.net/wiki/spaces/TECH/pages/789012/Migration+Runbook",
          "type": "confluence"
        }
      ],
      "slackSummary": "",
      "discoveredDocs": [],
      "jiraStats": {
        "total": 0,
        "done": 0,
        "inProgress": 0
      }
    },
    {
      "id": "invoice-automation",
      "name": "Invoice Automation",
      "summary": "Automate invoice generation and delivery for recurring billing cycles.",
      "team": "billing",
      "leads": ["niko.prassas@zocdoc.com"],
      "stage": "rollout",
      "slackChannels": [],
      "jiraEpics": [],
      "documents": [
        {
          "name": "Rollout Plan",
          "url": "https://zocdoc.atlassian.net/wiki/spaces/TECH/pages/456789/Invoice+Automation+Rollout",
          "type": "confluence"
        },
        {
          "name": "Metrics Dashboard",
          "url": "https://looker.zocdoc.com/dashboards/billing-automation",
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

- [ ] **Step 2: Verify JSON is valid and page renders**

```bash
python3 -c "import json; json.load(open('projects/data.json')); print('Valid JSON')"
open projects.html
```

Expected: Page shows 5 projects across different stages.

- [ ] **Step 3: Commit**

```bash
git add projects/data.json
git commit -m "feat: add sample projects with realistic data

5 projects across teams showing various SDLC stages.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 14: Final Testing and Push

**Files:**
- No new files

- [ ] **Step 1: Run full refresh script**

```bash
./scripts/refresh-projects.sh --skip-jira
```

Expected: Script completes, updates timestamp in data.json.

- [ ] **Step 2: Test all page functionality**

```bash
open projects.html
```

Test checklist:
- [ ] Page loads with 5 projects
- [ ] Team filter shows only selected team's projects
- [ ] Stage filter shows only selected stage's projects
- [ ] Clicking project name expands detail row
- [ ] Clicking again collapses it
- [ ] Documents section shows linked docs with icons
- [ ] Navigation to Directory and Scorecard works

- [ ] **Step 3: Test navigation from other pages**

```bash
open index.html
```

- [ ] Click "Projects" link — navigates to projects.html
- [ ] Click "Directory" link — navigates back

- [ ] **Step 4: Push all changes**

```bash
git push origin main
```

- [ ] **Step 5: Verify GitHub Pages deployment**

Wait 1-2 minutes, then visit:
https://rashmi-srivastava-zocdoc.github.io/team-management/projects.html

Expected: Projects page loads and functions correctly.

---

## Summary

This plan implements:
1. **Data layer**: `projects/data.json` with manual + enriched fields
2. **UI layer**: `projects.html` with table view, expandable rows, filters
3. **Scripts**: Jira stats fetcher, Slack summary generator, doc discovery, orchestrator
4. **Automation**: GitHub Action for daily refresh
5. **Navigation**: Updated links in existing pages

After completing all tasks, you'll have a functional project tracker that:
- Shows all projects in a filterable table
- Expands to show details, documents, and links
- Can be enriched with Jira stats automatically
- Refreshes daily via GitHub Actions
