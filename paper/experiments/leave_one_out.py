"""Leave-one-out validation of score variants (read-only; one EDHRec GET each).

Run from the repo root with the project venv and the repo on the import path,
e.g. in PowerShell:
    $env:PYTHONPATH = (Get-Location)
    .venv\\Scripts\\python paper\\experiments\\leave_one_out.py [slug ...]

For each recommended card c of a commander: recompute feature weights from the
other recommended cards, score c and every non-recommended pool card, and record
c's percentile among the non-recommended pool. The mean percentile is an AUC:
the probability a held-out recommended card outranks a random non-recommended one.
"""
import json
import logging
import statistics
import sys
import time
from math import log, sqrt

logging.basicConfig(level=logging.CRITICAL)

from services import analysis, bulk, edhrec, scryfall  # noqa: E402

SLUGS = sys.argv[1:] or [
    "vazi-keen-negotiator",
    "atraxa-praetors-voice",
    "the-ur-dragon",
    "krenko-mob-boss",
]
KW = dict(level="Balanced", include_types=False)
EPS = 1e-4
MIN_SUPPORT = 3
VARIANTS = (
    "sum_weighted", "sum_raw", "mean_weighted", "sqrt_weighted", "tag_count",
    "sum_centered", "sqrt_centered",
)


def variants(feats, w, lift, wc):
    hit = [f for f in feats if f in w]
    k = len(hit)
    s = sum(w[f] for f in hit)
    return (
        s,
        sum(lift[f] for f in hit),
        (s / k) if k else 0.0,
        (s / sqrt(k)) if k else 0.0,
        float(len(feats)),
        sum(wc[f] for f in hit),
        (sum(wc[f] for f in hit) / sqrt(k)) if k else 0.0,
    )


def run(slug):
    data = edhrec.get_commander_data(slug)
    info = edhrec.commander_info_from_data(data)
    rec = edhrec.cards_from_data(data)
    det = scryfall.get_cards_collection([c["name"] for c in rec])
    for c in rec:
        c.update(det.get(c["name"], scryfall._empty_card_details()))
    rec_names = {analysis.normalize_name(c["name"]) for c in rec}
    rec_names.add(analysis.normalize_name(info["name"]))
    pool = scryfall.get_color_identity_pool(info["color_identity"])
    non_rec = [
        analysis.card_features(c, **KW)
        for c in pool
        if analysis.normalize_name(c["name"]) not in rec_names
        and "Basic" not in (c.get("type_line") or "")
    ]
    rec_feats = [analysis.card_features(c, **KW) for c in rec]
    incl = [max(c["edhrec_inclusion"], EPS) for c in rec]
    base = [max(c["edhrec_inclusion"] - c["edhrec_synergy"], EPS) for c in rec]

    # full sums, then subtract the held-out card (exactly equals recomputation)
    isum, bsum, sup = {}, {}, {}
    for fs, i, b in zip(rec_feats, incl, base):
        for f in fs:
            isum[f] = isum.get(f, 0.0) + i
            bsum[f] = bsum.get(f, 0.0) + b
            sup[f] = sup.get(f, 0) + 1

    tot_i, tot_b = sum(incl), sum(base)
    global_lift = log(tot_i / tot_b)
    pct = {v: [] for v in VARIANTS}
    loo_scores = {v: [] for v in VARIANTS}
    for j, fs in enumerate(rec_feats):
        w, lift, wc = {}, {}, {}
        own = set(fs)
        l0 = log((tot_i - incl[j]) / (tot_b - base[j]))
        for f, n in sup.items():
            if f in own:
                n2, i2, b2 = n - 1, isum[f] - incl[j], bsum[f] - base[j]
            else:
                n2, i2, b2 = n, isum[f], bsum[f]
            if n2 < MIN_SUPPORT:
                continue
            px, pb = i2 / n2, b2 / n2
            lift[f] = log(px / pb)
            w[f] = px * lift[f]
            wc[f] = px * (lift[f] - l0)
        mine = variants(fs, w, lift, wc)
        below = [0] * len(VARIANTS)
        ties = [0] * len(VARIANTS)
        for nf in non_rec:
            other = variants(nf, w, lift, wc)
            for k in range(len(VARIANTS)):
                if other[k] < mine[k]:
                    below[k] += 1
                elif other[k] == mine[k]:
                    ties[k] += 1
        for k, v in enumerate(VARIANTS):
            pct[v].append((below[k] + 0.5 * ties[k]) / len(non_rec))
            loo_scores[v].append(mine[k])

    syn = [c["edhrec_synergy"] for c in rec]
    out = {"name": info["name"], "n_rec": len(rec), "n_non_rec": len(non_rec)}
    out["global_log_lift"] = round(global_lift, 4)
    out["mean_inclusion_rec"] = round(tot_i / len(rec), 4)
    out["mean_baseline_rec"] = round(tot_b / len(rec), 4)
    for v in VARIANTS:
        out[v] = {
            "auc": round(statistics.mean(pct[v]), 4),
            "median_pct": round(statistics.median(pct[v]), 4),
            "share_in_top_5pct": round(
                sum(1 for p in pct[v] if p >= 0.95) / len(rec), 4
            ),
            "share_in_top_1pct": round(
                sum(1 for p in pct[v] if p >= 0.99) / len(rec), 4
            ),
            "spearman_vs_synergy": round(
                statistics.correlation(loo_scores[v], syn, method="ranked"), 4
            ),
        }
    # nonland-only AUC (lands carry few functional tags)
    nonland = [j for j, c in enumerate(rec) if "Land" not in (c.get("type_line") or "")]
    out["n_rec_nonland"] = len(nonland)
    for v in VARIANTS:
        out[v]["auc_nonland"] = round(
            statistics.mean(pct[v][j] for j in nonland), 4
        )
    # high-synergy targets only: top quartile of EDHRec synergy among recommended
    q3 = statistics.quantiles(syn, n=4)[2]
    hi = [j for j in range(len(rec)) if syn[j] >= q3]
    out["synergy_q3"] = round(q3, 4)
    out["n_hi_syn"] = len(hi)
    lo = [j for j in range(len(rec)) if syn[j] <= statistics.quantiles(syn, n=4)[0]]
    for v in VARIANTS:
        out[v]["auc_hi_syn"] = round(statistics.mean(pct[v][j] for j in hi), 4)
        out[v]["hi_syn_top5"] = round(
            sum(1 for j in hi if pct[v][j] >= 0.95) / len(hi), 4
        )
        out[v]["hi_syn_top1"] = round(
            sum(1 for j in hi if pct[v][j] >= 0.99) / len(hi), 4
        )
        out[v]["auc_lo_syn"] = round(statistics.mean(pct[v][j] for j in lo), 4)
    return out


bulk.ensure_loaded()
res = {}
for s in SLUGS:
    t0 = time.time()
    try:
        res[s] = run(s)
        res[s]["seconds"] = round(time.time() - t0, 1)
    except Exception as e:
        res[s] = {"error": repr(e)}
    time.sleep(1.0)
print(json.dumps(res, indent=1))
