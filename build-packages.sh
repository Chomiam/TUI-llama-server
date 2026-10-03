#!/usr/bin/env bash
set -euo pipefail

# TUI-llama-server build & packaging script
# Builds standalone executable + .deb and .rpm packages

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "============================================================"
echo " Building TUI-llama-server (.deb & .rpm)"
echo "============================================================"

# Ensure dist directory exists
mkdir -p dist

# 1. Build standalone single binary using PyInstaller
echo "[1/3] Building standalone executable..."
pyinstaller --clean --distpath ./dist tui-llama-server.spec

chmod +x ./dist/tui-llama-server
echo "Executable built successfully: ./dist/tui-llama-server"

# 2. Check or install nfpm for deb and rpm creation
NFPM_BIN=""
if command -v nfpm &>/dev/null; then
    NFPM_BIN="nfpm"
elif [ -f "/tmp/nfpm" ]; then
    NFPM_BIN="/tmp/nfpm"
else
    echo "Downloading nfpm..."
    curl -sfL https://github.com/goreleaser/nfpm/releases/download/v2.41.3/nfpm_2.41.3_Linux_x86_64.tar.gz | tar -xz -C /tmp nfpm
    NFPM_BIN="/tmp/nfpm"
fi

# 3. Build .deb and .rpm
echo "[2/3] Packaging Debian (.deb) package..."
"${NFPM_BIN}" pkg --packager deb --target dist/

echo "[3/3] Packaging RedHat/Fedora (.rpm) package..."
"${NFPM_BIN}" pkg --packager rpm --target dist/

echo "============================================================"
echo " Build Completed Successfully! Generated artifacts:"
ls -lh dist/*.deb dist/*.rpm dist/tui-llama-server
echo "============================================================"
