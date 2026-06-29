"""
Local Scryfall bulk-data store.

Downloads Scryfall's ``default_cards`` and ``oracle_tags`` bulk files to a local
``cache/`` directory (refreshed every 24h) and serves card attributes, oracle
tags, and color-identity pools from in-memory indices. This keeps a commander
lookup to two EDHRec calls plus pure local computation — no per-request Scryfall
pagination and no cold-start re-download of the tag index.

We use ``default_cards`` (every paper printing) rather than ``oracle_cards`` (one
printing per card) so we can pick the cleanest *standard* printing for each card.
``oracle_cards`` picks the "most recent recognizable" printing, which for ~12% of
cards is a borderless / full-art / Un-set / art-series version — often missing the
normal frame or rules text. ``_printing_penalty`` ranks printings so we render the
plain, legible version.

Bulk files are reference data (the full Scryfall catalog), not per-request cache,
and are intentionally persisted to disk. See CLAUDE.md "Scryfall Rate Limiting".
"""

import functools
import logging
import os
import threading
import time
from collections import defaultdict

import ijson
import requests

SCRYFALL_BASE = "https://api.scryfall.com"
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}

# cache/ lives at the project root (one level up from services/).
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
MAX_AGE_SECONDS = 24 * 60 * 60  # refresh bulk files once per day

# Bulk "type" -> local filename.
_BULK_FILES = {
    "default_cards": "default-cards.json",
    "oracle_tags": "oracle-tags.json",
}

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

# Module-level indices, built once per process.
_otag_index: dict[str, list[str]] = {}
_cards: list[dict] = []
_by_name: dict[str, dict] = {}
_by_oracle_id: dict[str, dict] = {}
_loaded = False
# Serializes index building so a startup warm-up thread and an early request
# thread can't both download/parse the ~540MB bulk files concurrently.
_load_lock = threading.Lock()
# Memoized sorted list of front-face commander names; rebuilt when indices reload.
_commander_names: list[str] | None = None
# Memoized {partner_kind -> sorted [front-face name]}; rebuilt when indices reload.
_partner_pools: dict[str, list[str]] | None = None
# Oracle-tag hierarchy, derived from oracle_tags `parent_ids`. Slug-keyed
# (slugs are unique in the bulk); rebuilt when indices reload.
_tag_depth: dict[str, int] = {}      # slug -> depth (root = 1)
_tag_parents: dict[str, list[str]] = {}  # slug -> parent slugs (DAG edges)


def _bulk_path(kind: str) -> str:
    return os.path.join(CACHE_DIR, _BULK_FILES[kind])


def _is_stale(path: str) -> bool:
    if not os.path.exists(path):
        return True
    return (time.time() - os.path.getmtime(path)) > MAX_AGE_SECONDS


def _ensure_fresh(kind: str) -> str | None:
    """
    Ensure the bulk file for ``kind`` exists on disk and is < MAX_AGE old.
    Streams the download to disk to avoid holding the whole file in memory.
    Returns the local path, or None on failure.
    """
    path = _bulk_path(kind)
    if not _is_stale(path):
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        resp = requests.get(f"{SCRYFALL_BASE}/bulk-data", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        download_uri = next(
            (
                item["download_uri"]
                for item in resp.json().get("data", [])
                if item.get("type") == kind
            ),
            None,
        )
        if not download_uri:
            logger.error("bulk-data entry %r not found on Scryfall", kind)
            return path if os.path.exists(path) else None
        logger.info("Downloading Scryfall bulk %r ...", kind)
        tmp_path = path + ".tmp"
        with requests.get(
            download_uri, headers=HEADERS, stream=True, timeout=300
        ) as dl:
            dl.raise_for_status()
            with open(tmp_path, "wb") as fh:
                for chunk in dl.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)
        os.replace(tmp_path, path)
        logger.info("Saved Scryfall bulk %r to %s", kind, path)
        return path
    except Exception as e:
        logger.error("_ensure_fresh(%r) failed: %s", kind, e)
        # Fall back to a stale-but-present file rather than failing hard.
        return path if os.path.exists(path) else None


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


def _build_otag_index(path: str) -> None:
    """
    Stream the oracle-tags bulk into {oracle_id -> [tag slug, ...]} and, in the
    same pass, build the slug-keyed tag hierarchy (parent edges + depth) from
    each tag's ``parent_ids``. Hierarchy ids are translated to slugs (unique in
    the bulk) so the public accessors stay slug-based like the rest of the app.
    """
    index: dict[str, list[str]] = defaultdict(list)
    id_to_slug: dict[str, str] = {}
    id_to_parents: dict[str, list[str]] = {}
    try:
        with open(path, "rb") as fh:
            for tag_obj in ijson.items(fh, "item"):
                slug = tag_obj.get("slug", "")
                if not slug:
                    continue
                tag_id = tag_obj.get("id", "")
                if tag_id:
                    id_to_slug[tag_id] = slug
                    id_to_parents[tag_id] = list(tag_obj.get("parent_ids", []))
                for tagging in tag_obj.get("taggings", []):
                    oid = tagging.get("oracle_id", "")
                    if oid:
                        index[oid].append(slug)
    except Exception as e:
        logger.error("_build_otag_index failed: %s", e)
    _otag_index.clear()
    _otag_index.update(index)

    # Translate id-based parents to slug-based edges, dropping any parent id
    # not present in the file (dangling reference).
    parents: dict[str, list[str]] = {}
    for tag_id, slug in id_to_slug.items():
        parents[slug] = [
            id_to_slug[p] for p in id_to_parents.get(tag_id, []) if p in id_to_slug
        ]
    _tag_parents.clear()
    _tag_parents.update(parents)
    _compute_tag_depths()


