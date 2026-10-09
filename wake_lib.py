"""wake_lib -- shared code behind wake, mental-check, task-reminder and
diagnostics (each its own bare command; wake and Termux's startup show
all three together).

Requested: "make this called diagnostics and an other called task
reminder and an other called mental check and then output them all,
though I can select them individually, into one automatic upon opening
termux, also outside of wake".

State lives in ~/.wake/:
    mental.log     epoch \\t how you're feeling
    task.log       epoch \\t what you're doing
    mental-remind  on/off -- hourly "how are you feeling?"
    task-remind    on/off -- every 20 min "what are you doing now?"

One Android job (termux-job-scheduler job 2020, persisted) runs
`wake-tick` every 20 min while either reminder is on; tick() decides
which notifications are due. If nothing at all has been answered for
an hour, the mental check turns loud ("are you OK?").

Nothing here can call or text anyone -- this phone's Termux:API is the
Google Play build (no SMS/telephony). HELP_LINES is always one tap away.
"""

import concurrent.futures
import glob
import importlib.machinery
import json
import os
import select
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import babymenu  # noqa: E402

# overseer has no .py extension, so load it by path -- reuses its
# claude/RAM/sync/menu helpers instead of copying them.
overseer = importlib.machinery.SourceFileLoader(
    "overseer", os.path.join(HERE, "overseer")).load_module()

TERMUX_HOME = "/data/data/com.termux/files/home"
STATE = os.path.join(TERMUX_HOME, ".wake")
MENTAL_LOG = os.path.join(STATE, "mental.log")
TASK_LOG = os.path.join(STATE, "task.log")
ROOTFS = "/data/data/com.termux/files/usr/var/lib/proot-distro/containers/ubuntu/rootfs"
CLAUDE_HISTORY = ROOTFS + "/root/.claude/history.jsonl"
PY = "/data/data/com.termux/files/usr/bin/python3"
JOB_ID = "2020"
TICK_MIN = 20          # how often the job runs; task reminder cadence
MENTAL_EVERY_MIN = 60  # mental check cadence
LOUD_AFTER_MIN = 60    # no answer to anything this long -> loud "are you OK?"

HELP_LINES = [
    "In danger or hurt: call 911 (112 outside the US).",
    "Need someone to talk to right now: call or text 988 (US, free, 24/7).",
    "wake can't call or text anyone for you.",
]


# ---------------------------------------------------------------- helpers

def sh(cmd, timeout=10):
    """Run a command, return stdout ('' on any failure). stdin closed and
    a hard timeout, so a missing Termux:API app can't hang anything."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=timeout)
        return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def api_json(cmd, timeout=10):
    try:
        return json.loads(sh(cmd, timeout) or "null")
    except ValueError:
        return None


def prop(name):
    return sh(["getprop", name], 5)


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def ago(epoch):
    mins = int((time.time() - epoch) // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return "%d min ago" % mins
    if mins < 60 * 48:
        return "%dh %dm ago" % (mins // 60, mins % 60)
    return "%d days ago" % (mins // 1440)


def gb(n):
    return "%.1fGB" % (n / 1024 ** 3)


def pager(lines):
    print("\n".join(lines))
    try:
        return input("\n(enter to go back) ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def menu(title, options, header=None, has_parent=False):
    """A babymenu loop: header() lines printed above each redraw, options
    are (label, callable). Returns when 7 (back/exit) is chosen."""
    actions = [(label, i) for i, (label, _) in enumerate(options)]
    while True:
        if header:
            print("\n".join(header()))
        action, raw = overseer._menu_screen(title, actions, has_parent=has_parent)
        if action in (babymenu.EXIT, babymenu.BACK) or raw.lower() in ("q", "quit", "/quit"):
            return
        if isinstance(action, int):
            options[action][1]()


# ---------------------------------------------------------------- logs + settings

def read_log(path, n=5):
    rows = []
    for line in read(path).splitlines():
        t, _, text = line.partition("\t")
        try:
            rows.append((float(t), text))
        except ValueError:
            pass
    return rows[-n:]


def last_entry(path):
    rows = read_log(path, 1)
    return rows[0] if rows else None


def append_log(path, text):
    text = " ".join(text.split()) or "ok"
    os.makedirs(STATE, exist_ok=True)
    with open(path, "a") as f:
        f.write("%d\t%s\n" % (time.time(), text))
    return text


def _migrate():
    """wake's first version had one checkins.log + one remind switch."""
    old = os.path.join(STATE, "remind")
    if os.path.exists(old):
        on = read(old) == "on"
        for name in ("task-remind", "mental-remind"):
            if not os.path.exists(os.path.join(STATE, name)):
                with open(os.path.join(STATE, name), "w") as f:
                    f.write("on\n" if on else "off\n")
        os.remove(old)
    oldlog = os.path.join(STATE, "checkins.log")
    if os.path.exists(oldlog):
        with open(oldlog) as src, open(TASK_LOG, "a") as dst:
            dst.write(src.read())
        os.remove(oldlog)


