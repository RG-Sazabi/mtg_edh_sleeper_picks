---
name: feedback
description: Corrections and confirmed approaches from prior sessions — what to avoid and what to repeat
metadata:
  type: feedback
---

{Populated automatically as Claude Code learns your preferences.}

Structure for each entry:

**Rule**: [the behavior guideline]
**Why**: [the reason — often a past incident or strong preference]
**How to apply**: [when/where this guidance kicks in]

---

Examples of what gets recorded here:
- "Don't mock the database in tests — we got burned when mocked tests passed but prod migration failed"
- "Always use `await cookies()` from next/headers — never read cookies synchronously"
- "Prefer a single bundled PR for refactors — splitting creates churn in this codebase"
