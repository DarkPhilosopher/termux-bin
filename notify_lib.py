#!/data/data/com.termux/files/usr/bin/python3
"""notify_lib -- one vibrate setting for every Termux notification here.

Requested: "make also vibrate option for all termux notifications, most
importantly the reply button ones".

    vibrate             show the setting
    vibrate all         every notification vibrates (default)
    vibrate reply       only ones with a Reply button
    vibrate off         none
    vibrate test        post a test notification with a Reply button

Python callers: `cmd += notify_lib.vibrate_args(reply=True)`.
Shell callers:  `$(python3 ~/bin/notify_lib.py args reply)` (or `plain`).
The loud "are you OK?" mental check always vibrates, whatever this says.
"""
import os
import subprocess
import sys

SETTING = os.path.expanduser("~/.wake/vibrate")
MODES = ("all", "reply", "off")
PATTERN = "300,150,300"
# a Reply button is the one you need to notice, so it gets a stronger buzz
REPLY_PATTERN = "400,150,400,150,400"


def mode():
    try:
        with open(SETTING) as f:
            m = f.read().strip()
    except OSError:
        m = ""
    return m if m in MODES else "all"


def vibrate_args(reply=False):
    m = mode()
    if m == "off" or (m == "reply" and not reply):
        return []
    return ["--vibrate", REPLY_PATTERN if reply else PATTERN]


def set_mode(m):
    os.makedirs(os.path.dirname(SETTING), exist_ok=True)
    with open(SETTING, "w") as f:
        f.write(m + "\n")


def main():
    a = sys.argv[1:]
    if a[:1] == ["args"]:
        print(" ".join(vibrate_args(reply=a[1:2] == ["reply"])))
    elif a[:1] and a[0] in MODES:
        set_mode(a[0])
        print("vibrate: " + a[0])
    elif a[:1] == ["test"]:
        here = os.path.abspath(__file__)
        subprocess.run(["termux-notification", "--id", "vibrate-test",
                        "--title", "vibrate test",
                        "--content", "setting: %s -- tap Reply to check it works" % mode(),
                        "--button1", "Reply",
                        "--button1-action", "termux-toast got: $REPLY",
                        "--button2", "Dismiss",
                        "--button2-action", "termux-notification-remove --id vibrate-test"]
                       + vibrate_args(reply=True), stdin=subprocess.DEVNULL, timeout=20)
        print("posted a test notification (setting: %s)" % mode())
    elif not a:
        print("vibrate: %s   (vibrate all | reply | off | test)" % mode())
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
