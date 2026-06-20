# Greenfield Project Template — Setup Checklist

This folder is a ready-to-use AI layer template for Claude Code projects.
Copy the entire folder into your new project repo and follow the steps below.

> Full methodology reference: `AGENTIC-ENGINEERING-GUIDE.md` in this folder.

---

## Before You Start (One-Time Machine Setup)

These only need to be done once per machine, not per project.

- [ ] Install Claude Code: `npm install -g @anthropic-ai/claude-code`
- [ ] Install the GitHub CLI and authenticate: `gh auth login`
- [ ] Create a GitHub Personal Access Token with `repo` scope
      → GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
- [ ] Install Node.js 18+ if not already present
- [ ] Install Playwright browsers (for `/verify` browser automation):
      `npx playwright install --with-deps chromium`

---

## Per-Project Setup (Repeat for Every New Greenfield Project)

### 1. Copy the Template Into Your New Project

```bash
cp -r "C:\Users\zanri\Documents\claude templates\." your-new-project\
cd your-new-project
```

On Mac/Linux:
```bash
cp -r ~/Documents/claude\ templates/. your-new-project/
cd your-new-project
```

### 2. Initialize Git and Push to GitHub

```bash
git init
git add .gitignore   # commit gitignore first so .mcp.json is never tracked
git commit -m "Initial commit: AI layer template"
gh repo create your-project-name --public --source=. --push
```

### 3. Configure GitHub MCP

```bash
cp .mcp.json.example .mcp.json
```

Open `.mcp.json` and replace `YOUR_GITHUB_PAT_HERE` with your Personal Access Token.
`.mcp.json` is already listed in `.gitignore` — your token will never be committed.

### 4. Customize CLAUDE.md for Your Project

Open `CLAUDE.md` and fill in every `{placeholder}`. At minimum update:
- Project name and one-line description
- Your actual tech stack
- Your actual dev / build / test / lint commands
- Your project's directory structure

> Tip: Once you've scaffolded the project (e.g., run `npx create-next-app`), start a
> Claude Code session and run `/create-rules`. It will analyze your actual files and
> generate a tailored CLAUDE.md. Merge the good parts in.

### 5. Seed the Memory System

The `memory/` directory ships with placeholder files. Populate them as you start
your project — or let Claude Code fill them in during the first session.

At minimum, update `memory/references.md` with your GitHub repo URL so the agent
always knows where to find issues:

```
- "GitHub repo: github.com/owner/repo — primary issue tracker"
```

### 6. Open Claude Code and Verify MCP

```bash
claude
```

Ask: `Can you list my GitHub Issues for [owner/repo]?`
If it works, MCP is wired up correctly.

To verify Playwright is working:
```
/verify http://example.com
```

### 7. Begin the Methodology

You are ready. Follow the workflow in Section 12 of `AGENTIC-ENGINEERING-GUIDE.md`:

```
/create-prd              ← brain dump → PRD saved to .agents/PRDs/
/create-issues           ← PRD → GitHub Issues created automatically
/prime 1                 ← load context for Issue #1
/plan 1                  ← create implementation plan
# ── start a FRESH claude session ──
/implement .agents/plans/your-plan.plan.md
/validate
/verify                  ← browser-based E2E check (requires Playwright MCP)
```

---

## What's in This Template

| Path | Purpose |
|---|---|
| `SETUP.md` | This file — start here |
| `CLAUDE.md` | Global agent rules — fill in your stack and conventions |
| `CODEBASE-GUIDE.md` | Deep-dive reference doc — add architecture notes here |
| `memory/MEMORY.md` | Persistent memory index — recalled across sessions |
| `.mcp.json.example` | Copy to `.mcp.json`, then add your GitHub PAT |
| `.gitignore` | Pre-configured; excludes `.mcp.json`, `.env`, `node_modules`, etc. |
| `AGENTIC-ENGINEERING-GUIDE.md` | Full methodology reference |
| `.claude/commands/` | Slash commands — see table below |
| `.agents/PRDs/` | Generated PRDs saved here by `/create-prd` |
| `.agents/plans/` | Generated implementation plans saved here by `/plan` |

### Slash Commands

| Command | When to use |
|---|---|
| `/prime [issue#]` | Start of every session — loads codebase + GitHub Issue context |
| `/prime-server [issue#]` | Backend-only sessions — leaner context |
| `/prime-client [issue#]` | Frontend-only sessions — leaner context |
| `/create-prd` | Turn a brain dump into a structured PRD |
| `/create-issues <prd>` | Convert a PRD into GitHub Issues via MCP |
| `/plan <issue# or prd>` | Build an implementation plan (no code written) |
| `/implement <plan.md>` | Execute a plan in a **fresh** session |
| `/validate` | Type check + lint + unit tests + E2E (if configured) |
| `/verify [url]` | Browser-based verification using Playwright MCP |
| `/review` | Code review before opening a PR |
| `/security-review` | Security-focused review before merging sensitive changes |
| `/create-rules` | Generate/update CLAUDE.md from the current codebase |
| `/install` | Install dependencies and start the dev server |
| `/worktree <issue#>` | Set up a git worktree for parallel feature development |
