"""
Live canary: the same contract assertions against the real services.

Deselected by default (it needs the network and depends on third-party data).
Run it deliberately, e.g. after an upstream change is suspected:

    .venv\\Scripts\\python -m pytest -m live

Makes four requests: EDHRec Atraxa and The Ur-Dragon, Archidekt deck 1727139,
and the Scryfall /bulk-data listing.
"""

import time
from datetime import datetime, timezone

import pytest
import requests

from services import archidekt, bulk, edhrec
from tests.helpers import assert_edhrec_page_contract

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def _polite():
    yield
    time.sleep(1.0)  # space out requests to third-party services


@pytest.mark.parametrize(
    "slug,commanders",
    [
        ("atraxa-praetors-voice", ["Atraxa, Praetors' Voice"]),
        ("the-ur-dragon", ["The Ur-Dragon"]),
    ],
)
def test_edhrec_live_contract(slug, commanders):
    data, err = edhrec.fetch_commander_scope(slug)
    assert err is None, f"EDHRec fetch failed: {err}"
    assert edhrec.served_scope(data) == ("", "")
    assert_edhrec_page_contract(data, commanders)
    assert edhrec.featured_sections_from_data(data), "no featured rows"
    assert edhrec.available_tags_from_data(data), "no theme tags"


def test_archidekt_live_deck():
    deck = archidekt.get_deck("1727139")
    assert deck is not None, "Archidekt fetch failed"
    assert deck["commander_names"] == ["Thrasios, Triton Hero", "Tymna the Weaver"]
    # A user's live deck can be edited; it was exactly 100 when recorded.
    assert 95 <= len(deck["card_names"]) <= 101, len(deck["card_names"])


def test_scryfall_bulk_listing():
    resp = requests.get(
        f"{bulk.SCRYFALL_BASE}/bulk-data", headers=bulk.HEADERS, timeout=15
    )
    resp.raise_for_status()
    entries = {e.get("type"): e for e in resp.json().get("data", [])}
    for kind in bulk._BULK_FILES:
        entry = entries.get(kind)
        assert entry, f"bulk-data has no {kind!r} entry"
        uri = entry.get("jsonl_download_uri") or ""
        assert uri.startswith("https://") and uri.endswith(".jsonl.gz"), uri
        updated = datetime.fromisoformat(entry["updated_at"])
        age = (datetime.now(timezone.utc) - updated).days
        assert age <= bulk.STALE_WARN_DAYS, f"{kind} snapshot is {age} days old"
