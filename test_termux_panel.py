#!/data/data/com.termux/files/usr/bin/python3
"""Check termux-panel: add/remove a swipeable panel of Termux's own
extra keys, editing ~/.termux/termux.properties without disturbing
anything else in that file.

    python3 test_termux_panel.py

Standalone, no pytest -- matches how spark's own tests/check_*.py
files are written and run, since this lives right alongside them in
spirit even though it isn't part of that project.
"""

import importlib.util
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

HERE = Path(__file__).resolve().parent
loader = SourceFileLoader("termux_panel", str(HERE / "termux-panel"))
spec = importlib.util.spec_from_loader(loader.name, loader)
tp = importlib.util.module_from_spec(spec)
loader.exec_module(tp)

passed = failed = 0


def check(name, condition, extra=""):
    global passed, failed
    if condition:
        passed += 1
        print("  ok   " + name)
    else:
        failed += 1
        print("  FAIL " + name + ("  -> " + str(extra) if extra else ""))


print("load_panels: the three shapes Termux itself accepts, all normalized the same way")

ok_default = tp.load_panels("")
check("no extra-keys line at all -> the built-in default, as one panel",
      ok_default == [tp.BUILTIN_DEFAULT_PANEL], ok_default)

bare_row = tp.load_panels("extra-keys = ['ESC','TAB']")
check("a bare single row -> one panel with that one row",
      bare_row == [[["ESC", "TAB"]]], bare_row)

single_panel = tp.load_panels("extra-keys = [['ESC','TAB'],['CTRL','ALT']]")
check("a single panel (list of rows) -> one panel, unwrapped correctly",
      single_panel == [[["ESC", "TAB"], ["CTRL", "ALT"]]], single_panel)

two_panels = tp.load_panels("extra-keys = [[['ESC']],[['F1','F2']]]")
check("already a list of panels -> left as-is",
      two_panels == [[["ESC"]], [["F1", "F2"]]], two_panels)

check("an empty extra-keys list -> the built-in default",
      tp.load_panels("extra-keys = []") == [tp.BUILTIN_DEFAULT_PANEL])

print("\nload_panels: commented-out examples vs. an active line")

commented_only = tp.load_panels("# extra-keys = [['A','B']]")
check("only a commented-out example -> read as if it were the real thing",
      commented_only == [[["A", "B"]]], commented_only)

active_wins = tp.load_panels(
    "# extra-keys = [['STALE','EXAMPLE']]\nextra-keys = [['REAL']]\n")
check("an active line wins over any commented-out example, regardless of order",
      active_wins == [[["REAL"]]], active_wins)

try:
    tp.load_panels("extra-keys = [[{key: 'ESC', popup: 'DEL'}]]")
    check("bare (unquoted) object keys refuse rather than mangling", False)
except tp.PanelError:
    check("bare (unquoted) object keys refuse rather than mangling", True)

try:
    tp.load_panels("extra-keys = not-a-bracket-at-all")
    check("a value that isn't even a list refuses", False)
except tp.PanelError:
    check("a value that isn't even a list refuses", True)

print("\nrender_panels: back to Termux's own single-quoted style")

rendered = tp.render_panels([[["ESC", "TAB"]]])
check("plain strings, single-quoted, no spaces", rendered == "extra-keys = [[['ESC','TAB']]]", rendered)
round_trip = tp.load_panels(rendered)
check("round-trips back to the exact same structure", round_trip == [[["ESC", "TAB"]]], round_trip)

print("\nparse_rows_arg: the add command's own \"a,b;c,d\" syntax")

check("semicolons separate rows, commas separate keys",
      tp.parse_rows_arg("F1,F2;F3,F4,F5") == [["F1", "F2"], ["F3", "F4", "F5"]])
check("stray whitespace around keys is trimmed",
      tp.parse_rows_arg(" ESC , TAB ") == [["ESC", "TAB"]])
try:
    tp.parse_rows_arg("")
    check("nothing at all refuses rather than adding an empty panel", False)
except tp.PanelError:
    check("nothing at all refuses rather than adding an empty panel", True)
try:
    tp.parse_rows_arg(" ; , ;")
    check("only separators, no real keys, refuses too", False)
except tp.PanelError:
    check("only separators, no real keys, refuses too", True)

print("\nsave_panels + load_panels: a real file round trip, nothing else in it disturbed")

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / ".termux" / "termux.properties"

    tp.save_panels(path, [[["A", "B"]]])
    check("creates the file (and its .termux/ parent) from nothing", path.exists())
    check("...with exactly the rendered line", path.read_text().strip() == "extra-keys = [[['A','B']]]",
          path.read_text())

    tp.save_panels(path, [[["A", "B"]], [["C", "D"]]])
    check("a second save replaces the value, not appends a second line",
          path.read_text().count("extra-keys") == 1, path.read_text())
    check("...and the new value is actually there",
          tp.load_panels(path.read_text()) == [[["A", "B"]], [["C", "D"]]])

    backup = path.parent / (path.name + ".bak")
    check("a backup of the pre-edit file was made, the very first time",
          backup.exists() and backup.read_text().strip() == "extra-keys = [[['A','B']]]",
          backup.read_text() if backup.exists() else None)

    tp.save_panels(path, [[["E", "F"]]])
    check("the backup is NOT overwritten by later edits -- still the original",
          backup.read_text().strip() == "extra-keys = [[['A','B']]]", backup.read_text())

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / ".termux" / "termux.properties"
    path.parent.mkdir(parents=True)
    path.write_text(
        "allow-external-apps = true\n"
        "bell-character = ignore\n"
        "\n"
        "# extra-keys = [['ESC','TAB']]\n"
        "\n"
        "use-black-ui = true\n"
    )
    panels = tp.load_panels(path.read_text())
    panels.append([["NEW"]])
    tp.save_panels(path, panels)
    text = path.read_text()
    check("unrelated settings before the extra-keys line survive untouched",
          "allow-external-apps = true" in text and "bell-character = ignore" in text, text)
    check("unrelated settings after it survive untouched too",
          "use-black-ui = true" in text, text)
    check("the commented example became a live, active line",
          "\nextra-keys = " in text and "# extra-keys" not in text, text)
    check("...with the new panel actually folded in",
          tp.load_panels(text) == [[["ESC", "TAB"]], [["NEW"]]], tp.load_panels(text))

print("\n%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
