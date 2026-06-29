# PRD: Tag-Granularity Controls for Slept On Scoring

> **Status:** Draft for review
> **Author:** Generated from design conversation, 2026-06-28
> **Related code:** `services/bulk.py`, `services/analysis.py`, `app.py`, `templates/commander.html`, `static/js/filters.js`
> **Builds on:** Feature-lift model (Ferrone 2026); the tag/budget/bracket scope selectors (issue #19)

---

## 1. Executive Summary

The Slept On engine scores every color-legal card by how strongly the commander's
recommended cards over-use the *features* a candidate carries — where a feature is a
card type, subtype, or Scryfall oracle tag. Today, oracle-tag features are taken at
their **most specific (leaf) level**: a card tagged `tutor-creature-giant` contributes
that exact slug and nothing coarser. Scryfall's oracle tags form a hierarchy up to
**7 levels deep**, but Scryfall does **not** propagate a tagging up to its ancestors —
so the engine never sees the broader theme (`tutor`) a leaf tag belongs to. The result
is heavy fragmentation: a commander whose recommended cards collectively scream
"tutors" can still have each individual tutor slug fall below the `min_support = 3`
cutoff and be discarded, so the real shared theme never scores.

This feature adds a user-facing **granularity control** that collapses every oracle-tag
feature to a single, chosen depth of the tag hierarchy (rolling deeper tags up to that
depth, keeping shallower ones as-is). It also adds a control to **exclude card
types/subtypes** from the feature set (on by default), so scores can be driven by
oracle-tag themes alone. Both controls recompute feature weights server-side, in the
same way the existing `tag` scope selector already does.

**MVP goal:** Let the user pick how coarse or fine the oracle-tag themes are (three
named levels, defaulting to the middle) and whether card types/subtypes participate in
scoring — and have the Slept On rankings recompute accordingly.

---

## 2. Mission

Give the player direct control over the *granularity* of the thematic signal behind
Slept On picks, so the recommendations can be tuned from broad strategy overlap to fine
mechanical overlap.

**Core principles**

1. **One tag level at a time.** Scoring uses a single, uniform depth of the oracle-tag
   hierarchy — never a mix of leaf-and-ancestor for the same concept.
2. **No signal silently lost.** Tags shallower than the chosen level are kept at their
   own (coarser) level rather than dropped; deeper tags roll up rather than vanish.
3. **Source of truth is Scryfall.** Functional vs. non-functional is the split Scryfall
   already publishes (`oracle_tags` vs. `art_tags`); we do not reinvent it with
   heuristics.
4. **Controls that change the math are server-side.** Anything that alters the feature
   set (and therefore the weights) recomputes on the server; only pure display filters
   stay client-side.
5. **Named, not numbered.** The granularity levels carry human-meaningful names.

---

## 3. Target Users

**Primary persona — "the deck tuner" (the app's sole user).**

- A Commander player building a specific deck, hosting the Flask app locally for
  personal use.
- High domain knowledge (understands tutors, ramp, typal, etc.); moderate technical
  comfort (runs `python app.py`, reads a web UI, does not edit code to change behavior).
- **Need:** to dial the Slept On signal between "show me cards that fit the broad
  strategy" and "show me cards that share specific mechanics," without editing config.
- **Pain point today:** fine-grained tags fragment below `min_support` and disappear, so
  cohesive themes never surface; and type/subtype features can dominate scoring in ways
  the user can't turn off.

---

## 4. MVP Scope

**In scope**

- [ ] A tag-hierarchy index in `services/bulk.py`: per-tag depth and the set of
      ancestor tags at any requested depth, derived from `parent_ids` (DAG-safe,
      cycle-guarded).
- [ ] **Cap-at-level** feature generation: each oracle-tag feature is collapsed to the
      chosen depth — deeper tags replaced by **all** their ancestors at that depth;
      tags already at or above the depth kept unchanged.
- [ ] A **named granularity selector** with three levels (proposed: **Broad /
      Balanced / Fine**), default **Balanced**, applied to oracle-tag features only.
- [ ] A **"Include card types & subtypes" toggle**, default **off** (types/subtypes
      excluded from features by default).
- [ ] Both controls flow through the route as query params and trigger a server-side
      recompute of feature weights and Slept On rankings (mirroring the `tag` selector).
- [ ] Diagnostics views (`feature_stats`, per-card `features`, tooltip breakdown in
      `static/js/filters.js`) reflect the chosen level and type toggle consistently.
- [ ] Controls rendered on the commander page alongside the existing tag / budget /
      bracket scope selectors.

**Out of scope (deferred)**

- [ ] Ingesting non-functional **art tags** (`art_tags` bulk). We already ingest only
      `oracle_tags`, which *is* Scryfall's functional set — so the app is functional-only
      by construction. There is no "include non-functional tags" toggle. *(Decision:
      "functional-only, no toggle.")*
- [ ] Per-feature-kind level selection (e.g. a different depth for subtypes vs. otags).
- [ ] Persisting the user's level/type preference across sessions.
- [ ] Any change to the type/subtype hierarchy (types/subtypes remain flat features,
      governed by the on/off toggle only — the level selector does not apply to them).

---

## 5. User Stories

1. **As a deck tuner, I want to choose how broad or specific the tag themes are, so that
   I can move between strategy-level and mechanic-level recommendations.**
   *Example:* On a Krenko deck, switching from **Fine** to **Broad** collapses
   `typal-goblin`, `creates-goblin-token`, etc. up to coarser themes, surfacing cards
   that share the broad "go-wide tokens" idea rather than the exact goblin tags.

2. **As a deck tuner, I want a sensible default level, so that I get good results without
   touching the control.**
   *Example:* A first-time lookup of "Atraxa, Praetors' Voice" scores at **Balanced**
   (the middle level) with no interaction.

3. **As a deck tuner, I want fine-grained tags rolled up instead of dropped, so that
   cohesive themes stop falling below the support cutoff.**
   *Example:* Five recommended cards each carry a different leaf tutor tag; at
   **Balanced** they roll up to a shared `tutor`-level ancestor that now clears
   `min_support` and scores.

4. **As a deck tuner, I want to exclude card types and subtypes from scoring by default,
   so that oracle-tag themes drive the picks rather than "is a Creature."**
   *Example:* With the type toggle off, `type:Creature` / `sub:Goblin` no longer add
   weight; only mechanical tags do.

5. **As a deck tuner, I want to optionally turn types/subtypes back on, so that I can
   see how much they shift the rankings.**
   *Example:* Toggling "Include card types & subtypes" on re-ranks the Slept On grid and
   the diagnostics table updates to show `type:`/`sub:` rows again.

6. **As a deck tuner, I want the diagnostics breakdown and hover tooltip to match the
   level/type settings, so that the "why did this score" view is trustworthy.**
   *Example:* At **Broad**, a card's tooltip lists its broad rolled-up tags and their
   contributions — not the leaf tags it no longer scores on.

7. **As a deck tuner, I want the level/type controls to compose with the existing tag /
   budget / bracket scopes, so that I can combine them.**
   *Example:* Choosing a theme tag *and* **Fine** scopes the recommended set and then
   scores it at fine granularity.

---

## 6. Core Architecture & Patterns

### Where the work lives (respect the layer rules in CLAUDE.md)

```
services/bulk.py       # NEW: tag depth + ancestor-at-depth index (built from parent_ids)
services/analysis.py   # CHANGED: card_features() takes level + include_types;
                       #          compute_feature_stats / score_* thread them through
app.py                 # CHANGED: read ?level / ?include_types; pass into analysis;
                       #          recompute weights (same place as the tag rescope)
templates/commander.html  # CHANGED: render the named level selector + type toggle
static/js/filters.js   # CHANGED: keep tooltip breakdown in sync with the level
                       #          (server emits per-card capped features; JS mirrors math)
```

### Key design decisions (locked in this conversation)

| Concern | Decision |
|---|---|
| Shallow-tag handling | **Cap specificity at the chosen level.** Roll tags deeper than the level up to their level-N ancestor; keep tags already at/above the level unchanged. No taggings lost. |
| Default level | **Balanced** (the middle of three) — maps to hierarchy depth 3. |
| Multi-parent rollup | **Keep all** ancestors at the chosen level (the hierarchy is a DAG, not a tree). |
| Type/subtype features | **Excluded by default**, re-enabled by a toggle. The level selector does **not** apply to them (they are flat). |
| Non-functional tags | **Out of scope** — functional-only by construction (`oracle_tags` only). |
| Control surface | **Server-side recompute**, like the `tag` selector — not a client-side display filter. |

### Level naming (assumption — easily renamed)

| Level name | Hierarchy depth | Character |
|---|---|---|
| **Broad** | 2 | Coarse strategy-level themes |
| **Balanced** *(default)* | 3 | Middle ground |
| **Fine** | 4 | Specific mechanic-level themes |

> The UI exposes **names only**; the depth integers are an internal implementation
> detail. Levels are limited to 2–4 (depths 1 and 5–7 are out of range per the design
> conversation: depth 1 is too coarse; depths 5–7 carry too little support to matter).

### Capping algorithm (oracle-tag features only)

For a card and a chosen depth `N`:

```
for each leaf oracle tag t on the card:
    d = depth(t)
    if d <= N:
        emit  otag:t            # already at/above the level — keep as-is
    else:
        for a in ancestors_at_depth(t, N):   # may be several (DAG)
            emit  otag:a         # roll up; keep ALL level-N ancestors
```

`depth(t)` and `ancestors_at_depth(t, N)` come from the new `bulk.py` index, which must
guard against cycles in the parent graph (the existing depth computation already does).
Type/subtype features are emitted unchanged when the type toggle is on, and omitted
entirely when it is off.

### Control flow (server-side recompute)

`?level=<name>&include_types=<bool>` → `app.commander()` parses them → passes into
`analysis.compute_feature_stats(...)` and the per-card `card_features(...)` calls →
weights and Slept On rankings recompute → template re-renders. This is the same
recompute path the `tag` selector already uses (app.py:139–215); budget/bracket remain
display-only. The pure client-side filters (price, pauper, inclusion cap, N) are
unaffected and still run in `filters.js` over the already-scored cards.

---

## 7. Technology Stack

- **Backend:** Python 3.12, Flask 3.x (existing). No new runtime dependencies.
- **Tag data:** Scryfall `oracle_tags` bulk (already downloaded to `cache/` and indexed
  with `ijson`). The new depth/ancestor index is built in-memory from the `parent_ids`
  already present in that file — **no new download**.
- **Frontend:** Jinja2 templates + vanilla JS (`filters.js`), consistent with existing
  controls. No new JS libraries.
- **Third-party integrations:** none added.

---

## 8. Security & Configuration

- **Auth:** none (personal, local-only app — unchanged).
- **Environment variables:** none added.
- **New config/constants:** the level-name → depth mapping and the default level live as
  constants (e.g. in `analysis.py` or `bulk.py`), `SCREAMING_SNAKE_CASE`.
- **Input handling:** `?level` must be validated against the known level names and fall
  back to the default on anything unexpected; `?include_types` parsed as a strict
  boolean. No user data is stored or transmitted; security scope is unchanged.

---

## 9. Success Criteria

**MVP success:** The user can change the oracle-tag granularity between three named
levels and toggle type/subtype participation from the commander page, and the Slept On
rankings + diagnostics recompute correctly, with **Balanced** + types-off as the
defaults.

**Functional requirements**

- [ ] `bulk.py` exposes a function returning a tag's depth and its ancestors at a given
      depth; cycle-safe; built once per process and rebuilt on index reload.
- [ ] `analysis.card_features()` collapses oracle tags to the chosen level (roll deeper
      up to all level-N ancestors; keep shallower as-is) and honors the type toggle.
- [ ] `compute_feature_stats`, `score_card`, `score_breakdown`, `score_cards` all
      operate on the level/type-adjusted feature set consistently.
- [ ] Default render uses **Balanced** + types excluded with no query params.
- [ ] Changing the level or type toggle re-ranks Slept On and updates `feature_stats`.
- [ ] The tooltip breakdown in `filters.js` matches the server's per-card contributions
      at the chosen level (no leaf-tag rows the card no longer scores on).
- [ ] Controls compose with the existing `tag` / `budget` / `bracket` selectors.

**Quality indicators**

- [ ] `flake8 .` clean; `python -m py_compile app.py services/*.py` clean.
- [ ] Manual smoke test (CLAUDE.md): "Atraxa, Praetors' Voice" renders both sections at
      each of the three levels and with the type toggle both ways, with no 500s.
- [ ] Sanity check: at **Balanced**, a known commander surfaces a previously-fragmented
      theme (e.g. tutors) that was below `min_support` at leaf granularity.

---

## 10. Implementation Phases

### Phase 1 — Tag hierarchy index (`services/bulk.py`)
**Goal:** Make tag depth and level-N ancestry queryable in-memory.
**Deliverables**
- [ ] Build a `{tag -> depth}` and ancestor-resolution structure from `parent_ids`,
      DAG- and cycle-safe.
- [ ] Public accessor(s) for "depth of tag" and "ancestors of tag at depth N."
- [ ] Index built within `ensure_loaded()` and reset on reload (like the existing memoized views).
**Validation:** unit-style spot checks (e.g. `cycle-ons-fetchland` resolves to its
known ancestors; a depth-2 tag returns itself at level 2); `flake8`/`py_compile` clean.

### Phase 2 — Level-aware scoring (`services/analysis.py`)
**Goal:** Collapse features to a chosen level and honor the type toggle, purely.
**Deliverables**
- [ ] `card_features(card, level=..., include_types=False)` implementing the cap-at-N
      rollup (keep-all ancestors) and the type/subtype gate.
- [ ] Thread `level` / `include_types` through `compute_feature_stats`,
      `compute_feature_weights`, `score_card`, `score_breakdown`, `score_cards`.
- [ ] Level-name → depth mapping + default as module constants.
**Validation:** scoring stays pure (no I/O); leaf-vs-rolled-up behavior verified on a
sample card; `flake8`/`py_compile` clean.

### Phase 3 — Route wiring (`app.py`)
**Goal:** Read the controls and recompute on the existing weight path.
**Deliverables**
- [ ] Parse `?level` (validated to a known name, else default) and `?include_types`.
- [ ] Pass them into the scoring calls so weights/rankings recompute; ensure every
      `card_features(...)` call site (Slept On, EDHRec tab, featured, deck tab,
      diagnostics) uses the same settings.
- [ ] Pass selected level/type state to the template.
**Validation:** manual smoke test across levels + toggle; composes with `tag`; no 500s.

### Phase 4 — UI + diagnostics sync (`templates/commander.html`, `static/js/filters.js`)
**Goal:** Expose named controls and keep the breakdown/tooltip consistent.
**Deliverables**
- [ ] Named level selector (Broad / Balanced / Fine) + "Include card types & subtypes"
      toggle, placed with the tag/budget/bracket selectors; submit triggers the
      server recompute.
- [ ] `filters.js` tooltip math mirrors the server's per-card capped features.
- [ ] Diagnostics table (`feature_stats`) reflects the chosen level/type settings.
**Validation:** tooltip contributions match server values at each level; full
validation sequence clean.

---

## 11. Risks & Mitigations

1. **Scoring shifts noticeably from today's leaf model.** Cap-at-N plus types-off-by-
   default is a real change to the score distribution.
   *Mitigation:* validate against a known commander before merge; keep `feature_stats`
   diagnostics so the new weights are inspectable; **Balanced** chosen as a moderate
   default.

2. **Client/server breakdown drift.** `filters.js` mirrors `score_breakdown`; if the
   server caps features but the client still uses leaf tags, tooltips lie.
   *Mitigation:* the server emits each rendered card's already-capped `features`; the
   client scores only from that emitted list (no independent tag expansion in JS).

3. **DAG/cycle hazards in ancestry resolution.** Tags have multiple parents and the
   graph can contain cycles.
   *Mitigation:* reuse the cycle-guarded traversal pattern already used to compute depth;
   "keep all level-N ancestors" is well-defined for multi-parent tags.

4. **Performance of per-card rollup over a large color pool.** Capping runs for every
   candidate in the color identity (thousands for 4–5 color commanders).
   *Mitigation:* precompute and memoize per-leaf-tag → level-N ancestor sets in `bulk.py`
   so per-card work is a set union of cached lookups; recompute only on control change.

5. **Level naming may not land with the user.** Broad/Balanced/Fine is an assumption.
   *Mitigation:* names are UI-only over an internal depth mapping; renaming is a
   one-line change with no logic impact.

---

## 12. Future Considerations

- **Art-tag experimentation:** Scryfall also publishes an `art_tags` bulk (38 MB,
  subject/artwork tags). If subject-matter signal ever proves interesting, it could be
  ingested behind its own namespace and toggle — explicitly deferred for now.
- **Per-kind granularity:** distinct levels for subtypes vs. oracle tags, if a single
  global level proves too blunt.
- **Preference persistence:** remember the user's last level/type choice across lookups.
- **Adaptive support cutoff:** since rolling up raises per-feature support, revisit
  whether `min_support` should scale with the chosen level.
- **Minor data hygiene:** ~45 art-classified tags leak into the `oracle_tags` bulk; an
  optional scrub against Scryfall's published functional list would make the functional
  set exact (negligible scoring impact).

---

## Assumptions Flagged

- **Level names** are **Broad / Balanced / Fine** (default Balanced) — proposed by the
  author; rename freely (UI-only).
- **Depth mapping** Broad=2, Balanced=3, Fine=4; levels restricted to 2–4 per the design
  conversation.
- **Default state** is Balanced + types/subtypes excluded, per the stated defaults.
- Controls are **server-recompute** (not client filters), consistent with the existing
  `tag` selector; this is inferred from how scoring weights are produced in `app.py`.
