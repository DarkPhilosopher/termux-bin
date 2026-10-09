"""Shared logic behind relay-file / relay-command / relay-claude: three
separate pinned notifications, each with one Reply button that routes
your typed text somewhere different --

    relay-file     reply gets saved to a file
    relay-command  reply runs as a real Termux command
    relay-claude   reply gets relayed into the running `claude` tmux
                   session -- the file Claude actually reads is
                   OVERWRITTEN each time (so it never re-reads old
                   stuff), with a dated history kept in a sibling file
                   instead of being lost

Any reply to any of the three, if it's itself a request to read
something aloud ("read my history out loud", "speak the last one",
etc.), switches into text-to-speech instead of the door's normal
action -- see `maybe_speak()`.

State lives in ~/.relay/:
    file.log            door 1's own saved replies, timestamped, never cleared
    claude-latest.txt    the file Claude reads -- door 3's "inbox",
                         overwritten every time, "xx-xx-xxxx last" stamped
    claude-history.txt   door 3's sibling archive -- append-only,
                         speaker-tagged ("you"/"claude"), never cleared

Honest gap, not pretended away: there's no automatic capture of
Claude's own replies into claude-history.txt -- reading the live tmux
pane reliably (knowing when a reply has finished, separating it from
everything else on screen) is a harder problem than this first pass
solves. `relay log-claude <text>` exists so Claude's own side CAN be
logged -- by hand, or by Claude itself calling it -- just not
automatically yet.
"""
import os
import subprocess
import time
from datetime import datetime

HOME = "/data/data/com.termux/files/home"
STATE = os.path.join(HOME, ".relay")
TMUX_SOCK = "/tmp/tmux-claude.sock"

FILE_LOG = os.path.join(STATE, "file.log")
CLAUDE_LATEST = os.path.join(STATE, "claude-latest.txt")
CLAUDE_HISTORY = os.path.join(STATE, "claude-history.txt")

SPEAK_WORDS = ("read", "speak", "aloud", "out loud", "outloud", "voice")


def ensure_state():
    os.makedirs(STATE, exist_ok=True)


def sh(cmd, timeout=15):
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def now_stamp():
    return datetime.now().strftime("%m-%d-%Y %H:%M")


def append_timestamped(path, speaker, text):
    ensure_state()
    with open(path, "a") as f:
        f.write("%d\t%s\t%s\n" % (int(time.time()), speaker, text))


def read_timestamped(path):
    """Returns [(epoch, speaker, text), ...], oldest first. Tolerates
    lines from before a speaker tag existed (treats them as "you")."""
    if not os.path.exists(path):
        return []
    rows = []
    for line in open(path):
        parts = line.rstrip("\n").split("\t", 2)
        if len(parts) == 3:
            t, speaker, text = parts
        elif len(parts) == 2:
            t, text = parts
            speaker = "you"
        else:
            continue
        try:
            rows.append((float(t), speaker, text))
        except ValueError:
            continue
    return rows


def is_speak_request(text):
    low = text.lower()
    return any(w in low for w in SPEAK_WORDS)


def speak(text):
    """termux-tts-speak hangs/fails in this sandbox (no real Termux:API
    app here, same as every other termux-* call) -- not verified
    end-to-end, same standing caveat as everything else built this way."""
    sh(["termux-tts-speak", text], timeout=30)


def _select_count(label, rows, requested):
    """requested is whatever came after the trigger words -- a number,
    "all", or nothing. Returns the rows to actually speak."""
    if not rows:
        return []
    digits = "".join(c for c in requested if c.isdigit())
    if "all" in requested.lower():
        return rows
    if digits:
        n = max(1, min(int(digits), len(rows)))
        return rows[-n:]
    return rows[-1:]  # default: just the last one


def handle_speak_request(text):
    """Reports counts, then reads back whatever was asked for. "all"
    (with no door named) reads both histories interleaved, in order,
    labelled whose line is whose."""
    yours = read_timestamped(CLAUDE_HISTORY)  # door 3's history holds both speakers
    you_rows = [r for r in yours if r[1] == "you"]
    claude_rows = [r for r in yours if r[1] == "claude"]

    summary = "you have %d line%s, claude has %d line%s." % (
        len(you_rows), "" if len(you_rows) == 1 else "s",
        len(claude_rows), "" if len(claude_rows) == 1 else "s")
    speak(summary)

    low = text.lower()
    if "all" in low:
        combined = sorted(yours, key=lambda r: r[0])
        for _, speaker, line in combined:
            speak("%s said: %s" % (speaker, line))
        return
    if "claude" in low:
        for _, _, line in _select_count("claude", claude_rows, text):
            speak(line)
        return
    # default: your own history
    for _, _, line in _select_count("you", you_rows, text):
        speak(line)


def relay_to_claude_tmux(text):
    sh(["tmux", "-S", TMUX_SOCK, "send-keys", "-t", "claude", text, "Enter"])
