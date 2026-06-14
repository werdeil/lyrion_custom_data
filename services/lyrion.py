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
    asking for one item with the tags we display: a=artist, l=album,
    d=duration, c=coverid. Title and the Lyrion track id come back by default;
    that id is the key used to look up lyrics in the SQLite `tracks` table.
    """
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": [player_id, ["status", "-", 1, "tags:aldc"]],
    }
    data = lyrion_request(payload)
    result = data.get("result", {})
    loop = result.get("playlist_loop") or []
    track = loop[0] if loop else None

    if not track:
        return {"playing": False, "mode": result.get("mode", "stop")}

    return {
        "playing": result.get("mode") == "play",
        "mode": result.get("mode", "stop"),
        "time": result.get("time"),
        "duration": result.get("duration") or track.get("duration"),
        "track_id": track.get("id"),
        "title": track.get("title"),
        "artist": track.get("artist"),
        "album": track.get("album"),
        "coverid": track.get("coverid") or track.get("artwork_track_id") or track.get("id"),
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
            return now

    return {"playing": False, "mode": "stop", "player_name": None}
