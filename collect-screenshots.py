#!/data/data/com.termux/files/usr/bin/python
"""
Finds screenshot-like image files under one or more source directories and
relocates (moves) them into a single destination directory that's easy for
someone else to browse from outside the app sandbox.

Usage:
    python collect-screenshots.py SOURCE_DIR [SOURCE_DIR2 ...] [--dest DIR] [--copy] [--all-images]

Defaults:
    --dest defaults to /sdcard/ClaudeInbox/screenshots
    By default only files whose name contains "screenshot" (case-insensitive)
    are matched. Pass --all-images to grab every .png/.jpg/.jpeg instead.
    Pass --copy to copy instead of move (originals left in place).
"""
import argparse
import shutil
import sys
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_DEST = "/sdcard/ClaudeInbox/screenshots"


def is_match(path, all_images):
    if path.suffix.lower() not in IMAGE_EXTS:
        return False
    if all_images:
        return True
    return "screenshot" in path.name.lower()


def unique_destination(dest_dir, name):
    target = dest_dir / name
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    i = 1
    while True:
        candidate = dest_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sources", nargs="+", help="One or more directories to search")
    ap.add_argument("--dest", default=DEFAULT_DEST, help=f"Destination directory (default: {DEFAULT_DEST})")
    ap.add_argument("--copy", action="store_true", help="Copy instead of move (keeps originals)")
    ap.add_argument("--all-images", action="store_true", help="Grab all images, not just ones named 'screenshot*'")
    args = ap.parse_args()

    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)

    found = 0
    moved = 0
    errors = []

    for src in args.sources:
        src_dir = Path(src)
        if not src_dir.exists():
            print(f"skip (not found): {src_dir}")
            continue
        for path in src_dir.rglob("*"):
            if not path.is_file() or not is_match(path, args.all_images):
                continue
            found += 1
            target = unique_destination(dest_dir, path.name)
            try:
                if args.copy:
                    shutil.copy2(path, target)
                else:
                    shutil.move(str(path), str(target))
                moved += 1
                print(f"{'copied' if args.copy else 'moved'}: {path} -> {target}")
            except Exception as e:
                errors.append((path, str(e)))
                print(f"ERROR on {path}: {e}", file=sys.stderr)

    print(f"\n{found} matched, {moved} {'copied' if args.copy else 'moved'} into {dest_dir}")
    if errors:
        print(f"{len(errors)} error(s) - see above", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
