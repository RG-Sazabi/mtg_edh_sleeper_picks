---
description: Verify a code change works in the running app using Playwright browser automation
argument-hint: [url-or-feature-description]
---

# Verify: Browser-Based Feature Verification

**Input**: $ARGUMENTS (optional URL or description of what to verify)

## Objective

Launch the app in a browser and walk through key user flows to confirm the
recently implemented feature works end-to-end. This is the Layer 3 check in
the validation pyramid — above unit tests, below manual QA.

## Prerequisites

- Playwright MCP must be configured in `.mcp.json` (see SETUP.md)
- The dev server should be running, or this command will start it

## Process

### Step 1: Ensure the Dev Server Is Running

Read `CLAUDE.md` for the dev command. If the server isn't running, start it
in the background and wait for it to be ready (watch for "ready" or "localhost" in output).

### Step 2: Identify What to Verify

If `$ARGUMENTS` is a GitHub Issue number, fetch it via `mcp__github__get_issue`
and extract the acceptance criteria. Otherwise use the argument as a description
of the feature to test.

### Step 3: Navigate and Test

Use the Playwright MCP tools to:

1. Take a screenshot of the starting state
2. Navigate to the relevant page or URL
3. Walk through the primary happy path (the golden path)
4. Verify the expected outcome is visible on screen
5. Test at least one edge case or error state if applicable
6. Take a final screenshot showing the result

### Step 4: Report

```
## Verification Report

**Feature**: {feature name or issue number}
**URL tested**: {url}
**Browser**: Chromium (Playwright)

### Golden Path
- [ ] Step 1: {action} → {expected result} — PASS / FAIL
- [ ] Step 2: {action} → {expected result} — PASS / FAIL

### Edge Cases
- [ ] {edge case} — PASS / FAIL / SKIPPED

### Screenshots
{describe or reference screenshots taken}

### Verdict
PASS — ready for review
FAIL — {list specific failures to fix}
```
