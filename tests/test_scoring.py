"""Slept On scoring on the fixture commanders (offline)."""

import json
import os

import pytest

from services import analysis
from tests.helpers import FIXTURES, edhrec_data, score_page

GOLDEN = FIXTURES / "golden_top10_atraxa.json"
GOLDEN_NOTE = (
    "Atraxa Slept On Top 10 on the fixture data, default level, types off. "
    "Regenerate deliberately with: set UPDATE_GOLDEN=1 && .venv\\Scripts\\python "
    "-m pytest tests/test_scoring.py -k golden  (then review the diff)."
)

PAGES = [
    "atraxa-praetors-voice",
    "the-ur-dragon",
    "thrasios-triton-hero-tymna-the-weaver",
]


@pytest.mark.parametrize("slug", PAGES)
def test_enough_features_and_scored_cards(slug, loaded_bulk):
    cards, stats, slept_on = score_page(edhrec_data(slug))
    positive = [s for s in stats if s["weight"] > 0]
    assert len(stats) >= 40, f"only {len(stats)} features cleared min_support"
    assert len(positive) >= 15, f"only {len(positive)} features carry weight"
    assert all(s["support"] >= 3 for s in stats)
    assert len(slept_on) >= 300, f"only {len(slept_on)} cards scored > 0"
    scores = [c["buzzword_score"] for c in slept_on]
    assert scores == sorted(scores, reverse=True)
    # Sane band: ~1 for a low-synergy commander (Atraxa), 5-8 for highly
    # synergistic ones (Ur-Dragon, Thrasios+Tymna) on today's data.
    assert 0.05 < scores[0] < 15, scores[0]
    # Every EDHRec card resolved to a type line + tags from the sample store.
    assert sum(1 for c in cards if c["otags"]) >= 0.9 * len(cards)


@pytest.mark.parametrize("slug", PAGES)
def test_commanders_excluded_from_own_picks(slug, loaded_bulk):
    data = edhrec_data(slug)
    _, _, slept_on = score_page(data)
    names = {analysis.normalize_name(c["name"]) for c in slept_on}
    for cm in data["card"].get("names") or [data["card"]["name"]]:
        assert analysis.normalize_name(cm) not in names, cm


def test_picks_exclude_undeckable_cards(loaded_bulk):
    _, _, slept_on = score_page(edhrec_data("the-ur-dragon"))
    names = {c["name"] for c in slept_on}
    for bad in [
        "Urza, Planeswalker",
        "Brisela, Voice of Nightmares",
        "Forest",
        "Island",
        "Wastes",
    ]:
        assert bad not in names
    assert not any(c["type_line"] == "Stickers" for c in slept_on)


def test_level_and_types_change_the_feature_set(loaded_bulk):
    cards, base, _ = score_page(edhrec_data("atraxa-praetors-voice"))
    broad = analysis.compute_feature_stats(cards, level="Broad")
    typed = analysis.compute_feature_stats(cards, include_types=True)
    assert {s["feature"] for s in broad} != {s["feature"] for s in base}
    assert any(s["kind"] in ("type", "sub") for s in typed)
    assert not any(s["kind"] in ("type", "sub") for s in base)


def test_forced_inclusion_tilts_weights(loaded_bulk):
    cards, base, _ = score_page(edhrec_data("atraxa-praetors-voice"))
    lands = [c for c in cards if "Land" in c["type_line"]]
    for c in lands:
        c["forced_inclusion"] = 1.0
    tilted = analysis.compute_feature_stats(cards)
    base_px = {s["feature"]: s["p_x"] for s in base}
    raised = [
        s
        for s in tilted
        if s["feature"] in base_px and s["p_x"] > base_px[s["feature"]]
    ]
    assert raised
    # The displayed inclusion is never overwritten.
    assert all(c["edhrec_inclusion"] < 1.0 for c in lands)


def _top10(loaded_bulk):
    _, _, slept_on = score_page(edhrec_data("atraxa-praetors-voice"))
    return [
        {"name": c["name"], "score": round(c["buzzword_score"], 6)}
        for c in slept_on[:10]
    ]


def test_golden_top10_atraxa(loaded_bulk):
    top10 = _top10(loaded_bulk)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(
            json.dumps(
                {"_note": GOLDEN_NOTE, "top10": top10}, indent=2, ensure_ascii=False
            )
            + "\n",
            encoding="utf-8",
        )
        pytest.skip("golden Top 10 regenerated; review the diff")
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["top10"]
    assert [c["name"] for c in top10] == [c["name"] for c in golden]
    for got, want in zip(top10, golden):
        assert got["score"] == pytest.approx(want["score"], abs=1e-5), got["name"]
