# Codex Instructions

This repository is a portable bounty automation project.

When working here:

- Use `python3 scripts/bountyctl.py doctor` before running automation.
- If GitHub authentication is missing, stop and tell the user to run `python3 scripts/bountyctl.py login`.
- Use `python3 scripts/validate_system.py` after code changes.
- Do not commit `config.json`, `runtime/`, `outputs/`, `__pycache__/`, or local wallet/account data.
- Do not automate wallet registration, withdrawal, exchanges, bank/tax/payment setup, private keys, seed phrases, passwords, or verification codes.
- External GitHub actions are allowed only when config explicitly sets `automation.external_actions` to `auto_submit_except_wallet_withdrawal`.
- Keep auto-submitted fixes narrow: single-file, reproducible old failure, verified live replacement, duplicate checked, minimal diff, validation evidence captured.

