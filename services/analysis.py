"""
Slept On scoring — feature-lift model.

Implements the card-scoring framework from Ferrone (2026), "Feature-Based Card
Scoring for Commander Recommendations". Instead of a raw oracle-tag overlap, we
score each *feature* (card type, subtype, or oracle tag) by how much the
commander's decks over- or under-use it relative to its color-identity baseline,
then sum those log-lifts across the features a candidate card carries.

For a commander X with color-identity baseline B(X):

    P_X(f) = avg inclusion  i_{c,X}      over recommended cards carrying feature f
    P_B(f) = avg baseline   i_{c,B(X)}   over recommended cards carrying feature f
    lift(f) = log( P_X(f) / P_B(f) )                                   (eq. 3)
    Score(c, X) = sum( lift(f) for f in features(c) )                  (eq. 4)

Key data trick (no extra network calls): EDHRec's *synergy* is defined as
inclusion minus the color-identity baseline inclusion, so

    i_{c,B(X)} = edhrec_inclusion - edhrec_synergy

and both fields already come from the commander page.

Deck-scoped scoring (issue #34)
-------------------------------
When the commander page is reached with a linked Archidekt deck, we tilt the
weights toward what *that build* over-uses without disturbing the color baseline.
A scoring-only ``forced_inclusion`` field (set by the route on deck cards) drives
the P_X term:

    incl_c = forced_inclusion if present else edhrec_inclusion  # deck cards -> 1.0
    base_c = edhrec_inclusion - edhrec_synergy                  # UNCHANGED baseline

Deck membership thus forces P_X(f) toward 1.0 for the features the deck carries,
raising their lift/weight, while P_B(f) stays the true color-identity baseline so
the lift stays meaningful. We deliberately do NOT overwrite the displayed
``edhrec_inclusion``: that would (a) corrupt ``base_c = inclusion - synergy`` and
(b) push deck cards past the inclusion-cap filter, hiding the very cards we mean to
keep visible. Cards without ``forced_inclusion`` behave exactly as before, so the
non-deck flow is unchanged.

All functions here are pure: no network/HTTP/file I/O, no API calls. The otag
rollup consults the pure ``bulk`` hierarchy lookups (``tag_depth`` /
``ancestors_at_depth``), which are deterministic over the already-loaded index —
``analysis`` itself still performs no network/HTTP/file I/O.
"""

import logging
from math import log

from services import bulk

logger = logging.getLogger(__name__)

# Supertypes are not discriminating features (almost every legendary scores the
# same), so we drop them and keep only the core card types as features.
_SUPERTYPES = {"Legendary", "Basic", "Snow", "World", "Ongoing", "Host", "Elite"}

# Oracle-tag granularity (PRD: tag-granularity controls). The UI exposes names
# only; each maps to a hierarchy depth (root = 1) used to CAP otag features.
# Levels are restricted to 2-4 by design (depth 1 too coarse, 5-7 too sparse).
LEVEL_DEPTHS: dict[str, int] = {"Broad": 2, "Balanced": 3, "Fine": 4}
DEFAULT_LEVEL = "Balanced"

# Ordered (label, card-type) pairs for the per-type Slept On sections. Creatures
# slot only under Creatures (an artifact/enchantment creature is a creature to a
# deckbuilder); other multi-type cards still appear under every matching label
# (e.g. an artifact land under both Artifacts and Lands). Types outside this list
# are absent from the sections but remain eligible for the overall Top 10.
SLEPT_ON_TYPE_SECTIONS = [
    ("Creatures", "Creature"),
    ("Instants", "Instant"),
    ("Sorceries", "Sorcery"),
    ("Enchantments", "Enchantment"),
    ("Artifacts", "Artifact"),
    ("Lands", "Land"),
    ("Planeswalkers", "Planeswalker"),
]


def normalize_name(name: str) -> str:
    """
    Canonical key for matching a card across EDHRec and Scryfall data:
    case-folded, front face only (split on " // "), surrounding whitespace
    stripped. Pure; used by both the EDHRec inclusion join and Slept On
    exclusion so a card present in the EDHRec data cannot also appear as a
    0%-inclusion Slept On pick.
    """
    return (name or "").split(" // ", 1)[0].strip().casefold()


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


