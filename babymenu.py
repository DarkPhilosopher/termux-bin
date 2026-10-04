"""babymenu -- one consistent numbered-menu pattern, shared by any of
these utilities that want it: up to 8 options per screen, numbered.
Slot 7 is ALWAYS back (if there's a menu above this one) or exit (if
this is the top level) -- fixed, on purpose, so the same keypress
means the same thing on every screen in every tool, even on a screen
where "back" doesn't obviously apply. If more real options exist than
fit, slot 8 becomes "more..." (the next page) instead of a normal
option; if everything fits, slot 8 is just the 7th usable option slot
(1,2,3,4,5,6,8 -- 7 skipped, it's spoken for).

Requested directly: "make these utilities baby easy... minimize things
to a pattern of one button to open next menu or list options and all
options within 8 options else list placeholder, number them... 7th
option is always back button even if inapplicable but else... make it
an exit option."

Deliberately just the rendering/keymap logic, no I/O of its own -- each
program still does its own input()/print() loop, this only decides
what a screen looks like and what each digit means.
"""

BACK = "BACK"   # slot 7 chosen, and a parent menu exists
EXIT = "EXIT"   # slot 7 chosen, and this is the top level
MORE = "MORE"   # slot 8 chosen, meaning "show the next page"
ALL_KEY = "a"   # typed (not a digit slot -- doesn't compete with 1-8), means "show all"

_NO_OVERFLOW_SLOTS = [1, 2, 3, 4, 5, 6, 8]   # used when everything fits on one page
_PAGE_SIZE = 6                                # real options per page once paginated


def render(title, options, page=0, has_parent=True):
    """options: a list of (label, value) pairs, any length.
    Returns (lines, keymap): `lines` is what to print (title first);
    `keymap` maps the digit STRING typed to either one of `options`'
    own values, or BACK, EXIT, MORE.
    """
    lines = [title]
    keymap = {}
    total = len(options)

    if total <= len(_NO_OVERFLOW_SLOTS) and page == 0:
        chunk = options
        slots = _NO_OVERFLOW_SLOTS[:len(chunk)]
        has_more = False
    else:
        start = page * _PAGE_SIZE
        chunk = options[start:start + _PAGE_SIZE]
        slots = list(range(1, len(chunk) + 1))
        has_more = start + _PAGE_SIZE < total

    # Collected then sorted by slot number before printing -- slot 8 can
    # hold a real option (the "everything fits" case above), and it must
    # still show up in its actual numeric place (...6, 7, 8), not appended
    # out of order just because it was decided last.
    rows = {}
    for slot, (label, value) in zip(slots, chunk):
        rows[slot] = label
        keymap[str(slot)] = value
    rows[7] = "back" if has_parent else "exit"
    keymap["7"] = BACK if has_parent else EXIT
    if has_more:
        rows[8] = "more..."
        keymap["8"] = MORE

    for slot in sorted(rows):
        lines.append("%d. %s" % (slot, rows[slot]))

    if total > len(chunk):
        lines.append("(%s to see all %d at once)" % (ALL_KEY, total))

    return lines, keymap


def format_all(options):
    """The plain, un-paginated, numbered dump `a` shows -- every real
    option, one per line, 1..N in plain reading order (these numbers
    are NOT the same as any one screen's own slot numbers, and aren't
    meant to be typed back in -- this is a look, not a picker, so a
    long list doesn't need its own next/back navigation just to be
    read in full)."""
    return ["%d. %s" % (i, label) for i, (label, _value) in enumerate(options, 1)]
