# bin

Gabe's personal Termux scripts — pushed here so the same set of
programs can be kept in sync across his two phones (an A17 and an
A33), which was the whole point of finally giving this folder a git
repo: "i want you to keep them both in sync... i mean update same
programs."

## Setting this up on a phone that doesn't have it yet

```
cd ~
git clone https://github.com/DarkPhilosopher/termux-bin.git bin
~/bin/install.sh
```

`install.sh` creates the `$PREFIX/bin` shims that make these work as
bare commands (`overseer`, `programs`, etc.) — cloning the repo alone
only gets you the files, not the commands. Safe to re-run any time.

## Keeping both phones current

On whichever phone just got new work:

```
cd ~/bin && git add -A && git commit -m "..." && git push
```

On the other phone, whenever you want to catch up:

```
cd ~/bin && git pull && ~/bin/install.sh
```

Nothing syncs automatically — pulling (and re-running `install.sh`) is
still a manual step on each device.

## Checking everything for updates

`updates` doesn't just check this repo — it checks every one of
Gabe's own GitHub-backed projects at once (Spark, spark2, termux-chat,
gridplace, termux-link, ASC, and this repo), same as `overseer`'s own
"Check for updates" menu screen:

```
updates                   fetch + report every project
updates pull <name>       fetch + fast-forward just that one
updates pull all          fetch + fast-forward every one that's behind
```

Nothing here ever runs on its own — same standing rule Spark's own
`spark.py update` states for itself: a `git fetch` is a real network
call on a phone, so this only runs when `updates` (or the menu screen)
is actually opened, never silently in the background.

## Sorting loose files

`organize-files` sorts a messy folder (Downloads by default) into
type-based subfolders — Images, Videos, Documents, Archives,
Installers, Other:

```
organize-files                 dry run, prints what WOULD happen
organize-files --apply         actually move the files
organize-files --undo          reverse the most recent run
```

**Dry run by default, and every move is logged** so `--undo` can put
everything back exactly where it was — this never deletes anything,
only relocates. `DCIM/Camera` and anything under Termux's own home
are never touched, even if pointed at directly, since Android's
camera app and photo backup expect `DCIM/Camera` to stay put.

See [fileexplorer](https://github.com/DarkPhilosopher/fileexplorer)
for a Windows-Explorer-style offline browser for the result — its
own repo, since it's a small web app rather than a `~/bin` script.

## What's in here

| File | What it is |
|---|---|
| `overseer` | One dashboard: numbered menu (`babymenu.py`), `/help`/`/list`/`/open`/`/newsession`/`/sessions`/`/updates`, plus a pinned-notification mode |
| `programs` | Auto-detecting command lister (scans `$PREFIX/bin` for `# CATALOG:` tags) |
| `catalog_lib.py` | Shared scanning logic behind `programs`/`overseer` |
| `timeweather` | Shows + logs the current time and weather (wttr.in, no API key) |
| `updates` | Checks every one of Gabe's GitHub repos for updates, and can pull them — see above |
| `updates_lib.py` | The check/pull logic behind `updates` and `overseer`'s "Check for updates" screen |
| `babymenu.py` | The shared numbered-menu pattern (max 8 slots, 7 is always back/exit) |
| `termux-sessions` | Lists/closes real Termux session tabs — by pid, list position, or tty name |
| `opensession` | Opens a brand-new, independent Termux session via `RUN_COMMAND` |
| `note3` | Posts a 3-button Termux notification you define on the fly |
| `memguard.sh` | Boot-started: warns if free RAM drops too low |
| `termux-panel` | Adds/removes a swipeable panel of extra keys on Termux's keyboard row |
| `ti.sh` | Notification-based text input with tmux channel switching |
| `collect-screenshots.py` | Moves screenshot-like files into one easy-to-browse folder |
| `organize_files.py` | Sorts loose files into type folders — dry-run by default, see above |
| `install.sh` | (Re)creates the `$PREFIX/bin` shims for the commands above |

Full history and authorship notes (built with Claude vs. found already
in place): [DarkPhilosopher/PROJECTS-INDEX](https://github.com/DarkPhilosopher/PROJECTS-INDEX).