def is_on(name):
    return read(os.path.join(STATE, name)) == "on"


def set_on(name, on):
    os.makedirs(STATE, exist_ok=True)
    with open(os.path.join(STATE, name), "w") as f:
        f.write("on\n" if on else "off\n")
    _sync_job()


def _sync_job():
    """One Android job serves both reminders: on while either is on."""
    if is_on("task-remind") or is_on("mental-remind"):
        sh(["termux-job-scheduler", "--job-id", JOB_ID,
            "--period-ms", str(TICK_MIN * 60 * 1000), "--persisted", "true",
            "--script", os.path.join(HERE, "wake-tick")], 20)
    else:
        sh(["termux-job-scheduler", "--cancel", "--job-id", JOB_ID], 20)
    if not is_on("task-remind"):
        sh(["termux-notification-remove", "--id", "wake-task"], 10)
    if not is_on("mental-remind"):
        sh(["termux-notification-remove", "--id", "wake-mental"], 10)


def notification_volume():
    for x in api_json(["termux-volume"], 8) or []:
        if x.get("stream") == "notification":
            return x.get("volume")
    return None


def minutes_since_any_answer():
    times = [e[0] for e in (last_entry(MENTAL_LOG), last_entry(TASK_LOG)) if e]
    return (time.time() - max(times)) / 60 if times else None


# ---------------------------------------------------------------- notifications

def _btn(n, label, action):
    # $REPLY stays literal on purpose: Termux:API substitutes the typed
    # text in when that button is tapped (same trick as overseer notify)
    return ["--button%d" % n, label, "--button%d-action" % n, action]


def task_notify():
    last = last_entry(TASK_LOG)
    content = "What are you doing now?"
    if last:
        content = "Last: %s (%s). What are you doing now?" % (last[1], ago(last[0]))
    me = os.path.join(HERE, "task-reminder")
    sh(["termux-notification", "--id", "wake-task", "--title", "task reminder",
        "--content", content[:1000]]
       + _btn(1, "Reply", "%s %s set $REPLY" % (PY, me))
       + _btn(2, "Same thing", "%s %s same" % (PY, me))
       + _btn(3, "Pause", "%s %s remind off" % (PY, me)), 20)


def mental_notify(loud=False):
    me = os.path.join(HERE, "mental-check")
    cmd = ["termux-notification", "--id", "wake-mental",
           "--title", "are you OK?" if loud else "mental check",
           "--content", ("Nothing answered for over an hour. " if loud else "") + "How are you feeling?"]
    cmd += _btn(1, "Good", "%s %s log good" % (PY, me))
    cmd += _btn(2, "Not great", "%s %s log not great" % (PY, me))
    cmd += _btn(3, "Need help", "%s %s help" % (PY, me))
    if loud:
        cmd += ["--priority", "max", "--sound", "--vibrate", "600,300,600,300,600"]
    sh(cmd, 20)


def help_notify():
    sh(["termux-notification", "--id", "wake-help", "--title", "help",
        "--content", "\n".join(HELP_LINES), "--priority", "max"], 20)


def tick():
    _migrate()
    silent = minutes_since_any_answer()
    if is_on("task-remind"):
        last = last_entry(TASK_LOG)
        if not last or time.time() - last[0] > (TICK_MIN - 2) * 60:
            task_notify()
    if is_on("mental-remind"):
        last = last_entry(MENTAL_LOG)
        loud = silent is not None and silent >= LOUD_AFTER_MIN
        due = not last or time.time() - last[0] > (MENTAL_EVERY_MIN - 2) * 60
        if loud or due:
            mental_notify(loud=loud)


# ---------------------------------------------------------------- quick summaries

def mental_quick():
    last = last_entry(MENTAL_LOG)
    feel = "last %s: %s" % (ago(last[0]), last[1][:40]) if last else "no check-ins yet"
    return "mental    %s | reminders %s" % (feel, "hourly" if is_on("mental-remind") else "off")


def task_quick():
    last = last_entry(TASK_LOG)
    doing = "%s (%s)" % (last[1][:40], ago(last[0])) if last else "nothing logged yet"
    return "task      %s | reminders %s" % (doing, "every %d min" % TICK_MIN if is_on("task-remind") else "off")