def _compute_tag_depths() -> None:
    """
    Populate ``_tag_depth`` (slug -> shortest distance to a root, root = 1) from
    ``_tag_parents``. The parent graph is a DAG that may contain cycles from bad
    data, so the recursion carries the current stack and treats a revisited node
    as a non-contributing root (returns 1 for that branch only). Results are
    memoized into ``_tag_depth`` as they settle.
    """
    _tag_depth.clear()

    def _depth(slug: str, stack: frozenset[str]) -> int:
        if slug in _tag_depth:
            return _tag_depth[slug]
        if slug in stack:                 # cycle guard
            return 1
        parents = [p for p in _tag_parents.get(slug, []) if p in _tag_parents]
        d = 1 if not parents else 1 + min(
            _depth(p, stack | {slug}) for p in parents
        )
        _tag_depth[slug] = d
        return d

    for slug in _tag_parents:
        _depth(slug, frozenset())


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


def _build_card_index(path: str) -> None:
    """
    Stream the default-cards bulk (all printings) and keep, for each oracle id,
    the single cleanest standard printing — then build name/oracle_id lookups.
    """
    # oracle_id -> (penalty, highres_rank, released_at, trimmed record)
    best: dict[str, tuple] = {}
    try:
        with open(path, "rb") as fh:
            for raw in ijson.items(fh, "item"):
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
    except Exception as e:
        logger.error("_build_card_index failed: %s", e)

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
    _cards.clear()
    _cards.extend(cards)
    _by_name.clear()
    _by_name.update(by_name)
    _by_oracle_id.clear()
    _by_oracle_id.update(by_oracle_id)


def _neg(released: str) -> str:
    """Sort key helper: invert an ISO date string so newer sorts first (smaller)."""
    # Map each char to its complement so lexical ascending == date descending.
    return "".join(chr(255 - ord(ch)) for ch in released)


def ensure_loaded() -> None:
    """
    Download (if stale) and build all in-memory indices. Idempotent per process
    and thread-safe: concurrent callers (e.g. the startup warm-up thread and an
    early request) serialize on ``_load_lock`` so the build runs exactly once.
    """
    global _loaded, _commander_names, _partner_pools
    if _loaded:
        return
    with _load_lock:
        if _loaded:  # another thread finished the build while we waited
            return
        cards_path = _ensure_fresh("default_cards")
        tags_path = _ensure_fresh("oracle_tags")
        if tags_path:
            _build_otag_index(tags_path)
        if cards_path:
            _build_card_index(cards_path)
        # Indices were (re)built; drop any cached derived view so it rebuilds.
        _commander_names = None
        _partner_pools = None
        _loaded = True


def otags_for(oracle_id: str) -> list[str]:
    ensure_loaded()
    return _otag_index.get(oracle_id, [])


def card_record(name: str) -> dict | None:
    """Return the trimmed record for a card by (front-face) name, or None."""
    ensure_loaded()
    return _by_name.get(name)


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
        for rec in _cards
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
    global _commander_names
    ensure_loaded()
    if _commander_names is None:
        names = {
            rec["name"].split(" // ", 1)[0]
            for rec in _cards
            if rec["can_be_commander"] and rec["name"]
        }
        _commander_names = sorted(names, key=str.casefold)
    return _commander_names


def _partner_pools_built() -> dict[str, list[str]]:
    """
    {partner_kind -> sorted front-face names}. Built once per process and
    memoized. ``background`` cards are pooled by type regardless of
    ``can_be_commander`` (they are only ever offered as the second pick); all
    other kinds require ``commander_legal``.
    """
    global _partner_pools
    ensure_loaded()
    if _partner_pools is None:
        pools: dict[str, set[str]] = defaultdict(set)
        for rec in _cards:
            kind = rec.get("partner_kind", "")
            if not kind or not rec["name"]:
                continue
            front = rec["name"].split(" // ", 1)[0]
            if kind == "background" or rec["commander_legal"]:
                pools[kind].add(front)
        _partner_pools = {
            kind: sorted(names, key=str.casefold) for kind, names in pools.items()
        }
    return _partner_pools


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
