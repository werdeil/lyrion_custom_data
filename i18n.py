"""UI translations (FR/EN).

Language is picked per-request from the browser's Accept-Language header,
falling back to French. The whole dict for the chosen language is handed to the
template (and serialised to JS) so every visible string has a single source of
truth here.
"""

SUPPORTED = ("fr", "en")
DEFAULT_LANG = "fr"

TRANSLATIONS = {
    "fr": {
        # Now playing
        "empty_state": "Aucune lecture en cours",
        "no_lyrics": "Pas de paroles",
        "lyrics_search": "Recherche de paroles sur le web",
        "lyrics_label": "Paroles web",
        "lyrics_mode_off": "Désactivé",
        "lyrics_mode_once": "Une fois",
        "lyrics_mode_auto": "Auto",
        "lyrics_mode_off_hint": "Ne pas chercher en ligne",
        "lyrics_mode_once_hint": "Chercher pour ce morceau uniquement",
        "lyrics_mode_auto_hint": "Chercher automatiquement pour chaque morceau sans paroles",
        "searching": "Recherche…",
        "no_lyrics_web": "Aucune parole trouvée sur le web",
        "open_lyrion": "Ouvrir dans Lyrion",
        "cover_alt": "Pochette",
        "source_prefix": "Source :",
        "source_library": "Bibliothèque",
        "sync_on": "Paroles synchronisées",
        "sync_off": "Paroles simples",
        # Stats
        "stats_title": "Statistiques",
        "albums": "Albums",
        "album_artists": "Artistes d'album",
        "track_artists": "Artistes de morceau",
        "tracks": "Morceaux",
        "misc": "Divers",
        "total": "Total",
        "fully_played": "Écoutés complètement",
        "partially_played": "Partiellement écoutés",
        "never_played": "Jamais écoutés",
        "played": "Écoutés",
        "unplayed": "Jamais écoutés",
        "total_plays": "Écoutes cumulées",
        "total_skips": "Sauts cumulés",
        "genres": "Genres",
        "rated_songs": "Morceaux notés",
        "with_lyrics": "Avec paroles",
        "played_last_30d": "Écoutés (30 j)",
        "played_last_year": "Écoutés (1 an)",
    },
    "en": {
        # Now playing
        "empty_state": "Nothing playing",
        "no_lyrics": "No lyrics",
        "lyrics_search": "Web lyrics search",
        "lyrics_label": "Web lyrics",
        "lyrics_mode_off": "Off",
        "lyrics_mode_once": "Once",
        "lyrics_mode_auto": "Auto",
        "lyrics_mode_off_hint": "Don't search online",
        "lyrics_mode_once_hint": "Search for this track only",
        "lyrics_mode_auto_hint": "Search automatically for every track without lyrics",
        "searching": "Searching…",
        "no_lyrics_web": "No lyrics found on the web",
        "open_lyrion": "Open in Lyrion",
        "cover_alt": "Cover",
        "source_prefix": "Source:",
        "source_library": "Library",
        "sync_on": "Synced lyrics",
        "sync_off": "Plain lyrics",
        # Stats
        "stats_title": "Statistics",
        "albums": "Albums",
        "album_artists": "Album artists",
        "track_artists": "Track artists",
        "tracks": "Tracks",
        "misc": "Misc",
        "total": "Total",
        "fully_played": "Fully played",
        "partially_played": "Partially played",
        "never_played": "Never played",
        "played": "Played",
        "unplayed": "Never played",
        "total_plays": "Cumulative plays",
        "total_skips": "Cumulative skips",
        "genres": "Genres",
        "rated_songs": "Rated songs",
        "with_lyrics": "With lyrics",
        "played_last_30d": "Played last 30d",
        "played_last_year": "Played last year",
    },
}


def pick_lang(accept_languages):
    """Best supported language from a Werkzeug Accept-Language, defaulting to FR."""
    return accept_languages.best_match(SUPPORTED) or DEFAULT_LANG
