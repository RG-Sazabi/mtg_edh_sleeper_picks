---
description: Prime agent with frontend/client-layer context
argument-hint: [github-issue-number]
---

# Prime (Client): Load Frontend Context

**Input**: $ARGUMENTS

## Objective

A focused primer for frontend work. Loads only client-side context to avoid
loading backend details that are irrelevant to UI work.

## Process

### Step 0: Load GitHub Issue (if provided)

Same as `/prime` — fetch the issue using `mcp__github__get_issue` if a number is provided.

### Step 1: Frontend-Focused Analysis

1. Read `CLAUDE.md` — focus on the Tech Stack, Commands, and Code Patterns sections
2. Map frontend directories: components, pages/routes, styles, shared utilities
3. List available UI component primitives (e.g., from `src/components/ui/`)
4. Check recent commits for UI-related changes: `git log --oneline -5`
5. Read the components and pages most relevant to the issue

### Step 2: Output a Frontend Briefing

- **UI Framework**: Component model, routing approach
- **Component Library**: What's available in the design system
- **State Management**: How state flows in this project
- **Styling Approach**: CSS-in-JS, Tailwind, CSS modules — and conventions
- **Relevant Files**: Specific components and pages to touch for this issue
- **Patterns to Follow**: Component structure, naming, and prop conventions from CLAUDE.md
