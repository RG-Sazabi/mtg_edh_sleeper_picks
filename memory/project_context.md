---
name: project-context
description: Active goals, constraints, decisions, and work items for this project
metadata:
  type: project
---

**Fact/Decision**: MTG EDH Sleeper Picks — Flask + Jinja2 web app. Personal use only.
**Why**: Simplest stack that runs locally and can export static HTML for GitHub Pages. No need for scalability.
**How to apply**: Don't over-engineer. No auth, no database, no test suite required. (Exception: Scryfall bulk data IS persisted to disk under `cache/` — see bulk-data decision below.)

---

**Fact/Decision**: Prices sourced from Scryfall `prices.usd` (TCGPlayer market price embedded in Scryfall card objects).
**Why**: No API key required. We're already hitting Scryfall for otags.
**How to apply**: Never integrate TCGPlayer API directly.

---

**Fact/Decision**: GitHub Pages hosting via pre-generated static HTML. `export.py` writes to `/docs` on master branch.
**Why**: Flask can't run on GitHub Pages. User re-runs export locally to refresh data.
**How to apply**: Keep export.py simple — render Jinja templates to static files, no server-side logic at serve time.

---

**Fact/Decision**: Core differentiator is the "Slept On" section. As of 2026-06-19 the scoring is the **feature-lift model** from Ferrone (2026), replacing the old TF-weighted otag overlap. A *feature* = card type, subtype, or oracle tag (otags dominate: ~1850 appearances vs ~300 types / ~200 subtypes for Atraxa). `lift(f) = log(P_X(f)/P_B(f))` where P_X = avg inclusion among the commander's decks and P_B = avg color-identity-baseline inclusion, both over recommended cards carrying f. Baseline `i_{c,B(X)} = edhrec_inclusion − edhrec_synergy` (EDHRec synergy is defined as inclusion minus color baseline) — so NO extra network call is needed for the baseline.

IMPORTANT (2026-06-19 fix): the score is **inclusion-weighted** — `weight(f) = P_X(f)·log(P_X(f)/P_B(f))` (pointwise KL term), `Score(c) = Σ weight(f) for f in features(c)`, `min_support=3`. The raw log-lift is scale-invariant, so summing unweighted lifts let cards stacking many fringe features (planeswalkers w/ dozens of loyalty otags) run away with inflated scores (5–7) and nonsensical recs (planeswalker spam). Weighting by P_X makes a feature matter only if the commander both over-uses AND actually plays it. After fix, Atraxa top picks are on-theme (K'rrik, Pith Driller, Vault Skirge — Phyrexian/counters) and scores are ~0.5–1.0. Function is `compute_feature_weights` (was `compute_feature_lifts`).
**Why**: TF overlap was ad-hoc and otag-only; the lift model is principled, uses type/subtype too, and has no cold-start gap. Faithful to the paper at `~/Downloads/mtg_slept_on_math.pdf`.
**How to apply**: Keep it in `services/analysis.py` (`compute_feature_lifts`, `score_cards`, `card_features`), pure + well-commented. The `buzzword_score` dict key is retained for template/JS compatibility but now holds the summed log-lift. `min_support=2`/`eps=1e-4` are tunable.

---

**Fact/Decision**: Scryfall data is served from a **local bulk store** (`services/bulk.py`): downloads `default_cards` (~547MB) + `oracle_tags` (~18MB) to `cache/` (gitignored), refreshed >24h, stream-parsed with `ijson`. Color pool + tags + attributes are in-memory lookups; per-commander load hits only EDHRec. Replaced 25-page sequential Scryfall search pagination + cold-start otag re-download. Warm in-process requests are sub-second (cold ~33s for the bulk parse). User explicitly approved disk persistence (overrides the old "no persistent cache" rule for bulk reference data only). We use `default_cards` (all printings) not `oracle_cards` so each card shows its cleanest standard printing — `bulk._printing_penalty` ranks printings and we keep the lowest-penalty one per oracle id (tie-break high-res + newest), fixing the ~12% of cards `oracle_cards` rendered as borderless/full-art/art-series/Un-set with no normal frame or rules text. GOTCHA: art-series cards have their OWN oracle_id and a doubled name ("X // X", type_line "Card // Card"); front-face split made them collide with the real card's name in `_by_name` and hijack it with art. Fix: `_build_card_index` skips any printing whose layout is in `_EXCLUDED_LAYOUTS` so art/token/emblem records never enter the indices. Don't remove that skip.
**Why**: Pagination + per-request sleeps + re-downloading the 18MB otag bulk each server start were the two confirmed bottlenecks.
**How to apply**: Don't reintroduce live paginated Scryfall search for the color pool. Keep `services/scryfall.py`'s `/cards/named` fallback only for names absent from the bulk snapshot.
