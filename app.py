import logging

from flask import Flask, render_template, request, redirect, url_for

from services import edhrec, scryfall, analysis

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


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
        return render_template("error.html", message=f"Commander '{slug}' not found on EDHRec."), 404

    # 2. Fetch EDHRec recommended cards
    edhrec_cards = edhrec.get_commander_cards(slug)
    if not edhrec_cards:
        return render_template("error.html", message=f"No card data found for '{slug}'."), 404

    # 3. Enrich EDHRec cards with Scryfall data in one batch request
    scryfall._load_otag_index()
    card_details = scryfall.get_cards_collection([c["name"] for c in edhrec_cards])
    for card in edhrec_cards:
        card.update(card_details.get(card["name"], scryfall._empty_card_details()))

    # 4. Fetch all EDH-legal cards in the commander's color identity
    color_pool = scryfall.get_color_identity_pool(info["color_identity"])

    # 5. Score color pool against EDHRec TF weights
    edhrec_names = {c["name"] for c in edhrec_cards}
    tf = analysis.compute_tf(edhrec_cards)
    slept_on = analysis.score_cards(color_pool, tf, edhrec_names)

    return render_template(
        "commander.html",
        commander=info,
        edhrec_cards=edhrec_cards,
        slept_on=slept_on,
    )


if __name__ == "__main__":
    app.run(debug=True)
