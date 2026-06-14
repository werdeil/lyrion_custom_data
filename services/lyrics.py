"""Web fallback for lyrics, fetched on explicit user request.

Lyrion's `library.db` is read-only, so lyrics fetched from the web cannot be
stored there. We keep them in a process-local in-memory cache instead: gunicorn
runs a single worker with threads, so all requests share this dict. A positive
result is cached longer than a miss, so a track that simply has no lyrics online
is not retried on every click while a transient failure can recover sooner.

Several providers are tried in order (configurable via `LYRICS_PROVIDERS`); the
first one that returns anything wins. LRCLIB and Musixmatch can return synced
lyrics (LRC), so they come before Genius, which only offers plain text.
"""

import os
import time
import threading

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:  # Genius scraping is skipped if bs4 isn't installed.
    BeautifulSoup = None

LRCLIB_BASE = "https://lrclib.net/api"
MXM_BASE = "https://apic-desktop.musixmatch.com/ws/1.1"
USER_AGENT = "lyrion-custom-data (https://github.com/werdeil)"
# A browser-like UA avoids being blocked when scraping Genius / talking to the
# Musixmatch desktop endpoint.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# How long a cached entry stays valid, in seconds.
TTL_HIT = 24 * 3600
TTL_MISS = 3600

_cache = {}
_cache_lock = threading.Lock()


def _cache_get(track_id):
    with _cache_lock:
        entry = _cache.get(track_id)
        if entry and entry["expires_at"] > time.time():
            return entry["value"]
        if entry:
            _cache.pop(track_id, None)
    return None


def _cache_set(track_id, value, ttl):
    with _cache_lock:
        _cache[track_id] = {"value": value, "expires_at": time.time() + ttl}


def _int_duration(duration):
    """Coerce a possibly-fractional string duration to whole seconds, or None."""
    if not duration:
        return None
    try:
        # Duration arrives as a string and may be fractional (e.g. "247.144").
        return int(float(duration))
    except (TypeError, ValueError):
        return None


# --- Providers -------------------------------------------------------------
# Each provider takes (artist, title, album, duration) and returns either a
# dict {"lyrics": str|None, "synced": str|None} when it found something, or None.


def _provider_lrclib(artist, title, album, duration):
    """Ask LRCLIB for a track.

    Tries the exact `get` endpoint first (best match when artist/title/album/
    duration line up with their database), then falls back to `search` which is
    more forgiving about album and duration mismatches.
    """
    headers = {"User-Agent": USER_AGENT}

    params = {"artist_name": artist, "track_name": title}
    if album:
        params["album_name"] = album
    seconds = _int_duration(duration)
    if seconds is not None:
        params["duration"] = seconds

    payload = None
    try:
        r = requests.get(f"{LRCLIB_BASE}/get", params=params, headers=headers, timeout=5)
        if r.status_code == 200:
            payload = r.json()
    except requests.RequestException:
        payload = None

    if payload is None:
        try:
            r = requests.get(
                f"{LRCLIB_BASE}/search",
                params={"artist_name": artist, "track_name": title},
                headers=headers,
                timeout=5,
            )
            if r.status_code == 200:
                results = r.json()
                if results:
                    payload = results[0]
        except requests.RequestException:
            return None

    if not payload:
        return None
    return {"lyrics": payload.get("plainLyrics"), "synced": payload.get("syncedLyrics")}


_mxm_token = {"value": None, "expires_at": 0}
_mxm_lock = threading.Lock()
_MXM_HEADERS = {
    "authority": "apic-desktop.musixmatch.com",
    "cookie": "AWSELB=0",
    "User-Agent": BROWSER_UA,
}


def _musixmatch_token():
    """Return a usable Musixmatch user token, cached in-process.

    A token can be supplied via `MUSIXMATCH_TOKEN`; otherwise we fetch the one
    the web desktop app uses. Tokens are valid for hours, so we cache it and
    refresh lazily.
    """
    with _mxm_lock:
        if _mxm_token["value"] and _mxm_token["expires_at"] > time.time():
            return _mxm_token["value"]

        override = os.getenv("MUSIXMATCH_TOKEN")
        if override:
            _mxm_token.update(value=override, expires_at=time.time() + 9 * 3600)
            return override

        try:
            r = requests.get(
                f"{MXM_BASE}/token.get",
                params={"app_id": "web-desktop-app-v1.0"},
                headers=_MXM_HEADERS,
                timeout=5,
            )
            token = (r.json().get("message", {}).get("body", {}) or {}).get("user_token")
        except (requests.RequestException, ValueError, AttributeError):
            return None

        # Musixmatch hands out a sentinel token when rate-limiting; reject it.
        if not token or token.startswith("UpgradeOnly"):
            return None
        _mxm_token.update(value=token, expires_at=time.time() + 9 * 3600)
        return token


