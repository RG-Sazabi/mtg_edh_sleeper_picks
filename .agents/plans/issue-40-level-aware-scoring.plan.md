# Plan: Level-Aware Scoring (cap otags to a depth + type/subtype toggle)

## Summary
Make `services/analysis.py` feature generation honor (a) a chosen oracle-tag
granularity **level** and (b) a **type/subtype on-off toggle**, using the
hierarchy index landed in #39 (`bulk.tag_depth` / `bulk.ancestors_at_depth`).
`card_features` gains `level` (named: Broad=2 / Balanced=3 default / Fine=4) and
`include_types` (default `False`) parameters: leaf otags at depth ≤ N are kept
as-is, deeper otags roll up to **all** their level-N ancestors (DAG-safe,
keep-all, no taggings dropped), and `type:`/`sub:` features are emitted only when
`include_types=True` (flat — the level never applies to them). These two settings
thread through `compute_feature_stats`, `compute_feature_weights`, `score_card`,
`score_breakdown`, and `score_cards` so the whole pipeline shares one feature set.
This is Phase 2 of the tag-granularity PRD — analysis layer only. Route wiring
(app.py), UI controls, and the `filters.js` tooltip mirror are explicitly out of
scope (separate issues), but the new defaults are chosen so the **untouched**
app.py default path renders correctly at Balanced + types-off.

## User Story
As a deck tuner, I want to choose how broad or specific the tag themes are and
whether card types/subtypes participate, so that I can move between strategy-level
and mechanic-level recommendations.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | MEDIUM |
| GitHub Issue | #40 |
| Systems Affected | `services/analysis.py` (scoring layer only); depends on #39 `services/bulk.py` index |

---

## Context Facts (verified this session)

- `#39` is **landed**: [services/bulk.py:399](services/bulk.py) `tag_depth(slug) -> int`
  (unknown slug → 1) and [services/bulk.py:407](services/bulk.py)
  `@lru_cache ancestors_at_depth(slug, n) -> frozenset[str]` (all level-n
  ancestors, DAG-safe, includes self when its own depth == n). Both call
  `ensure_loaded()` internally.
- `bulk.py` imports **no** `services` module ([services/bulk.py:21-29](services/bulk.py)),
  so `analysis` importing `bulk` introduces **no circular import**.
- `analysis.card_features` is currently called from **6 sites**: internally by
  `compute_feature_stats` ([services/analysis.py:178](services/analysis.py)),
  `score_breakdown` ([services/analysis.py:218](services/analysis.py)), and
  `partition_by_type` ([services/analysis.py:289](services/analysis.py)); and from
  `app.py` at [app.py:221,229,257,289](app.py) (display-feature enrichment).
- **Default path stays consistent**: app.py builds `weights` from
  `compute_feature_stats(scoring_cards)` ([app.py:213-214](app.py)) and scores via
  `score_cards(color_pool, weights, exclude_names)` ([app.py:215](app.py)). Both
  will use the new defaults (Balanced, types-off) → weights and scoring share the
  same feature set. This matches the PRD's intended default render.
- **`partition_by_type` is the one breakage risk**: it calls `card_features(card)`
  only to read `type:` features ([services/analysis.py:289](services/analysis.py)).
  Under the new `include_types=False` default it would get **zero** type features
  and every per-type section would render empty. It must read types independently
  of the scoring toggle (see Task 2).

---

## Design Decisions

