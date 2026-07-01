#!/usr/bin/env python3
"""Batch-embed lyrics into the tags of every music file in a folder.

Walks a directory, reads each track's metadata, fetches plain-text lyrics from
the configured web providers (services.lyrics) and writes them into the file's
lyrics tag (services.tags). Lyrion is never involved: run it whenever, then let
Lyrion pick the changes up on its next scan.

Usage:
    python scripts/embed_lyrics.py /path/to/music [--dry-run] [--force]
                                   [--clear] [--no-verify] [--delay 0.5]
                                   [--verbose]

Because tags are written permanently (and then propagate to Lyrion, other
players and backups), a result is only accepted when the provider's own
metadata matches the file's title/artist/duration — a mismatch is worse than no
lyrics, and a miss can always be retried later. Pass --no-verify to turn that
check off and take whatever a provider returns.

--clear drops the existing lyrics tag when nothing is found online, so the file
matches what providers actually carry. Like --force it processes already-tagged
files too (it must look them up to know whether to clear), so a --clear run
hits the web for every file; combine with --force to also overwrite when found.
A result that fails verification counts as "nothing usable found", so --clear
treats it like a miss and still drops the tag — verification decides what gets
written, not what gets cleared.

Several targets are accepted, and shell-style wildcards work even when quoted
(or when the shell finds no match and passes the pattern through literally):
    python scripts/embed_lyrics.py /path/to/music/A*
    python scripts/embed_lyrics.py "/path/to/music/A*" /path/to/music/B*
Each target may be a directory (scanned recursively) or a single music file.

Config is read from the repo-root .env automatically (if python-dotenv is
installed), so the CLI honors the same settings as the web app without needing
`source .env`. Provider order comes from LYRICS_PROVIDERS (defaults to
lrclib,musixmatch,genius); LRCLIB_TIMEOUT (seconds, default 15) is honored too —
raise it for big batches when LRCLIB is slow under load.
"""

import argparse
import glob
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


def resolve_targets(patterns):
    """Expand CLI arguments into an ordered, de-duplicated list of paths.

    Patterns the shell already expanded arrive as plain paths; literal
    patterns (quoted, or left untouched because the shell found no match) are
    expanded here so `A*` works either way. Returns (paths, missing) where
    `missing` is the wildcard patterns that matched nothing — reported, not
    fatal, so a partial batch still runs.
    """
    paths, missing, seen = [], [], set()
    for pattern in patterns:
        if glob.has_magic(pattern):
            matches = sorted(glob.glob(pattern))
            if not matches:
                missing.append(pattern)
                continue
        else:
            matches = [pattern]
        for match in matches:
            if match not in seen:
                seen.add(match)
                paths.append(match)
    return paths, missing


def iter_music_files(targets):
    """Yield (path, rel) for every music file in `targets`, in stable order.

    Each target is a directory (walked) or a single music file (yielded as-is).
    `rel` is the path shown in logs: it stays relative to the target's parent so
    the matched folder name is kept (readable even when several targets match a
    wildcard), without the `../../` noise of a cwd-relative path.
    """
    for target in targets:
        base = os.path.dirname(os.path.normpath(target))
        if os.path.isdir(target):
            for dirpath, _dirs, files in os.walk(target):
                for name in sorted(files):
                    path = os.path.join(dirpath, name)
                    if tags.is_music_file(path):
                        yield path, os.path.relpath(path, base)
        elif os.path.isfile(target):
            if tags.is_music_file(target):
                yield target, os.path.relpath(target, base)
        else:
            print(f"warning: not a file or directory: {target}", file=sys.stderr)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Embed web lyrics into the tags of music files in a folder."
    )
    parser.add_argument(
        "targets", nargs="+",
        help="Directories or files to process. Shell-style wildcards (e.g. "
             "A*) are accepted, even quoted.",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Seconds to wait between web lookups, to stay polite (default 0.5).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite the lyrics tag even when one is already present.",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Remove an existing lyrics tag when nothing is found online "
             "(processes already-tagged files too, so it queries the web for "
             "every file).",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Accept a provider's lyrics even when its own title/artist/duration "
             "don't match the file. Off by default: since tags are written "
             "permanently, a mismatched result is worse than no lyrics.",
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
    targets, missing = resolve_targets(args.targets)
    for pattern in missing:
        print(f"warning: no match for pattern: {pattern}", file=sys.stderr)
    if not targets:
        print("error: no existing file or directory to process", file=sys.stderr)
        return 2

    counts = {
        "scanned": 0, "written": 0, "already": 0,
        "not_found": 0, "rejected": 0, "cleared": 0, "no_meta": 0, "failed": 0,
    }
    dry = " (dry-run)" if args.dry_run else ""

    for path, rel in iter_music_files(targets):
        counts["scanned"] += 1

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
        # Skip already-tagged files unless we have a reason to look them up:
        # --force (to overwrite) or --clear (to drop the tag if nothing is
        # found online). Both require fetching to make that decision.
        if already and not args.force and not args.clear:
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
            verify=not args.no_verify,
        )
        plain = result.get("lyrics")
        if not plain and result.get("synced"):
            plain = tags.lrc_to_plain(result["synced"])

        if not plain:
            # Nothing usable online — either a genuine miss or a candidate that
            # failed verification. With --clear, drop an existing tag in both
            # cases so the file reflects what providers actually carry:
            # verification governs what we *write*, not what we *clear*.
            if already and args.clear:
                if args.dry_run:
                    counts["cleared"] += 1
                    print(f"[would-clear] {rel}")
                else:
                    try:
                        tags.clear_lyrics(path)
                        counts["cleared"] += 1
                        print(f"[cleared]   {rel}")
                    except tags.LyricsTagError as exc:
                        counts["failed"] += 1
                        print(f"[fail]      {rel}: {exc}")
            elif result.get("source") == "rejected":
                counts["rejected"] += 1
                print(f"[reject]    {rel}  (no confident match)")
            else:
                counts["not_found"] += 1
                print(f"[none]      {rel}")
            time.sleep(args.delay)
            continue

        # Found online. Only write when it's new or --force overwrites; an
        # existing tag we're not forcing (reached here via --clear) is kept.
        if already and not args.force:
            counts["already"] += 1
            if args.verbose:
                print(f"[skip:has]  {rel}  (found online, kept existing)")
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
    print(f"written:     {counts['written']}{dry}")
    print(f"cleared:     {counts['cleared']}{dry}")
    print(f"already:     {counts['already']}")
    print(f"not found:   {counts['not_found']}")
    print(f"rejected:    {counts['rejected']}")
    print(f"no metadata: {counts['no_meta']}")
    print(f"failed:      {counts['failed']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
