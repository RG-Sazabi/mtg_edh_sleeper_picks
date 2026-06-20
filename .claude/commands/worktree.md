---
description: Set up a git worktree for parallel feature development
argument-hint: <github-issue-number> [worktree-parent-dir]
---

# Worktree: Set Up Parallel Development Branch

**Input**: $ARGUMENTS
- Argument 1: GitHub Issue number (required)
- Argument 2: Parent directory for the worktree (optional, defaults to `../{repo-name}-worktrees/`)

## Objective

Create an isolated git worktree for working on a GitHub Issue in parallel with
other in-progress work. Each worktree is a separate filesystem checkout that
shares the same git history.

## Process

### Step 1: Gather Context

1. Run `git remote get-url origin` to determine repo name
2. Run `git branch --show-current` to confirm current branch
3. If an issue number is provided, fetch via `mcp__github__get_issue` to get the title

### Step 2: Create the Worktree

```bash
# Derive a branch name from the issue number and title
# e.g., feature/issue-42-add-authentication

BRANCH="feature/issue-{N}-{slug}"
WORKTREE_PATH="../{repo-name}-worktrees/{branch}"

git worktree add "$WORKTREE_PATH" -b "$BRANCH"
```

### Step 3: Copy Environment Config

If a `.env` file exists in the current directory, copy it to the worktree:

```bash
cp .env "$WORKTREE_PATH/.env"
```

Remind the user to update the port and database name in the worktree's `.env`
if the project uses local servers (to avoid conflicts with the main checkout).

### Step 4: Output Instructions

```
## Worktree Created

**Path**: {worktree-path}
**Branch**: {branch-name}
**Issue**: #{N} — {issue-title}

### Start working in this worktree:

  cd {worktree-path}
  claude

### Then in the new session:

  /prime {N}
  /plan {N}
  # ── start a FRESH session ──
  /implement .agents/plans/{plan-name}.plan.md

### When done (after PR merges):

  git worktree remove {worktree-path}

### ⚠️ Port & database conflicts
If this project runs a local server, update {worktree-path}/.env:
- Change PORT to a different value (e.g., 3001 instead of 3000)
- Use a separate dev database if running migrations
```