def _provider_musixmatch(artist, title, album, duration):
    token = _musixmatch_token()
    if not token:
        return None

    params = {
        "format": "json",
        "namespace": "lyrics_richsynched",
        "subtitle_format": "lrc",
        "app_id": "web-desktop-app-v1.0",
        "usertoken": token,
        "q_artist": artist,
        "q_track": title,
    }
    seconds = _int_duration(duration)
    if seconds is not None:
        params["q_duration"] = seconds

    try:
        r = requests.get(
            f"{MXM_BASE}/macro.subtitles.get", params=params, headers=_MXM_HEADERS, timeout=6
        )
        calls = r.json().get("message", {}).get("body", {})
        calls = calls.get("macro_calls", {}) if isinstance(calls, dict) else {}
    except (requests.RequestException, ValueError, AttributeError):
        return None

    def _body(call):
        node = calls.get(call, {})
        body = node.get("message", {}).get("body") if isinstance(node, dict) else None
        return body if isinstance(body, dict) else {}

    synced = None
    subtitle_list = _body("track.subtitles.get").get("subtitle_list")
    if subtitle_list:
        synced = subtitle_list[0].get("subtitle", {}).get("subtitle_body") or None

    lyrics = _body("track.lyrics.get").get("lyrics", {}).get("lyrics_body") or None

    if lyrics or synced:
        return {"lyrics": lyrics, "synced": synced}
    return None


def _parse_genius_html(html):
    if BeautifulSoup is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select('[data-lyrics-container="true"]')
    if not containers:
        return None
    # Genius wraps non-lyrics noise (contributor counts, translation links,
    # the song description) in elements flagged for exclusion — drop them.
    for noise in soup.select('[data-exclude-from-selection="true"]'):
        noise.decompose()
    text = "\n".join(c.get_text(separator="\n") for c in containers).strip()
    return text or None


def _provider_genius(artist, title, album, duration):
    if BeautifulSoup is None:
        return None

    try:
        r = requests.get(
            "https://genius.com/api/search/multi",
            params={"q": f"{artist} {title}"},
            headers={"User-Agent": BROWSER_UA},
            timeout=6,
        )
        sections = r.json().get("response", {}).get("sections", [])
    except (requests.RequestException, ValueError, AttributeError):
        return None

    url = None
    for section in sections:
        if section.get("type") != "song":
            continue
        for hit in section.get("hits", []):
            url = hit.get("result", {}).get("url")
            if url:
                break
        if url:
            break
    if not url:
        return None

    try:
        page = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=6)
    except requests.RequestException:
        return None
    if page.status_code != 200:
        return None

    text = _parse_genius_html(page.text)
    if text:
        return {"lyrics": text, "synced": None}
    return None


PROVIDERS = {
    "lrclib": _provider_lrclib,
    "musixmatch": _provider_musixmatch,
    "genius": _provider_genius,
}
DEFAULT_PROVIDER_ORDER = "lrclib,musixmatch,genius"


def _enabled_providers():
    """Resolve the ordered provider list from `LYRICS_PROVIDERS`.

    Unknown names are ignored, so an operator can disable a flaky provider just
    by dropping it from the list.
    """
    raw = os.getenv("LYRICS_PROVIDERS", DEFAULT_PROVIDER_ORDER)
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    return [(n, PROVIDERS[n]) for n in names if n in PROVIDERS]


def fetch_lyrics(track_id, artist, title, album=None, duration=None, force=False):
    """Resolve lyrics for the current track from the web, with caching.

    Tries each enabled provider in order and keeps the first non-empty result.
    Returns a dict {"lyrics": str|None, "synced": str|None, "source": str}.
    `source` is "cache" on a cache hit, the provider name on a fresh hit, or
    "none" when nothing was found.
    """
    if not title or not artist:
        return {"lyrics": None, "synced": None, "source": "none"}

    cache_key = track_id or f"{artist}|{title}"
    if not force:
        cached = _cache_get(cache_key)
        if cached is not None:
            return {**cached, "source": "cache"}

    result = {"lyrics": None, "synced": None, "source": "none"}
    for name, provider in _enabled_providers():
        try:
            found = provider(artist, title, album, duration)
        except Exception:
            # A misbehaving provider must not break the chain.
            found = None
        if found and (found.get("lyrics") or found.get("synced")):
            result = {
                "lyrics": found.get("lyrics"),
                "synced": found.get("synced"),
                "source": name,
            }
            break

    found = bool(result["lyrics"] or result["synced"])
    _cache_set(cache_key, {"lyrics": result["lyrics"], "synced": result["synced"]},
               TTL_HIT if found else TTL_MISS)
    return result
