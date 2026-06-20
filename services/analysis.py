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

All functions here are pure: no I/O, no API calls.
"""

import logging
from math import log

logger = logging.getLogger(__name__)

# Supertypes are not discriminating features (almost every legendary scores the
# same), so we drop them and keep only the core card types as features.
_SUPERTYPES = {"Legendary", "Basic", "Snow", "World", "Ongoing", "Host", "Elite"}


def card_features(card: dict) -> list[str]:
    """
    Namespaced feature list for a card: types, subtypes, and oracle tags.

    Example "Legendary Creature — Phyrexian Horror" with otags ["proliferate"]
    -> ["type:Creature", "sub:Phyrexian", "sub:Horror", "otag:proliferate"].
    Handles split/DFC type lines ("... // ...") by unioning both faces.
    """
    feats: set[str] = set()
    type_line = card.get("type_line", "") or ""
    for face in type_line.split("//"):
        # type_line format: "<supertypes> <types> — <subtypes>"
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
    """
    incl_sum: dict[str, float] = {}
    base_sum: dict[str, float] = {}
    support: dict[str, int] = {}

    for card in edhrec_cards:
        incl = card.get("edhrec_inclusion", 0.0) or 0.0
        syn = card.get("edhrec_synergy", 0.0) or 0.0
        incl_c = max(incl, eps)
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


def score_card(card: dict, weights: dict[str, float]) -> float:
    """
    Feature-lift score for a single card: the sum of the inclusion-weighted
    log-lifts (``weights``) of the features it carries. Features absent from
    ``weights`` (below ``min_support``) contribute nothing. Pure; no mutation.
    """
    return sum(weights[f] for f in card_features(card) if f in weights)


def score_cards(
    color_pool: list[dict],
    weights: dict[str, float],
    edhrec_card_names: set[str],
) -> list[dict]:
    """
    Score each color-pool card not already in the EDHRec list as the sum of the
    inclusion-weighted log-lifts of the features it carries. Returns a new list
    sorted descending by score, keeping only positive-scoring cards (those that
    stack features the commander over-uses). Does not mutate input dicts.
    """
    scored = []
    for card in color_pool:
        if card["name"] in edhrec_card_names:
            continue
        score = score_card(card, weights)
        if score > 0:
            card = dict(card)
            card["buzzword_score"] = score
            scored.append(card)
    scored.sort(key=lambda c: c["buzzword_score"], reverse=True)
    return scored


def apply_inclusion_cap(slept_on: list[dict], cap: float) -> list[dict]:
    """
    Filter out cards whose edhrec_inclusion exceeds cap.
    Note: color-pool cards have edhrec_inclusion=0.0 by default (they are not in
    the EDHRec list), so this filter primarily catches borderline cross-reference cases.
    """
    return [c for c in slept_on if c.get("edhrec_inclusion", 0.0) <= cap]
