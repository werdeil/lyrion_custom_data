import sqlite3
from flask import current_app


def get_db_conn():
    conn = sqlite3.connect(current_app.config["DB_PATH"])
    conn.execute(
        f"ATTACH DATABASE '{current_app.config['DB_PERSIST_PATH']}' AS persist"
    )
    conn.row_factory = sqlite3.Row
    return conn


def get_albums():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT albums.id,
               albums.title,
               contributors.name AS artist,
               albums.artwork
        FROM albums
        JOIN contributors ON albums.contributor = contributors.id
        ORDER BY RANDOM()
        LIMIT 5
    """)
    albums = cur.fetchall()
    conn.close()
    return albums


def get_albums_by_ids(album_ids):
    if not album_ids:
        return []

    conn = get_db_conn()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in album_ids)
    order_case = " ".join(f"WHEN albums.id=? THEN {idx}" for idx, _ in enumerate(album_ids))
    query = f"""
        SELECT albums.id,
               albums.title,
               contributors.name AS artist,
               albums.artwork
        FROM albums
        JOIN contributors ON albums.contributor = contributors.id
        WHERE albums.id IN ({placeholders})
        ORDER BY CASE {order_case} END
    """
    params = [*album_ids, *album_ids]
    cur.execute(query, params)
    albums = cur.fetchall()
    conn.close()
    return albums


def get_stats():
    conn = get_db_conn()
    cur = conn.cursor()

    def q(sql):
        try:
            return cur.execute(sql).fetchone()[0] or 0
        except Exception as e:
            print(f"[STATS ERROR] {e}\nSQL: {sql}")
            return 0

    def pct(part, total):
        if total == 0:
            return 0
        return round(part * 100 / total, 1)

    stats = {
        # Albums
        "albums_total": q("SELECT count(distinct albums.id) FROM albums"),
        "albums_played": q("""
            SELECT count(distinct albums.id) FROM albums
            WHERE albums.id NOT IN (
                SELECT tracks.album FROM tracks
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND (alternativeplaycount.playcount=0 OR alternativeplaycount.playcount IS NULL)
            )
        """),
        "albums_not_fully": q("""
            SELECT count(distinct albums.id) FROM albums
            JOIN tracks ON tracks.album=albums.id
            JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
            WHERE tracks.audio=1 AND (alternativeplaycount.playcount=0 OR alternativeplaycount.playcount IS NULL)
            AND albums.id IN (
                SELECT tracks.album FROM tracks
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND alternativeplaycount.playcount>0
            )
        """),
        "albums_never": q("""
            SELECT count(distinct albums.id) FROM albums
            WHERE albums.id NOT IN (
                SELECT tracks.album FROM tracks
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND alternativeplaycount.playcount>0
            )
        """),
        # Album artists
        "artists_total": q("""
            SELECT count(distinct contributors.id) FROM contributors
            LEFT JOIN contributor_track ON contributors.id=contributor_track.contributor
            WHERE contributor_track.role=5
        """),
        "artists_played": q("""
            SELECT count(distinct contributor_track.contributor) FROM contributor_track
            JOIN tracks ON tracks.id=contributor_track.track
            WHERE contributor_track.contributor NOT IN (
                SELECT contributors.id FROM contributors
                JOIN contributor_track ON contributors.id=contributor_track.contributor
                JOIN tracks ON tracks.id=contributor_track.track
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1
                AND (alternativeplaycount.playcount=0 OR alternativeplaycount.playcount IS NULL)
                AND contributor_track.role=5
            ) AND contributor_track.role=5
        """),
        "artists_partial": q("""
            SELECT count(distinct contributor_track.contributor) FROM contributor_track
            LEFT JOIN tracks ON tracks.id=contributor_track.track
            JOIN alternativeplaycount ON tracks.url=alternativeplaycount.url
            WHERE tracks.audio=1
            AND (alternativeplaycount.playcount=0 OR alternativeplaycount.playcount IS NULL)
            AND contributor_track.role=5
            AND contributor_track.contributor IN (
                SELECT contributors.id FROM contributors
                LEFT JOIN contributor_track ON contributors.id=contributor_track.contributor
                JOIN tracks ON tracks.id=contributor_track.track
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND alternativeplaycount.playcount>0
                AND contributor_track.role=5
            )
        """),
        "artists_unplayed": q("""
            SELECT count(distinct contributor_track.contributor) FROM contributor_track
            JOIN tracks ON tracks.id=contributor_track.track
            WHERE contributor_track.contributor NOT IN (
                SELECT contributors.id FROM contributors
                LEFT JOIN contributor_track ON contributors.id=contributor_track.contributor
                JOIN tracks ON tracks.id=contributor_track.track
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND alternativeplaycount.playcount>0
                AND contributor_track.role=5
            ) AND contributor_track.role=5
        """),
        # Songs
        "songs_total": q("SELECT count(*) FROM tracks WHERE audio=1"),
        "songs_played_apc": q("""
            SELECT count(distinct tracks.id) FROM tracks
            JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
            WHERE audio=1 AND alternativeplaycount.playcount>0
        """),
        "songs_unplayed_apc": q("""
            SELECT count(distinct tracks.id) FROM tracks
            JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
            WHERE audio=1 AND ifnull(alternativeplaycount.playcount, 0) = 0
        """),
        "songs_total_plays_apc": q("""
            SELECT sum(alternativeplaycount.playcount) FROM tracks
            JOIN alternativeplaycount ON tracks.url=alternativeplaycount.url
            WHERE audio=1 AND alternativeplaycount.playcount>0
        """),
        # Divers
        "genres": q("SELECT count(*) FROM genres"),
        "rated_songs": q("""
            SELECT count(*) FROM tracks
            JOIN persist.tracks_persistent ON tracks.url=persist.tracks_persistent.url
            WHERE audio=1 AND persist.tracks_persistent.rating>0
        """),
        "songs_with_lyrics": q("""
            SELECT count(distinct tracks.id) FROM tracks
            WHERE audio=1 AND lyrics IS NOT NULL
        """),
        # Velocity
        "velocity_30d": q("""
            SELECT COUNT(*) FROM persist.tracks_persistent
            WHERE lastplayed > strftime('%s','now','-30 days')
        """),
    }

    # Pourcentages albums
    stats["albums_played_pct"] = pct(stats["albums_played"], stats["albums_total"])
    stats["albums_not_fully_pct"] = pct(stats["albums_not_fully"], stats["albums_total"])
    stats["albums_never_pct"] = pct(stats["albums_never"], stats["albums_total"])

    # Pourcentages artistes
    stats["artists_played_pct"] = pct(stats["artists_played"], stats["artists_total"])
    stats["artists_partial_pct"] = pct(stats["artists_partial"], stats["artists_total"])
    stats["artists_unplayed_pct"] = pct(stats["artists_unplayed"], stats["artists_total"])

    # Pourcentages songs
    stats["songs_played_pct"] = pct(stats["songs_played_apc"], stats["songs_total"])
    stats["songs_unplayed_apc_pct"] = pct(stats["songs_unplayed_apc"], stats["songs_total"])

    # Pourcentages divers
    stats["rated_songs_pct"] = pct(stats["rated_songs"], stats["songs_total"])
    stats["lyrics_pct"] = pct(stats["songs_with_lyrics"], stats["songs_total"])

    conn.close()
    return stats
