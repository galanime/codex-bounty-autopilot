# Codex Setup

Use this when cloning the project into another Codex environment.

## 1. One Command Install

```bash
curl -fsSL https://raw.githubusercontent.com/galanime/codex-bounty-autopilot/main/bootstrap.sh | bash
```

This clones or updates `~/codex-bounty-autopilot`, checks the environment, guides GitHub login, restores same-account state if available, and installs local Codex automations.

## 2. Manual Install

```bash
git clone https://github.com/galanime/codex-bounty-autopilot.git
cd codex-bounty-autopilot
python3 scripts/bountyctl.py setup
```

## 3. Log in to GitHub

```bash
python3 scripts/bountyctl.py login
python3 scripts/bountyctl.py doctor
```

The workflow uses GitHub CLI for repository reads, branch pushes, PR creation, and claim comments. If login is missing, `doctor` reports it and prints the next command.

## 4. Configure Local State

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

## 5. Install Codex Automations

```bash
python3 scripts/bountyctl.py install-automation --interval-hours 1
```

This creates local automation files under `~/.codex/automations/`.

## 6. Restore Existing Account Progress

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

## 7. Run

```bash
python3 scripts/bountyctl.py loop
python3 scripts/bountyctl.py web --port 8787
```

Open:

```text
http://127.0.0.1:8787
```
