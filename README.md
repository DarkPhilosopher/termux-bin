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

## What's in here

| File | What it is |
|---|---|
| `overseer` | One dashboard: numbered menu (`babymenu.py`), `/help`/`/list`/`/open`/`/newsession`/`/sessions`, plus a pinned-notification mode |
| `programs` | Auto-detecting command lister (scans `$PREFIX/bin` for `# CATALOG:` tags) |
| `catalog_lib.py` | Shared scanning logic behind `programs`/`overseer` |
| `babymenu.py` | The shared numbered-menu pattern (max 8 slots, 7 is always back/exit) |
| `termux-sessions` | Lists/closes real Termux session tabs — by pid, list position, or tty name |
| `opensession` | Opens a brand-new, independent Termux session via `RUN_COMMAND` |
| `note3` | Posts a 3-button Termux notification you define on the fly |
| `memguard.sh` | Boot-started: warns if free RAM drops too low |
| `termux-panel` | Adds/removes a swipeable panel of extra keys on Termux's keyboard row |
| `ti.sh` | Notification-based text input with tmux channel switching |
| `collect-screenshots.py` | Moves screenshot-like files into one easy-to-browse folder |
| `install.sh` | (Re)creates the `$PREFIX/bin` shims for the commands above |

Full history and authorship notes (built with Claude vs. found already
in place): [DarkPhilosopher/PROJECTS-INDEX](https://github.com/DarkPhilosopher/PROJECTS-INDEX).
