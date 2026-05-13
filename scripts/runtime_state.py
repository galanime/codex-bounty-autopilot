#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "runtime"
STATE_PATH = RUNTIME_DIR / "state.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": now_iso(),
        "mode": "manual_confirm",
        "wallet": {"wallet_id": "", "confirmed_rtc": 0.0, "last_checked_at": ""},
        "earnings": {
            "received_rtc": 0.0,
            "approved_pending_min_rtc": 0.0,
            "approved_pending_max_rtc": 0.0,
            "submitted_pending_min_rtc": 0.0,
            "submitted_pending_max_rtc": 0.0,
            "estimated_usd_per_rtc": 0.10,
        },
        "progress": {"active": 0, "approved": 0, "submitted": 0, "merged": 0, "paid": 0, "rejected": 0},
        "active_items": [],
        "candidate_queue": [],
        "runs": [],
        "activity": [],
        "next_action": "Run the autopilot once to populate status.",
        "health": {"ok": True, "last_error": ""},
    }


def read_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        state = empty_state()
        state["health"] = {"ok": False, "last_error": f"Could not read state: {exc}"}
        return state


def write_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def add_activity(state: dict[str, Any], message: str, *, level: str = "info", meta: dict[str, Any] | None = None) -> None:
    state.setdefault("activity", []).insert(
        0,
        {
            "time": now_iso(),
            "level": level,
            "message": message,
            "meta": meta or {},
        },
    )
    state["activity"] = state["activity"][:200]


def add_run(state: dict[str, Any], run: dict[str, Any]) -> None:
    state.setdefault("runs", []).insert(0, run)
    state["runs"] = state["runs"][:80]
