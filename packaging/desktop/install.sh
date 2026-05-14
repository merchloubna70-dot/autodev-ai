#!/usr/bin/env bash
# install.sh — autodev-x macOS .app desktop installer
# Run once from this directory: bash packaging/desktop/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SRC="$SCRIPT_DIR/autodev-x.app"
OPEN_SH_SRC="$SCRIPT_DIR/autodev-x-open.sh"

APP_DST="$HOME/Desktop/autodev-x.app"
BIN_DST="$HOME/bin/autodev-x-open.sh"

echo "=== autodev-x desktop installer ==="
echo ""

# 1. Copy .app to Desktop
echo "1. Copying autodev-x.app → ~/Desktop/"
cp -R "$APP_SRC" "$APP_DST"
echo "   ✓ $APP_DST"

# 2. Copy open.sh to ~/bin/
echo "2. Installing autodev-x-open.sh → ~/bin/"
mkdir -p "$HOME/bin"
cp "$OPEN_SH_SRC" "$BIN_DST"
echo "   ✓ $BIN_DST"

# 3. chmod open.sh
echo "3. chmod +x ~/bin/autodev-x-open.sh"
chmod +x "$BIN_DST"

# 4. chmod launcher inside .app
echo "4. chmod +x ~/Desktop/autodev-x.app/Contents/MacOS/launcher"
chmod +x "$APP_DST/Contents/MacOS/launcher"

# 5. Remove quarantine so first double-click skips Gatekeeper warning
echo "5. Removing com.apple.quarantine from ~/Desktop/autodev-x.app"
xattr -dr com.apple.quarantine "$APP_DST" 2>/dev/null || true

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  • Double-click ~/Desktop/autodev-x.app to launch"
echo "  • Edit ~/bin/autodev-x-open.sh to customize without re-signing"
echo "  • Logs: ~/.autodev-x/.launcher.log"
echo ""
