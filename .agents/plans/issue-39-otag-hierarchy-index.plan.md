# Plan: Oracle-Tag Hierarchy Index (depth + level-N ancestors)

## Summary
Add an in-memory oracle-tag hierarchy index to `services/bulk.py`, derived purely
from the `parent_ids` already present in the `oracle_tags` bulk file (no new
download). The index provides two public accessors — a tag's **depth** (root =
depth 1) and the set of **all** level-N ancestors of a tag (the graph is a DAG, so
a tag can have multiple parents). Depth is computed with a cycle-guarded DFS and
memoized; ancestor-at-depth resolution is `lru_cache`-backed so later per-card
scoring (issue #34/Phase 2) is a cheap cached set union over thousands of
color-pool cards. Everything is built inside `ensure_loaded()` and reset on index
reload, mirroring the existing `_commander_names` / `_partner_pools` memoized
views. This is Phase 1 (data foundation only) of the tag-granularity PRD — no
scoring, route, or UI changes.

## User Story
As a deck tuner, I want fine-grained tags rolled up instead of dropped, so that
cohesive themes stop falling below the support cutoff. (This issue lays the data
foundation: making tag depth and ancestry queryable.)

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY (data layer) |
| Complexity | MEDIUM |
| GitHub Issue | #39 |
| Systems Affected | `services/bulk.py` (bulk store / indexing only) |

---

## Data Facts (verified against `cache/oracle-tags.json`)

- Tag records carry: `id` (UUID), `slug` (unique — **0 duplicate slugs** across
  4488 tags), `parent_ids` (list of parent UUIDs), `child_ids`, `taggings`.
- Hierarchy is keyed by `id`, but the rest of the app keys oracle tags by **slug**
  (`_otag_index` maps `oracle_id -> [slug]`). So the public accessors take/return
  **slugs**; we translate `id`-based parents to slug-based parents at build time.
- 936 roots (no `parent_ids` → depth 1); **672 multi-parent tags** → confirmed DAG.
- Depth = shortest path to a root (`depth(t) = 1 + min(depth(p) for p in parents)`).
  Verified sample depths: `tutor`=1, `tutor-to`=2, `fetchland`=2,
  `tutor-to-battlefield`=3, `tutor-creature-giant`=3, `cycle-ons-fetchland`=4.
- Because the argmin parent on the shortest path has depth `depth(t)-1`
  recursively down to 1, **for every N in 1..depth(t) there is always ≥1 ancestor
  at exactly depth N** — so cap-at-N rollup never silently loses a tag.

---

## Patterns to Follow

### Memoized derived view + reset-on-reload
```python
# SOURCE: services/bulk.py:76-79 (module-level memo slots)
_commander_names: list[str] | None = None
_partner_pools: dict[str, list[str]] | None = None

# SOURCE: services/bulk.py:320-335 (ensure_loaded resets memo slots after rebuild)
global _loaded, _commander_names, _partner_pools
...
    if cards_path:
        _build_card_index(cards_path)
    # Indices were (re)built; drop any cached derived view so it rebuilds.
    _commander_names = None
    _partner_pools = None
    _loaded = True
```

### Streaming the oracle-tags bulk (extend this single pass)
```python
# SOURCE: services/bulk.py:204-220 (_build_otag_index — already reads each tag_obj)
def _build_otag_index(path: str) -> None:
    """Stream the oracle-tags bulk into {oracle_id -> [tag slug, ...]}."""
    index: dict[str, list[str]] = defaultdict(list)
    try:
        with open(path, "rb") as fh:
            for tag_obj in ijson.items(fh, "item"):
                slug = tag_obj.get("slug", "")
                if not slug:
                    continue
                for tagging in tag_obj.get("taggings", []):
                    oid = tagging.get("oracle_id", "")
                    if oid:
                        index[oid].append(slug)
    except Exception as e:
        logger.error("_build_otag_index failed: %s", e)
    _otag_index.clear()
    _otag_index.update(index)
```

### Public accessor calls ensure_loaded() first
```python
# SOURCE: services/bulk.py:338-340
def otags_for(oracle_id: str) -> list[str]:
    ensure_loaded()
    return _otag_index.get(oracle_id, [])
```

### Cycle-guard via a recursion stack (prototype validated during planning)
```python
def _depth(tag_id, stack):
    if tag_id in stack:        # cycle: stop contributing, treat as no parent
        return 1
    parents = [p for p in _raw_parents.get(tag_id, []) if p in _raw_parents]
    if not parents:
        return 1               # root
    return 1 + min(_depth(p, stack | {tag_id}) for p in parents)
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/bulk.py` | UPDATE | Add slug-keyed depth + parent maps, build them while streaming oracle-tags, add cycle-guarded depth computation, add `lru_cache`-backed level-N ancestor resolution, wire build+reset into `ensure_loaded()`, expose `tag_depth()` / `ancestors_at_depth()` accessors. |

No new files; no new dependencies (`functools` is stdlib).

---

## Design

**New module-level state** (near `services/bulk.py:67-79`):
- `_tag_depth: dict[str, int] = {}` — slug → depth (root = 1). Cleared/rebuilt on load.
- `_tag_parents: dict[str, list[str]] = {}` — slug → parent slugs (DAG edges).
- The ancestor accessor is a separate `@functools.lru_cache(maxsize=None)`-wrapped
  helper; its cache is cleared on reload (analogous to nulling the memo slots).

**Build path** — extend the existing single stream pass in `_build_otag_index` to
also collect `id -> slug` and `id -> parent_ids`; after the loop, translate parents
to slugs into `_tag_parents`, then compute `_tag_depth` for every slug with the
cycle-guarded DFS. Keeping it in the one place that already parses oracle-tags
avoids a second 18 MB stream (perf concern in the PRD/AC).

**`tag_depth(slug) -> int`** — `ensure_loaded()`, then `_tag_depth.get(slug, 1)`.
Unknown slugs default to depth 1 (kept as-is by the future cap algorithm → "no
signal silently lost"); in practice every otag slug is present in the hierarchy.

**`ancestors_at_depth(slug, n) -> frozenset[str]`** — `ensure_loaded()`, then a
cached BFS/DFS up the parent edges (cycle-guarded) collecting every reachable
**ancestor-or-self** whose `_tag_depth == n`. Returns a `frozenset` (hashable,
cache-friendly). When `tag_depth(slug) == n` the result is `{slug}` (self) — matches
the "a depth-2 tag returns itself at level 2" spot-check.

**Dependency order:** `_tag_parents` must be populated before `_tag_depth` is
computed; `_tag_depth` must exist before `ancestors_at_depth` can filter by depth.

| Risk | Mitigation |
|------|-----------|
| Cycle in parent graph → infinite recursion | DFS carries a `stack` set; a node already on the stack contributes no further (returns depth 1 for that branch). Same guard reused in the ancestor walk. |
| `parent_ids` referencing an id not in the file | Filter parents to ids present in the raw map before recursing (`if p in _raw_parents`). |
| `lru_cache` returns stale ancestors after a 24h bulk refresh/reload | Call `ancestors_at_depth.cache_clear()` in the `ensure_loaded()` reset block alongside the memo-slot resets. |
| Double-streaming the 18 MB tags file | Build the hierarchy in the same pass as `_build_otag_index` (one open/parse). |
| Slug collisions making slug-keyed depth ambiguous | Verified 0 duplicate slugs in the bulk; slug keying is safe. |

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Add imports + module-level hierarchy state
- **File**: `services/bulk.py`
- **Action**: UPDATE
- **Implement**:
  - Add `import functools` to the stdlib import block (near line 21-25).
  - Below the existing memo slots (after `services/bulk.py:79`), add:
    ```python
    # Oracle-tag hierarchy, derived from oracle_tags `parent_ids`. Slug-keyed
    # (slugs are unique in the bulk); rebuilt when indices reload.
    _tag_depth: dict[str, int] = {}      # slug -> depth (root = 1)
    _tag_parents: dict[str, list[str]] = {}  # slug -> parent slugs (DAG edges)
    ```
- **Mirror**: `services/bulk.py:67-79`
- **Validate**: `python -m py_compile services/bulk.py`

### Task 2: Capture the hierarchy while streaming oracle-tags
- **File**: `services/bulk.py`
- **Action**: UPDATE (`_build_otag_index`, lines 204-220)
- **Implement**:
  - While iterating `tag_obj`, also collect locals `id_to_slug: dict[str, str]` and
    `id_to_parents: dict[str, list[str]]` from `tag_obj["id"]`, `slug`, and
    `tag_obj.get("parent_ids", [])`.
  - After the loop (still inside the function, after `_otag_index.update(index)`),
    rebuild `_tag_parents`: for each id, map its parent ids to slugs via
    `id_to_slug` (dropping any parent id not present), keyed by the tag's own slug.
    Clear `_tag_parents` then update it.
  - Then call a new `_compute_tag_depths()` (Task 3).
  - Update the docstring to note it also builds the depth/parent hierarchy.
- **Mirror**: `services/bulk.py:204-220` (same stream loop, same clear+update idiom)
- **Validate**: `python -m py_compile services/bulk.py`

### Task 3: Cycle-guarded depth computation
- **File**: `services/bulk.py`
- **Action**: UPDATE (new private helper, place after `_build_otag_index`)
- **Implement**:
  - `def _compute_tag_depths() -> None:` — clears `_tag_depth`, then for every slug
    in `_tag_parents` computes its depth via a memoized, cycle-guarded recursion:
    ```python
    def _depth(slug: str, stack: frozenset[str]) -> int:
        if slug in _tag_depth:
            return _tag_depth[slug]
        if slug in stack:                 # cycle guard
            return 1
        parents = [p for p in _tag_parents.get(slug, []) if p in _tag_parents]
        d = 1 if not parents else 1 + min(
            _depth(p, stack | {slug}) for p in parents
        )
        _tag_depth[slug] = d              # memoize only off the recursion stack
        return d
    ```
    Note: only memoize results computed without hitting a cycle short-circuit on
    *this* slug; simplest correct form is to compute into a local then assign — but
    since cycles return 1 for the *revisited* node only (not the origin), the form
    above is safe. Iterate all slugs to fully populate `_tag_depth`.
- **Mirror**: cycle-guard prototype in "Patterns to Follow" above
- **Validate**: `python -m py_compile services/bulk.py`

### Task 4: Wire build + reset into ensure_loaded()
- **File**: `services/bulk.py`
- **Action**: UPDATE (`ensure_loaded`, lines 320-335)
- **Implement**:
  - The hierarchy is built inside `_build_otag_index` (Tasks 2-3), which
    `ensure_loaded` already calls when `tags_path` is truthy — confirm no extra
    call is needed there.
  - In the reset block (where `_commander_names = None` / `_partner_pools = None`),
    also clear the ancestor cache: `ancestors_at_depth.cache_clear()`.
  - `_tag_depth` / `_tag_parents` are cleared+rebuilt inside the build functions, so
    they do not need nulling here (mirrors how `_otag_index` is handled, not how the
    lazy memo slots are handled).
- **Mirror**: `services/bulk.py:320-335`
- **Validate**: `python -m py_compile services/bulk.py`

### Task 5: Public accessors
- **File**: `services/bulk.py`
- **Action**: UPDATE (add near `otags_for`, after line 340)
- **Implement**:
  ```python
  def tag_depth(slug: str) -> int:
      """Depth of an oracle-tag slug in the hierarchy (root = depth 1).
      Unknown slugs default to 1 (treated as already-coarse / kept as-is)."""
      ensure_loaded()
      return _tag_depth.get(slug, 1)


  @functools.lru_cache(maxsize=None)
  def ancestors_at_depth(slug: str, n: int) -> frozenset[str]:
      """All level-``n`` ancestors of ``slug`` (the parent graph is a DAG, so
      there may be several). Includes ``slug`` itself when its own depth == n.
      Cycle-guarded; cached for cheap repeated per-card lookups during scoring.
      Cache is cleared on index reload in ensure_loaded()."""
      ensure_loaded()
      result: set[str] = set()
      stack: list[str] = [slug]
      seen: set[str] = set()
      while stack:
          cur = stack.pop()
          if cur in seen:            # cycle / DAG re-convergence guard
              continue
          seen.add(cur)
          if _tag_depth.get(cur, 1) == n:
              result.add(cur)
          stack.extend(_tag_parents.get(cur, []))
      return frozenset(result)
  ```
  - Note: `ensure_loaded()` inside the cached function is cheap (early `_loaded`
    return) and keeps the accessor self-sufficient like `otags_for`.
- **Mirror**: `services/bulk.py:338-340` (ensure_loaded-first accessor idiom)
- **Validate**: `python -m py_compile services/bulk.py`

### Task 6: Spot-check the index against known chains
- **File**: (no file change) — throwaway verification run
- **Action**: RUN
- **Implement**: run with the venv interpreter and confirm output:
  ```bash
  ./.venv/Scripts/python.exe -c "from services import bulk; \
  print('depths', {s: bulk.tag_depth(s) for s in \
  ['tutor','tutor-to','fetchland','cycle-ons-fetchland','tutor-creature-giant']}); \
  print('anc cycle-ons-fetchland@2', bulk.ancestors_at_depth('cycle-ons-fetchland', 2)); \
  print('anc cycle-ons-fetchland@3', bulk.ancestors_at_depth('cycle-ons-fetchland', 3)); \
  print('depth-2 self', bulk.ancestors_at_depth('fetchland', 2))"
  ```
  - Expect: `tutor`=1, `tutor-to`=2, `fetchland`=2, `cycle-ons-fetchland`=4,
    `tutor-creature-giant`=3.
  - Expect `ancestors_at_depth('fetchland', 2)` to include `'fetchland'` itself
    (depth-2 tag returns itself at level 2).
  - Expect `ancestors_at_depth('cycle-ons-fetchland', 2)` to be non-empty and to
    contain `tutor-to`-level ancestors along its known chain.
- **Validate**: output matches the expected depths above; no exception/recursion error.

---

## Validation Sequence

```bash
# From the project root, using the venv interpreter for the runtime check.
python -m py_compile services/bulk.py
flake8 .
./.venv/Scripts/python.exe -c "from services import bulk; bulk.ensure_loaded(); \
print('hierarchy slugs:', len(bulk._tag_depth)); \
print('cycle-ons-fetchland depth:', bulk.tag_depth('cycle-ons-fetchland'))"
```

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] `{tag -> depth}` built from `parent_ids` (root = depth 1)
- [ ] `tag_depth(slug)` accessor returns a tag's depth
- [ ] `ancestors_at_depth(slug, n)` returns **all** level-N ancestors (DAG-aware),
      and the tag itself when its depth == n
- [ ] Traversal is cycle-guarded (depth DFS + ancestor walk both guard revisits)
- [ ] Built within `ensure_loaded()` and reset on reload (cache cleared alongside
      `_commander_names` / `_partner_pools`)
- [ ] Per-leaf → level-N resolution is memoized (`lru_cache`) for cheap repeated use
- [ ] No new download; derived only from the existing `oracle_tags` bulk
- [ ] `bulk.py` stays data/indexing only (no scoring logic)
- [ ] `flake8 .` clean; `python -m py_compile services/bulk.py` clean
- [ ] Spot-checks (Task 6) pass: `cycle-ons-fetchland` chain + depth-2-returns-self
- [ ] GitHub Issue #39 criteria satisfied
