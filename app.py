import logging
import os
import threading

from flask import Flask, render_template, request, redirect, url_for, jsonify

from services import edhrec, scryfall, analysis, bulk

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# The color pool is now unbounded (whole color identity), but the N slider tops
# out at 100. Each Slept On section renders its top SLEPT_ON_SECTION_CAP cards so
# the slider can always reach its max, while 5-color commanders don't emit
# thousands of DOM nodes per section the user can never scroll to. Sections draw
# from the *full* scored list (not a global top-N), so a sparse type (e.g.
# sorceries) still fills up to the cap.
SLEPT_ON_SECTION_CAP = 100

# The single overall Slept On section shows the N highest-scoring picks.
TOP_OVERALL_N = 10


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("commander", "").strip()
        partner = request.form.get("partner", "").strip()
        if name:
            # A partner pairing routes through one combined EDHRec slug; the whole
            # scoring/Slept On pipeline then treats it as a single commander.
            if partner:
                slug = edhrec.resolve_pairing_slug(name, partner)
            else:
                slug = edhrec.slugify(name)
            return redirect(url_for("commander", slug=slug))
    return render_template("index.html")


@app.route("/commanders.json")
def commanders_json():
    # Commander-name list for the search-bar autocomplete. First hit on a cold
    # server warms the bulk store (~30s); the page renders without waiting on it.
    scryfall.warm_up()
    return jsonify(bulk.commander_names())


@app.route("/partners")
def partners():
    # Partner-eligibility + legal-pairing pool for the second autocomplete.
    # {'eligible': bool, 'kind': str, 'partners': [name, ...]}.
    scryfall.warm_up()
    name = request.args.get("name", "").strip()
    return jsonify(bulk.partner_eligibility(name))


