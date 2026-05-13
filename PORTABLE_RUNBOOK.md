# Portable Runbook

This project is intentionally lightweight so it can be copied to another Codex computer and run with the system Python plus GitHub CLI.

## Requirements

- Python 3.11+
- `gh` authenticated to GitHub
- `curl`
- Network access to GitHub and bounty sources

Check:

```bash
python3 scripts/bountyctl.py doctor
```

## First-Time Setup

One-command bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/galanime/codex-bounty-autopilot/main/bootstrap.sh | bash
```

This clones or updates `~/codex-bounty-autopilot`, checks the environment, guides GitHub login, restores same-account progress if available, and installs local Codex automations.

Manual setup:

```bash
cd /path/to/codex-bounty-autopilot
python3 scripts/bountyctl.py setup
```

For non-technical users, print the guided steps:

```bash
python3 scripts/bountyctl.py guide
```

Edit local config if needed:

```bash
cp config.example.json config.json
```

The local `config.json` should not contain secrets. It stores wallet id, scan cadence, tracked PRs, and automation mode.

## GitHub Sync Rule

Use one durable GitHub repository for this project. If the repository already exists, pull and push to that same repository instead of creating a duplicate.

Recommended repository:

```text
codex-bounty-autopilot
```

Before publishing updates:

```bash
git pull --rebase
git status --short
python3 scripts/validate_system.py
git push
```

## Account State Sync

When the same GitHub account moves to another computer, sync progress through the private state repository:

```bash
python3 scripts/bountyctl.py sync-push
```

On the new computer:

```bash
python3 scripts/bountyctl.py login
python3 scripts/bountyctl.py sync-pull
python3 scripts/bountyctl.py once --no-scan
```

Default private state repo:

```text
codex-bounty-autopilot-state
```

If GitHub is not logged in:

```bash
python3 scripts/bountyctl.py login
```

## One-Shot Refresh

```bash
python3 scripts/bountyctl.py once
```

Use `--no-scan` when you only want to refresh PR/wallet status:

```bash
python3 scripts/bountyctl.py once --no-scan
```

## 24h Autopilot

```bash
python3 scripts/bountyctl.py loop
```

The loop safely automates scanning and monitoring. It opens PRs/comments only when `config.json` explicitly enables `auto_submit_except_wallet_withdrawal`. It never registers wallets, withdraws, transfers, or configures payment accounts.

## Web Supervisor

```bash
python3 scripts/bountyctl.py web --port 8787
```

Open:

```text
http://127.0.0.1:8787
```

## Export / Restore

Export state:

```bash
python3 scripts/bountyctl.py export --output ~/bounty-state.json
```

Restore on another computer:

```bash
mkdir -p runtime
cp ~/bounty-state.json runtime/state.json
```

## Suggested Long-Running Setup

For now, run the loop in a terminal, tmux, screen, or Codex automation. Future hardening can add `launchd` and `systemd` service templates.

Two-terminal local mode:

```bash
python3 scripts/bountyctl.py loop
python3 scripts/bountyctl.py web --port 8787
```

Codex automation mode:

```bash
python3 scripts/bountyctl.py install-automation --interval-hours 1
```

## Safety Boundary

The default mode is `manual_confirm`.

Allowed unattended:

- scan candidate sources
- check GitHub issue/PR state
- refresh wallet balance
- update local dashboard state
- generate reports

Requires human confirmation:

- register wallet
- configure withdrawal/payment
- run high-risk security or payment tasks

Can be automated only after explicit config opt-in:

- open low-risk PR
- post claim/comment for that PR

## Environment Completion Agent

Use global agent `environment-completion-engineer` when another Codex computer cannot meet this project's technical standard.

Its job is to:

- read the original acceptance checks in this runbook and project scripts
- inventory Python, GitHub CLI, curl, network, browser, and service availability
- install or configure missing local dependencies when safe
- use Computer Use only for browser/desktop setup that cannot be completed through files or CLI
- rerun the original checks without weakening them

It must not:

- mark the project ready when required checks still fail
- skip tests because the machine is missing dependencies
- silently switch to a lower-confidence validation
- make global, privileged, account, wallet, or payment changes without explicit user confirmation
