import logging

from flask import Flask, render_template, request, redirect, url_for

from services import edhrec, scryfall, analysis

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


@app.route("/commander/<slug>")
def commander(slug):
    # 1. Fetch commander info (color identity, display name)
    info = edhrec.get_commander_info(slug)
    if not info:
        return (
            render_template(
                "error.html", message=f"Commander '{slug}' not found on EDHRec."
            ),
            404,
        )

    # 2. Fetch EDHRec recommended cards
    edhrec_cards = edhrec.get_commander_cards(slug)
    if not edhrec_cards:
        return (
            render_template("error.html", message=f"No card data found for '{slug}'."),
            404,
        )

    # 3. Enrich EDHRec cards with Scryfall data from the local bulk store
    scryfall.warm_up()
    card_details = scryfall.get_cards_collection([c["name"] for c in edhrec_cards])
    for card in edhrec_cards:
        card.update(card_details.get(card["name"], scryfall._empty_card_details()))

    # 4. Fetch all EDH-legal cards in the commander's color identity
    color_pool = scryfall.get_color_identity_pool(info["color_identity"])

    # 5. Score color pool with feature-lift model (Ferrone 2026).
    #    Exclude the EDHRec recommendations AND the commander itself (it sits in
    #    its own color pool but is never a "slept on" pick).
    edhrec_names = {c["name"] for c in edhrec_cards}
    edhrec_names.add(info["name"])
    feature_stats = analysis.compute_feature_stats(edhrec_cards)
    weights = {s["feature"]: s["weight"] for s in feature_stats}
    slept_on = analysis.score_cards(color_pool, weights, edhrec_names)[
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
    for c in slept_on:
        c["features"] = analysis.card_features(c)

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
