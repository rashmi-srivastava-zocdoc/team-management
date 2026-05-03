# Team Hub & People Insights - Phase 1: Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure EM-Dashboard into team-hub (public) and people-insights (private) directories.

**Architecture:** Rename team-management → team-hub. Create people-insights and migrate TeamMetrics + people-management into it. Preserve git history where possible.

**Tech Stack:** Bash, Git, Python

---

## File Structure

After this phase:

```
EM-Dashboard/
├── people-insights/
│   ├── config/
│   │   └── teams.yaml
│   ├── data/
│   │   ├── sprints.json
│   │   ├── slack.json
│   │   └── individuals/
│   │       ├── gap-analysis/
│   │       └── activity-reports/
│   ├── frontend/          (from TeamMetrics)
│   ├── backend/           (from TeamMetrics)
│   └── scripts/
│       └── .gitkeep
│
├── team-hub/              (renamed from team-management)
│   ├── data/
│   │   ├── teams.json
│   │   ├── sprints.json
│   │   └── projects.json
│   ├── index.html
│   ├── scorecard.html
│   └── projects.html
│
└── docs/
    └── superpowers/
        └── specs/
```

---

### Task 1: Create people-insights Directory Structure

**Files:**
- Create: `people-insights/config/`
- Create: `people-insights/data/individuals/gap-analysis/`
- Create: `people-insights/data/individuals/activity-reports/`
- Create: `people-insights/scripts/`

- [ ] **Step 1: Create the directory structure**

```bash
cd ~/Desktop/Github/EM-Dashboard
mkdir -p people-insights/config
mkdir -p people-insights/data/individuals/gap-analysis
mkdir -p people-insights/data/individuals/activity-reports
mkdir -p people-insights/scripts
```

- [ ] **Step 2: Add .gitkeep files to preserve empty directories**

```bash
touch people-insights/scripts/.gitkeep
touch people-insights/data/individuals/gap-analysis/.gitkeep
touch people-insights/data/individuals/activity-reports/.gitkeep
```

- [ ] **Step 3: Verify structure**

```bash
find people-insights -type d
```

Expected:
```
people-insights
people-insights/config
people-insights/data
people-insights/data/individuals
people-insights/data/individuals/gap-analysis
people-insights/data/individuals/activity-reports
people-insights/scripts
```

---

### Task 2: Move TeamMetrics Frontend to people-insights

**Files:**
- Move: `TeamMetrics/src/` → `people-insights/frontend/src/`
- Move: `TeamMetrics/index.html` → `people-insights/frontend/index.html`
- Move: `TeamMetrics/package.json` → `people-insights/frontend/package.json`
- Move: `TeamMetrics/vite.config.js` → `people-insights/frontend/vite.config.js`

- [ ] **Step 1: Create frontend directory and move files**

```bash
cd ~/Desktop/Github/EM-Dashboard
mkdir -p people-insights/frontend
cp -r TeamMetrics/src people-insights/frontend/
cp TeamMetrics/index.html people-insights/frontend/
cp TeamMetrics/package.json people-insights/frontend/
cp TeamMetrics/package-lock.json people-insights/frontend/
cp TeamMetrics/vite.config.js people-insights/frontend/
cp TeamMetrics/.gitignore people-insights/frontend/
```

- [ ] **Step 2: Verify frontend files exist**

```bash
ls -la people-insights/frontend/
```

Expected: `src/`, `index.html`, `package.json`, `vite.config.js`

---

### Task 3: Move TeamMetrics Backend to people-insights

**Files:**
- Move: `TeamMetrics/backend/src/` → `people-insights/backend/src/`
- Move: `TeamMetrics/backend/tests/` → `people-insights/backend/tests/`
- Move: `TeamMetrics/backend/pyproject.toml` → `people-insights/backend/pyproject.toml`

- [ ] **Step 1: Create backend directory and move files**

```bash
cd ~/Desktop/Github/EM-Dashboard
mkdir -p people-insights/backend
cp -r TeamMetrics/backend/src people-insights/backend/
cp -r TeamMetrics/backend/tests people-insights/backend/
cp TeamMetrics/backend/pyproject.toml people-insights/backend/ 2>/dev/null || echo "No pyproject.toml"
cp TeamMetrics/backend/.env.example people-insights/backend/ 2>/dev/null || echo "No .env.example"
cp TeamMetrics/backend/.env people-insights/backend/ 2>/dev/null || echo "No .env (expected)"
```

- [ ] **Step 2: Move config to people-insights/config**

```bash
cp TeamMetrics/backend/config/teams.yaml people-insights/config/
```

- [ ] **Step 3: Move data files**

```bash
cp TeamMetrics/backend/data/*.json people-insights/data/ 2>/dev/null || echo "No JSON files"
```

- [ ] **Step 4: Verify backend structure**

```bash
ls -la people-insights/backend/
ls -la people-insights/config/
ls -la people-insights/data/
```

Expected: `src/`, `tests/`, and config/data files

---

### Task 4: Move people-management Content to people-insights

**Files:**
- Move: `people-management/reports/` → `people-insights/data/individuals/reports/`
- Move: `people-management/*.md` → `people-insights/data/individuals/activity-reports/`

- [ ] **Step 1: Move reports**

```bash
cd ~/Desktop/Github/EM-Dashboard
cp -r people-management/reports/* people-insights/data/individuals/gap-analysis/ 2>/dev/null || echo "No reports"
```

- [ ] **Step 2: Move activity reports**

```bash
cp people-management/*.md people-insights/data/individuals/activity-reports/ 2>/dev/null || echo "No activity reports"
```

