from flask import Blueprint, render_template, current_app, jsonify, request, Response, abort

from services.lyrion import get_active_now_playing, fetch_cover, fetch_remote_cover
from services.database import get_track_lyrics, get_stats
from services.lyrics import fetch_lyrics
from i18n import pick_lang, TRANSLATIONS

nowplaying_bp = Blueprint("nowplaying", __name__)


@nowplaying_bp.route("/")
def index():
    stats = get_stats()
    lang = pick_lang(request.accept_languages)
    return render_template(
        "nowplaying.html",
        lyrion_host=current_app.config["LYRION_HOST"],
        stats=stats,
        lang=lang,
        t=TRANSLATIONS[lang],
    )


@nowplaying_bp.route("/now-playing.json")
def now_playing_json():
    """Live state of whichever player is currently playing, polled by the page."""
    now = get_active_now_playing()
    now["lyrics"] = get_track_lyrics(now.get("track_id"))
    return jsonify(now)


@nowplaying_bp.route("/cover/<coverid>.jpg")
def cover(coverid):
    """Proxy an album cover from Lyrion, served same-origin so the page can
    sample its colours on a canvas. Cached client-side since covers are stable."""
    content, content_type = fetch_cover(coverid)
    return Response(
        content,
        content_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@nowplaying_bp.route("/cover/remote.jpg")
def cover_remote():
    """Proxy the artwork_url of the currently playing remote/streaming track
    (Deezer, Spotify, radio, ...), same-origin like /cover/<id>.jpg.

    Looked up server-side from Lyrion instead of taking a URL from the
    client, so this can't be used as an open image proxy.
    """
    now = get_active_now_playing()
    artwork_url = now.get("artwork_url")
    if not artwork_url:
        abort(404)
    content, content_type = fetch_remote_cover(artwork_url)
    return Response(
        content,
        content_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@nowplaying_bp.route("/lyrics.json")
def lyrics_json():
    """Fetch lyrics from the web for a track, on explicit user request.

    The page calls this only when the local library has no lyrics, passing the
    metadata it already displays so we avoid re-querying Lyrion. Results are
    cached in-memory by services.lyrics, so repeated clicks are cheap.
    """
    result = fetch_lyrics(
        track_id=request.args.get("track_id"),
        artist=request.args.get("artist"),
        title=request.args.get("title"),
        album=request.args.get("album"),
        duration=request.args.get("duration"),
        force=request.args.get("refresh") == "1",
    )
    return jsonify(result)
