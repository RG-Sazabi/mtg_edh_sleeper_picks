import logging

from flask import Flask, render_template, request, redirect, url_for, jsonify

from services import edhrec, scryfall, analysis, bulk

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# The color pool is now unbounded (whole color identity), but the N slider tops
# out at 100; cap the rendered Slept On list so 5-color commanders don't emit
# thousands of DOM nodes the user can never scroll to.
SLEPT_ON_RENDER_CAP = 200


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("commander", "").strip()
        if name:
            return redirect(url_for("commander", slug=edhrec.slugify(name)))
    return render_template("index.html")


@app.route("/commanders.json")
def commanders_json():
    # Commander-name list for the search-bar autocomplete. First hit on a cold
    # server warms the bulk store (~30s); the page renders without waiting on it.
    scryfall.warm_up()
    return jsonify(bulk.commander_names())


@app.route("/commander/<slug>")
def commander(slug):
    # 1. Fetch the commander page once: info + cards + inclusion index all come
    #    from a single stable EDHRec request.
    data = edhrec.get_commander_data(slug)
    info = edhrec.commander_info_from_data(data) if data else None
    if not info:
        return (
            render_template(
                "error.html", message=f"Commander '{slug}' not found on EDHRec."
            ),
            404,
        )

    # 2. Type-category recommendation list + the broad inclusion index.
    edhrec_cards = edhrec.cards_from_data(data)
    if not edhrec_cards:
        return (
            render_template("error.html", message=f"No card data found for '{slug}'."),
            404,
        )
    incl_index = edhrec.inclusion_index_from_data(data)

    # 3. Enrich EDHRec cards with Scryfall data from the local bulk store
    scryfall.warm_up()
    card_details = scryfall.get_cards_collection([c["name"] for c in edhrec_cards])
    for card in edhrec_cards:
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
    exclude_names = {analysis.normalize_name(info["name"])}
    feature_stats = analysis.compute_feature_stats(edhrec_cards)
    weights = {s["feature"]: s["weight"] for s in feature_stats}
    slept_on = analysis.score_cards(color_pool, weights, exclude_names)[
        :SLEPT_ON_RENDER_CAP
    ]

    # Score the EDHRec recommendations on the same scale so the EDHRec tab is
    # directly comparable to Slept On. We do NOT re-rank them (they stay grouped
    # by category); features power the client-side re-score on Diagnostics toggles.
    for c in edhrec_cards:
        c["features"] = analysis.card_features(c)
        c["buzzword_score"] = analysis.score_card(c, weights)

    # Surface each card's feature list so the Diagnostics toggles can re-score it
    # client-side without a round trip. weights -> feature_weights for the same.
    # in_edhrec flags picks that are actually EDHRec recommendations (surfaced
    # only because their inclusion is under the cap) so the template can badge them.
    for c in slept_on:
        c["features"] = analysis.card_features(c)
        c["in_edhrec"] = analysis.normalize_name(c["name"]) in edhrec_names

    return render_template(
        "commander.html",
        commander=info,
        edhrec_cards=edhrec_cards,
        slept_on=slept_on,
        feature_stats=feature_stats,
        feature_weights=weights,
    )


if __name__ == "__main__":
    app.run(debug=True)
