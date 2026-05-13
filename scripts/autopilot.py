#!/usr/bin/env python3
"""Long-running bounty workflow autopilot.

This process performs guided automation:
- scan public bounty candidates
- refresh active PR and wallet status
- optionally auto-submit low-risk, single-file broken-link fixes
- update a portable JSON state file for the web dashboard

It never registers wallets, configures withdrawal, touches tax/payment settings,
or performs money movement.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from runtime_state import STATE_PATH, add_activity, add_run, now_iso, read_state, write_state


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
CONFIG_EXAMPLE_PATH = ROOT / "config.example.json"
LATEST_CANDIDATES = ROOT / "outputs" / "latest" / "candidates.json"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    source = path if path.exists() else CONFIG_EXAMPLE_PATH
    return json.loads(source.read_text(encoding="utf-8"))


def run_cmd(args: list[str], *, timeout: int = 60, cwd: Path = ROOT.parent) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def gh_json(args: list[str], *, timeout: int = 35) -> Any | None:
    code, stdout, _ = run_cmd(["gh", *args], timeout=timeout)
    if code != 0 or not stdout.strip():
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def amount_range(item: dict[str, Any]) -> tuple[float, float]:
    if "expected_rtc" in item:
        value = float(item["expected_rtc"])
        return value, value
    return float(item.get("expected_rtc_min", 0)), float(item.get("expected_rtc_max", item.get("expected_rtc_min", 0)))


def classify_pr(data: dict[str, Any] | None) -> str:
    if not data:
        return "unknown"
    if data.get("mergedAt"):
        return "merged_pending_payout"
    if data.get("state") == "CLOSED":
        return "rejected"
    reviews = data.get("latestReviews") or []
    if any(review.get("state") == "CHANGES_REQUESTED" for review in reviews):
        # A later approval may exist, but keep this visible when GitHub still
        # reports review-required. Maintainer merge remains the real gate.
        if not any(review.get("state") == "APPROVED" for review in reviews):
            return "changes_requested"
    if any(review.get("state") == "APPROVED" for review in reviews):
        return "approved_pending_merge"
    checks = data.get("statusCheckRollup") or []
    if any(check.get("conclusion") == "SUCCESS" for check in checks):
        return "submitted_pending_review"
    return "submitted_pending_review"


def refresh_active_items(config: dict[str, Any], state: dict[str, Any]) -> None:
    refreshed = []
    active_items = [*config.get("active_items", []), *state.get("auto_submitted_items", [])]
    seen = set()
    unique_items = []
    for item in active_items:
        key = (item.get("repo"), item.get("number"))
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    for item in unique_items:
        if item.get("kind") != "pr":
            continue
        data = gh_json(
            [
                "pr",
                "view",
                str(item["number"]),
                "--repo",
                item["repo"],
                "--json",
                "number,title,state,mergedAt,mergeStateStatus,reviewDecision,latestReviews,statusCheckRollup,url,updatedAt",
            ]
        )
        status = classify_pr(data)
        min_rtc, max_rtc = amount_range(item)
        refreshed.append(
            {
                **item,
                "status": status,
                "expected_rtc_min": min_rtc,
                "expected_rtc_max": max_rtc,
                "url": data.get("url") if data else "",
                "state": data.get("state") if data else "unknown",
                "merged_at": data.get("mergedAt") if data else None,
                "review_decision": data.get("reviewDecision") if data else "",
                "merge_state": data.get("mergeStateStatus") if data else "",
                "updated_at": data.get("updatedAt") if data else "",
                "approvals": sum(1 for review in (data or {}).get("latestReviews", []) if review.get("state") == "APPROVED"),
                "checks_passed": any(
                    check.get("conclusion") == "SUCCESS" for check in (data or {}).get("statusCheckRollup", [])
                ),
            }
        )
    state["active_items"] = refreshed
    add_activity(state, f"Refreshed {len(refreshed)} active PR items.")


def run_auto_submit(config: dict[str, Any], state: dict[str, Any]) -> None:
    automation = config.get("automation", {})
    mode = automation.get("external_actions", "manual_confirm")
    if mode != "auto_submit_except_wallet_withdrawal":
        add_activity(state, "Auto-submit skipped because mode is not enabled.")
        return
    if not automation.get("auto_submit_low_risk_link_fixes", False):
        add_activity(state, "Auto-submit skipped because low-risk link automation is disabled.")
        return
    max_active = int(automation.get("max_active_items", 6))
    active_count = len([item for item in state.get("active_items", []) if item.get("status") not in {"rejected", "paid"}])
    if active_count >= max_active:
        add_activity(state, f"Auto-submit skipped because active queue is full ({active_count}/{max_active}).")
        return

    started = now_iso()
    args = [
        sys.executable,
        str(ROOT / "scripts" / "auto_link_submitter.py"),
        "--apply",
        "--wallet",
        config.get("wallet_id", ""),
    ]
    code, stdout, stderr = run_cmd(args, timeout=240)
    child_state = read_state()
    if child_state.get("auto_submitted_items"):
        state["auto_submitted_items"] = child_state.get("auto_submitted_items", [])
    run = {
        "time": started,
        "kind": "auto_submit_low_risk_link_fix",
        "ok": code == 0,
        "stdout_tail": stdout[-1800:],
        "stderr_tail": stderr[-1800:],
    }
    add_run(state, run)
    if code == 0:
        add_activity(state, "Auto-submit completed one low-risk link fix.", meta={"stdout_tail": stdout[-800:]})
    elif code == 2:
        add_activity(state, "Auto-submit found no safe non-duplicate candidate.", level="warn")
    else:
        add_activity(state, "Auto-submit failed.", level="error", meta={"stderr": stderr[-1200:]})


def refresh_wallet(config: dict[str, Any], state: dict[str, Any]) -> None:
    wallet_id = config.get("wallet_id", "")
    state.setdefault("wallet", {})["wallet_id"] = wallet_id
    if not wallet_id:
        return
    code, stdout, stderr = run_cmd(
        ["curl", "-sk", "--max-time", "12", "--connect-timeout", "5", f"https://50.28.86.131/wallet/balance?miner_id={wallet_id}"],
        timeout=20,
    )
    if code != 0:
        state["wallet"].update({"last_checked_at": now_iso(), "last_error": stderr.strip()})
        add_activity(state, "Wallet balance check failed.", level="warn", meta={"stderr": stderr.strip()})
        return
    try:
        data = json.loads(stdout)
        state["wallet"].update(
            {
                "confirmed_rtc": float(data.get("amount_rtc", 0)),
                "last_checked_at": now_iso(),
                "last_error": "",
            }
        )
    except Exception as exc:
        state["wallet"].update({"last_checked_at": now_iso(), "last_error": str(exc), "raw": stdout.strip()})


def run_scan(config: dict[str, Any], state: dict[str, Any]) -> None:
    scan = config.get("scan", {})
    if not scan.get("enabled", True):
        add_activity(state, "Candidate scan skipped because scan.enabled=false.", level="warn")
        return

    started = now_iso()
    args = [
        sys.executable,
        str(ROOT / "scripts" / "bounty_pipeline.py"),
        "--limit",
        str(scan.get("limit", 40)),
        "--issuehunt-pages",
        str(scan.get("issuehunt_pages", 5)),
    ]
    code, stdout, stderr = run_cmd(args, timeout=180)
    run = {
        "time": started,
        "kind": "candidate_scan",
        "ok": code == 0,
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-1200:],
    }
    add_run(state, run)
    if code != 0:
        state["health"] = {"ok": False, "last_error": stderr[-1200:]}
        add_activity(state, "Candidate scan failed.", level="error", meta={"stderr": stderr[-1200:]})
        return

    candidates = []
    if LATEST_CANDIDATES.exists():
        candidates = json.loads(LATEST_CANDIDATES.read_text(encoding="utf-8"))
    state["candidate_queue"] = candidates[:20]
    state["health"] = {"ok": True, "last_error": ""}
    add_activity(state, f"Candidate scan completed with {len(candidates)} scored candidates.")


def recompute_progress_and_earnings(state: dict[str, Any]) -> None:
    progress = {"active": 0, "approved": 0, "submitted": 0, "merged": 0, "paid": 0, "rejected": 0, "needs_changes": 0}
    approved_min = approved_max = submitted_min = submitted_max = 0.0
    for item in state.get("active_items", []):
        status = item.get("status", "unknown")
        progress["active"] += 1
        min_rtc = float(item.get("expected_rtc_min", 0))
        max_rtc = float(item.get("expected_rtc_max", min_rtc))
        if status == "approved_pending_merge":
            progress["approved"] += 1
            approved_min += min_rtc
            approved_max += max_rtc
        elif status == "merged_pending_payout":
            progress["merged"] += 1
            approved_min += min_rtc
            approved_max += max_rtc
        elif status == "changes_requested":
            progress["needs_changes"] += 1
        elif status == "rejected":
            progress["rejected"] += 1
        else:
            progress["submitted"] += 1
            submitted_min += min_rtc
            submitted_max += max_rtc

    received = float(state.get("wallet", {}).get("confirmed_rtc", 0))
    state["progress"] = progress
    state["earnings"] = {
        "received_rtc": received,
        "approved_pending_min_rtc": round(approved_min, 4),
        "approved_pending_max_rtc": round(approved_max, 4),
        "submitted_pending_min_rtc": round(submitted_min, 4),
        "submitted_pending_max_rtc": round(submitted_max, 4),
        "estimated_usd_per_rtc": 0.10,
    }

    if received > 0:
        state["next_action"] = "Check payout source and update earnings ledger."
    elif approved_min > 0:
        state["next_action"] = "Wait for maintainer merge/payout, while scanning the next low-risk candidate."
    elif state.get("candidate_queue"):
        top = state["candidate_queue"][0]
        state["next_action"] = f"Inspect next candidate: {top.get('repo')}{top.get('issue')}."
    else:
        state["next_action"] = "No candidate queue yet. Run a scan."


def run_once(config: dict[str, Any], *, scan: bool = True) -> dict[str, Any]:
    state = read_state()
    state["mode"] = config.get("automation", {}).get("external_actions", "manual_confirm")
    if scan:
        run_scan(config, state)
    refresh_active_items(config, state)
    if scan:
        run_auto_submit(config, state)
        refresh_active_items(config, state)
    refresh_wallet(config, state)
    recompute_progress_and_earnings(state)
    write_state(state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--no-scan", action="store_true")
    parser.add_argument("--interval", type=int, default=0)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    if args.once or not args.loop:
        state = run_once(config, scan=not args.no_scan)
        print(f"State written: {STATE_PATH}")
        print(f"Next action: {state.get('next_action')}")
        return 0

    interval = args.interval or int(config.get("scan", {}).get("interval_seconds", 3600))
    while True:
        try:
            run_once(config, scan=not args.no_scan)
        except Exception as exc:
            state = read_state()
            state["health"] = {"ok": False, "last_error": str(exc)}
            add_activity(state, f"Autopilot loop error: {exc}", level="error")
            write_state(state)
        time.sleep(max(interval, 60))


if __name__ == "__main__":
    raise SystemExit(main())
