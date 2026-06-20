---
description: Prime agent with backend/server-layer context
argument-hint: [github-issue-number]
---

# Prime (Server): Load Backend Context

**Input**: $ARGUMENTS

## Objective

A focused primer for backend work. Loads only server-side context to keep
the context window lean when you're not touching the frontend.

## Process

### Step 0: Load GitHub Issue (if provided)

Same as `/prime` — fetch the issue using `mcp__github__get_issue` if a number is provided.

### Step 1: Backend-Focused Analysis

1. Read `CLAUDE.md` — focus on the Commands, Architecture, and Code Patterns sections
2. Map server-side directories: API routes, services, repositories, database schema
3. Run `git log --oneline -5` for recent backend changes
4. Read the database schema file(s) if they exist
5. Read the service and repository files most relevant to the issue

### Step 2: Output a Backend Briefing

- **API Layer**: How routes/endpoints are organized
- **Service Layer**: Key services and their responsibilities
- **Data Layer**: Schema, ORM patterns, key queries
- **Relevant Files**: Specific files to touch for this issue
- **Patterns to Follow**: Error handling, validation, logging patterns from CLAUDE.md
