"""Check Gabe's own GitHub-backed projects for updates, and pull one (or
all of them) if asked.

Same standing rule ~/spark/engine/updater.py already states for Spark
specifically, extended to every project here: nothing in this file runs
on its own. A `git fetch` is a real network call on a phone, and a
program that quietly rewrites itself while it's in use is worse than one
that's simply out of date -- so this only ever runs when `overseer`'s
"Check for updates" screen is actually opened, or the bare `updates`
command is actually typed, never automatically.

    updates                  fetch + report every known repo
    updates pull <name>      fetch + fast-forward just that one
    updates pull all         fetch + fast-forward every repo that's behind

Spark gets special-cased for the actual pull (not the check) -- it has
its own `python3 spark.py update`, which also stashes/restores tracked
game files and regenerates tiles.json; redoing that generically here
would just drift from the one that's already right. Every other repo
uses a plain fetch + stash-if-dirty + fast-forward-only merge, the exact
same shape Spark's own updater uses under the hood.
"""

import subprocess
import sys
from pathlib import Path

HOME = Path.home()

# display name -> repo path. Only things with their own git history and
# an `origin` remote belong here -- gridplace counts (git added
# 2026-10-04) even though it lives in Downloads, not ~.
REPOS = {
    "spark": HOME / "spark",
    "spark2": HOME / "spark2",
    "termux-chat": HOME / "termux-chat",
    "gridplace": Path("/sdcard/Download/gridplace"),
    "termux-link": HOME / "termux-link",
    "ASC": HOME / "github/termux/android/ASC",
    "termux-bin": HOME / "bin",
}

STASH_NAME = "update-check"


def git(repo, *args, timeout=120):
    """Run git in `repo`. Returns (ok, output) -- never raises.

    `-c safe.directory=*` is needed for gridplace specifically -- it
    lives under /sdcard, owned by a different uid than whatever's
    running this, and git refuses to touch a repo like that at all
    ("dubious ownership") without being told it's fine. The wildcard
    (rather than the repo's own path) is deliberate: git's internal
    path resolution reports /sdcard/... paths under a different real
    path (e.g. /mnt/sdcard/...) than what's passed to -C, which makes
    pinning the exact string fragile across devices/environments --
    `*` sidesteps that while staying scoped to just this one
    subprocess call, never written to any config file."""
    try:
        done = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, "git is not installed"
    except (OSError, subprocess.SubprocessError) as err:
        return False, "git would not run: %s" % err
    return done.returncode == 0, (done.stdout + done.stderr).strip()


def branch(repo):
    ok, out = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return out if ok and out != "HEAD" else "main"


def dirty(repo):
    """Tracked files changed since the last commit -- see Spark's own
    updater.py for why `diff --name-only` beats `status --porcelain`
    here (porcelain's leading space for an unstaged change gets eaten
    by strip())."""
    ok, out = git(repo, "diff", "--name-only", "HEAD")
    return [line.strip() for line in out.splitlines() if line.strip()] if ok else []


def check_one(repo):
    """Fetch + report how far behind `repo` is. Never pulls anything."""
    if not repo.exists():
        return {"ok": False, "error": "not found at %s" % repo}
    ok, _ = git(repo, "rev-parse", "--git-dir")
    if not ok:
        return {"ok": False, "error": "not a git repo"}
    ok, remote = git(repo, "remote", "get-url", "origin")
    if not ok or not remote:
        return {"ok": False, "error": "no origin remote"}
    here = branch(repo)
    ok, out = git(repo, "fetch", "origin", here)
    if not ok:
        return {"ok": False, "error": "could not reach GitHub: " + out}
    ok, behind = git(repo, "rev-list", "--count", "HEAD..origin/" + here)
    count = int(behind) if ok and behind.isdigit() else 0
    return {"ok": True, "behind": count, "branch": here}


def check_all():
    """Returns {name: check_one(path)} for every repo in REPOS, in order."""
    return {name: check_one(path) for name, path in REPOS.items()}


def format_report(results):
    lines = []
    behind_any = False
    for name, status in results.items():
        if not status["ok"]:
            lines.append("  %-12s %s" % (name, status["error"]))
        elif status["behind"] == 0:
            lines.append("  %-12s up to date" % name)
        else:
            behind_any = True
            n = status["behind"]
            lines.append("  %-12s %d new commit%s available" %
                          (name, n, "" if n == 1 else "s"))
    if behind_any:
        lines.append("")
        lines.append("pull one:  updates pull <name>")
        lines.append("pull all:  updates pull all")
    return lines


def pull_spark():
    """Spark's own updater does the real work -- stashing/restoring
    tracked game files, regenerating tiles.json. Just run it and let it
    print its own lines."""
    subprocess.run([sys.executable, str(REPOS["spark"] / "spark.py"), "update"])
    return []


def pull_generic(repo):
    said = []
    here = branch(repo)
    _, was = git(repo, "rev-parse", "--short", "HEAD")

    mine = dirty(repo)
    stashed = False
    if mine:
        said.append("putting aside your changes to %d file%s" %
                     (len(mine), "" if len(mine) == 1 else "s"))
        ok, out = git(repo, "stash", "push", "-m", STASH_NAME)
        if not ok:
            said.append("could not put your changes aside: " + out)
            return said
        stashed = True

    ok, out = git(repo, "merge", "--ff-only", "origin/" + here)
    if not ok:
        if stashed:
            git(repo, "stash", "pop")
        said.append("could not fast-forward -- this copy has commits GitHub doesn't.")
        said.append("  " + out)
        return said

    _, now = git(repo, "rev-parse", "--short", "HEAD")
    said.append("updated %s -> %s" % (was, now))

    if stashed:
        ok, out = git(repo, "stash", "pop")
        said.append("...and put your changes back" if ok else
                     "YOUR CHANGES ARE SAFE but collided coming back -- "
                     "see: git -C %s stash pop" % repo)
    return said


def pull_one(name):
    if name not in REPOS:
        return ["no such project: %s" % name]
    repo = REPOS[name]
    if not repo.exists():
        return ["%s not found at %s" % (name, repo)]
    if name == "spark":
        return pull_spark()
    said = pull_generic(repo)
    if name == "termux-bin":
        # install.sh is the other half of a pull here -- a new/changed
        # shim does nothing until it's regenerated. Same two-step the
        # repo's own README already documents for the other phone.
        install = repo / "install.sh"
        if install.exists():
            subprocess.run(["bash", str(install)])
            said.append("re-ran install.sh")
    said.append("restart whatever's running the old version to pick it up")
    return said


def pull_all(results):
    said = []
    for name, status in results.items():
        if status.get("ok") and status.get("behind", 0) > 0:
            said.append("-- %s --" % name)
            said.extend(pull_one(name))
    if not said:
        said.append("everything already up to date")
    return said