def compute_feature_weights(
    edhrec_cards: list[dict],
    min_support: int = 3,
    eps: float = 1e-4,
) -> dict[str, float]:
    """
    Build {feature -> weighted log-lift} from the commander's recommended cards.

    For each recommended card we have:
        incl_c = i_{c,X}      = edhrec_inclusion
        base_c = i_{c,B(X)}   = edhrec_inclusion - edhrec_synergy   (clamped > 0)

    For each feature f, average over the recommended cards carrying it:
        P_X(f) = avg incl_c   (how often X's decks actually run cards with f)
        P_B(f) = avg base_c   (color-identity baseline for those cards)
        lift(f) = log(P_X / P_B)        # eq. 3 — over/under-representation

    The raw log-lift is *scale-invariant*: a niche feature carried by a few
    6%-inclusion cards gets the same lift as a core theme carried by 60%-inclusion
    cards. That let cards stacking many fringe features (e.g. planeswalkers with
    dozens of loyalty-ability tags) run away with the score. So we weight each
    feature's lift by its inclusion-weighted prevalence P_X(f):

        weight(f) = P_X(f) * lift(f) = P_X(f) * log( P_X(f) / P_B(f) )

    i.e. each feature's contribution is the pointwise KL-divergence term between
    the commander's deck and its color baseline. Features the commander both
    over-uses (high lift) *and* actually plays a lot (high P_X) dominate; fringe
    features barely move the needle. Features carried by fewer than ``min_support``
    cards are dropped outright to suppress small-sample noise.
    """
    return {s["feature"]: s["weight"] for s in compute_feature_stats(
        edhrec_cards, min_support=min_support, eps=eps
    )}


def compute_feature_stats(
    edhrec_cards: list[dict],
    min_support: int = 3,
    eps: float = 1e-4,
) -> list[dict]:
    """
    Full per-feature breakdown behind the scoring, for the diagnostics view.

    Returns a list of dicts (sorted by ``weight`` descending), one per qualifying
    feature::

        {"feature", "kind", "name", "support", "p_x", "p_b", "lift", "weight"}

    where ``kind`` is "type" | "sub" | "otag", ``support`` is the number of the
    commander's recommended cards carrying the feature, ``p_x``/``p_b`` are the
    average inclusion among the commander's decks vs. the color baseline, ``lift``
    is ``log(p_x / p_b)`` and ``weight`` is the inclusion-weighted contribution
    ``p_x * lift`` actually summed into each card's score.

    Deck-scoped scoring (issue #34): a card may carry a scoring-only
    ``forced_inclusion``; when present it (not ``edhrec_inclusion``) drives the
    P_X term, so deck cards push P_X toward 1.0 for their features. P_B is always
    the real ``edhrec_inclusion - edhrec_synergy`` baseline. Absent the override,
    behavior is identical to before. Still pure (no I/O).
    """
    incl_sum: dict[str, float] = {}
    base_sum: dict[str, float] = {}
    support: dict[str, int] = {}

    for card in edhrec_cards:
        incl = card.get("edhrec_inclusion", 0.0) or 0.0
        syn = card.get("edhrec_synergy", 0.0) or 0.0
        forced = card.get("forced_inclusion")
        incl_c = max(forced if forced is not None else incl, eps)
        base_c = max(incl - syn, eps)  # baseline inclusion for this card's color pool
        for feat in card_features(card):
            incl_sum[feat] = incl_sum.get(feat, 0.0) + incl_c
            base_sum[feat] = base_sum.get(feat, 0.0) + base_c
            support[feat] = support.get(feat, 0) + 1

    stats: list[dict] = []
    for feat, n in support.items():
        if n < min_support:
            continue
        p_x = incl_sum[feat] / n  # P_X(f): average inclusion among X's decks
        p_b = base_sum[feat] / n  # P_B(f): average inclusion in the color baseline
        lift = log(p_x / p_b)
        kind, _, name = feat.partition(":")
        stats.append({
            "feature": feat,
            "kind": kind,
            "name": name,
            "support": n,
            "p_x": p_x,
            "p_b": p_b,
            "lift": lift,
            "weight": p_x * lift,
        })
    stats.sort(key=lambda s: s["weight"], reverse=True)
    return stats


