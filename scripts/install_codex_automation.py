#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_automation(codex_home: Path, automation_id: str, *, name: str, prompt: str, rrule: str, cwd: Path) -> Path:
    target = codex_home / "automations" / automation_id
    target.mkdir(parents=True, exist_ok=True)
    path = target / "automation.toml"
    now_ms = int(time.time() * 1000)
    body = "\n".join(
        [
            "version = 1",
            f"id = {toml_string(automation_id)}",
            'kind = "cron"',
            f"name = {toml_string(name)}",
            f"prompt = {toml_string(prompt)}",
            'status = "ACTIVE"',
            f"rrule = {toml_string(rrule)}",
            'model = "gpt-5.4"',
            'reasoning_effort = "medium"',
            'execution_environment = "local"',
            f"cwds = [{toml_string(str(cwd))}]",
            f"created_at = {now_ms}",
            f"updated_at = {now_ms}",
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install local Codex automations for this bounty workflow.")
    parser.add_argument("--codex-home", default=str(Path.home() / ".codex"))
    parser.add_argument("--interval-hours", type=int, default=1)
    parser.add_argument("--id-prefix", default="bounty-autopilot")
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser()
    interval = max(args.interval_hours, 1)
    rrule = f"FREQ=HOURLY;INTERVAL={interval}"

    autopilot_prompt = (
        "Run the local bounty workflow once in this workspace. First run "
        "`python3 scripts/bountyctl.py doctor`. If GitHub authentication is missing, do not continue; "
        "tell the user to run `python3 scripts/bountyctl.py login`. If checks pass, run "
        "`python3 scripts/bountyctl.py once`, then summarize submitted PRs, approved PRs, rejected PRs, "
        "wallet balance, and any user action required. Do not register wallets, withdraw, bridge, exchange, "
        "enter payment details, or perform financial/account setup."
    )
    monitor_prompt = (
        "Check the local bounty workflow state. Run `python3 scripts/bountyctl.py once --no-scan` and "
        "`python3 scripts/bountyctl.py status`. Report only actionable changes: merged PRs, payout comments, "
        "wallet balance changes, rejected PRs, or login/config blockers. If nothing changed, keep the update brief."
    )

    files = [
        write_automation(
            codex_home,
            f"{args.id_prefix}-run",
            name="Bounty Autopilot Run",
            prompt=autopilot_prompt,
            rrule=rrule,
            cwd=ROOT,
        ),
        write_automation(
            codex_home,
            f"{args.id_prefix}-monitor",
            name="Bounty Payment Monitor",
            prompt=monitor_prompt,
            rrule=rrule,
            cwd=ROOT,
        ),
    ]

    print("Installed Codex automations:")
    for path in files:
        print(f"- {path}")
    print("Restart Codex if the automation list does not refresh immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

