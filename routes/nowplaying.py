from flask import Blueprint, render_template, current_app, jsonify

from services.lyrion import get_active_now_playing
from services.database import get_track_lyrics, get_stats

nowplaying_bp = Blueprint("nowplaying", __name__)


@nowplaying_bp.route("/")
def index():
    stats = get_stats()
    return render_template(
        "nowplaying.html",
        lyrion_host=current_app.config["LYRION_HOST"],
        stats=stats,
    )


@nowplaying_bp.route("/now-playing.json")
def now_playing_json():
    """Live state of whichever player is currently playing, polled by the page."""
    now = get_active_now_playing()
    now["lyrics"] = get_track_lyrics(now.get("track_id"))
    return jsonify(now)
