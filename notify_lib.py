#!/data/data/com.termux/files/usr/bin/python3
"""notify_lib -- one vibrate setting for every Termux notification here.

Requested: "make also vibrate option for all termux notifications, most
importantly the reply button ones".

    vibrate             show the setting
    vibrate all         every notification vibrates (default)
    vibrate reply       only ones with a Reply button
    vibrate off         none
    vibrate test        post a test notification with a Reply button
    vibrate log [n]     the last n button presses / replies (default 15)

Python callers: `cmd += notify_lib.vibrate_args(reply=True)`.
Shell callers:  `$(python3 ~/bin/notify_lib.py args reply)` (or `plain`).
The loud "are you OK?" mental check always vibrates, whatever this says.

Vibration is done with `termux-vibrate -f`: Android 8+ ignores a
notification's own --vibrate pattern (the channel decides), and Samsung's
Mute mode blocks it -- `-f` vibrates even then. --vibrate is still passed
for phones where it does work.

Every button goes through `action()`, which runs it via `notify_lib.py
run` -- that logs the press to ~/.wake/replies.log BEFORE and whatever
the command does (date, time, which notification, which button, what
was typed, what the notification said, and ok / FAILED + why), and pops
a toast if it failed. Requested: "replies need to always save file
whether read correctly or not, classification and context, also date
and time".
"""
import os
import shlex
import subprocess
import sys
import time

SETTING = os.path.expanduser("~/.wake/vibrate")
MODES = ("all", "reply", "off")
PATTERN = "300,150,300"
# a Reply button is the one you need to notice, so it gets a stronger buzz
REPLY_PATTERN = "400,150,400,150,400"


SELF = os.path.abspath(__file__)
TERMUX_BIN = "/data/data/com.termux/files/usr/bin"
PY = TERMUX_BIN + "/python3"
LOG = os.path.expanduser("~/.wake/replies.log")
CONTEXT_DIR = os.path.expanduser("~/.wake/notify-context")


def mode():
    try:
        with open(SETTING) as f:
            m = f.read().strip()
    except OSError:
        m = ""
    return m if m in MODES else "all"


def buzz(reply=False):
    """Vibrate now, even on Mute. Two pulses for Reply notifications."""
    v = TERMUX_BIN + "/termux-vibrate"
    script = ("%s -f -d 400; sleep 0.3; %s -f -d 400" % (v, v)) if reply else "%s -f -d 300" % v
    try:
        subprocess.Popen(["/system/bin/sh", "-c", script], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass


def vibrate_args(reply=False, buzz_now=True):
    """Args for termux-notification -- and, unless buzz_now=False, a real
    vibration right now (see the docstring for why both)."""
    m = mode()
    if m == "off" or (m == "reply" and not reply):
        return []
    if buzz_now:
        buzz(reply)
    return ["--vibrate", REPLY_PATTERN if reply else PATTERN]


# ---------------------------------------------------------------- button log

def remember(source, title, content):
    """What a notification currently says -- saved so a button press can
    be logged with its context."""
    try:
        os.makedirs(CONTEXT_DIR, exist_ok=True)
        with open(os.path.join(CONTEXT_DIR, source), "w") as f:
            f.write(" ".join(("%s -- %s" % (title, content)).split())[:300])
    except OSError:
        pass


def action(source, button, command):
    """A --buttonN-action string that runs `command` through the logger.
    `command` may contain $REPLY -- Termux:API swaps in the typed text,
    already double-quoted, before running it."""
    return "%s %s run %s %s -- %s" % (PY, SELF, shlex.quote(source), shlex.quote(button), command)


def _log(source, button, said, result):
    try:
        with open(os.path.join(CONTEXT_DIR, source)) as f:
            context = f.read().strip()
    except OSError:
        context = "-"
    line = "%s | %s | %s | said: %s | context: %s | %s\n" % (
        time.strftime("%Y-%m-%d %a %H:%M:%S"), source, button,
        " ".join(said.split()) or "-", context, result)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line)


def run_logged(source, button, cmd):
    said = " ".join(cmd[2:] if cmd[:1] == [PY] else cmd[1:])
    _log(source, button, said, "pressed")          # saved first, no matter what
    env = dict(os.environ)
    env["PATH"] = TERMUX_BIN + ":" + env.get("PATH", "/system/bin")
    env.setdefault("HOME", "/data/data/com.termux/files/home")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                           stdin=subprocess.DEVNULL, env=env)
        out = " ".join((p.stderr or p.stdout or "").split())
        result = "ok" if p.returncode == 0 else "FAILED exit %d: %s" % (p.returncode, out[-200:])
    except Exception as e:  # noqa: BLE001 -- log anything
        result = "FAILED: %s" % e
    _log(source, button, said, result)
    if result.startswith("FAILED"):
        subprocess.run([TERMUX_BIN + "/termux-toast", "%s %s button failed: %s" % (source, button, result[:120])],
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=20, env=env)


def set_mode(m):
    os.makedirs(os.path.dirname(SETTING), exist_ok=True)
    with open(SETTING, "w") as f:
        f.write(m + "\n")


def main():
    a = sys.argv[1:]
    if a[:1] == ["args"]:
        print(" ".join(vibrate_args(reply=a[1:2] == ["reply"], buzz_now=a[2:3] != ["nobuzz"])))
    elif a[:1] == ["run"] and "--" in a:
        i = a.index("--")
        source, button = (a[1:i] + ["?", "?"])[:2]
        run_logged(source, button, a[i + 1:])
    elif a[:1] == ["log"]:
        try:
            print("".join(open(LOG).readlines()[-int(a[1] if len(a) > 1 else 15):]), end="")
        except OSError:
            print("no button presses logged yet")
    elif a[:1] and a[0] in MODES:
        set_mode(a[0])
        print("vibrate: " + a[0])
    elif a[:1] == ["test"]:
        here = os.path.abspath(__file__)
        remember("vibrate-test", "vibrate test", "setting: " + mode())
        subprocess.run(["termux-notification", "--id", "vibrate-test",
                        "--title", "vibrate test",
                        "--content", "setting: %s -- tap Reply to check it works" % mode(),
                        "--button1", "Reply",
                        "--button1-action", action("vibrate-test", "Reply",
                                                   "%s/termux-toast got: $REPLY" % TERMUX_BIN),
                        "--button2", "Dismiss",
                        "--button2-action", action("vibrate-test", "Dismiss",
                                                   "%s/termux-notification-remove --id vibrate-test" % TERMUX_BIN)]
                       + vibrate_args(reply=True), stdin=subprocess.DEVNULL, timeout=20)
        print("posted a test notification (setting: %s)" % mode())
    elif not a:
        print("vibrate: %s   (vibrate all | reply | off | test)" % mode())
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
