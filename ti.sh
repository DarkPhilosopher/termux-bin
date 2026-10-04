#!/data/data/com.termux/files/usr/bin/bash
# Notification text-input with channel switching.
# Run with no args to post it. Buttons: <- prev channel | Reply | next channel ->
# Whatever you type in Reply gets sent to the current tmux session and logged
# to ~/ti.log. Content shows the last few lines of that session's output.
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
export HOME="/data/data/com.termux/files/home"
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
STATE="$HOME/.ti_channel"
LOG="$HOME/ti.log"
LINES=6

sessions() {
    # `|| true` matters: with no tmux server started yet, this exits
    # non-zero, and under `set -e` (this script's very first line) an
    # un-guarded `list=$(sessions)` elsewhere would silently kill the
    # whole script right there -- before it ever reaches post() -- which
    # looks exactly like "running ti.sh does nothing at all."
    tmux list-sessions -F '#S' 2>/dev/null || true
}

current_channel() {
    local list saved
    list=$(sessions)
    [ -z "$list" ] && return
    saved=$(cat "$STATE" 2>/dev/null || true)
    if [ -n "$saved" ] && grep -qxF "$saved" <<< "$list"; then
        echo "$saved"
    else
        head -1 <<< "$list"
    fi
}

switch_channel() {
    local dir="$1" list cur idx=0 n
    list=$(sessions)
    [ -z "$list" ] && return
    mapfile -t arr <<< "$list"
    cur=$(current_channel)
    for i in "${!arr[@]}"; do
        [ "${arr[$i]}" = "$cur" ] && idx=$i && break
    done
    n=${#arr[@]}
    if [ "$dir" = "next" ]; then
        idx=$(( (idx + 1) % n ))
    else
        idx=$(( (idx - 1 + n) % n ))
    fi
    printf '%s' "${arr[$idx]}" > "$STATE"
}

history_text() {
    local ch="$1"
    [ -z "$ch" ] && { echo "(no tmux sessions - tmux new -s name)"; return; }
    tmux capture-pane -p -t "$ch" -S "-$LINES" 2>/dev/null | tail -n "$LINES"
}

post() {
    local ch hist
    ch=$(current_channel)
    hist=$(history_text "$ch")
    termux-notification --id ti \
        --title "Termux: ${ch:-no session}" \
        --content "$hist" \
        --button1 "<-" --button1-action "$SELF --prev" \
        --button2 "Reply" --button2-action "$SELF --reply \$REPLY" \
        --button3 "->" --button3-action "$SELF --next" \
        --ongoing
}

case "${1:-}" in
    --next) switch_channel next; post ;;
    --prev) switch_channel prev; post ;;
    --reply)
        shift
        text="$*"
        ch=$(current_channel)
        if [ -n "$ch" ] && [ -n "$text" ]; then
            tmux send-keys -t "$ch" "$text" Enter
            echo "$text" >> "$LOG"
        fi
        post
        ;;
    *) post ;;
esac
