#!/bin/sh
# Hang detector for a backgrounded `codex exec` run.
# Usage: sh .claude/codex-stall-watch.sh <log> [stall_minutes] [poll_seconds]
# Emits ONE line and exits 1 if the log stops growing while codex.exe is still
# alive. Exits 0 silently once codex.exe is gone (the run_in_background
# completion notification covers that case).
# ponytail: counts every codex.exe on the box, so a second concurrent run masks
# a stall in the first. Tag per-PID if that ever matters.
log="$1"
stall_min="${2:-10}"
poll_s="${3:-60}"
last=-1
quiet=0

while true; do
  sleep "$poll_s"
  alive=$(ps -W 2>/dev/null | grep -ci 'codex\.exe')
  size=$(wc -c < "$log" 2>/dev/null || echo 0)
  [ "$alive" -eq 0 ] && exit 0
  if [ "$size" -eq "$last" ]; then
    quiet=$((quiet + 1))
  else
    quiet=0
    last=$size
  fi
  if [ "$quiet" -ge "$stall_min" ]; then
    echo "STALL: $log unchanged for $((quiet * poll_s))s (${size}B), codex.exe still running"
    exit 1
  fi
done
