import requests
import urllib3
from flask import current_app

urllib3.disable_warnings()


def lyrion_request(payload):
    host = current_app.config["LYRION_HOST"]
    r = requests.post(
        f"{host}/jsonrpc.js",
        json=payload,
        verify=False,
        timeout=5,
    )
    return r.json()


def fetch_cover(coverid):
    """Fetch an album cover from Lyrion so the page can serve it same-origin.

    Loading the cover through our own host (instead of pointing the <img> at
    LYRION_HOST directly) lets the page read the image pixels on a canvas to
    derive a tint colour — cross-origin images would taint the canvas.
    """
    host = current_app.config["LYRION_HOST"]
    r = requests.get(f"{host}/music/{coverid}/cover.jpg", verify=False, timeout=5)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "image/jpeg")


def fetch_remote_cover(url):
    """Fetch artwork from a remote stream's artwork_url (Deezer, Spotify, radio
    icons, etc.) so the page can serve it same-origin, same reasoning as
    fetch_cover. These are public CDN URLs, not the local Lyrion host, so
    certificate verification stays on."""
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "image/jpeg")


def get_players():
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": ["", ["players", "0", "100"]],
    }
    data = lyrion_request(payload)
    return data["result"].get("players_loop", [])


def get_now_playing(player_id):
    """Return the current track + transport state of a player.

    Uses the JSON-RPC `status` query for the current playlist position (`-`),
    asking for one item with the tags we display: a=artist, A=role-keyed
    artist lists, l=album, d=duration, c=coverid, K=artwork_url. With tag A
    the multiple artists come back joined by ", " under a role key
    (`trackartist` for the track's contributors, `artist` for the ARTIST
    role) — we prefer `trackartist` so a "feat." line shows everyone,
    matching Lyrion's display. Title and the Lyrion track id come back by
    default; that id is the key used to look up lyrics in the SQLite
    `tracks` table.

    Streamed tracks (Deezer, Spotify, radio, ...) have no local coverid, but
    plugins for those services attach an `artwork_url` to the track instead —
    that's what tag K surfaces. It's sometimes relative to the Lyrion host.
    """
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": [player_id, ["status", "-", 1, "tags:aAldcK"]],
    }
    data = lyrion_request(payload)
    result = data.get("result", {})
    loop = result.get("playlist_loop") or []
    track = loop[0] if loop else None

    if not track:
        return {"playing": False, "mode": result.get("mode", "stop")}

    artwork_url = track.get("artwork_url")
    if artwork_url and not artwork_url.startswith("http"):
        host = current_app.config["LYRION_HOST"]
        artwork_url = f"{host}/{artwork_url.lstrip('/')}"

    return {
        "playing": result.get("mode") == "play",
        "mode": result.get("mode", "stop"),
        "time": result.get("time"),
        "duration": result.get("duration") or track.get("duration"),
        "track_id": track.get("id"),
        "title": track.get("title"),
        "artist": track.get("trackartist") or track.get("artist") or track.get("albumartist"),
        "album": track.get("album"),
        "coverid": track.get("coverid"),
        "artwork_url": artwork_url,
    }


def get_active_now_playing():
    """Now-playing state of the player that is currently playing.

    Lyrion has no single call returning the transport state of every player,
    so we enumerate players and query `status` on each, returning the first one
    whose mode is 'play'. If none is actually playing, we return a not-playing
    payload so the page shows its empty state — a paused/stopped player with a
    track still loaded is deliberately not surfaced.
    """
    for player in get_players():
        player_id = player.get("playerid")
        if not player_id:
            continue

        now = get_now_playing(player_id)
        if now.get("playing") and now.get("track_id"):
            now["player_name"] = player.get("name")
            # Exposed so the page can deep-link the "open Lyrion" button to the
            # Material skin focused on this very player (?player=<id>).
            now["player_id"] = player_id
            return now

    return {"playing": False, "mode": "stop", "player_name": None}
