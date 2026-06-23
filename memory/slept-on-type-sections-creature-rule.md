---
name: slept-on-type-sections-creature-rule
description: Slept On per-type sections — creatures slot only under Creatures (approved override of the "every matching section" spec)
metadata:
  type: project
---

In the Slept On per-type sections (issue #31), creatures slot **only** under the
Creatures section. An artifact/enchantment creature is treated as a creature and is
kept out of the Artifacts/Enchantments sections; other multi-type cards still appear
under every matching section (e.g. an artifact land in both Artifacts and Lands).
Implemented via the `is_creature` guard in `partition_by_type` (`services/analysis.py`).

**Why:** The user explicitly directed this deviation during #31 implementation —
"a creature is a creature to a deckbuilder." It intentionally overrides the original
PRD/issue acceptance criterion of "appear in every matching section."

**How to apply:** Do NOT "fix" `partition_by_type` to put creatures in every matching
section — that contradicts a deliberate decision. The records (PRD, #31 plan, code
comment) were reconciled to this behavior. Other as-built #31 deviations: sections cap
at `SLEPT_ON_SECTION_CAP = 100` from the full scored list (not a global 200 cap), and
some per-grid client filtering planned for #32 already shipped in #31. See
[[issue-32-slept-on-filters-status]] if tracking remaining #32 work.
