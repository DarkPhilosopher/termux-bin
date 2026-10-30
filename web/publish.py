#!/usr/bin/env python3
"""publish.py DEST -- build the public copy of the Mind & Routine app into
DEST (a clone of the public `mind` repo, served by GitHub Pages).

Only CODE goes public. This refuses to build if any personal text or any
check-in data would end up in the copy:
  - the <script id="seed"> block must be empty ([]) -- check-ins never ship
  - personal comment lines (quoted requests, names) are stripped first
  - then a word list is checked; any hit = stop, nothing written
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {"mind.html": "index.html", "sw.js": "sw.js", "manifest.webmanifest": "manifest.webmanifest",
         "icon-192.png": "icon-192.png", "icon-512.png": "icon-512.png"}
# lowercase words that must never appear in the public copy
PERSONAL = ["gabe", "gabriel", "lewis", "yahoona", "chicken", "deligation", "denver",
            "a17", "a33", "requested:", "asked for:", "lewisgabe", "darkphilosopher/claude"]

HEADER = """<!--
  Mind & Routine -- mental health check-in + daily routine, offline.
  One page: no account, no server. Everything you enter stays in this
  browser on your phone (localStorage); "Save JSON" exports it to a file.
  Installable from Chrome (Add to Home screen); works offline after the
  first visit; optional check-in reminders via Chrome notifications.
  Crisis help: 988 (US, call or text), 911 / 112 for emergencies.
-->"""


def clean_html(s):
    s = re.sub(r"<!--.*?-->", HEADER, s, count=1, flags=re.S)       # first comment = personal header
    s = re.sub(r"^// Asked for:.*\n", "", s, flags=re.M)
    s = s.replace("Gabe's rule (merge-provenance): never silently", "Rule: never silently")
    m = re.search(r'<script id="seed" type="application/json">(.*?)</script>', s, re.S)
    if not m or m.group(1).strip() != "[]":
        sys.exit("STOP: the seed block isn't empty -- check-in data must never be published")
    return s


def main(dest):
    out = {}
    for src, name in FILES.items():
        data = open(os.path.join(HERE, src), "rb").read()
        if src.endswith((".html", ".js", ".webmanifest")):
            text = data.decode()
            if src == "mind.html":
                text = clean_html(text)
            low = text.lower()
            hits = [w for w in PERSONAL if w in low]
            if hits:
                sys.exit("STOP: personal text in %s: %s -- nothing written" % (name, ", ".join(hits)))
            data = text.encode()
        out[name] = data
    for name, data in out.items():
        with open(os.path.join(dest, name), "wb") as f:
            f.write(data)
    print("built %d files into %s, personal-text check passed" % (len(out), dest))


if __name__ == "__main__":
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit(__doc__)
    main(sys.argv[1])
