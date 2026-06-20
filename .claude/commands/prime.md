---
description: Prime agent with codebase and GitHub Issue context
argument-hint: [github-issue-number(s)]
---

# Prime: Load Project Context

**Input**: $ARGUMENTS

## Objective

Build a comprehensive understanding of this codebase and the current work item
before any planning or implementation begins.

## Process

### Step 0: Load GitHub Issue Context (if provided)

The argument is an optional GitHub Issue number or comma-separated list
(e.g., `42` or `42,43,44`).

If issue numbers are provided:
1. Determine the repository owner and name from git remote: run `git remote get-url origin`
2. For each issue number, call `mcp__github__get_issue` with the owner, repo, and issue number
3. Read the issue title, body, labels, and any comments
4. Use this context to understand what work is expected in this session
5. Note the issue number(s) — they will be referenced in any implementation plan

If no issue number is provided, skip this step.

### Step 1: Analyze the Codebase

1. Read `CLAUDE.md` in full — this is your primary source of truth for this project
2. Read `CODEBASE-GUIDE.md` if it exists and contains relevant context
3. Run `find . -type f -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/dist/*" -not -path "*/.next/*" | head -80` to map the project structure
4. Check recent commits: `git log --oneline -10`
5. Check current branch: `git branch --show-current`
6. If a feature directory is relevant to the issue, read the key files in it

### Step 2: Output a Briefing

Produce a scannable summary:

- **Project Purpose**: One sentence
- **Tech Stack**: Frontend / Backend / Database / Key libraries
- **Current Branch**: Name and any relevant context
- **Recent Work**: Last 5 commits summarized
- **Issue Context** (if provided): What needs to be built, acceptance criteria
- **Relevant Code Areas**: Files or directories most relevant to the current work
- **Ready For**: What the next step should be (`/plan`, `/implement`, or discussion)

Use bullet points. Keep it concise. This briefing is the starting point for the session.
