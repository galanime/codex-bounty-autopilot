---
name: codex-bounty-autopilot
description: Install, configure, restore, and operate the Codex Bounty Autopilot from GitHub. Use when the user wants a one-command setup, Codex automation installation, GitHub login guidance, account-state sync across computers, or the local bounty dashboard. Never automate wallet registration, withdrawals, exchanges, bank/tax/payment setup, passwords, seed phrases, private keys, or verification codes.
---

# Codex Bounty Autopilot

Use this skill to install or restore the project from GitHub and make it usable in Codex with minimal user steps.

## One Command Install

Run:

```bash
curl -fsSL https://raw.githubusercontent.com/galanime/codex-bounty-autopilot/main/bootstrap.sh | bash
```

The bootstrap script clones or updates `~/codex-bounty-autopilot`, then runs:

```bash
python3 scripts/bountyctl.py setup
```

## Codex Workflow

When a user asks to install or configure this project:

1. Run the one-command installer above, or clone `https://github.com/galanime/codex-bounty-autopilot.git` and run `python3 scripts/bountyctl.py setup`.
2. If GitHub authentication is missing, guide the user through `python3 scripts/bountyctl.py login`; do not bypass or fake account login.
3. Let `setup` restore private account state with `sync-pull` if the same GitHub account has a private `codex-bounty-autopilot-state` repo.
4. Let `setup` install Codex automations unless the user asks to skip them.
5. After setup, offer these commands:

```bash
python3 scripts/bountyctl.py web --port 8787
python3 scripts/bountyctl.py once
python3 scripts/bountyctl.py loop
```

## Safety Boundary

Allowed automation:

- scan bounty sources
- refresh GitHub PR/issue state
- restore non-secret account progress from private GitHub state sync
- install local Codex automation files
- run local validation
- open low-risk PRs or claim comments only after explicit config opt-in

Never automate:

- wallet registration
- withdrawal, transfer, exchange, bridge, bank, tax, or payment setup
- passwords, seed phrases, private keys, keystore files, or verification codes

If the user wants those financial/account actions, stop and give manual guidance only.
