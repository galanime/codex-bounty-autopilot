#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${CODEX_BOUNTY_REPO_URL:-https://github.com/galanime/codex-bounty-autopilot.git}"
INSTALL_DIR="${CODEX_BOUNTY_HOME:-$HOME/codex-bounty-autopilot}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    return 1
  fi
}

need git
need python3

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing install: $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --rebase
elif [ -e "$INSTALL_DIR" ]; then
  echo "Install path exists but is not a git checkout: $INSTALL_DIR"
  echo "Set CODEX_BOUNTY_HOME to another directory or move the existing path."
  exit 1
else
  echo "Cloning $REPO_URL into $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
python3 scripts/bountyctl.py setup "$@"