def score_breakdown(
    card: dict,
    weights: dict[str, float],
    top_n: int | None = None,
) -> list[tuple[str, float]]:
    """
    The per-feature contributions behind a card's Buzzword Score: a list of
    ``(feature, contribution)`` for each feature the card carries that has a
    weight, sorted by absolute contribution descending. ``top_n`` truncates to
    the strongest contributors (None = all). Single source of truth shared with
    ``score_card`` and mirrored by ``static/js/filters.js`` for the hover
    tooltip. Pure; no mutation.
    """
    contribs = [(f, weights[f]) for f in card_features(card) if f in weights]
    contribs.sort(key=lambda c: abs(c[1]), reverse=True)
    return contribs[:top_n] if top_n else contribs


def score_card(card: dict, weights: dict[str, float]) -> float:
    """
    Feature-lift score for a single card: the sum of the inclusion-weighted
    log-lifts (``weights``) of the features it carries. Features absent from
    ``weights`` (below ``min_support``) contribute nothing. Pure; no mutation.
    """
    return sum(c for _, c in score_breakdown(card, weights))


def score_cards(
    color_pool: list[dict],
    weights: dict[str, float],
    exclude_names: set[str],
) -> list[dict]:
    """
    Score each color-pool card as the sum of the inclusion-weighted log-lifts of
    the features it carries. Returns a new list sorted descending by score,
    keeping only positive-scoring cards (those that stack features the commander
    over-uses). Does not mutate input dicts.

    ``exclude_names`` is a set of names already passed through ``normalize_name``
    (e.g. the commander itself, which sits in its own color pool but is never a
    pick); each color-pool card is normalized the same way before the check.
    EDHRec-recommended cards are intentionally NOT excluded here — they stay in
    the candidate set so low-inclusion recommendations can surface as Slept On
    picks (flagged "in EDHRec list" by the route); the inclusion-cap filter is
    what drops the high-inclusion ones.
    """
    scored = []
    for card in color_pool:
        if normalize_name(card["name"]) in exclude_names:
            continue
        score = score_card(card, weights)
        if score > 0:
            card = dict(card)
            card["buzzword_score"] = score
            scored.append(card)
    scored.sort(key=lambda c: c["buzzword_score"], reverse=True)
    return scored


def partition_by_type(cards: list[dict], cap: int | None = None) -> list[dict]:
    """
    Bucket already-scored Slept On cards into the per-type sections.

    Returns one dict per entry in ``SLEPT_ON_TYPE_SECTIONS`` (stable order)::

        {"label": "Creatures", "type": "Creature", "cards": [...]}

    Creatures slot **only** under Creatures: a creature card (including an artifact
    creature or enchantment creature) is a creature to a deckbuilder, so it is kept
    out of the Artifacts/Enchantments/etc. sections, which hold only their
    non-creature members. A non-creature card still appears under every matching
    section (e.g. an artifact land lands in both Artifacts and Lands). Cards with
    none of the seven types appear in no section.

    ``cap`` bounds each section to at most that many cards (``None`` = unbounded).
    Because ``cards`` is iterated in order and buckets fill independently, passing a
    score-desc list yields score-desc sections, and capping keeps each section's
    top-``cap`` highest-scoring cards. Pure: the same card dicts are referenced (not
    copied) and never mutated.
    """
    buckets: dict[str, list[dict]] = {
        label: [] for label, _ in SLEPT_ON_TYPE_SECTIONS
    }
    for card in cards:
        types = {
            f for f in _type_and_sub_features(card.get("type_line", "") or "")
            if f.startswith("type:")
        }
        is_creature = "type:Creature" in types
        for label, type_name in SLEPT_ON_TYPE_SECTIONS:
            if f"type:{type_name}" not in types:
                continue
            # Creatures belong only in the Creatures section.
            if is_creature and type_name != "Creature":
                continue
            if cap is not None and len(buckets[label]) >= cap:
                continue
            buckets[label].append(card)
    return [
        {"label": label, "type": type_name, "cards": buckets[label]}
        for label, type_name in SLEPT_ON_TYPE_SECTIONS
    ]


def apply_inclusion_cap(slept_on: list[dict], cap: float) -> list[dict]:
    """
    Filter out cards whose edhrec_inclusion exceeds cap.
    Note: color-pool cards have edhrec_inclusion=0.0 by default (they are not in
    the EDHRec list), so this filter primarily catches borderline cross-reference cases.
    """
    return [c for c in slept_on if c.get("edhrec_inclusion", 0.0) <= cap]
