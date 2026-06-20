---
description: Create a detailed implementation plan before writing any code
argument-hint: <github-issue-number | path/to/prd.md | feature description>
---

# Plan: Create Implementation Plan

**Input**: $ARGUMENTS

## Objective

Transform the input into a concrete, step-by-step implementation plan through
codebase exploration and pattern extraction.

**Core Rule**: PLAN ONLY — no code is written during this command.
The output is a plan file that `/implement` will execute in a fresh session.

**Order**: CODEBASE FIRST — solutions must fit existing patterns, not introduce new ones.

---

## Phase 1: PARSE — Understand the Input

### Determine Input Type

| Input | Action |
|-------|--------|
| GitHub issue number (e.g., `42`) | Fetch issue via `mcp__github__get_issue`, use body as feature description |
| `.md` file path | Read and extract feature description |
| Free-form text | Use directly |
| Blank | Use conversation context |

### Extract Feature Understanding

- **Problem**: What are we solving?
- **User Story**: As a [user], I want to [action], so that [benefit]
- **Type**: NEW_CAPABILITY / ENHANCEMENT / REFACTOR / BUG_FIX
- **Complexity**: LOW / MEDIUM / HIGH
- **GitHub Issue**: Note the issue number if available (used by `/implement` to update status)

---

## Phase 2: EXPLORE — Study the Codebase

Use the TodoWrite/Explore agent to find, in parallel:

1. **Similar implementations** — analogous features with file:line references
2. **Naming conventions** — actual examples from the codebase
3. **Error handling patterns** — how errors are created and surfaced
4. **Type definitions** — relevant interfaces and types
5. **Test patterns** — test file structure and assertion style
6. **Import patterns** — how modules are imported

Document findings:

| Category | File:Lines | Pattern |
|----------|-----------|---------|
| NAMING | `path/file.ts:10-15` | description |
| ERRORS | `path/file.ts:20-30` | description |
| TESTS | `path/test.ts:1-25` | description |

---

## Phase 3: DESIGN — Map the Changes

- What files need to be CREATED?
- What files need to be MODIFIED?
- What is the dependency order? (What must be built first?)
- What are the risks?

| Risk | Mitigation |
|------|-----------|
| potential issue | how to handle |

---

## Phase 4: GENERATE — Write the Plan File

**Output path**: `.agents/plans/{kebab-case-feature-name}.plan.md`

```
mkdir -p .agents/plans
```

### Plan File Structure

```markdown
# Plan: {Feature Name}

## Summary
{One paragraph: what we're building and the approach}

## User Story
As a {user}, I want to {action}, so that {benefit}.

## Metadata
| Field | Value |
|-------|-------|
| Type | {NEW_CAPABILITY / ENHANCEMENT / REFACTOR / BUG_FIX} |
| Complexity | {LOW / MEDIUM / HIGH} |
| GitHub Issue | #{number or N/A} |
| Systems Affected | {list of layers/features} |

---

## Patterns to Follow

### Naming
// SOURCE: path/file.ts:lines
{code snippet}

### Error Handling
// SOURCE: path/file.ts:lines
{code snippet}

### Tests
// SOURCE: path/test.ts:lines
{code snippet}

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `path/to/file.ts` | CREATE | why |
| `path/to/other.ts` | UPDATE | why |

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: {Description}
- **File**: `path/to/file.ts`
- **Action**: CREATE / UPDATE
- **Implement**: {what to do, be specific}
- **Mirror**: `path/to/example.ts:lines` — follow this pattern exactly
- **Validate**: `{lint/typecheck command}`

### Task 2: {Description}
- **File**: `path/to/file.ts`
- **Action**: CREATE / UPDATE
- **Implement**: {what to do}
- **Mirror**: `path/to/example.ts:lines`
- **Validate**: `{command}`

{Continue for each task...}

---

## Validation Sequence

```bash
# Run in this order after all tasks complete
{typecheck-command}
{lint-command}
{test-command}
```

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] Type check passes
- [ ] Lint passes
- [ ] Tests pass
- [ ] Follows existing patterns from CLAUDE.md
- [ ] GitHub Issue #{number} criteria satisfied
```

---

## Phase 5: OUTPUT

```
## Plan Created

**File**: `.agents/plans/{name}.plan.md`

**Summary**: {2–3 sentence overview}

**Scope**:
- {N} files to CREATE
- {M} files to UPDATE
- {K} total tasks

**Key Patterns**:
- {Pattern 1 from file:line}
- {Pattern 2 from file:line}

**Next Step**:
Close this session. Start a fresh `claude` session and run:
  /implement .agents/plans/{name}.plan.md
```
