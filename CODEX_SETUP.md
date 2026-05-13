# Codex Setup

Use this when cloning the project into another Codex environment.

## 1. Install

```bash
bash install.sh
```

## 2. Log in to GitHub

```bash
python3 scripts/bountyctl.py login
python3 scripts/bountyctl.py doctor
```

The workflow uses GitHub CLI for repository reads, branch pushes, PR creation, and claim comments. If login is missing, `doctor` reports it and prints the next command.

## 3. Configure Local State

```bash
python3 scripts/bountyctl.py init
```

Then edit `config.json`:

```json
{
  "wallet_id": "your-public-wallet-or-miner-id",
  "automation": {
    "external_actions": "manual_confirm"
  }
}
```

To allow low-risk automated PR submission, change:

```json
{
  "automation": {
    "external_actions": "auto_submit_except_wallet_withdrawal",
    "auto_submit_low_risk_link_fixes": true
  }
}
```

## 4. Install Codex Automations

```bash
python3 scripts/bountyctl.py install-automation --interval-hours 1
```

This creates local automation files under `~/.codex/automations/`.

## 5. Restore Existing Account Progress

If this GitHub account has used the workflow on another computer:

```bash
python3 scripts/bountyctl.py sync-pull
python3 scripts/bountyctl.py once --no-scan
```

Before leaving the old computer, push state:

```bash
python3 scripts/bountyctl.py sync-push
```

The state is stored in a private GitHub repository named `codex-bounty-autopilot-state`.

## 6. Run

```bash
python3 scripts/bountyctl.py loop
python3 scripts/bountyctl.py web --port 8787
```

Open:

```text
http://127.0.0.1:8787
```
