---
description: Perform a code review of current changes before opening a PR
---

# Review: Code Review

## Objective

Perform a thorough review of all uncommitted or PR-staged changes.
Catch issues that automated checks miss: logic bugs, missing edge cases,
pattern violations, incomplete implementations, and readability problems.

## Process

### Step 1: Get the Diff

```bash
git diff HEAD          # uncommitted changes
# or
git diff main...HEAD   # all commits on current branch vs main
```

### Step 2: Review Each Changed File

For each file in the diff, check:

**Correctness**
- Does the logic do what it's supposed to do?
- Are there off-by-one errors, null/undefined edge cases, or incorrect conditionals?
- Are all error paths handled?

**Pattern Adherence**
- Does the code follow CLAUDE.md conventions?
- Are the right layers doing the right things? (No business logic in repositories, etc.)
- Are naming conventions consistent with the rest of the codebase?

**Test Coverage**
- Are the new code paths tested?
- Do the tests verify behavior (not implementation details)?
- Are edge cases and failure paths covered?

**Security**
- Are user inputs validated before use?
- Are there any SQL injection, XSS, or path traversal risks?
- Are secrets or sensitive data handled correctly?

**Completeness**
- Does this fully implement the GitHub Issue acceptance criteria?
- Are there TODOs or FIXMEs left in the code?
- Is the PR description accurate?

### Step 3: Output Review

```
## Code Review

### Summary
{1–2 sentences on overall quality and readiness}

### ✅ Looks Good
- {things done well}

### ❌ Must Fix Before Merge
- {file:line} — {issue and why it matters}

### ⚠️ Should Fix (non-blocking)
- {file:line} — {suggestion}

### 💡 Consider for Future
- {things worth noting but deferred}

### Verdict
APPROVE / REQUEST CHANGES / NEEDS DISCUSSION
```
