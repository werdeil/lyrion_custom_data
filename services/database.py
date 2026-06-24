import sqlite3
from flask import current_app
from contextlib import contextmanager


@contextmanager
def get_db_conn():
    db = current_app.config["DB_PATH"]
    persist = current_app.config["DB_PERSIST_PATH"]
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.isolation_level = None
    conn.execute(f"ATTACH DATABASE 'file:{persist}?mode=ro' AS persist")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA mmap_size = 268435456")
    conn.execute("PRAGMA cache_size = -32000")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("BEGIN DEFERRED")
    try:
        yield conn
    finally:
        conn.execute("COMMIT")
        conn.close()


def get_track_lyrics(track_id):
    """Return the stored lyrics for a Lyrion track id, or None if absent."""
    if not track_id:
        return None

    with get_db_conn() as conn:
        row = conn.execute(
            "SELECT lyrics FROM tracks WHERE id = ?",
            (track_id,),
        ).fetchone()

    if row and row["lyrics"]:
        return row["lyrics"]
    return None


def get_stats():
    with get_db_conn() as conn:
        cur = conn.cursor()

        def pct(part, total):
            if total == 0:
                return 0
            return round(part * 100 / total, 1)

        # Query 1: albums + songs — single scan of tracks JOIN alternativeplaycount
        row = cur.execute("""
            WITH track_play AS (
                SELECT
                    t.id,
                    t.album,
                    COALESCE(apc.playcount, 0) > 0 AS is_played,
                    COALESCE(apc.playcount, 0)      AS playcount,
                    COALESCE(apc.skipcount, 0)      AS skipcount
                FROM tracks t
                LEFT JOIN alternativeplaycount apc ON t.urlmd5 = apc.urlmd5
                WHERE t.audio = 1
            ),
            album_agg AS (
                SELECT album, COUNT(*) AS total, SUM(is_played) AS played
                FROM track_play
                GROUP BY album
            )
            SELECT
                (SELECT COUNT(DISTINCT id) FROM albums)                          AS albums_total,
                SUM(played = total)                                              AS albums_played,
                SUM(played > 0 AND played < total)                              AS albums_not_fully,
                SUM(played = 0)                                                  AS albums_never,
                (SELECT COUNT(*) FROM track_play)                               AS songs_total,
                (SELECT SUM(is_played) FROM track_play)                        AS songs_played_apc,
                (SELECT COUNT(*) - SUM(is_played) FROM track_play)             AS songs_unplayed_apc,
                (SELECT SUM(playcount) FROM track_play WHERE playcount > 0)    AS songs_total_plays_apc,
                (SELECT SUM(skipcount) FROM track_play WHERE skipcount > 0)    AS songs_total_skips_apc
            FROM album_agg
        """).fetchone()

        stats = {
            "albums_total":          row["albums_total"] or 0,
            "albums_played":         row["albums_played"] or 0,
            "albums_not_fully":      row["albums_not_fully"] or 0,
            "albums_never":          row["albums_never"] or 0,
            "albums_non_played":     (row["albums_not_fully"] or 0) + (row["albums_never"] or 0),
            "songs_total":           row["songs_total"] or 0,
            "songs_played_apc":      row["songs_played_apc"] or 0,
            "songs_unplayed_apc":    row["songs_unplayed_apc"] or 0,
            "songs_total_plays_apc": row["songs_total_plays_apc"] or 0,
            "songs_total_skips_apc": row["songs_total_skips_apc"] or 0,
        }

        # Query 2: artists (album artists) — single scan via contributor_track
        row = cur.execute("""
            WITH track_play AS (
                SELECT t.id, COALESCE(apc.playcount, 0) > 0 AS is_played
                FROM tracks t
                LEFT JOIN alternativeplaycount apc ON t.urlmd5 = apc.urlmd5
                WHERE t.audio = 1
            ),
            artist_agg AS (
                SELECT ct.contributor, COUNT(*) AS total, SUM(tp.is_played) AS played
                FROM contributor_track ct
                JOIN track_play tp ON ct.track = tp.id
                WHERE ct.role = 5
                GROUP BY ct.contributor
            )
            SELECT
                (SELECT COUNT(DISTINCT contributor) FROM contributor_track WHERE role = 5) AS artists_total,
                SUM(played = total)                AS artists_played,
                SUM(played = 0)                    AS artists_unplayed,
                SUM(played > 0 AND played < total) AS artists_partial
            FROM artist_agg
        """).fetchone()

        stats.update({
            "artists_total":    row["artists_total"] or 0,
            "artists_played":   row["artists_played"] or 0,
            "artists_unplayed": row["artists_unplayed"] or 0,
            "artists_partial":  row["artists_partial"] or 0,
            "artists_non_played": (row["artists_unplayed"] or 0) + (row["artists_partial"] or 0),
        })

        # Query 3: track artists — single scan via contributor_track
        row = cur.execute("""
            WITH track_play AS (
                SELECT t.id, COALESCE(apc.playcount, 0) > 0 AS is_played
                FROM tracks t
                LEFT JOIN alternativeplaycount apc ON t.urlmd5 = apc.urlmd5
                WHERE t.audio = 1
            ),
            track_artist_agg AS (
                SELECT ct.contributor, COUNT(*) AS total, SUM(tp.is_played) AS played
                FROM contributor_track ct
                JOIN track_play tp ON ct.track = tp.id
                WHERE ct.role IN (1, 5)
                GROUP BY ct.contributor
            )
            SELECT
                (SELECT COUNT(DISTINCT contributor) FROM contributor_track WHERE role IN (1, 5)) AS track_artists_total,
                SUM(played = total)                AS track_artists_fully_played,
                SUM(played = 0)                    AS track_artists_unplayed,
                SUM(played > 0 AND played < total) AS track_artists_partially_played
            FROM track_artist_agg
        """).fetchone()

        stats.update({
            "track_artists_total": row["track_artists_total"] or 0,
            "track_artists_fully_played": row["track_artists_fully_played"] or 0,
            "track_artists_unplayed": row["track_artists_unplayed"] or 0,
            "track_artists_partially_played": row["track_artists_partially_played"] or 0,
            "track_artists_non_played": (row["track_artists_unplayed"] or 0) + (row["track_artists_partially_played"] or 0),
        })

        # Query 4: misc stats (genres, ratings, lyrics, velocity)
        row = cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM genres) AS genres,
                (SELECT COUNT(DISTINCT t.id) FROM tracks t
                 JOIN persist.tracks_persistent tp ON t.url = tp.url
                 WHERE t.audio = 1 AND tp.rating > 0)                         AS rated_songs,
                (SELECT COUNT(DISTINCT id) FROM tracks
                 WHERE audio = 1 AND lyrics IS NOT NULL)                       AS songs_with_lyrics,
                (SELECT COUNT(*) FROM persist.tracks_persistent
                 WHERE lastplayed > strftime('%s', 'now', '-30 days'))         AS velocity_30d,
                (SELECT COUNT(*) FROM persist.tracks_persistent
                 WHERE lastplayed > strftime('%s', 'now', '-1 year'))          AS velocity_1year
        """).fetchone()

        stats.update({
            "genres":            row["genres"] or 0,
            "rated_songs":       row["rated_songs"] or 0,
            "songs_with_lyrics": row["songs_with_lyrics"] or 0,
            "velocity_30d":      row["velocity_30d"] or 0,
            "velocity_1year":    row["velocity_1year"] or 0,
        })

        # Pourcentages albums
        stats["albums_played_pct"]    = pct(stats["albums_played"],    stats["albums_total"])
        stats["albums_not_fully_pct"] = pct(stats["albums_not_fully"], stats["albums_total"])
        stats["albums_never_pct"]     = pct(stats["albums_never"],     stats["albums_total"])
        stats["albums_non_played_pct"] = pct(stats["albums_non_played"], stats["albums_total"])

        # Pourcentages artistes (album artists)
        stats["artists_played_pct"]   = pct(stats["artists_played"],   stats["artists_total"])
        stats["artists_partial_pct"]  = pct(stats["artists_partial"],  stats["artists_total"])
        stats["artists_unplayed_pct"] = pct(stats["artists_unplayed"], stats["artists_total"])
        stats["artists_non_played_pct"] = pct(stats["artists_non_played"], stats["artists_total"])

        # Pourcentages track artists
        stats["track_artists_fully_played_pct"] = pct(stats["track_artists_fully_played"], stats["track_artists_total"])
        stats["track_artists_partially_played_pct"] = pct(stats["track_artists_partially_played"], stats["track_artists_total"])
        stats["track_artists_unplayed_pct"] = pct(stats["track_artists_unplayed"], stats["track_artists_total"])
        stats["track_artists_non_played_pct"] = pct(stats["track_artists_non_played"], stats["track_artists_total"])

        # Pourcentages songs
        stats["songs_played_pct"]       = pct(stats["songs_played_apc"],  stats["songs_total"])
        stats["songs_unplayed_apc_pct"] = pct(stats["songs_unplayed_apc"], stats["songs_total"])

        # Pourcentages divers
        stats["rated_songs_pct"]        = pct(stats["rated_songs"],       stats["songs_total"])
        stats["songs_with_lyrics_pct"]  = pct(stats["songs_with_lyrics"], stats["songs_total"])

        return stats
