# Technical Standard

This file defines the minimum technical standard for running and validating the Bounty Autopilot project. Environment completion must meet these standards instead of lowering them.

## Required Tools

- Python 3.11 or newer.
- GitHub CLI `gh`, authenticated when GitHub status refresh or PR operations are needed.
- `curl` for network and wallet checks.
- Local network access to GitHub and configured bounty sources.

## Required Project Checks

Run from the repository root:

```bash
python3 scripts/validate_system.py
python3 scripts/bountyctl.py doctor
python3 scripts/bountyctl.py once --no-scan
```

Expected result:

- Python files compile.
- Web assets exist.
- `gh` and `curl` are present.
- Runtime state is written to `runtime/state.json`.
- The command exits successfully without skipping required checks.

## Dashboard Standard

Start:

```bash
python3 scripts/bountyctl.py web --port 8787
```

Required endpoints:

```bash
curl -s http://127.0.0.1:8787/api/health
curl -s http://127.0.0.1:8787/api/state
curl -s http://127.0.0.1:8787/
```

Expected result:

- `/api/health` returns JSON with `ok`.
- `/api/state` returns the runtime state JSON.
- `/` returns the HTML dashboard.

## Autopilot Standard

One-shot safe refresh:

```bash
python3 scripts/bountyctl.py once
```

Long-running mode:

```bash
python3 scripts/bountyctl.py loop
```

The loop may scan, refresh PR status, refresh wallet status, and update the dashboard state. It may open low-risk PRs/comments only when local config explicitly enables `auto_submit_except_wallet_withdrawal`. It must not register wallets, withdraw, bridge, transfer, exchange, or configure payment without explicit user action.

## Earnings Standard

The system must separate:

- `received_rtc`: confirmed by wallet or ledger.
- `approved_pending_*`: approved but not paid.
- `submitted_pending_*`: submitted but not approved.

Pending value must not be reported as earned money.

## Portability Standard

On another Codex computer, the project should be restorable by copying the folder and running:

```bash
bash install.sh
```

If a requirement is missing, `environment-completion-engineer` should install or configure it locally when safe. If it cannot do so without system privileges, external accounts, browser UI, or user secrets, it must stop and ask for confirmation.

## No Lowering Standards

Do not accept any of these as a pass:

- `gh` missing but GitHub checks marked ready.
- Dashboard not reachable but UI marked complete.
- Wallet endpoint failed but payout shown as confirmed.
- Tests skipped because dependencies were missing.
- TLS or network failures ignored without being documented.
- A weaker check substituted for a required check without explicit approval and clear labeling.
