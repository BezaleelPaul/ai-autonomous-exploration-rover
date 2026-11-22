#!/usr/bin/env bash
# AI Rover - 1-Click Unified Desktop Launcher
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Check if Mission Control server is already responding on port 5000
SERVER_RUNNING=0
if curl -s --max-time 1 http://127.0.0.1:5000/api/state > /dev/null 2>&1; then
    SERVER_RUNNING=1
fi

STARTED_SERVER=0
SERVER_PID=""

if [ "$SERVER_RUNNING" -eq 0 ]; then
    echo "Starting AI Rover Mission Control backend..."

    # Auto-detect hardware connection: USB Arduino vs Wireless ESP32
    ARDUINO_ARG=""
    if [ -e "/dev/ttyACM0" ]; then
        ARDUINO_ARG="--arduino /dev/ttyACM0"
    elif [ -e "/dev/ttyACM1" ]; then
        ARDUINO_ARG="--arduino /dev/ttyACM1"
    elif [ -e "/dev/ttyUSB0" ]; then
        ARDUINO_ARG="--arduino /dev/ttyUSB0"
    elif ping -c 1 -W 1 192.168.4.1 > /dev/null 2>&1; then
        ARDUINO_ARG="--esp32-bridge http://192.168.4.1"
    else
        # Default to wireless ESP32 bridge
        ARDUINO_ARG="--esp32-bridge http://192.168.4.1"
    fi

    python3 -u scripts/dashboard.py --controls --host 0.0.0.0 --port 5000 --no-plugins --no-clip $ARDUINO_ARG > /tmp/ai_rover_server.log 2>&1 &
    SERVER_PID=$!
    STARTED_SERVER=1

    # Wait up to 6 seconds for server to be responsive
    for i in {1..12}; do
        if curl -s --max-time 1 http://127.0.0.1:5000/api/state > /dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
fi

# 2. Verify / Build Flutter Companion Desktop Binary
FLUTTER_BIN="$DIR/mobile/rover_companion/build/linux/x64/debug/bundle/rover_companion"
if [ ! -f "$FLUTTER_BIN" ]; then
    echo "Building Flutter companion binary..."
    (cd "$DIR/mobile/rover_companion" && flutter build linux --debug)
fi

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

# Launch Flutter app in foreground
"$FLUTTER_BIN"

# 3. Cleanup: If this launcher started the background server, stop it on exit
if [ "$STARTED_SERVER" -eq 1 ] && [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
fi