@app.route("/commander/<slug>")
def commander(slug):
    # 0. Scope selectors (issue #19). A `tag` re-scopes AND re-scores Slept On;
    #    `budget`/`bracket` are display-only scopes — they change which EDHRec
    #    cards are shown but leave the Buzzword Scores anchored to the no-tag
    #    baseline (see the separate scoring view below).
    tag = request.args.get("tag", "")
    budget = request.args.get("budget", "")
    bracket = request.args.get("bracket", "")

    # 1. Display view: the fully-composed scope drives the EDHRec tab, featured
    #    rows, the inclusion cross-ref, and the Slept On exclusion set.
    display_data = edhrec.get_commander_data(
        slug, tag=tag, budget=budget, bracket=bracket
    )
    info = edhrec.commander_info_from_data(display_data) if display_data else None
    commanders = edhrec.commanders_from_data(display_data) if display_data else []
    if not info:
        return (
            render_template(
                "error.html", message=f"Commander '{slug}' not found on EDHRec."
            ),
            404,
        )

    # 2. Type-category recommendation list + the broad inclusion index + theme
    #    options, all from the display view.
    edhrec_cards = edhrec.cards_from_data(display_data)
    if not edhrec_cards:
        return (
            render_template("error.html", message=f"No card data found for '{slug}'."),
            404,
        )
    incl_index = edhrec.inclusion_index_from_data(display_data)
    available_tags = edhrec.available_tags_from_data(display_data)

    # 2b. Display-only featured rows (New / High Synergy / Top) shown atop the
    #     EDHRec tab. These are NOT added to edhrec_cards or the scoring set.
    featured = edhrec.featured_sections_from_data(display_data)
    featured_cards = [c for sec in featured for c in sec["cards"]]

    # 2c. Scoring view: only a tag recomputes feature weights. Budget/bracket
    #     keep scores fixed to the base (no-tag) baseline, so resolve a separate
    #     scoring view that ignores them. When neither applies, the display view
    #     IS the scoring view (reuse it to avoid a second fetch + re-enrichment).
    if tag:
        scoring_data = edhrec.get_commander_data(slug, tag=tag)
    elif budget or bracket:
        scoring_data = edhrec.get_commander_data(slug)
    else:
        scoring_data = display_data
    if scoring_data is display_data:
        scoring_cards = edhrec_cards
    else:
        scoring_cards = edhrec.cards_from_data(scoring_data)

    # 3. Enrich display + scoring cards with Scryfall data from the local bulk
    #    store in one collection call.
    scryfall.warm_up()
    names = [c["name"] for c in edhrec_cards] + [c["name"] for c in featured_cards]
    if scoring_cards is not edhrec_cards:
        names += [c["name"] for c in scoring_cards]
    card_details = scryfall.get_cards_collection(names)
    enrich_targets = edhrec_cards + featured_cards
    if scoring_cards is not edhrec_cards:
        enrich_targets = enrich_targets + scoring_cards
    for card in enrich_targets:
        card.update(card_details.get(card["name"], scryfall._empty_card_details()))

    # 4. Fetch all EDH-legal cards in the commander's color identity
    color_pool = scryfall.get_color_identity_pool(info["color_identity"])

    # 4b. Join EDHRec's real inclusion/synergy onto pool cards so Slept On shows
    #     true inclusion % (not a misleading 0%). Cards absent from the index keep
    #     their 0.0 default — the "no EDHRec data" sentinel.
    for card in color_pool:
        hit = incl_index.get(analysis.normalize_name(card["name"]))
        if hit:
            card["edhrec_inclusion"] = hit["inclusion"]
            card["edhrec_synergy"] = hit["synergy"]

    # 5. Score color pool with feature-lift model (Ferrone 2026).
    #    Only the commander itself is excluded (it sits in its own color pool but
    #    is never a "slept on" pick). EDHRec recommendations are NOT excluded:
    #    low-inclusion ones can surface here, gated by the inclusion-cap slider
    #    rather than a hard cut, and are flagged with an "in EDHRec list" badge.
    #    edhrec_names (normalized) drives that badge.
    edhrec_names = {analysis.normalize_name(c["name"]) for c in edhrec_cards}
    # Exclude every commander on the page (both halves of a partner pairing) from
    # its own Slept On list, not just the combined card's display name.
    exclude_names = {analysis.normalize_name(info["name"])}
    for cm in commanders:
        exclude_names.add(analysis.normalize_name(cm["name"]))
    # Weights come strictly from the scoring view (tag-only or base) so that
    # budget/bracket never move scores; only a tag rescopes the feature weights.
    feature_stats = analysis.compute_feature_stats(scoring_cards)
    weights = {s["feature"]: s["weight"] for s in feature_stats}
    slept_on = analysis.score_cards(color_pool, weights, exclude_names)

    # Score the EDHRec recommendations on the same scale so the EDHRec tab is
    # directly comparable to Slept On. We do NOT re-rank them (they stay grouped
    # by category); features power the client-side re-score on Diagnostics toggles.
    for c in edhrec_cards:
        c["features"] = analysis.card_features(c)
        c["buzzword_score"] = analysis.score_card(c, weights)

    # Display-score the featured cards on the same weights (for the EDHRec tab's
    # featured rows). They are display-only — never appended to edhrec_cards and
    # never passed to compute_feature_stats/score_cards.
    for c in featured_cards:
        c["features"] = analysis.card_features(c)
        c["buzzword_score"] = analysis.score_card(c, weights)

    # Presentation-only split (issue #31): one overall Top 10 plus the seven
    # per-type sections. Partition the FULL scored list (not a global top-N) so a
    # sparse type still fills up to SLEPT_ON_SECTION_CAP; creatures slot only under
    # Creatures. partition_by_type buckets the same dicts by reference and preserves
    # score-desc order, so a card can appear in Top 10 and in its type section.
    top_overall = slept_on[:TOP_OVERALL_N]
    type_sections = analysis.partition_by_type(slept_on, cap=SLEPT_ON_SECTION_CAP)

    # Surface each displayed card's feature list so the Diagnostics toggles can
    # re-score it client-side without a round trip. weights -> feature_weights for
    # the same. in_edhrec flags picks that are actually EDHRec recommendations
    # (surfaced only because their inclusion is under the cap) so the template can
    # badge them. Enrich only the rendered cards (Top 10 + section members), not
    # the whole scored color pool; the shared dicts are deduped by identity.
    displayed = top_overall + [c for sec in type_sections for c in sec["cards"]]
    seen_ids: set[int] = set()
    for c in displayed:
        if id(c) in seen_ids:
            continue
        seen_ids.add(id(c))
        c["features"] = analysis.card_features(c)
        c["in_edhrec"] = analysis.normalize_name(c["name"]) in edhrec_names

    return render_template(
        "commander.html",
        commander=info,
        commanders=commanders,
        edhrec_cards=edhrec_cards,
        featured=featured,
        top_overall=top_overall,
        type_sections=type_sections,
        feature_stats=feature_stats,
        feature_weights=weights,
        selected_tag=tag,
        selected_budget=budget,
        selected_bracket=bracket,
        available_tags=available_tags,
        budget_options=edhrec.BUDGET_OPTIONS,
        bracket_options=edhrec.BRACKET_OPTIONS,
    )


if __name__ == "__main__":
    debug = True
    # Warm the bulk store on startup so the first autocomplete keystroke doesn't
    # pay the ~540MB download/parse cost. Run it in a daemon thread so the server
    # still binds immediately (and code-reload stays snappy); ensure_loaded() is
    # thread-safe, so an early request that races the warm-up just waits on it.
    # With the reloader on (debug), only the request-serving child sets
    # WERKZEUG_RUN_MAIN=true — warm there, not in the parent, to avoid loading
    # the bulk files twice.
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Thread(target=scryfall.warm_up, daemon=True).start()
    app.run(debug=debug)
