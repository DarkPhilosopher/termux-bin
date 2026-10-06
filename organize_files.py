#!/data/data/com.termux/files/usr/bin/python
"""Sorts loose files in a folder into type-based subfolders (Images,
Videos, Documents, ...). Moves, never deletes -- and every move is
logged, so `--undo` can put everything back exactly where it was.

    organize-files                     dry run on the default folders,
                                        prints what WOULD happen
    organize-files --apply             actually do it
    organize-files --source /sdcard/Download --apply
    organize-files --undo              reverse the most recent run

**Dry run by default, on purpose** -- nothing moves until you pass
--apply, same reasoning Spark's own updater.py states for itself:
seeing what a sweep over possibly thousands of files would do, before
it does it, matters more than saving a keystroke.

**Scope, on purpose**: defaults to /sdcard/Download only -- the one
folder that's genuinely "unsorted inbox" on every Android phone. Pass
--source as many times as you like to widen it. Two things are never
touched even if you point --source at them directly: any folder named
exactly "Camera" (Android's camera app, and Google Photos backup,
expect DCIM/Camera to stay exactly as it is -- moving photos out of
it breaks both) and Termux's own home / anything containing a .git
folder (that's code, not an inbox).
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

LOG_FILE = Path.home() / ".organize_files.log.jsonl"

DEFAULT_SOURCES = ["/sdcard/Download"]

NEVER_TOUCH_NAMES = {"Camera", "Android", ".git"}
TERMUX_HOME = Path("/data/data/com.termux/files/home").resolve()

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".svg"},
    "Videos": {".mp4", ".mov", ".mkv", ".webm", ".avi", ".3gp", ".m4v"},
    "Audio": {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                  ".txt", ".odt", ".md", ".csv"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "Installers": {".apk", ".apks", ".xapk"},
}
CATEGORY_NAMES = set(CATEGORIES) | {"Other"}


def category_for(path):
    ext = path.suffix.lower()
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return "Other"


def is_protected(path):
    try:
        path.resolve().relative_to(TERMUX_HOME)
        return True
    except ValueError:
        pass
    return any(part in NEVER_TOUCH_NAMES for part in path.parts)


def unique_destination(dest_dir, name):
    target = dest_dir / name
    if not target.exists():
        return target
    stem, suffix = Path(name).stem, Path(name).suffix
    i = 1
    while True:
        candidate = dest_dir / ("%s_%d%s" % (stem, i, suffix))
        if not candidate.exists():
            return candidate
        i += 1


def find_loose_files(source):
    """Files directly under `source` or any subfolder that ISN'T already
    one of our own category names -- so a second run doesn't try to
    re-sort Images/Images/..."""
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        if is_protected(item):
            continue
        if item.parent.name in CATEGORY_NAMES and item.parent.parent == source:
            continue  # already sorted into <source>/<Category>/
        yield item


def log_move(src, dest):
    with LOG_FILE.open("a") as f:
        f.write(json.dumps({"time": time.time(), "from": str(src), "to": str(dest)}) + "\n")


def do_organize(sources, apply):
    moves = []
    for source in sources:
        source = Path(source)
        if is_protected(source):
            print("skipping %s -- protected location" % source)
            continue
        if not source.is_dir():
            print("skipping %s -- not a folder" % source)
            continue
        for item in find_loose_files(source):
            category = category_for(item)
            dest_dir = source / category
            dest = unique_destination(dest_dir, item.name)
            moves.append((item, dest))

    if not moves:
        print("nothing to organize.")
        return

    for src, dest in moves:
        print(("would move: " if not apply else "moving:     ") +
              "%s -> %s" % (src, dest))
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            log_move(src, dest)

    print()
    print("%d file%s %s." % (
        len(moves), "" if len(moves) == 1 else "s",
        "moved" if apply else "would move -- nothing changed, run with --apply"))
    if apply:
        print("undo any time with: organize-files --undo")


def do_undo():
    if not LOG_FILE.exists():
        print("nothing logged -- nothing to undo.")
        return
    entries = [json.loads(line) for line in LOG_FILE.read_text().splitlines() if line.strip()]
    if not entries:
        print("nothing logged -- nothing to undo.")
        return
    undone = []
    skipped = []
    for entry in reversed(entries):
        src, dest = Path(entry["from"]), Path(entry["to"])
        if not dest.exists():
            skipped.append((dest, "no longer there"))
            continue
        if src.exists():
            skipped.append((dest, "original spot is occupied again"))
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(src))
        undone.append((dest, src))
        print("restored: %s -> %s" % (dest, src))
    print()
    print("%d restored, %d skipped." % (len(undone), len(skipped)))
    for path, reason in skipped:
        print("  skipped %s (%s)" % (path, reason))
    if undone:
        LOG_FILE.unlink()
        print("log cleared -- that run is fully undone.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", action="append", default=None,
                   help="a folder to organize (repeatable). Default: /sdcard/Download")
    p.add_argument("--apply", action="store_true", help="actually move files")
    p.add_argument("--undo", action="store_true", help="reverse the logged moves")
    args = p.parse_args()

    if args.undo:
        do_undo()
        return
    do_organize(args.source or DEFAULT_SOURCES, args.apply)


if __name__ == "__main__":
    main()
