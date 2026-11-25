"""Local Scryfall bulk store on the gzip JSON-Lines sample (offline)."""

import gzip
import json
import os

import pytest

from services import bulk, scryfall
from tests.conftest import FakeResponse, copy_bulk_fixtures
from tests.helpers import BULK_FIXTURES, load_json, raw_fixture_cards

LISTING = load_json("scryfall_bulk_data.json")


def _listing_uri(kind: str) -> str:
    entry = next(e for e in LISTING["data"] if e["type"] == kind)
    return entry["jsonl_download_uri"]


def _serve_bulk_downloads(fake_http) -> None:
    """Route both jsonl_download_uri URLs from the listing to the sample files."""
    for kind, fname in bulk._BULK_FILES.items():
        content = (BULK_FIXTURES / fname).read_bytes()
        fake_http.routes[_listing_uri(kind)] = FakeResponse(
            content=content, headers={"Content-Length": str(len(content))}
        )


def _write_gzip_lines(path, lines) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("".join(line + "\n" for line in lines))


# ------------------------------------------------------------- loading


def test_sample_loads_from_gzip_jsonl(empty_bulk):
    copy_bulk_fixtures(empty_bulk)
    bulk.ensure_loaded()
    info = bulk.snapshot_info()
    assert info["state"] == "ready"
    assert bulk._loaded is True
    assert info["as_of_date"] == "2026-11-25"  # from bulk-meta.json updated_at
    assert info["card_count"] > 3000
    assert len(bulk._store.otag_index) > 3000
    assert bulk.card_record("Sol Ring")["type_line"] == "Artifact"
    assert "mana-rock" in bulk.otags_for(bulk.card_record("Sol Ring")["oracle_id"])
    assert bulk.tag_depth("mana-rock") > 1  # hierarchy built from parent_ids


def test_first_run_downloads_from_jsonl_download_uri(empty_bulk, fake_http):
    """Fresh install: both files come from the listing's jsonl_download_uri."""
    _serve_bulk_downloads(fake_http)
    bulk.ensure_loaded()
    assert bulk.snapshot_info()["state"] == "ready"
    assert _listing_uri("default_cards") in fake_http.calls
    assert _listing_uri("oracle_tags") in fake_http.calls
    meta = json.loads((empty_bulk / "bulk-meta.json").read_text())
    entry = next(e for e in LISTING["data"] if e["type"] == "default_cards")
    assert meta["default_cards"]["updated_at"] == entry["updated_at"]


def test_download_reads_jsonl_uri_and_removes_legacy_file(empty_bulk, fake_http):
    _serve_bulk_downloads(fake_http)
    legacy = empty_bulk / "default-cards.json"
    legacy.write_text("[]")
    assert bulk._download("default_cards") is True
    assert fake_http.calls == [
        "https://api.scryfall.com/bulk-data",
        _listing_uri("default_cards"),
    ]
    saved = (empty_bulk / "default-cards.jsonl.gz").read_bytes()
    assert saved == (BULK_FIXTURES / "default-cards.jsonl.gz").read_bytes()
    assert not legacy.exists()
    assert not (empty_bulk / "default-cards.jsonl.gz.tmp").exists()


def test_listing_without_jsonl_uri_fails_safely(empty_bulk, fake_http):
    listing = load_json("scryfall_bulk_data.json")
    for entry in listing["data"]:
        entry["download_uri"] = entry.pop("jsonl_download_uri").replace(
            ".jsonl.gz", ".json"
        )
    fake_http.routes["https://api.scryfall.com/bulk-data"] = FakeResponse(
        payload=listing
    )
    existing = empty_bulk / "default-cards.jsonl.gz"
    existing.write_bytes(b"old")
    assert bulk._download("default_cards") is False
    assert existing.read_bytes() == b"old"


def test_truncated_download_is_rejected(empty_bulk, fake_http):
    _serve_bulk_downloads(fake_http)
    resp = fake_http.routes[_listing_uri("default_cards")]
    resp.headers["Content-Length"] = str(len(resp.content) + 1000)
    existing = empty_bulk / "default-cards.jsonl.gz"
    existing.write_bytes(b"old")
    assert bulk._download("default_cards") is False
    assert existing.read_bytes() == b"old"
    assert not (empty_bulk / "default-cards.jsonl.gz.tmp").exists()


