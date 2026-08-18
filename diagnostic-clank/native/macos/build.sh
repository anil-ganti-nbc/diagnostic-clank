#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$ROOT/native/macos/build"
exec "${PYTHON:-python3}" -m PyInstaller --noconfirm --clean --windowed \
  --paths "$ROOT/src" \
  --name "Diagnostic Clank" \
  --onedir \
  --specpath "$ROOT/native/macos/build" \
  --distpath "$ROOT/native/macos/dist" \
  --workpath "$ROOT/native/macos/build" \
  --osx-bundle-identifier com.clank.diagnosticclank.fieldtest \
  "$ROOT/native/macos/launcher.py"
