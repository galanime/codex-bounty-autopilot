#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 scripts/bountyctl.py init
if ! python3 scripts/bountyctl.py doctor; then
  cat <<'MSG'

Action required: GitHub login or a required tool is missing.
Follow the printed guidance above, usually:
  python3 scripts/bountyctl.py login
  python3 scripts/bountyctl.py doctor

Continuing with local file validation so the download remains usable.
MSG
fi
python3 scripts/validate_system.py

cat <<'MSG'

Install check complete.

Run one safe refresh:
  python3 scripts/bountyctl.py once

Start the 24h autopilot loop:
  python3 scripts/bountyctl.py loop

Start the web supervisor:
  python3 scripts/bountyctl.py web --port 8787

Install Codex desktop automations:
  python3 scripts/bountyctl.py install-automation
MSG
