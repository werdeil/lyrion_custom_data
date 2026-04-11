from flask import Blueprint, render_template, redirect, request, session, current_app, url_for

from services.lyrion import get_players, play_album
from services.database import get_albums, get_albums_by_ids, get_stats

suggester_bp = Blueprint("suggester", __name__)


@suggester_bp.route("/", methods=["GET", "POST"])
def index():
    players = get_players()
    selected_player = session.get("player_id")

    if request.method == "POST":
        selected_player = request.form.get("player_id")
        if selected_player is not None:
            session["player_id"] = selected_player

        refresh = request.form.get("refresh") == "1"
        if refresh:
            return redirect(url_for("suggester.index", refresh=1))
        return redirect(url_for("suggester.index"))

    refresh = request.args.get("refresh") == "1"
    album_ids = session.get("album_ids")
    if refresh or not album_ids:
        albums = get_albums()
        session["album_ids"] = [album["id"] for album in albums]
    else:
        albums = get_albums_by_ids(album_ids)

    stats = get_stats()

    return render_template(
        "suggester.html",
        players=players,
        albums=albums,
        selected_player=selected_player,
        lyrion_host=current_app.config["LYRION_HOST"],
        stats=stats,
    )


@suggester_bp.route("/play/<int:album_id>")
def play(album_id):
    player_id = session.get("player_id")
    if not player_id:
        return "Aucun lecteur sélectionné", 400

    play_album(player_id, album_id)
    return redirect("/")
