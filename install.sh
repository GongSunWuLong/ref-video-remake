#!/usr/bin/env bash
# One-line install (macOS / Linux / Git Bash):
#   curl -fsSL https://raw.githubusercontent.com/GongSunWuLong/ref-video-remake/main/install.sh | bash
# Copies the skill into ~/.claude/skills/ref-video-remake and installs the Python deps.
set -euo pipefail
REPO="GongSunWuLong/ref-video-remake"
DEST="${HOME}/.claude/skills/ref-video-remake"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Downloading ${REPO} ..."
if command -v git >/dev/null 2>&1; then
  git clone --depth 1 "https://github.com/${REPO}.git" "$TMP/src" >/dev/null 2>&1
else
  curl -fsSL "https://github.com/${REPO}/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP"
  mv "$TMP"/ref-video-remake-* "$TMP/src"
fi
rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
cp -R "$TMP/src/plugins/ref-video-remake/skills/ref-video-remake" "$DEST"
echo "Skill installed to $DEST"

PY="$(command -v python3 || command -v python || true)"
if [ -n "$PY" ]; then
  "$PY" -m pip install -q -r "$DEST/requirements.txt" || "$PY" -m pip install -q --user -r "$DEST/requirements.txt"
  "$PY" "$DEST/scripts/check_env.py" || true
else
  echo "Python 3.9+ not found. Install it, then: python3 -m pip install -r \"$DEST/requirements.txt\""
fi
command -v ffmpeg >/dev/null 2>&1 || echo "ffmpeg not found. Install: brew install ffmpeg  /  sudo apt install ffmpeg"
echo "Done. Restart Claude Code, then say: 参考这个视频帮我做一条新的"