def test_non_gzip_download_is_rejected(empty_bulk, fake_http):
    fake_http.routes[_listing_uri("default_cards")] = FakeResponse(
        content=b"<html>error</html>", headers={}
    )
    assert bulk._download("default_cards") is False
    assert not (empty_bulk / "default-cards.jsonl.gz").exists()


# ----------------------------------------------- refusing a broken build


def test_empty_build_is_never_published(empty_bulk):
    _write_gzip_lines(empty_bulk / "default-cards.jsonl.gz", [])
    _write_gzip_lines(empty_bulk / "oracle-tags.jsonl.gz", [])
    before = bulk._store
    bulk.ensure_loaded()
    info = bulk.snapshot_info()
    assert info["state"] == "error"
    assert info["warn"] is True
    assert "too small" in info["error"]
    assert bulk._loaded is False
    assert bulk._store is before and bulk._store.cards == []


def test_failed_first_load_is_not_retried_on_every_request(empty_bulk, monkeypatch):
    calls = []
    monkeypatch.setattr(
        bulk,
        "_build_store",
        lambda: calls.append(1) or (_ for _ in ()).throw(RuntimeError("boom")),
    )
    copy_bulk_fixtures(empty_bulk)
    bulk.ensure_loaded()
    bulk.ensure_loaded()
    bulk.commander_names()
    assert calls == [1]
    assert bulk.snapshot_info()["state"] == "error"


def test_sample_rejected_at_production_floor(empty_bulk, monkeypatch):
    """The real floor (10k cards) rejects a build as small as the sample."""
    monkeypatch.setattr(bulk, "_MIN_CARDS", 10_000)
    copy_bulk_fixtures(empty_bulk)
    bulk.ensure_loaded()
    assert bulk.snapshot_info()["state"] == "error"
    assert bulk._store.cards == []


def test_truncated_file_is_refused_and_deleted(empty_bulk):
    copy_bulk_fixtures(empty_bulk)
    path = empty_bulk / "default-cards.jsonl.gz"
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    bulk.ensure_loaded()
    info = bulk.snapshot_info()
    assert info["state"] == "error" and "unreadable" in info["error"]
    assert bulk._store.cards == []
    assert not path.exists()  # deleted so the next attempt re-downloads it


def test_failed_refresh_keeps_serving_previous_snapshot(
    loaded_bulk, monkeypatch, tmp_path
):
    good = bulk._store
    _write_gzip_lines(tmp_path / "default-cards.jsonl.gz", ['{"oracle_id": "x"}'])
    _write_gzip_lines(tmp_path / "oracle-tags.jsonl.gz", [])
    monkeypatch.setattr(bulk, "_download", lambda kind: True)
    bulk._refresh_stale(["default_cards", "oracle_tags"])
    assert bulk._store is good
    info = bulk.snapshot_info()
    assert info["last_refresh_failed"] is True and info["warn"] is True


def test_snapshot_info_never_loads(empty_bulk, monkeypatch):
    monkeypatch.setattr(
        bulk, "ensure_loaded", lambda: pytest.fail("snapshot_info must not load")
    )
    info = bulk.snapshot_info()
    assert info["state"] == "empty" and info["as_of_date"] is None


# --------------------------------------------------- pool and lookups

POOL_EXCLUDED = [
    "Urza, Planeswalker",  # meld result
    "Brisela, Voice of Nightmares",  # meld result
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    "Wastes",
    "Snow-Covered Forest",
]


def _sticker_sheets():
    return sorted(
        {r["name"] for r in raw_fixture_cards() if r.get("type_line") == "Stickers"}
    )


def test_pool_excludes_meld_results_stickers_and_basics(loaded_bulk):
    pool = {r["name"] for r in bulk.color_identity_pool(list("WUBRG"))}
    assert len(pool) > 2500
    stickers = _sticker_sheets()
    assert stickers
    for name in POOL_EXCLUDED + stickers:
        assert name not in pool, name
        assert bulk.card_record(name) is not None, f"{name} should still resolve"
    for part in [
        "Urza, Lord Protector",
        "The Mightstone and Weakstone",
        "Gisela, the Broken Blade",
        "Bruna, the Fading Light",
    ]:
        assert part in pool, part
    assert not any(
        "Basic" in r["type_line"].split("—")[0]
        for r in bulk.color_identity_pool(list("WUBRG"))
    )


def test_pool_respects_color_identity(loaded_bulk):
    pool = bulk.color_identity_pool(["G"])
    assert pool and all(set(r["color_identity"]) <= {"G"} for r in pool)
    ranks = [r["edhrec_rank"] for r in pool if r["edhrec_rank"] is not None]
    assert ranks == sorted(ranks)


