"""Model profile per commander for the theory paper (read-only).

Makes one EDHRec GET per commander. Run from the repo root with the project venv
and the repo on the import path, e.g. in PowerShell:
    $env:PYTHONPATH = (Get-Location)
    .venv\\Scripts\\python paper\\experiments\\profile.py [slug ...]
"""
import json
import logging
import statistics
import sys
import time
from math import log

logging.basicConfig(level=logging.CRITICAL)

from services import analysis, bulk, edhrec, scryfall  # noqa: E402

SLUGS = sys.argv[1:] or [
    "vazi-keen-negotiator",
    "atraxa-praetors-voice",
    "the-ur-dragon",
    "krenko-mob-boss",
]
OUT = {}


def enrich(cards):
    det = scryfall.get_cards_collection([c["name"] for c in cards])
    for c in cards:
        c.update(det.get(c["name"], scryfall._empty_card_details()))


def run(slug):
    res = {}
    data = edhrec.get_commander_data(slug)
    info = edhrec.commander_info_from_data(data)
    cards = edhrec.cards_from_data(data)
    enrich(cards)
    incl_index = edhrec.inclusion_index_from_data(data)
    res["name"] = info["name"]
    res["n_rec"] = len(cards)
    res["list_tags"] = [cl.get("tag") for cl in data.get("cardlists", [])]

    # raw cardview schema + EDHRec's own lift field, if any
    cv0 = data["cardlists"][0]["cardviews"][0]
    res["cardview_keys"] = sorted(cv0.keys())
    errs = []
    for cl in data["cardlists"]:
        for cv in cl["cardviews"]:
            if cv.get("lift") is None:
                continue
            inc = edhrec._inclusion_from_cardview(cv)
            syn = float(cv.get("synergy") or 0.0)
            if inc - syn > 1e-6:
                errs.append(abs(cv["lift"] - inc / (inc - syn)))
    res["lift_field_n"] = len(errs)
    res["lift_field_max_abs_err"] = max(errs) if errs else None
    res["lift_field_median_abs_err"] = statistics.median(errs) if errs else None

    # baseline clamps and list floors
    res["n_baseline_nonpositive"] = sum(
        1 for c in cards if c["edhrec_inclusion"] - c["edhrec_synergy"] <= 0
    )
    res["min_inclusion_rec"] = min(c["edhrec_inclusion"] for c in cards)
    res["n_decks"] = data["cardlists"][0]["cardviews"][0].get("potential_decks")

    pool = scryfall.get_color_identity_pool(info["color_identity"])
    for c in pool:
        hit = incl_index.get(analysis.normalize_name(c["name"]))
        if hit:
            c["edhrec_inclusion"] = hit["inclusion"]
            c["edhrec_synergy"] = hit["synergy"]
            c["_has_data"] = True
    res["n_pool"] = len(pool)
    excl = {analysis.normalize_name(info["name"])}

    for label, kw in (
        ("otag_only", dict(level="Balanced", include_types=False)),
        ("with_types", dict(level="Balanced", include_types=True)),
    ):
        r = {}
        stats = analysis.compute_feature_stats(cards, **kw)
        all_stats = analysis.compute_feature_stats(cards, min_support=1, **kw)
        r["n_features_all"] = len(all_stats)
        r["n_features_supported"] = len(stats)
        r["n_pos"] = sum(1 for s in stats if s["weight"] > 0)
        r["top_features"] = [
            {k: (round(s[k], 4) if isinstance(s[k], float) else s[k])
             for k in ("feature", "support", "p_x", "p_b", "lift", "weight")}
            for s in stats[:12]
        ]
        r["bottom_features"] = [
            {k: (round(s[k], 4) if isinstance(s[k], float) else s[k])
             for k in ("feature", "support", "p_x", "p_b", "lift", "weight")}
            for s in stats[-5:]
        ]
        pos_mass = sum(s["weight"] for s in stats if s["weight"] > 0)
        r["pos_mass"] = pos_mass
        r["pos_mass_support_le5"] = sum(
            s["weight"] for s in stats if s["weight"] > 0 and s["support"] <= 5
        ) / pos_mass
        # generalized KL (I-divergence) between feature measures
        r["i_divergence"] = sum(
            s["p_x"] * log(s["p_x"] / s["p_b"]) - s["p_x"] + s["p_b"] for s in stats
        )
        w = {s["feature"]: s["weight"] for s in stats}
        w_raw = {s["feature"]: s["lift"] for s in stats}
        scored = analysis.score_cards(pool, w, excl, **kw)
        scored_raw = analysis.score_cards(pool, w_raw, excl, **kw)
        r["n_scored_pos"] = len(scored)
        r["top10"] = [
            (c["name"], round(c["buzzword_score"], 3),
             round(c.get("edhrec_inclusion", 0.0), 4), bool(c.get("_has_data")))
            for c in scored[:10]
        ]
        r["top10_raw"] = [
            (c["name"], round(c["buzzword_score"], 3)) for c in scored_raw[:10]
        ]
        top100 = {c["name"] for c in scored[:100]}
        top100_raw = {c["name"] for c in scored_raw[:100]}
        r["top100_overlap_weighted_vs_raw"] = len(top100 & top100_raw)
        r["top100_no_edhrec_data"] = sum(
            1 for c in scored[:100] if not c.get("_has_data")
        )
        # does score grow with the number of weighted features a card carries?
        n_feats, sc, n_feats_raw = [], [], []
        for c in pool:
            if analysis.normalize_name(c["name"]) in excl:
                continue
            feats = analysis.card_features(c, **kw)
            k = sum(1 for f in feats if f in w)
            n_feats.append(k)
            n_feats_raw.append(len(c.get("otags") or []))
            sc.append(sum(w[f] for f in feats if f in w))
        r["spearman_score_vs_nfeatures"] = statistics.correlation(
            n_feats, sc, method="ranked"
        )
        r["mean_features_top100"] = statistics.mean(
            sum(1 for f in analysis.card_features(c, **kw) if f in w)
            for c in scored[:100]
        )
        r["mean_features_pool"] = statistics.mean(n_feats)
        # mean score among the commander's own recommended cards vs the pool
        rec_scores = [analysis.score_card(c, w, **kw) for c in cards]
        r["mean_score_rec"] = statistics.mean(rec_scores)
        r["mean_score_pool"] = statistics.mean(sc)
        # rank correlation between score and inclusion on recommended cards
        r["spearman_score_vs_inclusion_rec"] = statistics.correlation(
            rec_scores, [c["edhrec_inclusion"] for c in cards], method="ranked"
        )
        r["spearman_score_vs_synergy_rec"] = statistics.correlation(
            rec_scores, [c["edhrec_synergy"] for c in cards], method="ranked"
        )
        if slug.startswith("vazi"):
            rank = {c["name"]: i + 1 for i, c in enumerate(scored)}
            rank_raw = {c["name"]: i + 1 for i, c in enumerate(scored_raw)}
            ex = {}
            for nm in ("Biotech Specialist", "Gadrak, the Crown-Scourge"):
                rec = next((c for c in pool if c["name"] == nm), None)
                if rec is None:
                    ex[nm] = "not in pool"
                    continue
                ex[nm] = {
                    "score": round(analysis.score_card(rec, w, **kw), 4),
                    "rank": rank.get(nm),
                    "rank_raw": rank_raw.get(nm),
                    "raw_score": round(analysis.score_card(rec, w_raw, **kw), 4),
                    "of": len(scored),
                    "edhrec": incl_index.get(analysis.normalize_name(nm)),
                    "breakdown": [
                        (f, round(v, 4))
                        for f, v in analysis.score_breakdown(rec, w, top_n=8, **kw)
                    ],
                    "otags": rec.get("otags"),
                    "type_line": rec.get("type_line"),
                }
            r["examples"] = ex
        res[label] = r
    return res


t0 = time.time()
bulk.ensure_loaded()
OUT["_load_s"] = round(time.time() - t0, 1)
for s in SLUGS:
    try:
        OUT[s] = run(s)
    except Exception as e:  # keep going; report the failure
        OUT[s] = {"error": repr(e)}
    time.sleep(1.0)
print(json.dumps(OUT, indent=1, default=str))
