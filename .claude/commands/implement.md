---
description: Execute an implementation plan in a clean context window
argument-hint: path/to/plan.md
---

# Implement: Execute Plan

**Input**: $ARGUMENTS (path to a `.plan.md` file)

## Critical Rules

1. **This command must run in a FRESH Claude Code session.** Never implement in the
   same session where planning occurred. Context from planning degrades implementation.
2. **Follow the plan exactly.** Do not improvise. If the plan is wrong, stop and say so
   rather than deviating silently.
3. **One task at a time.** Complete Task 1 fully before starting Task 2.
4. **Validate after every task**, not just at the end.

## Process

### Step 1: Read and Internalize the Plan

Read the plan file at `$ARGUMENTS` in full. Confirm you understand:
- The feature being built
- The files to create/modify
- The patterns to follow (with their file:line sources)
- The acceptance criteria

### Step 2: Execute Tasks in Order

For each task in the plan:

1. Read the mirror file (the pattern to follow) if one is specified
2. Write the code for this task
3. Run the task's validation command (`lint`, `typecheck`)
4. Fix any errors before moving to the next task
5. Make a descriptive git commit:
   ```bash
   git add {changed files}
   git commit -m "{type}: {description} - task {N} of {total}"
   ```

Never proceed to the next task while the current one has failing checks.

### Step 3: Final Validation

After all tasks are complete, run the full validation sequence from the plan:

```bash
{typecheck-command}
{lint-command}
{test-command}
```

Fix everything until all checks are clean.

### Step 4: Update GitHub Issue (if applicable)

If the plan includes a GitHub Issue number:
1. Call `mcp__github__create_issue_comment` to add a comment summarizing what was implemented
2. Do NOT close the issue — that happens via the PR merge

### Step 5: Output Summary

```
## Implementation Complete

**Plan**: {plan-file}
**Tasks Completed**: {N}/{N}
**Files Changed**: {list}

**Checks**:
- Type check: PASS / FAIL
- Lint: PASS / FAIL
- Tests: PASS / FAIL

**Next Steps**:
1. Review changes: /review
2. Open a PR:
   git checkout -b feature/issue-{N}-{slug}
   git push origin feature/issue-{N}-{slug}
   gh pr create --title "{title}" --body "Closes #{issue}" --base main
```
