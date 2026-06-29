import logging
import os
import threading

from flask import Flask, render_template, request, redirect, url_for, jsonify

from services import edhrec, scryfall, analysis, bulk, archidekt

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
        # Archidekt deck-URL branch (issue #33). Checked first; falls through to
        # the commander/partner name flow when the deck field is empty. Routing
        # carries ?deck=<id> for issue #34 (deck-scoped scoring), which the
        # commander route currently ignores.
        archidekt_url = request.form.get("archidekt_url", "").strip()
        if archidekt_url:
            deck_id = archidekt.parse_deck_id(archidekt_url)
            deck = archidekt.get_deck(deck_id) if deck_id else None
            if not deck:
                return (
                    render_template(
                        "error.html",
                        message="Couldn't read that Archidekt deck. Check the "
                        "URL is a public archidekt.com deck link.",
                    ),
                    400,
                )
            names = deck["commander_names"]
            if not names or len(names) > 2:
                return (
                    render_template(
                        "error.html",
                        message="Couldn't find a commander in that deck. The "
                        "deck needs a card in its Commander category.",
                    ),
                    400,
                )
            if len(names) == 2:
                slug = edhrec.resolve_pairing_slug(names[0], names[1])
            else:
                slug = edhrec.slugify(names[0])
            return redirect(url_for("commander", slug=slug, deck=deck["deck_id"]))

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
    # Granularity controls (issue #41). Unlike budget/bracket these RE-SCORE: they
    # change the feature set, so they thread into compute_feature_stats + every
    # card_features/score_card call below (like `tag`). `level` is validated to a
    # known name (else default Balanced); `include_types` is a strict boolean.
    level = request.args.get("level", "")
    if level not in analysis.LEVEL_DEPTHS:
        level = analysis.DEFAULT_LEVEL
    include_types = request.args.get("include_types", "").lower() == "true"
    # Deck-scoped scoring (issue #34): an Archidekt deck id carried over from the
    # index route. When present, the deck's cards tilt the feature weights (forced
    # to 100% inclusion in the scoring path) and get an "In deck" badge.
    deck_id = request.args.get("deck", "")

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

    # 2d. Deck-scoped scoring (issue #34): fetch the linked Archidekt deck once
    #     (reused by the Deck tab in step 6) and force its cards in the scoring set
    #     to 100% inclusion via the scoring-only `forced_inclusion` field. This
    #     tilts the feature weights toward what the deck over-uses without touching
    #     the displayed `edhrec_inclusion` (which keeps the real baseline and keeps
    #     deck cards visible under the inclusion-cap filter). A missing/unreadable
    #     deck leaves `deck_names` empty -> normal commander-average render, no 500.
    deck = None
    deck_names: set[str] = set()
    if deck_id:
        deck = archidekt.get_deck(deck_id)
        if deck:
            deck_names = {
                analysis.normalize_name(n) for n in deck["card_names"]
            }
            for c in scoring_cards:
                if analysis.normalize_name(c["name"]) in deck_names:
                    c["forced_inclusion"] = 1.0
        else:
            app.logger.warning(
                "deck %s could not be fetched; rendering commander average",
                deck_id,
            )

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
    feature_stats = analysis.compute_feature_stats(
        scoring_cards, level=level, include_types=include_types
    )
    weights = {s["feature"]: s["weight"] for s in feature_stats}
    slept_on = analysis.score_cards(
        color_pool, weights, exclude_names, level=level, include_types=include_types
    )

    # Score the EDHRec recommendations on the same scale so the EDHRec tab is
    # directly comparable to Slept On. We do NOT re-rank them (they stay grouped
    # by category); features power the client-side re-score on Diagnostics toggles.
    for c in edhrec_cards:
        c["features"] = analysis.card_features(
            c, level=level, include_types=include_types
        )
        c["buzzword_score"] = analysis.score_card(
            c, weights, level=level, include_types=include_types
        )
        c["in_deck"] = analysis.normalize_name(c["name"]) in deck_names

    # Display-score the featured cards on the same weights (for the EDHRec tab's
    # featured rows). They are display-only — never appended to edhrec_cards and
    # never passed to compute_feature_stats/score_cards.
    for c in featured_cards:
        c["features"] = analysis.card_features(
            c, level=level, include_types=include_types
        )
        c["buzzword_score"] = analysis.score_card(
            c, weights, level=level, include_types=include_types
        )
        c["in_deck"] = analysis.normalize_name(c["name"]) in deck_names

    # Presentation-only split (issue #31/#32): one overall Top 10 plus the seven
    # per-type sections. Partition the FULL scored list (not a global top-N) so a
    # sparse type still fills up to SLEPT_ON_SECTION_CAP; creatures slot only under
    # Creatures. partition_by_type buckets the same dicts by reference and preserves
    # score-desc order, so a card can appear in Top 10 and in its type section.
    # The Top 10 grid renders a refill pool of up to SLEPT_ON_SECTION_CAP candidates
    # (same magnitude as a type section) and is capped to TOP_OVERALL_N *visible*
    # cards client-side via data-fixed-n, so filters can refill it from the pool
    # instead of thinning it out. The "10" lives only in that fixed-N attribute.
    overall_pool = slept_on[:SLEPT_ON_SECTION_CAP]
    type_sections = analysis.partition_by_type(slept_on, cap=SLEPT_ON_SECTION_CAP)

    # Surface each displayed card's feature list so the Diagnostics toggles can
    # re-score it client-side without a round trip. weights -> feature_weights for
    # the same. in_edhrec flags picks that are actually EDHRec recommendations
    # (surfaced only because their inclusion is under the cap) so the template can
    # badge them. Enrich only the rendered cards (Top 10 + section members), not
    # the whole scored color pool; the shared dicts are deduped by identity.
    displayed = overall_pool + [c for sec in type_sections for c in sec["cards"]]
    seen_ids: set[int] = set()
    for c in displayed:
        if id(c) in seen_ids:
            continue
        seen_ids.add(id(c))
        c["features"] = analysis.card_features(
            c, level=level, include_types=include_types
        )
        c["in_edhrec"] = analysis.normalize_name(c["name"]) in edhrec_names
        c["in_deck"] = analysis.normalize_name(c["name"]) in deck_names

    # 6. Deck tab (issue #33): when the page was reached from an Archidekt link,
    #    the index route attached ?deck=<id>. Reuse the deck already fetched in
    #    step 2d and render its own card list as a fourth tab. Each card is
    #    enriched + scored on the SAME weights as Slept On so its up-to-date
    #    Buzzword Score shows, and joined to the inclusion index for a real
    #    inclusion %. The tab is display-only: the template renders it outside the
    #    Slept On / EDHRec grids the client filters touch, so price/pauper/
    #    inclusion/N gating never hides deck cards. A missing/unreadable deck just
    #    yields no tab (degrade, never 500).
    deck_cards: list[dict] = []
    if deck:
        card_names = deck["card_names"]
        deck_details = scryfall.get_cards_collection(card_names)
        for name in card_names:
            card = {
                "name": name,
                "edhrec_category": "",
                "edhrec_synergy": 0.0,
                "edhrec_inclusion": 0.0,
                "buzzword_score": 0.0,
            }
            card.update(
                deck_details.get(name, scryfall._empty_card_details())
            )
            hit = incl_index.get(analysis.normalize_name(name))
            if hit:
                card["edhrec_inclusion"] = hit["inclusion"]
                card["edhrec_synergy"] = hit["synergy"]
            card["features"] = analysis.card_features(
                card, level=level, include_types=include_types
            )
            card["buzzword_score"] = analysis.score_card(
                card, weights, level=level, include_types=include_types
            )
            card["in_edhrec"] = (
                analysis.normalize_name(name) in edhrec_names
            )
            card["in_deck"] = True
            deck_cards.append(card)

    return render_template(
        "commander.html",
        commander=info,
        commanders=commanders,
        edhrec_cards=edhrec_cards,
        deck_cards=deck_cards,
        featured=featured,
        overall_pool=overall_pool,
        top_overall_n=TOP_OVERALL_N,
        type_sections=type_sections,
        feature_stats=feature_stats,
        feature_weights=weights,
        selected_tag=tag,
        selected_budget=budget,
        selected_bracket=bracket,
        selected_level=level,
        include_types=include_types,
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
