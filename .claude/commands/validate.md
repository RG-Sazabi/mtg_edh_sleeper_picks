---
description: Run the full validation suite and fix all failures
---

# Validate: Run All Checks

## Objective

Run the complete validation pyramid from bottom to top. Fix each layer before
moving to the next. Report a clean bill of health or a list of remaining issues.

## Validation Pyramid

```
Layer 5: Manual testing          ← You do this (golden path + edge cases)
Layer 4: Code review             ← Run /review before opening PR
Layer 3: Integration / E2E       ← Agent runs if browser skill is configured
Layer 2: Unit tests              ← Agent runs and fixes
Layer 1: Type check + lint       ← Agent runs and fixes
```

This command handles Layers 1–2 automatically. Layer 3 requires the agent-browser
skill (see AGENTIC-ENGINEERING-GUIDE.md §8). Layers 4–5 require you.

## Process

### Step 1: Type Check

Read `CLAUDE.md` to get the exact typecheck command, then run it.

If errors:
1. Read each error carefully (file, line, message)
2. Fix the root cause — do not use type assertions (`as any`, `!`) to silence errors
3. Re-run until clean

### Step 2: Lint

Read `CLAUDE.md` for the lint command, then run it.
Try the auto-fix command first (`lint:fix` or equivalent).
For remaining errors, fix manually.
Re-run until clean.

### Step 3: Unit Tests

Read `CLAUDE.md` for the test command, then run it.

If failures:
1. Read the failure output: test name, file:line, expected vs actual
2. Determine if the test is wrong (spec changed) or the code is wrong (bug)
3. Fix the appropriate side — never delete tests to make them pass
4. Re-run until green

### Step 4: E2E / Integration (if configured)

If Playwright or another browser automation tool is configured:
1. Start the dev server in the background
2. Run the E2E test suite
3. Fix failures, shut down server
4. Re-run until green

### Step 5: Report

```
## Validation Report

| Check | Status | Notes |
|-------|--------|-------|
| Type check | ✅ PASS / ❌ FAIL | details |
| Lint | ✅ PASS / ❌ FAIL | details |
| Unit tests | ✅ PASS / ❌ FAIL | {N} passed, {M} failed |
| E2E tests | ✅ PASS / ❌ FAIL / ⏭️ SKIPPED | details |

### Remaining Issues (if any)
{List anything that could not be fixed automatically}

### Manual Testing Needed
{Describe the user flows to verify manually}
```