1. **`analysis` imports `bulk`.** The issue authorizes this ("the only new
   dependency is the pure lookups exposed by `bulk.py`"). `tag_depth` /
   `ancestors_at_depth` are deterministic over the loaded hierarchy; `analysis`
   itself still performs no network/HTTP/file I/O. Document this in the module
   docstring so the "pure computation" contract stays honest.

2. **Extract a `_type_and_sub_features(type_line)` helper.** Today the type-line
   parsing lives inline in `card_features`. Pull it into a private helper so it has
   **one** source of truth, used by `card_features` (gated by `include_types`) and
   by `partition_by_type` (always, filtering for `type:`). This both fixes the
   `partition_by_type` breakage and avoids running the otag rollup over the full
   scored pool just to bucket by type.

3. **Level resolution by name, fallback to default.** Module constants
   `LEVEL_DEPTHS = {"Broad": 2, "Balanced": 3, "Fine": 4}` and
   `DEFAULT_LEVEL = "Balanced"`. Resolve inline with
   `LEVEL_DEPTHS.get(level, LEVEL_DEPTHS[DEFAULT_LEVEL])` so any unknown/invalid
   level falls back to the default depth (AC: "unknown/invalid level falls back to
   the default").

4. **New params go at the end of each signature** as keyword args with defaults, so
   every existing positional call site in `app.py` keeps working untouched.

5. **Capping algorithm** (otags only), per PRD §6:
   ```
   depth = LEVEL_DEPTHS.get(level, default)
   for tag in card otags:
       if bulk.tag_depth(tag) <= depth:  emit otag:tag          # keep as-is
       else:                             emit otag:a for every a # roll up, keep ALL
                                         in bulk.ancestors_at_depth(tag, depth)
   ```

---

## Patterns to Follow

### Pure feature builder + namespaced features (current shape to preserve)
```python
# SOURCE: services/analysis.py:81-104 (card_features today)
def card_features(card: dict) -> list[str]:
    feats: set[str] = set()
    type_line = card.get("type_line", "") or ""
    for face in type_line.split("//"):
        if "—" in face:
            left, right = face.split("—", 1)
        else:
            left, right = face, ""
        for word in left.split():
            if word not in _SUPERTYPES:
                feats.add(f"type:{word}")
        for word in right.split():
            feats.add(f"sub:{word}")
    for tag in card.get("otags", []) or []:
        feats.add(f"otag:{tag}")
    return list(feats)
```

### Delegation pattern already used for params (mirror for level/include_types)
```python
# SOURCE: services/analysis.py:138-140 (compute_feature_weights delegates, passing kwargs through)
return {s["feature"]: s["weight"] for s in compute_feature_stats(
    edhrec_cards, min_support=min_support, eps=eps
)}
```

### #39 lookups (the only new dependency)
```python
# SOURCE: services/bulk.py:399-403, 407 (pure-over-loaded-state accessors)
def tag_depth(slug: str) -> int: ...            # unknown -> 1
def ancestors_at_depth(slug: str, n: int) -> frozenset[str]: ...  # all level-n ancestors, DAG-safe
```

### Module constants (SCREAMING_SNAKE_CASE, with the SLEPT_ON_TYPE_SECTIONS precedent)
```python
# SOURCE: services/analysis.py:59-67 (existing module constant style)
SLEPT_ON_TYPE_SECTIONS = [("Creatures", "Creature"), ...]
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/analysis.py` | UPDATE | Add `bulk` import; add `LEVEL_DEPTHS` / `DEFAULT_LEVEL` constants; extract `_type_and_sub_features`; rewrite `card_features` with `level` + `include_types` (cap-at-N otag rollup + type gate); thread both params through `compute_feature_stats`, `compute_feature_weights`, `score_breakdown`, `score_card`, `score_cards`; fix `partition_by_type` to read types toggle-independently; update module docstring. |

No new files; no new dependencies (`bulk` is already in the package).

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Import `bulk` + add level constants + note the dependency
- **File**: `services/analysis.py`
- **Action**: UPDATE
- **Implement**:
  - Add `from services import bulk` to the imports (after `from math import log`,
    [services/analysis.py:45-48](services/analysis.py)).
  - Below `_SUPERTYPES` ([services/analysis.py:52](services/analysis.py)) add the
    constants with a brief comment:
    ```python
    # Oracle-tag granularity (PRD: tag-granularity controls). The UI exposes names
    # only; each maps to a hierarchy depth (root = 1) used to CAP otag features.
    # Levels are restricted to 2-4 by design (depth 1 too coarse, 5-7 too sparse).
    LEVEL_DEPTHS: dict[str, int] = {"Broad": 2, "Balanced": 3, "Fine": 4}
    DEFAULT_LEVEL = "Balanced"
    ```
  - Update the module docstring's final line ("All functions here are pure: no I/O,
    no API calls.") to note that otag rollup now consults the pure `bulk` hierarchy
    lookups (`tag_depth` / `ancestors_at_depth`), which are deterministic over the
    already-loaded index — `analysis` itself still does no network/HTTP/file I/O.
- **Mirror**: `services/analysis.py:45-67` (import + constant style)
- **Validate**: `python -m py_compile services/analysis.py`

### Task 2: Extract `_type_and_sub_features` + make `partition_by_type` toggle-independent
- **File**: `services/analysis.py`
- **Action**: UPDATE
- **Implement**:
  - Add a private helper (place just above `card_features`):
    ```python
    def _type_and_sub_features(type_line: str) -> set[str]:
        """type:/sub: features from a (possibly split/DFC) type line. Pure.
        Single source of truth for type-line parsing, shared by card_features
        (gated by include_types) and partition_by_type (always — sectioning is
        independent of the scoring type toggle)."""
        feats: set[str] = set()
        for face in (type_line or "").split("//"):
            if "—" in face:
                left, right = face.split("—", 1)
            else:
                left, right = face, ""
            for word in left.split():
                if word not in _SUPERTYPES:
                    feats.add(f"type:{word}")
            for word in right.split():
                feats.add(f"sub:{word}")
        return feats
    ```
  - In `partition_by_type` ([services/analysis.py:289](services/analysis.py)),
    replace `types = {f for f in card_features(card) if f.startswith("type:")}`
    with:
    ```python
    types = {
        f for f in _type_and_sub_features(card.get("type_line", "") or "")
        if f.startswith("type:")
    }
    ```
    so per-type sectioning still works when scoring runs with `include_types=False`.
    (Leave the rest of `partition_by_type` unchanged — it stays pure, same dict refs.)
- **Mirror**: `services/analysis.py:91-101` (the parsing being extracted)
- **Validate**: `python -m py_compile services/analysis.py`

### Task 3: Rewrite `card_features` with `level` + `include_types` (cap-at-N rollup)
- **File**: `services/analysis.py`
- **Action**: UPDATE ([services/analysis.py:81-104](services/analysis.py))
- **Implement**:
  ```python
  def card_features(
      card: dict,
      level: str = DEFAULT_LEVEL,
      include_types: bool = False,
  ) -> list[str]:
      """
      Namespaced feature list for a card: oracle tags (capped to a granularity
      ``level``) plus, when ``include_types`` is True, its flat card types and
      subtypes.

      Oracle tags are collapsed to the chosen level's hierarchy depth N
      (LEVEL_DEPTHS; unknown level -> DEFAULT_LEVEL): a tag at depth <= N is kept
      as-is; a deeper tag is replaced by ALL of its level-N ancestors (the parent
      graph is a DAG, so there may be several) via bulk.ancestors_at_depth. No
      tagging is ever dropped. The level does NOT apply to type/subtype features,
      which are flat and emitted unchanged only when include_types is True
      (default off, so oracle-tag themes drive scoring).
      """
      feats: set[str] = set()
      if include_types:
          feats |= _type_and_sub_features(card.get("type_line", "") or "")
      depth = LEVEL_DEPTHS.get(level, LEVEL_DEPTHS[DEFAULT_LEVEL])
      for tag in card.get("otags", []) or []:
          if bulk.tag_depth(tag) <= depth:
              feats.add(f"otag:{tag}")
          else:
              for anc in bulk.ancestors_at_depth(tag, depth):
                  feats.add(f"otag:{anc}")
      return list(feats)
  ```
- **Mirror**: capping algorithm in PRD §6; `services/bulk.py:399-424` for the lookups
- **Validate**: `python -m py_compile services/analysis.py`

### Task 4: Thread `level` / `include_types` through `compute_feature_stats` + `compute_feature_weights`
- **File**: `services/analysis.py`
- **Action**: UPDATE ([services/analysis.py:107-202](services/analysis.py))
- **Implement**:
  - `compute_feature_stats(edhrec_cards, min_support=3, eps=1e-4, level=DEFAULT_LEVEL, include_types=False)`:
    change the inner call at [services/analysis.py:178](services/analysis.py) to
    `for feat in card_features(card, level=level, include_types=include_types):`.
  - `compute_feature_weights(edhrec_cards, min_support=3, eps=1e-4, level=DEFAULT_LEVEL, include_types=False)`:
    pass both through to `compute_feature_stats(...)` at
    [services/analysis.py:138-140](services/analysis.py)
    (`level=level, include_types=include_types`).
  - Add a one-line note to each docstring that otag features are capped to ``level``
    and type/subtype features are included only when ``include_types``.
- **Mirror**: `services/analysis.py:138-140` (kwarg pass-through)
- **Validate**: `python -m py_compile services/analysis.py`

### Task 5: Thread `level` / `include_types` through `score_breakdown`, `score_card`, `score_cards`
- **File**: `services/analysis.py`
- **Action**: UPDATE ([services/analysis.py:205-261](services/analysis.py))
- **Implement**:
  - `score_breakdown(card, weights, top_n=None, level=DEFAULT_LEVEL, include_types=False)`:
    change [services/analysis.py:218](services/analysis.py) to
    `contribs = [(f, weights[f]) for f in card_features(card, level=level, include_types=include_types) if f in weights]`.
  - `score_card(card, weights, level=DEFAULT_LEVEL, include_types=False)`:
    change [services/analysis.py:229](services/analysis.py) to
    `return sum(c for _, c in score_breakdown(card, weights, level=level, include_types=include_types))`.
  - `score_cards(color_pool, weights, exclude_names, level=DEFAULT_LEVEL, include_types=False)`:
    change the `score_card` call at [services/analysis.py:255](services/analysis.py)
    to `score = score_card(card, weights, level=level, include_types=include_types)`.
  - Keep all new params **after** the existing positional args so app.py's positional
    calls (`score_cards(color_pool, weights, exclude_names)`) still resolve.
- **Mirror**: `services/analysis.py:138-140` (kwarg pass-through)
- **Validate**: `python -m py_compile services/analysis.py`

### Task 6: Spot-check rollup, default fallback, and type toggle
- **File**: (no file change) — throwaway verification run with the venv interpreter
- **Action**: RUN
- **Implement**: confirm the cap-at-N behavior against a known chain
  (`tutor-creature-giant` depth 3, `cycle-ons-fetchland` depth 4 from #39's facts):
  ```bash
  ./.venv/Scripts/python.exe -c "from services import analysis as a; \
  card = {'type_line': 'Legendary Creature — Goblin', 'otags': ['tutor-creature-giant', 'cycle-ons-fetchland']}; \
  print('Broad   ', sorted(a.card_features(card, level='Broad'))); \
  print('Balanced', sorted(a.card_features(card, level='Balanced'))); \
  print('Fine    ', sorted(a.card_features(card, level='Fine'))); \
  print('bad->def', sorted(a.card_features(card, level='Nonsense')) == sorted(a.card_features(card))); \
  print('types on', sorted(a.card_features(card, include_types=True)))"
  ```
  - Expect: no `type:`/`sub:` entries unless `include_types=True`.
  - Expect: at **Balanced** (depth 3), `otag:tutor-creature-giant` is kept as-is
    (depth 3 ≤ 3) while `cycle-ons-fetchland` (depth 4) rolls up to its depth-3
    ancestor(s); at **Broad** (depth 2) both roll up to depth-2 ancestors.
  - Expect: `bad->def` prints `True` (unknown level == default Balanced output).
  - Expect: `types on` includes `type:Creature` and `sub:Goblin`.
- **Validate**: output matches expectations; no exception.

---

## Validation Sequence

```bash
# From the project root.
python -m py_compile services/analysis.py
flake8 .
# Confirm no circular import and the defaults still score:
./.venv/Scripts/python.exe -c "from services import analysis as a; \
cards = [{'edhrec_inclusion': 0.4, 'edhrec_synergy': 0.2, 'type_line': 'Creature — Goblin', 'otags': ['tutor-creature-giant']} for _ in range(3)]; \
w = a.compute_feature_weights(cards); print('weights ok:', isinstance(w, dict))"
```

Then the CLAUDE.md manual smoke test (`python app.py`, search "Atraxa, Praetors'
Voice") to confirm both sections + all seven type sections still render with the
new defaults — app.py is unchanged, so this verifies the default path: Balanced +
types-off, and that `partition_by_type` sections are **not** empty.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| `include_types=False` default empties the per-type sections (`partition_by_type` read types via `card_features`) | Task 2: `partition_by_type` reads types via `_type_and_sub_features`, independent of the scoring toggle. Smoke test asserts sections are non-empty. |
| Default change silently alters app.py scoring/display | Intended: PRD default is Balanced + types-off. Weights (`compute_feature_stats`) and scoring (`score_cards`) both default identically → internally consistent. app.py wiring of the controls is a separate issue; this issue only changes the defaults. |
| Circular import (`analysis` → `bulk`) | Verified `bulk.py` imports no `services` module ([services/bulk.py:21-29](services/bulk.py)); validation run imports `services.analysis` to confirm. |
| Purity contract (CLAUDE.md: analysis = no I/O) | Issue explicitly authorizes the `bulk` lookup dependency; lookups are pure over the loaded index. Documented in the module docstring (Task 1). |
| Tooltip/display features in app.py now drop types until UI issue wires `include_types` | Expected and in-scope-bounded: app.py/`filters.js` wiring is deferred to later issues per the PRD; not a regression that breaks rendering. |

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] `card_features(card, level=..., include_types=False)` caps otags at level N
      (depth ≤ N kept; depth > N → all level-N ancestors, keep-all/DAG-safe)
- [ ] `include_types=False` (default) omits all `type:`/`sub:`; `True` emits them
      unchanged; level does not apply to types/subtypes
- [ ] `level` / `include_types` threaded through `compute_feature_stats`,
      `compute_feature_weights`, `score_card`, `score_breakdown`, `score_cards`
- [ ] `LEVEL_DEPTHS` (Broad=2, Balanced=3, Fine=4) and `DEFAULT_LEVEL="Balanced"`
      are module constants (SCREAMING_SNAKE_CASE)
- [ ] Unknown/invalid level falls back to the default
- [ ] Functions stay pure (only new dependency = `bulk` pure lookups); no I/O in
      `analysis`
- [ ] `partition_by_type` per-type sections still populate under types-off default
- [ ] `flake8 .` clean; `python -m py_compile services/analysis.py` clean
- [ ] GitHub Issue #40 criteria satisfied
