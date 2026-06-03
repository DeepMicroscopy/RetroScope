#!/usr/bin/env bash
# RetroScope Launcher with auto-restart.
# Exit code 42 = requested restart (after update or manual restart).
# Any other exit code = stop.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

# Single-instance lock, exit if another instance is already running.
LOCK="/tmp/retroscope.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "[RetroScope] Another instance is already running. Exiting."
    exit 0
fi

# Activate venv if present
for VENV in "$REPO_DIR/venv" "$REPO_DIR/.venv" "/home/pi/venv" "/home/pi/.venv"; do
    if [ -f "$VENV/bin/activate" ]; then
        source "$VENV/bin/activate"
        break
    fi
done

while true; do
    python app.py "$@"
    EXIT=$?
    if [ $EXIT -ne 42 ]; then
        echo "RetroScope exited with code $EXIT. Not restarting."
        exit $EXIT
    fi
    echo "Restarting RetroScope (exit code 42)..."
    sleep 1
done
