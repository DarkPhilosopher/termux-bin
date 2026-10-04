"""Shared catalog-scanning logic for `programs` and `overseer` -- kept
in one place so the two don't drift into slightly different copies of
the same $PREFIX/bin scan. See either program's own docstring for what
this is actually for; see programs-catalog memory for the convention
("# CATALOG: ..." near the top of a shim) that makes it work.
"""

import os

BIN_DIR = "/data/data/com.termux/files/usr/bin"
TAG = "# CATALOG:"


def discover():
    """Every $PREFIX/bin file that's executable, readable as text, and
    carries a "# CATALOG: ..." line -- re-scanned fresh every call, on
    purpose, so this never drifts out of date with what's installed."""
    entries = []
    try:
        names = sorted(os.listdir(BIN_DIR))
    except OSError:
        return entries
    for name in names:
        path = os.path.join(BIN_DIR, name)
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            continue
        try:
            with open(path, "r") as f:
                head = f.read(2000)
        except (UnicodeDecodeError, OSError):
            continue  # a binary or something unreadable -- not one of ours
        for line in head.splitlines():
            stripped = line.strip()
            if stripped.startswith(TAG):
                entries.append((name, stripped[len(TAG):].strip()))
                break
    return entries


def format_list():
    """Numbered, in the same stable order discover() always returns
    (alphabetical by filename) -- the "open by number" instruction is
    said once here, in the header, rather than repeated on every line."""
    entries = discover()
    if not entries:
        return ["no tagged commands found in " + BIN_DIR]
    width = max(len(name) for name, _ in entries)
    num_width = len(str(len(entries)))
    lines = ["%d command%s found -- open one by name or number (e.g. /open 3):"
             % (len(entries), "" if len(entries) == 1 else "s")]
    for i, (name, desc) in enumerate(entries, 1):
        lines.append("  %*d. %-*s  %s" % (num_width, i, width, name, desc))
    return lines


def resolve(token):
    """token is either a command's name or its 1-based number from
    format_list()'s own ordering -- returns the matching name, or None
    if it matches neither. Shared so /open (in both `programs` and
    `overseer`) never has to know which form it was given."""
    entries = discover()
    token = token.strip()
    if token.isdigit():
        i = int(token)
        return entries[i - 1][0] if 1 <= i <= len(entries) else None
    names = {n for n, _ in entries}
    return token if token in names else None
