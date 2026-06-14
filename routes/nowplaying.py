from flask import (
    Blueprint,
    render_template,
    redirect,
    request,
    session,
    current_app,
    url_for,
    jsonify,
)

from services.lyrion import get_players, get_now_playing
from services.database import get_track_lyrics, get_stats

nowplaying_bp = Blueprint("nowplaying", __name__)


@nowplaying_bp.route("/", methods=["GET", "POST"])
def index():
    players = get_players()
    selected_player = session.get("player_id")

    if request.method == "POST":
        selected_player = request.form.get("player_id")
        if selected_player is not None:
            session["player_id"] = selected_player
        return redirect(url_for("nowplaying.index"))

    stats = get_stats()

    return render_template(
        "nowplaying.html",
        players=players,
        selected_player=selected_player,
        lyrion_host=current_app.config["LYRION_HOST"],
        stats=stats,
    )


@nowplaying_bp.route("/now-playing.json")
def now_playing_json():
    """Live state of the selected player, polled by the page."""
    player_id = session.get("player_id")
    if not player_id:
        return jsonify({"playing": False, "error": "no_player"})

    now = get_now_playing(player_id)
    now["lyrics"] = get_track_lyrics(now.get("track_id"))
    return jsonify(now)
