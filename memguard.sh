#!/data/data/com.termux/files/usr/bin/bash
# Watches free memory continuously and warns via notification when it
# gets low enough to risk a freeze -- root-caused 2026-09-18: multiple
# concurrent `claude` sessions forced 2.2GB into swap with only 95MB
# RAM free, which is what made Termux itself feel frozen (heavy swap
# I/O on phone storage blocks everything, input included).
#
# Meant to run forever, started once at boot -- see the call to it in
# ~/.termux/boot/start-claude.sh -- not something to toggle on and off
# like ~/.termux-voice/loop.sh; this one has nothing to turn off for.
THRESHOLD_MB=300
CHECK_EVERY=60
COOLDOWN=300   # once warned, wait this long before warning again
LOG="$HOME/.memguard.log"

while true; do
  avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo 2>/dev/null)
  if [ -n "$avail" ] && [ "$avail" -lt "$THRESHOLD_MB" ]; then
    n=$(pgrep -x claude 2>/dev/null | wc -l)
    termux-notification --id memguard --title "Low memory -- ${avail}MB free" \
      --content "$n claude session(s) running. More than one at a time is what caused the last freeze -- overseer's /sessions can close extras." \
      2>/dev/null
    echo "$(date '+%F %T') low: ${avail}MB free, $n claude session(s)" >> "$LOG"
    sleep "$COOLDOWN"
  fi
  sleep "$CHECK_EVERY"
done
