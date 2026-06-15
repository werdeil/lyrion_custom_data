#!/usr/bin/env python3
"""Batch-embed lyrics into the tags of every music file in a folder.

Walks a directory, reads each track's metadata, fetches plain-text lyrics from
the configured web providers (services.lyrics) and writes them into the file's
lyrics tag (services.tags). Lyrion is never involved: run it whenever, then let
Lyrion pick the changes up on its next scan.

Usage:
    python scripts/embed_lyrics.py /path/to/music [--dry-run] [--force]
                                   [--delay 0.5] [--verbose]

Config is read from the repo-root .env automatically (if python-dotenv is
installed), so the CLI honors the same settings as the web app without needing
`source .env`. Provider order comes from LYRICS_PROVIDERS (defaults to
lrclib,musixmatch,genius); LRCLIB_TIMEOUT (seconds, default 15) is honored too —
raise it for big batches when LRCLIB is slow under load.
"""

import argparse
import os
import sys
import time

# Allow running both as a script (python scripts/embed_lyrics.py) and as a
# module (python -m scripts.embed_lyrics) by putting the repo root on the path.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Load .env so the CLI honors the same config as the web app (LYRICS_PROVIDERS,
# LRCLIB_TIMEOUT, ...) without needing `source .env`. This must run before
# importing services.lyrics, whose timeout constant is read at import time.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:  # python-dotenv is optional; fall back to the real env.
    pass

from services.lyrics import fetch_lyrics  # noqa: E402
from services import tags  # noqa: E402


def iter_music_files(root):
    """Yield every music file under `root`, recursively, in stable order."""
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            if tags.is_music_file(path):
                yield path


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Embed web lyrics into the tags of music files in a folder."
    )
    parser.add_argument("folder", help="Directory to scan recursively.")
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Seconds to wait between web lookups, to stay polite (default 0.5).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite the lyrics tag even when one is already present.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would happen without writing any tag.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Log every file, including those skipped.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not os.path.isdir(args.folder):
        print(f"error: not a directory: {args.folder}", file=sys.stderr)
        return 2

    counts = {
        "scanned": 0, "written": 0, "already": 0,
        "not_found": 0, "no_meta": 0, "failed": 0,
    }

    for path in iter_music_files(args.folder):
        counts["scanned"] += 1
        rel = os.path.relpath(path, args.folder)

        meta = tags.read_metadata(path)
        if not meta or not meta.get("artist") or not meta.get("title"):
            counts["no_meta"] += 1
            if args.verbose:
                print(f"[skip:meta] {rel}")
            continue

        try:
            already = tags.has_lyrics(path)
        except Exception:
            already = False
        if already and not args.force:
            counts["already"] += 1
            if args.verbose:
                print(f"[skip:has]  {rel}")
            continue

        result = fetch_lyrics(
            track_id=None,
            artist=meta["artist"],
            title=meta["title"],
            album=meta.get("album"),
            duration=meta.get("duration"),
        )
        plain = result.get("lyrics")
        if not plain and result.get("synced"):
            plain = tags.lrc_to_plain(result["synced"])

        if not plain:
            counts["not_found"] += 1
            print(f"[none]      {rel}")
            time.sleep(args.delay)
            continue

        if args.dry_run:
            counts["written"] += 1
            print(f"[would]     {rel}  ({result.get('source')})")
        else:
            try:
                tags.write_lyrics(path, plain)
                counts["written"] += 1
                print(f"[ok]        {rel}  ({result.get('source')})")
            except tags.LyricsTagError as exc:
                counts["failed"] += 1
                print(f"[fail]      {rel}: {exc}")

        time.sleep(args.delay)

    print("\n--- Summary ---")
    print(f"scanned:     {counts['scanned']}")
    print(f"written:     {counts['written']}{' (dry-run)' if args.dry_run else ''}")
    print(f"already:     {counts['already']}")
    print(f"not found:   {counts['not_found']}")
    print(f"no metadata: {counts['no_meta']}")
    print(f"failed:      {counts['failed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
