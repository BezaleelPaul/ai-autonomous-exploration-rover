#!/usr/bin/env bash
# Install the shared AIRoverCore library into the Arduino IDE sketchbook.
#
#   ./scripts/install_arduino_library.sh
#   ARDUINO_SKETCHBOOK=/path/to/Arduino ./scripts/install_arduino_library.sh
#
# You only need this if you open the .ino files in the Arduino IDE. The
# arduino-cli flow (make compile / flash) passes --libraries and needs nothing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/firmware/libraries/AIRoverCore"

if [ -n "${ARDUINO_SKETCHBOOK:-}" ]; then
  BOOK="$ARDUINO_SKETCHBOOK"
elif command -v arduino-cli >/dev/null 2>&1; then
  BOOK="$(arduino-cli config get directories.user 2>/dev/null || true)"
  BOOK="${BOOK:-$HOME/Arduino}"
else
  BOOK="$HOME/Arduino"
fi

DEST="$BOOK/libraries"
mkdir -p "$DEST"
rm -rf "$DEST/AIRoverCore"
cp -R "$SRC" "$DEST/AIRoverCore"

echo "Installed AIRoverCore -> $DEST/AIRoverCore"
echo "Re-run this script after updating firmware/libraries/AIRoverCore."
echo "Then in the IDE: File > Examples (or open the .ino) and select the board."