- [ ] **Step 3: Verify individual data**

```bash
ls -la people-insights/data/individuals/gap-analysis/
ls -la people-insights/data/individuals/activity-reports/
```

---

### Task 5: Rename team-management to team-hub

**Files:**
- Rename: `team-management/` → `team-hub/`

- [ ] **Step 1: Rename directory**

```bash
cd ~/Desktop/Github/EM-Dashboard
mv team-management team-hub
```

- [ ] **Step 2: Verify rename**

```bash
ls -la
```

Expected: `people-insights/`, `team-hub/`, no `team-management/`

- [ ] **Step 3: Update any internal references in team-hub**

Check for hardcoded paths in HTML files:

```bash
grep -r "team-management" team-hub/*.html 2>/dev/null || echo "No references found"
```

---

### Task 6: Create team-hub/data Directory for Aggregated Data

**Files:**
- Create: `team-hub/data/teams.json`
- Create: `team-hub/data/sprints.json`

- [ ] **Step 1: Create data directory if not exists**

```bash
cd ~/Desktop/Github/EM-Dashboard
mkdir -p team-hub/data
```

- [ ] **Step 2: Create initial teams.json from teams.md**

```bash
cat > team-hub/data/teams.json << 'EOF'
{
  "lastUpdated": "2026-05-03T00:00:00Z",
  "teams": [
    {
      "id": "peacock",
      "name": "Peacock (Provider Onboarding)",
      "jiraProject": "PROVGRO",
      "memberCount": 9
    },
    {
      "id": "pterodactyl",
      "name": "Pterodactyl (Account & User Setup)",
      "jiraProject": "PTERODACTL",
      "memberCount": 7
    },
    {
      "id": "billing",
      "name": "Billing",
      "jiraProject": "BILL",
      "memberCount": 9
    }
  ]
}
EOF
```

- [ ] **Step 3: Create initial sprints.json placeholder**

```bash
cat > team-hub/data/sprints.json << 'EOF'
{
  "lastUpdated": "2026-05-03T00:00:00Z",
  "sprints": {}
}
EOF
```

- [ ] **Step 4: Verify data files**

```bash
ls -la team-hub/data/
cat team-hub/data/teams.json | python3 -c "import json,sys; json.load(sys.stdin); print('Valid JSON')"
```

---

### Task 7: Initialize people-insights as Local Git Repo

**Files:**
- Create: `people-insights/.git`
- Create: `people-insights/.gitignore`

- [ ] **Step 1: Create .gitignore**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
cat > .gitignore << 'EOF'
# Dependencies
frontend/node_modules/
backend/.venv/
__pycache__/
*.pyc

# Environment
.env
*.env.local

# IDE
.idea/
.vscode/

# Build
frontend/dist/
*.egg-info/

# Cache
.pytest_cache/
.mypy_cache/
EOF
```

- [ ] **Step 2: Initialize git repo**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights
git init
git add .
git commit -m "Initial commit: migrate TeamMetrics + people-management

Private repository for individual metrics and analysis.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 8: Commit team-hub Changes

**Files:**
- Commit: `team-hub/data/*`

- [ ] **Step 1: Check git status**

```bash
cd ~/Desktop/Github/EM-Dashboard/team-hub
git status
```

- [ ] **Step 2: Add and commit new data files**

```bash
git add data/teams.json data/sprints.json docs/superpowers/
git commit -m "feat: add team data structure for public metrics

Prepares team-hub for aggregated sprint/PR data.
Renamed from team-management.

Generated with AI

Co-Authored-By: Claude Code"
```

---

### Task 9: Verify Final Structure

- [ ] **Step 1: List EM-Dashboard contents**

```bash
cd ~/Desktop/Github/EM-Dashboard
ls -la
```

Expected:
```
people-insights/
team-hub/
TeamMetrics/     (original, can be deleted after verification)
people-management/  (original, can be deleted after verification)
docs/
```

- [ ] **Step 2: Verify people-insights structure**

```bash
find people-insights -type d | grep -v node_modules | grep -v __pycache__ | grep -v .git
```

- [ ] **Step 3: Verify team-hub structure**

```bash
ls -la team-hub/
ls -la team-hub/data/
```

- [ ] **Step 4: Test frontend still works**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights/frontend
npm install
npm run dev &
sleep 3
curl -s http://localhost:3000 > /dev/null && echo "Frontend OK" || echo "Frontend FAIL"
```

- [ ] **Step 5: Test backend still works**

```bash
cd ~/Desktop/Github/EM-Dashboard/people-insights/backend
PYTHONPATH=src uvicorn team_metrics.main:app --port 8001 &
sleep 3
curl -s http://localhost:8001/health && echo "" || echo "Backend FAIL"
```

---

### Task 10: Clean Up Original Directories (Optional)

Only after verifying everything works:

- [ ] **Step 1: Archive originals (safe approach)**

```bash
cd ~/Desktop/Github/EM-Dashboard
mkdir -p .archive
mv TeamMetrics .archive/TeamMetrics-backup
mv people-management .archive/people-management-backup
```

Or delete if confident:

```bash
# rm -rf TeamMetrics people-management
```

---

## Summary

After Phase 1:
- ✅ `people-insights/` contains all private data and the React/FastAPI app
- ✅ `team-hub/` is the public-facing site with aggregated data
- ✅ Both have proper git repos
- ✅ Original code preserved in `.archive/` for safety

**Next:** Phase 2 - Create data collection scripts (refresh.py, publish-to-hub.py, backfill.py)
