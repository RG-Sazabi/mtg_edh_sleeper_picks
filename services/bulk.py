"""
Local Scryfall bulk-data store.

Downloads Scryfall's ``default_cards`` and ``oracle_tags`` bulk files to a local
``cache/`` directory (refreshed every 24h, stale-while-revalidate: a stale
file is served immediately while a background thread re-downloads) and serves
card attributes, oracle tags, and color-identity pools from in-memory indices.
This keeps a commander lookup to two EDHRec calls plus pure local computation —
no per-request Scryfall pagination and no cold-start re-download of the tag
index.

Format: Scryfall publishes bulk files only as gzip JSON-Lines
(``jsonl_download_uri``; one card / tag object per line). We keep the ``.jsonl.gz``
on disk as downloaded (~81 MB + ~6 MB) and stream-decompress it line by line with
the standard library, so parsing memory stays bounded by the indices we keep.

Concurrency: every index lives on one ``_Store`` object. A (re)build fills a new
``_Store`` in locals and publishes it with a single reference assignment, so a
reader that grabbed ``_store`` always sees one complete, consistent snapshot —
never a half-cleared index during a background refresh.

We use ``default_cards`` (every paper printing) rather than ``oracle_cards`` (one
printing per card) so we can pick the cleanest *standard* printing for each card.
``oracle_cards`` picks the "most recent recognizable" printing, which for ~12% of
cards is a borderless / full-art / Un-set / art-series version — often missing the
normal frame or rules text. ``_printing_penalty`` ranks printings so we render the
plain, legible version.

Bulk files are reference data (the full Scryfall catalog), not per-request cache,
and are intentionally persisted to disk. See CLAUDE.md "Scryfall Rate Limiting".
"""

import gzip
import json
import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

SCRYFALL_BASE = "https://api.scryfall.com"
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}

# cache/ lives at the project root (one level up from services/).
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
MAX_AGE_SECONDS = 24 * 60 * 60  # refresh bulk files once per day
# After a failed first load, don't retry the (blocking) download on every
# request — wait this long between attempts.
RETRY_AFTER_FAILURE_SECONDS = 5 * 60
# snapshot_info() flags the data as old once Scryfall's snapshot is this stale.
STALE_WARN_DAYS = 3
# Sanity floor for a build: fewer cards / tagged cards than this means the file
# or its schema is broken, and the result is never published.
_MIN_CARDS = 10_000
_MIN_TAGGED = 1_000

# Bulk "type" -> local filename (gzip JSON-Lines, kept compressed on disk).
_BULK_FILES = {
    "default_cards": "default-cards.jsonl.gz",
    "oracle_tags": "oracle-tags.jsonl.gz",
}
# Pre-JSONL filenames; deleted once their replacement downloads successfully.
_LEGACY_FILES = {
    "default_cards": "default-cards.json",
    "oracle_tags": "oracle-tags.json",
}
# Records Scryfall's `updated_at` per bulk kind (the snapshot's real age).
_META_FILE = "bulk-meta.json"

# Frame effects that signal a non-standard, "fancy" art treatment.
_FANCY_FRAME = {
    "showcase",
    "extendedart",
    "borderless",
    "inverted",
    "companion",
    "etched",
    "fullart",
}

# Layouts that are not real, deckable cards.
_EXCLUDED_LAYOUTS = {
    "token",
    "double_faced_token",
    "emblem",
    "art_series",
    "vanguard",
    "scheme",
    "planar",
}

logger = logging.getLogger(__name__)


class _Store:
    """
    One complete snapshot of every in-memory index. Treated as immutable once
    published; derived views (commander names, partner pools, tag ancestors)
    are memoized on the store itself so they can never mix two snapshots.
    """

    def __init__(
        self,
        cards: list[dict] | None = None,
        by_name: dict[str, dict] | None = None,
        by_oracle_id: dict[str, dict] | None = None,
        otag_index: dict[str, list[str]] | None = None,
        tag_parents: dict[str, list[str]] | None = None,
        tag_depth: dict[str, int] | None = None,
        as_of: str | None = None,
    ):
        self.cards = cards or []
        self.by_name = by_name or {}
        self.by_oracle_id = by_oracle_id or {}
        self.otag_index = otag_index or {}  # oracle_id -> [tag slug, ...]
        # Oracle-tag hierarchy, derived from oracle_tags `parent_ids`, slug-keyed
        # (slugs are unique in the bulk).
        self.tag_parents = tag_parents or {}  # slug -> parent slugs (DAG edges)
        self.tag_depth = tag_depth or {}  # slug -> depth (root = 1)
        self.as_of = as_of  # Scryfall `updated_at` of default_cards (ISO 8601)
        self.commander_names: list[str] | None = None
        self.partner_pools: dict[str, list[str]] | None = None
        self.ancestors: dict[tuple[str, int], frozenset[str]] = {}