def test_commander_names(loaded_bulk):
    names = set(bulk.commander_names())
    for name in [
        "Atraxa, Praetors' Voice",
        "The Ur-Dragon",
        "Tymna the Weaver",
        "Esika, God of the Tree",
        "Grist, the Hunger Tide",
        "Hearthhull, the Worldseed",
        "Lim-Dûl the Necromancer",
        "Urza, Lord Protector",
        "Gisela, the Broken Blade",
    ]:
        assert name in names, name
    for name in [
        "Urza, Planeswalker",
        "Brisela, Voice of Nightmares",
        "Esika, God of the Tree // The Prismatic Bridge",
        "Sol Ring",
    ]:
        assert name not in names, name
    assert not any(n.startswith("A-") for n in names)


def test_double_faced_commander_resolves_by_front_face(loaded_bulk):
    rec = bulk.card_record("Esika, God of the Tree")
    assert rec is not None
    assert rec["name"] == "Esika, God of the Tree // The Prismatic Bridge"
    assert rec["can_be_commander"]
    assert scryfall.get_card_details("Esika, God of the Tree")["image_uri"]


def test_partner_pools(loaded_bulk):
    assert bulk.legal_partners_for("Pir, Imaginative Rascal") == [
        "Toothy, Imaginary Friend"
    ]
    assert bulk.legal_partners_for("Toothy, Imaginary Friend") == [
        "Pir, Imaginative Rascal"
    ]
    elig = bulk.partner_eligibility("Thrasios, Triton Hero")
    assert elig["eligible"] and elig["kind"] == "partner"
    assert "Tymna the Weaver" in elig["partners"]
    assert "Thrasios, Triton Hero" not in elig["partners"]
    assert "Pir, Imaginative Rascal" not in elig["partners"]
    assert bulk.partner_eligibility("Atraxa, Praetors' Voice")["eligible"] is False


# ------------------------------------------------- price and rarity facts


def _expected_facts():
    """Per oracle id: cheapest playable-paper USD and whether any is common,
    computed independently from the raw fixture printings."""
    prices, common = {}, set()
    for raw in raw_fixture_cards():
        if not bulk._is_playable_paper(raw):
            continue
        oid = raw["oracle_id"]
        usd = (raw.get("prices") or {}).get("usd")
        if usd and (oid not in prices or float(usd) < prices[oid]):
            prices[oid] = float(usd)
        if raw.get("rarity") == "common":
            common.add(oid)
    return prices, common


def test_price_is_cheapest_paper_printing(loaded_bulk):
    prices, _ = _expected_facts()
    for rec in bulk._store.cards:
        assert rec["price_usd"] == prices.get(rec["oracle_id"]), rec["name"]
    for name in [
        "Mana Confluence",
        "Boros Charm",
        "Siege-Gang Commander",
        "Blasphemous Act",
    ]:
        assert bulk.card_record(name)["price_usd"] is not None, name


def test_unpriced_display_printing_still_gets_a_price(loaded_bulk):
    """Tundra's cleanest printing has no USD price; a cheaper paper one does."""
    raws = [r for r in raw_fixture_cards() if r["name"] == "Tundra"]
    assert len(raws) >= 2
    best = min(
        raws,
        key=lambda r: (
            bulk._printing_penalty(r),
            0 if r.get("highres_image") else 1,
            bulk._neg(r.get("released_at", "")),
        ),
    )
    assert not (best.get("prices") or {}).get("usd")
    rec = bulk.card_record("Tundra")
    assert rec["image_uri"] == bulk._image_uri(best)  # displayed printing unchanged
    assert rec["price_usd"] is not None


def test_ever_common(loaded_bulk):
    _, common = _expected_facts()
    mismatched = 0
    for rec in bulk._store.cards:
        assert rec["ever_common"] == (rec["oracle_id"] in common), rec["name"]
        if rec["ever_common"] and rec["rarity"] != "common":
            mismatched += 1
    assert mismatched > 0, "sample should hold a non-common printing of a common"
    details = scryfall.get_card_details("Golgari Signet")
    assert details["ever_common"] is True


def test_no_real_cache_dir_in_tests(loaded_bulk):
    real_cache = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache"
    )
    assert os.path.abspath(bulk.CACHE_DIR) != os.path.abspath(real_cache)