def diag_quick():
    b = api_json(["termux-battery-status"], 8) or {}
    free = overseer._free_mb()
    pids = overseer._live_claude_pids() or []
    line = "phone     battery %s%%%s, %s RAM free, claude %s, memguard %s" % (
        b.get("percentage", "?"),
        " charging" if b.get("plugged") not in (None, "UNPLUGGED") else "",
        "%dMB" % free if free is not None else "?",
        "x%d" % len(pids) if pids else "off",
        "on" if overseer._running("memguard.sh") else "OFF")
    if (is_on("task-remind") or is_on("mental-remind")) and notification_volume() == 0:
        line += "\n          notification volume is 0 -- reminders make no sound"
    return line


def all_quick():
    _migrate()
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        parts = [ex.submit(f) for f in (mental_quick, task_quick, diag_quick)]
    return [p.result() for p in parts]


def startup():
    """Shown automatically when a Termux session opens (~/.bashrc). Never
    blocks for long: 15 s to pick one, otherwise it gets out of the way."""
    print("\n".join(["wake -- " + time.strftime("%a %d %b  %H:%M")] + all_quick()))
    print("open: 1 mental check  2 task reminder  3 diagnostics  4 wake  (enter = skip)")
    sys.stdout.write("> ")
    sys.stdout.flush()
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 15)
    except (OSError, ValueError):
        return
    if not ready:
        print()
        return
    choice = sys.stdin.readline().strip()
    prog = {"1": "mental-check", "2": "task-reminder", "3": "diagnostics", "4": "wake"}.get(choice)
    if prog:
        subprocess.run([PY, os.path.join(HERE, prog)])


# ---------------------------------------------------------------- task summary

def _repos():
    seen, out = set(), []
    for pattern in [TERMUX_HOME + "/*/.git", TERMUX_HOME + "/github/*/.git",
                    ROOTFS + "/root/github/*/.git", ROOTFS + "/root/*/.git",
                    "/storage/emulated/0/Download/*/.git"]:
        for g in glob.glob(pattern):
            repo = os.path.dirname(g)
            if os.path.realpath(repo) not in seen:
                seen.add(os.path.realpath(repo))
                out.append(repo)
    return out


def last_commits(n=3):
    rows = []
    for repo in _repos():
        line = sh(["git", "-c", "safe.directory=*", "-c", "maintenance.auto=false",
                   "-C", repo, "log", "-1", "--format=%ct\t%s"], 10)
        t, _, msg = line.partition("\t")
        if t.isdigit():
            rows.append((int(t), os.path.basename(repo), msg))
    seen, uniq = set(), []
    for row in sorted(rows, reverse=True):
        if (row[0], row[2]) not in seen:
            seen.add((row[0], row[2]))
            uniq.append(row)
    return uniq[:n]


def last_prompts(n=3):
    rows = []
    for line in read(CLAUDE_HISTORY).splitlines()[-50:]:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        text = " ".join(str(d.get("display", "")).split())
        if text and not text.startswith("/") and text.lower() not in ("exit", "quit", "q", "clear"):
            rows.append((d.get("timestamp", 0) / 1000, text))
    return rows[-n:]


def newest_files(n=3):
    files = []
    for d in ["/storage/emulated/0/Download", "/storage/emulated/0/Documents",
              "/storage/emulated/0/Pictures/Screenshots", "/storage/emulated/0/DCIM/Screenshots"]:
        for p in glob.glob(d + "/*"):
            try:
                if os.path.isfile(p):
                    files.append((os.path.getmtime(p), p))
            except OSError:
                pass
    return sorted(files, reverse=True)[:n]


def doing_summary():
    lines = ["What you were doing", ""]
    rows = read_log(TASK_LOG, 5)
    lines.append("what you logged:")
    lines += ["  %-14s %s" % (ago(t), text) for t, text in reversed(rows)] or ["  nothing yet -- task-reminder, 1"]
    lines.append("you asked Claude:")
    lines += ["  %-14s %s" % (ago(t), text[:70]) for t, text in reversed(last_prompts())] or ["  nothing found"]
    lines.append("last saved work (git):")
    lines += ["  %-14s %s: %s" % (ago(t), repo, msg[:50]) for t, repo, msg in last_commits()] or ["  nothing found"]
    lines.append("newest files:")
    lines += ["  %-14s %s" % (ago(t), p.replace("/storage/emulated/0/", "")) for t, p in newest_files()] or ["  nothing found"]
    # one-line "so you were probably..." from the freshest signal
    signals = [(t, "you said: " + x) for t, x in rows[-1:]]
    signals += [(t, "asking Claude: " + x[:60]) for t, x in last_prompts(1)]
    signals += [(t, "working on %s (%s)" % (r, m[:40])) for t, r, m in last_commits(1)]
    if signals:
        t, what = max(signals)
        lines += ["", "most recently (%s): %s" % (ago(t), what)]
    return lines