# The live snapshot. Readers take one reference (``store = _store``) and use it
# for the whole call; rebuilds replace it with a single assignment.
_store = _Store()
_loaded = False
# Serializes the first load so a startup warm-up thread and an early request
# thread can't both download/parse the bulk files concurrently.
_load_lock = threading.Lock()
# Ensures at most one background refresh runs at a time.
_refresh_lock = threading.Lock()
# Load status for the UI: "empty" (not started) | "loading" | "ready" | "error".
_state = "empty"
_last_error = ""
_last_refresh_failed = False
_last_failed_attempt = 0.0


def _bulk_path(kind: str) -> str:
    return os.path.join(CACHE_DIR, _BULK_FILES[kind])


def _is_stale(path: str) -> bool:
    if not os.path.exists(path):
        return True
    return (time.time() - os.path.getmtime(path)) > MAX_AGE_SECONDS


def _read_meta() -> dict:
    try:
        with open(os.path.join(CACHE_DIR, _META_FILE), encoding="utf-8") as fh:
            meta = json.load(fh)
        return meta if isinstance(meta, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_meta(kind: str, updated_at: str | None) -> None:
    meta = _read_meta()
    meta[kind] = {"updated_at": updated_at, "downloaded_at": time.time()}
    try:
        with open(os.path.join(CACHE_DIR, _META_FILE), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
    except OSError as e:
        logger.error("Could not write %s: %s", _META_FILE, e)


def _download(kind: str) -> bool:
    """
    Download the current gzip JSON-Lines bulk file for ``kind``, streaming the
    compressed bytes straight to disk (never held in memory). The file is only
    swapped into place after a complete, gzip-valid download. Returns True on
    success; False on any failure (an existing file is left untouched).
    """
    path = _bulk_path(kind)
    tmp_path = path + ".tmp"
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        resp = requests.get(f"{SCRYFALL_BASE}/bulk-data", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        entry = next(
            (i for i in resp.json().get("data", []) if i.get("type") == kind), None
        )
        uri = (entry or {}).get("jsonl_download_uri")
        if not uri:
            logger.error("bulk-data entry %r has no jsonl_download_uri", kind)
            return False
        logger.info("Downloading Scryfall bulk %r from %s ...", kind, uri)
        written = 0
        with requests.get(uri, headers=HEADERS, stream=True, timeout=(15, 120)) as dl:
            dl.raise_for_status()
            expected = int(dl.headers.get("Content-Length") or 0)
            with open(tmp_path, "wb") as fh:
                for chunk in dl.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
                    written += len(chunk)
        if expected and written != expected:
            raise IOError(f"truncated download: {written} of {expected} bytes")
        with open(tmp_path, "rb") as fh:
            if fh.read(2) != b"\x1f\x8b":
                raise IOError("downloaded file is not gzip")
        os.replace(tmp_path, path)
        _write_meta(kind, entry.get("updated_at"))
        logger.info("Saved Scryfall bulk %r (%.1f MB) to %s", kind, written / 1e6, path)
        legacy = os.path.join(CACHE_DIR, _LEGACY_FILES[kind])
        if os.path.exists(legacy):
            try:
                os.remove(legacy)  # reclaim the old ~550 MB .json
            except OSError:
                pass
        return True
    except Exception as e:
        logger.error("_download(%r) failed: %s", kind, e)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False


def _iter_jsonl(path: str):
    """Yield one decoded object per line of a gzip JSON-Lines file. Streams:
    only the current line is ever held in memory. A truncated/corrupt file
    raises (EOFError / ValueError) so the caller can refuse the build."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _image_uri(card: dict) -> str:
    uri = (card.get("image_uris") or {}).get("normal", "")
    if uri:
        return uri
    faces = card.get("card_faces") or [{}]
    return (faces[0].get("image_uris") or {}).get("normal", "")


def _can_be_commander(card: dict) -> bool:
    """
    Standard ``is:commander`` heuristic: a legendary creature, or any card whose
    oracle text says it "can be your commander" (the planeswalkers/Backgrounds and
    similar). Reads the front- plus back-face oracle text so DFC cards qualify.
    """
    type_line = card.get("type_line", "")
    if "Legendary" in type_line and "Creature" in type_line:
        return True
    texts = [card.get("oracle_text", "")]
    texts += [face.get("oracle_text", "") for face in card.get("card_faces") or []]
    return any("can be your commander" in t.lower() for t in texts)


def _partner_kind(card: dict) -> str:
    """
    Classify a card's partner-pairing eligibility from its keywords, type line,
    and face oracle texts. One of:
      "partner"          — Partner / "Partner with X" (one shared pool per rules)
      "friends_forever"  — Friends forever
      "choose_background"— pairs with any Background
      "background"       — a Background (pairs with any "choose a background")
      ""                 — not partner-eligible
    Mutually exclusive in practice; checked in priority order. Backgrounds are
    detected by type line so they qualify even when not ``can_be_commander``.
    """
    kws = [k.lower() for k in (card.get("keywords") or [])]
    type_line = card.get("type_line", "")
    texts = " ".join(
        [card.get("oracle_text", "")]
        + [f.get("oracle_text", "") for f in card.get("card_faces") or []]
    ).lower()
    if any("friends forever" in k for k in kws) or "friends forever" in texts:
        return "friends_forever"
    if any("choose a background" in k for k in kws) or "choose a background" in texts:
        return "choose_background"
    if any(k.startswith("partner") for k in kws) or "\npartner" in ("\n" + texts):
        return "partner"
    if "Background" in type_line:
        return "background"
    return ""


def _trim(card: dict) -> dict:
    price_raw = (card.get("prices") or {}).get("usd")
    return {
        "name": card.get("name", ""),
        "oracle_id": card.get("oracle_id", ""),
        "type_line": card.get("type_line", ""),
        "color_identity": card.get("color_identity", []),
        "price_usd": float(price_raw) if price_raw else None,
        "rarity": card.get("rarity", ""),
        "image_uri": _image_uri(card),
        "edhrec_rank": card.get("edhrec_rank"),
        "commander_legal": (card.get("legalities") or {}).get("commander") == "legal",
        "layout": card.get("layout", ""),
        "can_be_commander": _can_be_commander(card),
        "partner_kind": _partner_kind(card),
    }


def _build_otag_index(
    path: str,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, int]]:
    """
    Stream the oracle-tags bulk into {oracle_id -> [tag slug, ...]} and, in the
    same pass, build the slug-keyed tag hierarchy (parent edges + depth) from
    each tag's ``parent_ids``. Hierarchy ids are translated to slugs (unique in
    the bulk) so the public accessors stay slug-based like the rest of the app.
    Returns ``(otag_index, tag_parents, tag_depth)``; raises on a corrupt file.
    """
    index: dict[str, list[str]] = defaultdict(list)
    id_to_slug: dict[str, str] = {}
    id_to_parents: dict[str, list[str]] = {}
    for tag_obj in _iter_jsonl(path):
        slug = tag_obj.get("slug", "")
        if not slug:
            continue
        tag_id = tag_obj.get("id", "")
        if tag_id:
            id_to_slug[tag_id] = slug
            id_to_parents[tag_id] = list(tag_obj.get("parent_ids") or [])
        for tagging in tag_obj.get("taggings") or []:
            oid = tagging.get("oracle_id", "")
            if oid:
                index[oid].append(slug)

    # Translate id-based parents to slug-based edges, dropping any parent id
    # not present in the file (dangling reference).
    parents: dict[str, list[str]] = {}
    for tag_id, slug in id_to_slug.items():
        parents[slug] = [
            id_to_slug[p] for p in id_to_parents.get(tag_id, []) if p in id_to_slug
        ]
    return dict(index), parents, _compute_tag_depths(parents)


def _compute_tag_depths(tag_parents: dict[str, list[str]]) -> dict[str, int]:
    """
    Return {slug -> shortest distance to a root, root = 1} from ``tag_parents``.
    The parent graph is a DAG that may contain cycles from bad data, so the
    recursion carries the current stack and treats a revisited node as a
    non-contributing root (returns 1 for that branch only). Results are
    memoized as they settle.
    """
    tag_depth: dict[str, int] = {}

    def _depth(slug: str, stack: frozenset[str]) -> int:
        if slug in tag_depth:
            return tag_depth[slug]
        if slug in stack:                 # cycle guard
            return 1
        parents = [p for p in tag_parents.get(slug, []) if p in tag_parents]
        d = 1 if not parents else 1 + min(
            _depth(p, stack | {slug}) for p in parents
        )
        tag_depth[slug] = d
        return d

    for slug in tag_parents:
        _depth(slug, frozenset())
    return tag_depth


def _printing_penalty(card: dict) -> int:
    """
    Lower is better. Ranks how "standard" a printing's art/frame is so we can
    prefer the plain, legible version of a card over showcase/borderless/full-art/
    Un-set/art-series printings (which often lack a normal frame or rules text).
    """
    p = 0
    if card.get("layout") == "art_series":
        p += 5000  # no rules text at all
    if card.get("textless"):
        p += 4000
    if card.get("set_type") in ("funny", "memorabilia"):
        p += 2000  # silver-border Un-cards, oversized/gold-border memorabilia
    if card.get("digital"):
        p += 1000  # prefer real paper scans
    border = card.get("border_color")
    if border == "borderless":
        p += 300
    elif border not in ("black", "white"):
        p += 800  # silver / gold
    if card.get("full_art"):
        p += 200
    p += 150 * len(set(card.get("frame_effects") or []) & _FANCY_FRAME)
    if card.get("promo"):
        p += 50
    if not _image_uri(card):
        p += 100000  # unusable — never pick if any alternative has art
    return p


def _build_card_index(
    path: str,
) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    """
    Stream the default-cards bulk (all printings) and keep, for each oracle id,
    the single cleanest standard printing — then build name/oracle_id lookups.
    Returns ``(cards, by_name, by_oracle_id)``; raises on a corrupt file.
    """
    # oracle_id -> (penalty, highres_rank, released_at, trimmed record)
    best: dict[str, tuple] = {}
    for raw in _iter_jsonl(path):
        oid = raw.get("oracle_id", "")
        if not oid:
            continue
        # Skip non-card products entirely (art series, tokens, emblems,
        # schemes, ...) so they never enter the name/oracle indices. Art
        # series cards in particular share a real card's name (e.g.
        # "Clearwater Pathway // Clearwater Pathway", type_line "Card //
        # Card") and would otherwise hijack the name lookup with artwork
        # that has no rules text.
        if raw.get("layout", "") in _EXCLUDED_LAYOUTS:
            continue
        pen = _printing_penalty(raw)
        highres = 0 if raw.get("highres_image") else 1
        released = raw.get("released_at", "") or ""
        cur = best.get(oid)
        # Prefer lower penalty; tie-break high-res scan, then newer print.
        if cur is None or (pen, highres, _neg(released)) < (
            cur[0],
            cur[1],
            _neg(cur[2]),
        ):
            best[oid] = (pen, highres, released, _trim(raw))

    cards: list[dict] = []
    by_name: dict[str, dict] = {}
    by_oracle_id: dict[str, dict] = {}
    for oid, (_, _, _, rec) in best.items():
        cards.append(rec)
        by_oracle_id[oid] = rec
        name = rec["name"]
        if name:
            by_name.setdefault(name, rec)
            # Index the front face of split/DFC cards ("A // B" -> "A").
            if " // " in name:
                by_name.setdefault(name.split(" // ", 1)[0], rec)
    return cards, by_name, by_oracle_id


def _neg(released: str) -> str:
    """Sort key helper: invert an ISO date string so newer sorts first (smaller)."""
    # Map each char to its complement so lexical ascending == date descending.
    return "".join(chr(255 - ord(ch)) for ch in released)


def _build_store() -> _Store:
    """
    Build a complete new ``_Store`` from the on-disk bulk files, entirely in
    locals (the live store is untouched). Raises if a file is missing, corrupt,
    or yields implausibly few records — an empty/broken store is never returned.
    A file that fails to parse is deleted so the next attempt re-downloads it.
    """
    built = {}
    for kind, builder in (
        ("oracle_tags", _build_otag_index),
        ("default_cards", _build_card_index),
    ):
        path = _bulk_path(kind)
        if not os.path.exists(path):
            raise RuntimeError(f"bulk file {kind!r} is missing")
        try:
            built[kind] = builder(path)
        except Exception as e:
            try:
                os.remove(path)
            except OSError:
                pass
            raise RuntimeError(f"bulk file {kind!r} is unreadable: {e}") from e
    otag_index, tag_parents, tag_depth_map = built["oracle_tags"]
    cards, by_name, by_oracle_id = built["default_cards"]
    if len(cards) < _MIN_CARDS or len(otag_index) < _MIN_TAGGED:
        raise RuntimeError(
            f"bulk build too small: {len(cards)} cards, {len(otag_index)} tagged"
        )
    as_of = (_read_meta().get("default_cards") or {}).get("updated_at")
    if not as_of:  # no sidecar (e.g. hand-copied file): fall back to file mtime
        mtime = os.path.getmtime(_bulk_path("default_cards"))
        as_of = datetime.fromtimestamp(mtime, timezone.utc).isoformat()
    return _Store(
        cards, by_name, by_oracle_id, otag_index, tag_parents, tag_depth_map, as_of
    )


def _publish(store: _Store) -> None:
    """Make ``store`` the live snapshot in one atomic reference swap."""
    global _store
    _store = store


def _refresh_stale(kinds: list[str]) -> None:
    """
    Background refresh: download the stale bulk files for ``kinds``, build a new
    store from them in locals, then swap it in. Any failure leaves the current
    (already served) snapshot in place and sets ``last_refresh_failed``.
    """
    global _last_refresh_failed
    if not _refresh_lock.acquire(blocking=False):
        return  # a refresh is already running
    try:
        results = {k: _download(k) for k in kinds}
        failed = [k for k, ok in results.items() if not ok]
        if len(failed) == len(results):
            _last_refresh_failed = True
            logger.error("Background bulk refresh failed; serving stale data")
            return
        try:
            new_store = _build_store()
        except Exception as e:
            _last_refresh_failed = True
            logger.error("Background bulk rebuild failed (serving old data): %s", e)
            return
        _publish(new_store)
        _last_refresh_failed = bool(failed)
        logger.info(
            "Background bulk refresh complete (%d cards); failed: %s",
            len(new_store.cards),
            ", ".join(failed) or "none",
        )
    finally:
        _refresh_lock.release()


def ensure_loaded() -> None:
    """
    Build all in-memory indices, downloading bulk files only when absent.
    Stale-but-present files are served immediately and refreshed in a background
    thread (stale-while-revalidate), so the daily re-download never blocks the
    first request of the day. Idempotent per process and thread-safe: concurrent
    callers (e.g. the startup warm-up thread and an early request) serialize on
    ``_load_lock`` so the build runs exactly once.

    If the first load fails (no network, broken file), the store stays empty and
    *unloaded* with status "error"; another attempt is made at most every
    ``RETRY_AFTER_FAILURE_SECONDS`` so requests don't each block on a download.
    """
    global _loaded, _state, _last_error, _last_failed_attempt
    if _loaded or _in_failure_backoff():
        return
    stale: list[str] = []
    with _load_lock:
        if _loaded or _in_failure_backoff():  # settled while we waited
            return
        _state = "loading"
        try:
            for kind in _BULK_FILES:
                path = _bulk_path(kind)
                if not os.path.exists(path):
                    # First run: nothing to serve, must block.
                    if not _download(kind):
                        raise RuntimeError(f"could not download bulk {kind!r}")
                elif _is_stale(path):
                    stale.append(kind)  # serve now, refresh in the background
            _publish(_build_store())
        except Exception as e:
            _state = "error"
            _last_error = str(e)
            _last_failed_attempt = time.time()
            logger.error("Scryfall bulk store failed to load: %s", e)
            return
        _state = "ready"
        _last_error = ""
        _loaded = True
    if stale:
        threading.Thread(target=_refresh_stale, args=(stale,), daemon=True).start()


def _in_failure_backoff() -> bool:
    return bool(_last_failed_attempt) and (
        time.time() - _last_failed_attempt < RETRY_AFTER_FAILURE_SECONDS
    )


def otags_for(oracle_id: str) -> list[str]:
    ensure_loaded()
    return _store.otag_index.get(oracle_id, [])


def tag_depth(slug: str) -> int:
    """Depth of an oracle-tag slug in the hierarchy (root = depth 1).
    Unknown slugs default to 1 (treated as already-coarse / kept as-is)."""
    ensure_loaded()
    return _store.tag_depth.get(slug, 1)


def ancestors_at_depth(slug: str, n: int) -> frozenset[str]:
    """All level-``n`` ancestors of ``slug`` (the parent graph is a DAG, so
    there may be several). Includes ``slug`` itself when its own depth == n.
    Cycle-guarded; memoized on the current store for cheap repeated per-card
    lookups during scoring (a new snapshot starts with an empty memo)."""
    ensure_loaded()
    store = _store
    key = (slug, n)
    cached = store.ancestors.get(key)
    if cached is not None:
        return cached
    result: set[str] = set()
    stack: list[str] = [slug]
    seen: set[str] = set()
    while stack:
        cur = stack.pop()
        if cur in seen:            # cycle / DAG re-convergence guard
            continue
        seen.add(cur)
        if store.tag_depth.get(cur, 1) == n:
            result.add(cur)
        stack.extend(store.tag_parents.get(cur, []))
    frozen = frozenset(result)
    store.ancestors[key] = frozen
    return frozen


def card_record(name: str) -> dict | None:
    """Return the trimmed record for a card by (front-face) name, or None."""
    ensure_loaded()
    return _store.by_name.get(name)


def color_identity_pool(color_identity: list[str]) -> list[dict]:
    """
    All commander-legal cards whose color identity is a subset of the given
    identity, sorted by EDHRec rank ascending (most-played first; None last).
    Pure in-memory filter — no network.
    """
    ensure_loaded()
    target = set(color_identity)
    pool = [
        rec
        for rec in _store.cards
        if rec["commander_legal"]
        and rec["layout"] not in _EXCLUDED_LAYOUTS
        and set(rec["color_identity"]) <= target
    ]
    pool.sort(key=lambda r: (r["edhrec_rank"] is None, r["edhrec_rank"] or 0))
    return pool


def commander_names() -> list[str]:
    """
    Sorted, deduped list of legal-commander names (front face only) for the
    search-bar autocomplete. Built once per process and memoized; pure in-memory.
    """
    ensure_loaded()
    store = _store
    if store.commander_names is None:
        names = {
            rec["name"].split(" // ", 1)[0]
            for rec in store.cards
            if rec["can_be_commander"] and rec["name"]
        }
        store.commander_names = sorted(names, key=str.casefold)
    return store.commander_names


def _partner_pools_built() -> dict[str, list[str]]:
    """
    {partner_kind -> sorted front-face names}. Built once per process and
    memoized. ``background`` cards are pooled by type regardless of
    ``can_be_commander`` (they are only ever offered as the second pick); all
    other kinds require ``commander_legal``.
    """
    ensure_loaded()
    store = _store
    if store.partner_pools is None:
        pools: dict[str, set[str]] = defaultdict(set)
        for rec in store.cards:
            kind = rec.get("partner_kind", "")
            if not kind or not rec["name"]:
                continue
            front = rec["name"].split(" // ", 1)[0]
            if kind == "background" or rec["commander_legal"]:
                pools[kind].add(front)
        store.partner_pools = {
            kind: sorted(names, key=str.casefold) for kind, names in pools.items()
        }
    return store.partner_pools


def legal_partners_for(name: str) -> list[str]:
    """
    Sorted legal partner names for a card, per its ``partner_kind``:
      partner -> other partners; friends_forever -> other friends_forever;
      choose_background -> all Backgrounds; background -> all choose-a-background
      commanders; otherwise []. The card itself is never in its own pool.
    """
    rec = card_record(name)
    if not rec:
        return []
    kind = rec.get("partner_kind", "")
    front = rec["name"].split(" // ", 1)[0]
    pools = _partner_pools_built()
    pool_key = {
        "partner": "partner",
        "friends_forever": "friends_forever",
        "choose_background": "background",
        "background": "choose_background",
    }.get(kind)
    if not pool_key:
        return []
    return [n for n in pools.get(pool_key, []) if n != front]


def partner_eligibility(name: str) -> dict:
    """``{'eligible': bool, 'kind': str, 'partners': [name, ...]}`` for a card."""
    rec = card_record(name)
    kind = rec.get("partner_kind", "") if rec else ""
    partners = legal_partners_for(name)
    return {"eligible": bool(partners), "kind": kind, "partners": partners}
