---
description: Convert a PRD into GitHub Issues via MCP
argument-hint: path/to/PRD.md [owner/repo]
---

# Create GitHub Issues from PRD

**Input**: $ARGUMENTS
- Argument 1: Path to PRD file (e.g., `.agents/PRDs/PRD.md`)
- Argument 2 (optional): GitHub repo in `owner/repo` format. If omitted, detect from `git remote get-url origin`.

## Objective

Read the PRD, identify each unit of MVP work, and create one GitHub Issue per
story or feature using the GitHub MCP. Save a manifest of created issues.

## Process

### Step 1: Determine Repository

Run `git remote get-url origin` to detect owner/repo if not provided as argument.
Parse the URL to extract `owner` and `repo`.

### Step 2: Read the PRD

Read the PRD file. Extract:
- Each item from the **MVP Scope / In Scope** section
- Each **User Story**
- Any **Implementation Phase** that maps to a discrete deliverable

Group related items: one GitHub Issue per logical unit of work.
Avoid creating issues that are too large (more than a few days of work) or
too small (a single file change). Issues should be independently implementable.

### Step 3: Create Each Issue

For each work item, call `mcp__github__create_issue` with:

**title**: Action-oriented, specific.
- Good: "Add email/password authentication with session management"
- Bad: "Authentication"

**body** (use this template):
```markdown
## User Story
As a [user type], I want to [action], so that [benefit].

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Technical Notes
[Any implementation context from the PRD relevant to this issue]

## Out of Scope for This Issue
[Anything explicitly deferred]
```

**labels**: Apply as appropriate:
- `enhancement` — new feature
- `bug` — fix
- `tech-debt` — refactor/cleanup
- `documentation` — docs only

### Step 4: Save Manifest

After all issues are created, save a manifest to `.agents/stories/issues-manifest.md`:

```markdown
# GitHub Issues Manifest

Generated from: {prd-path}
Date: {date}
Repository: {owner/repo}

| # | Issue | Title | URL |
|---|-------|-------|-----|
| 1 | #42 | Add authentication | https://github.com/... |
| 2 | #43 | Build dashboard | https://github.com/... |
```

### Step 5: Output Summary

```
## Issues Created

**Repository**: {owner/repo}
**Issues Created**: {N}
**Manifest**: `.agents/stories/issues-manifest.md`

| Issue | Title |
|-------|-------|
| #42 | Add authentication |
| #43 | Build dashboard |

### Next Step
Pick the first issue to implement and run:
  /prime {issue-number}
  /plan {issue-number}
```