# ---------------------------------------------------------------- device

def _battery():
    b = api_json(["termux-battery-status"]) or {}
    if not b:
        return ["battery   unavailable (Termux:API app?)"]
    return ["battery   %s%% %s, %s, %s°C, health %s" % (
        b.get("percentage"), str(b.get("status", "")).lower(),
        str(b.get("plugged", "")).lower(), b.get("temperature"),
        str(b.get("health", "")).lower())]


def _cpu():
    cores = os.cpu_count() or 0
    maxes = []
    for p in sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/cpuinfo_max_freq")):
        v = read(p)
        if v.isdigit():
            maxes.append(int(v) // 1000)
    clusters = ", ".join("%dx %.2fGHz" % (maxes.count(m), m / 1000)
                         for m in sorted(set(maxes), reverse=True)) if maxes else "?"
    chip = prop("ro.soc.model") or prop("ro.board.platform") or prop("ro.hardware")
    load = read("/proc/loadavg").split()[:3]
    return ["cpu       %s, %d cores (%s), load %s" % (chip or "?", cores, clusters, " ".join(load) or "?")]


def _memory():
    m = {}
    for line in read("/proc/meminfo").splitlines():
        k, _, v = line.partition(":")
        if v.split() and v.split()[0].isdigit():
            m[k] = int(v.split()[0]) * 1024
    if not m:
        return ["memory    ?"]
    swap_used = m.get("SwapTotal", 0) - m.get("SwapFree", 0)
    return ["memory    %s free of %s, swap used %s of %s" % (
        gb(m.get("MemAvailable", 0)), gb(m.get("MemTotal", 0)),
        gb(swap_used), gb(m.get("SwapTotal", 0)))]


def _storage():
    out, seen = [], set()
    for label, path in [("internal", "/storage/emulated/0"), ("termux", TERMUX_HOME)]:
        try:
            s = os.statvfs(path)
            free, total = s.f_bavail * s.f_frsize, s.f_blocks * s.f_frsize
            if (free, total) in seen:
                continue
            seen.add((free, total))
            out.append("storage   %-8s %s free of %s (%d%% used)" % (
                label, gb(free), gb(total), 100 - free * 100 // max(total, 1)))
        except OSError:
            pass
    return out


def _thermal():
    temps = []
    for z in glob.glob("/sys/class/thermal/thermal_zone*"):
        t, kind = read(z + "/temp"), read(z + "/type")
        if t.lstrip("-").isdigit() and int(t) > 0:
            temps.append((int(t) / (1000 if int(t) > 1000 else 1), kind))
    if not temps:
        return []
    hot = max(temps)
    return ["heat      hottest sensor %.1f°C (%s), %d sensors" % (hot[0], hot[1], len(temps))]


def _network_local():
    ups = [os.path.basename(n) for n in glob.glob("/sys/class/net/*")
           if read(n + "/operstate") == "up" and not n.endswith("/lo")]
    return ["network   interfaces up: %s (Wi-Fi/SIM details need the F-Droid Termux:API)"
            % (", ".join(ups) or "none visible")]


def notification_volume():
    for x in api_json(["termux-volume"], 8) or []:
        if x.get("stream") == "notification":
            return x.get("volume")
    return None


def _volume():
    v = api_json(["termux-volume"]) or []
    parts = ["%s %s/%s" % (x.get("stream"), x.get("volume"), x.get("max_volume"))
             for x in v if x.get("stream") in ("music", "ring", "notification", "alarm")]
    muted = any(x.get("stream") == "notification" and x.get("volume") == 0 for x in v)
    return ["volume    " + ", ".join(parts) + ("  <- notifications MUTED: check-ins make no sound" if muted else "")] if parts else []


def _extras():
    sensors = api_json(["termux-sensor", "-l"]) or {}
    cams = api_json(["termux-camera-info"]) or []
    out = []
    if sensors:
        out.append("sensors   %d available" % len(sensors.get("sensors", [])))
    if cams:
        out.append("cameras   %d (%s)" % (len(cams), ", ".join(
            "%s %dMP" % (c.get("facing", "?"),
                         max([s.get("width", 0) * s.get("height", 0) for s in c.get("jpeg_output_sizes", [])] or [0]) // 1_000_000)
            for c in cams)))
    return out


def _termux():
    pkgs = sh(["dpkg-query", "-f", ".\n", "-W"], 20).count(".")
    return ["termux    %s, %d packages installed, Termux:API %s" % (
        os.environ.get("TERMUX_VERSION", "version ?"), pkgs,
        "Play-store build (limited)" if "Google Play" in sh(["termux-wifi-connectioninfo"], 10) else "full")]


def _claude():
    pids = overseer._live_claude_pids() or []
    return ["claude    %d running%s | sync %s | memguard %s" % (
        len(pids), "  <- close extras (overseer 2)" if len(pids) > 1 else "",
        overseer._sync_status(), "watching" if overseer._running("memguard.sh") else "NOT running")]


def device_report():
    up = read("/proc/uptime").split()
    up_h = float(up[0]) / 3600 if up else 0
    head = [
        "Device diagnostics",
        "",
        "phone     %s %s (%s)" % (prop("ro.product.manufacturer"), prop("ro.product.model"), prop("ro.product.device")),
        "android   %s (SDK %s), security patch %s, build %s" % (
            prop("ro.build.version.release"), prop("ro.build.version.sdk"),
            prop("ro.build.version.security_patch"), prop("ro.build.display.id")),
        "kernel    %s %s, up %dd %dh" % (os.uname().release, os.uname().machine, up_h // 24, up_h % 24),
    ]
    # the slow Termux:API calls run side by side
    parts = [_battery, _cpu, _memory, _storage, _thermal, _network_local,
             _volume, _extras, _termux, _claude]
    with concurrent.futures.ThreadPoolExecutor(len(parts)) as ex:
        results = list(ex.map(lambda f: f(), parts))
    return head + [line for r in results for line in r]


# ---------------------------------------------------------------- online

def _timed_get(url, timeout=10, limit=None):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8 wake"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(limit) if limit else r.read()
            return r.status, body, time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, b"", time.time() - t
    except (OSError, ValueError):
        return None, b"", time.time() - t


def online_report():
    lines = ["Online report", ""]
    t = time.time()
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=5).close()
        lines.append("internet  connected, %d ms to 1.1.1.1" % ((time.time() - t) * 1000))
    except OSError:
        return lines + ["internet  NOT connected -- nothing else here can run"]
    t = time.time()
    try:
        socket.gethostbyname("github.com")
        lines.append("dns       working, %d ms" % ((time.time() - t) * 1000))
    except OSError:
        lines.append("dns       FAILING")

    jobs = {
        "ip": lambda: _timed_get("https://ipinfo.io/json"),
        "github": lambda: _timed_get("https://api.github.com/rate_limit"),
        "claude": lambda: _timed_get("https://api.anthropic.com/"),
        "weather": lambda: _timed_get("https://wttr.in/?format=3"),
        "speed": lambda: _timed_get("https://speed.cloudflare.com/__down?bytes=2000000", 30),
    }
    with concurrent.futures.ThreadPoolExecutor(len(jobs)) as ex:
        res = {k: f.result() for k, f in {k: ex.submit(j) for k, j in jobs.items()}.items()}

    code, body, _ = res["ip"]
    try:
        ip = json.loads(body)
        lines.append("public    %s -- %s, %s, %s" % (ip.get("ip"), ip.get("org", "?"), ip.get("city", "?"), ip.get("country", "?")))
    except ValueError:
        lines.append("public    couldn't look up")
    code, body, dt = res["github"]
    try:
        core = json.loads(body)["resources"]["core"]
        lines.append("github    reachable (%d ms), %d/%d API calls left" % (dt * 1000, core["remaining"], core["limit"]))
    except (ValueError, KeyError):
        lines.append("github    %s" % ("reachable" if code else "UNREACHABLE"))
    code, _, dt = res["claude"]
    lines.append("claude    api.anthropic.com %s" % ("reachable (%d ms)" % (dt * 1000) if code else "UNREACHABLE"))
    code, body, _ = res["weather"]
    if code == 200 and body:
        lines.append("weather   " + body.decode("utf-8", "replace").strip())
    code, body, dt = res["speed"]
    if code == 200 and body and dt > 0:
        lines.append("download  %.1f Mbit/s (2MB test)" % (len(body) * 8 / dt / 1e6))
    lines += ["", "8 = look this phone model up online (opens browser)"]
    return lines


def lookup_phone():
    model = (prop("ro.product.manufacturer") + " " + prop("ro.product.model")).strip()
    url = "https://www.gsmarena.com/results.php3?sQuickSearch=yes&sName=" + urllib.request.quote(model)
    sh(["termux-open-url", url], 15)
    return "opened " + url


