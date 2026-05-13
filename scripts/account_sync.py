#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from runtime_state import STATE_PATH, now_iso, read_state, write_state


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
CONFIG_EXAMPLE = ROOT / "config.example.json"
DEFAULT_STATE_REPO = "codex-bounty-autopilot-state"
DEFAULT_CACHE_DIR = Path.home() / ".codex-bounty-autopilot-state"
TRANSIENT_GIT_ERRORS = (
    "Operation timed out",
    "Recv failure",
    "Failed to connect",
    "Connection reset",
    "The requested URL returned error: 502",
    "The requested URL returned error: 503",
    "The requested URL returned error: 504",
)


def is_transient_failure(proc: subprocess.CompletedProcess[str]) -> bool:
    combined = f"{proc.stdout}\n{proc.stderr}"
    return any(marker in combined for marker in TRANSIENT_GIT_ERRORS)


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    attempts: int = 1,
    input_text: str | None = None,
    timeout: int | None = 60,
) -> subprocess.CompletedProcess[str]:
    last_proc: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, attempts + 1):
        try:
            proc = subprocess.run(
                args,
                cwd=cwd,
                text=True,
                input=input_text,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            proc = subprocess.CompletedProcess(
                args,
                returncode=124,
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + f"\nCommand timed out after {timeout} seconds.",
            )
        last_proc = proc
        if proc.returncode == 0:
            return proc
        if not check:
            return proc
        if attempt < attempts and (is_transient_failure(proc) or proc.returncode == 124):
            time.sleep(min(2 * attempt, 8))
            continue
        break
    assert last_proc is not None
    if check and last_proc.returncode:
        raise RuntimeError(f"Command failed: {' '.join(args)}\nSTDOUT:\n{last_proc.stdout}\nSTDERR:\n{last_proc.stderr}")
    return last_proc


def ensure_remote_repo(owner: str, repo: str) -> None:
    full = f"{owner}/{repo}"
    exists = run(["gh", "repo", "view", full, "--json", "nameWithOwner"], check=False)
    if exists.returncode == 0:
        return
    run(["gh", "repo", "create", full, "--private", "--description", "Private state sync for Codex Bounty Autopilot"])


def api_read_file(owner: str, repo: str, path: str) -> dict[str, str] | None:
    proc = run(["gh", "api", f"repos/{owner}/{repo}/contents/{path}"], check=False)
    if proc.returncode != 0:
        return None
    data = json.loads(proc.stdout)
    content = base64.b64decode(data.get("content", "")).decode("utf-8")
    return {"sha": data.get("sha", ""), "content": content}


def api_write_file(owner: str, repo: str, path: str, content: str, message: str) -> bool:
    current = api_read_file(owner, repo, path)
    if current and current.get("content") == content:
        return False
    body = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }
    if current and current.get("sha"):
        body["sha"] = current["sha"]
    run(
        ["gh", "api", "--method", "PUT", f"repos/{owner}/{repo}/contents/{path}", "--input", "-"],
        input_text=json.dumps(body),
        attempts=3,
    )
    return True


def gh_login() -> str:
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI `gh` is required. Run `brew install gh`, then `python3 scripts/bountyctl.py login`.")
    status = run(["gh", "auth", "status"], check=False)
    if status.returncode != 0:
        raise RuntimeError("GitHub login is required. Run `python3 scripts/bountyctl.py login` first.")
    return run(["gh", "api", "user", "--jq", ".login"]).stdout.strip()


def load_config() -> dict[str, Any]:
    source = CONFIG if CONFIG.exists() else CONFIG_EXAMPLE
    return json.loads(source.read_text(encoding="utf-8"))


def save_config(config: dict[str, Any]) -> None:
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def item_key(item: dict[str, Any]) -> tuple[str, int]:
    return str(item.get("repo", "")), int(item.get("number", 0) or 0)


def public_item(item: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "id",
        "repo",
        "kind",
        "number",
        "title",
        "expected_rtc",
        "expected_rtc_min",
        "expected_rtc_max",
        "bounty",
        "status",
        "url",
        "auto_submitted_at",
    }
    return {key: item[key] for key in allowed if key in item and item[key] not in (None, "")}


def tracked_items(config: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    for item in [*config.get("active_items", []), *state.get("active_items", []), *state.get("auto_submitted_items", [])]:
        if item.get("kind", "pr") != "pr" or not item.get("repo") or not item.get("number"):
            continue
        key = item_key(item)
        merged[key] = {**merged.get(key, {}), **public_item(item)}
        merged[key].setdefault("kind", "pr")
    return list(merged.values())


def make_payload(login: str) -> dict[str, Any]:
    config = load_config()
    state = read_state()
    wallet_id = config.get("wallet_id") or state.get("wallet", {}).get("wallet_id", "")
    return {
        "schema_version": 1,
        "synced_at": now_iso(),
        "github_login": login,
        "wallet_id": wallet_id,
        "tracked_items": tracked_items(config, state),
        "workflow_state": {
            "active_items": [public_item(item) for item in state.get("active_items", [])],
            "auto_submitted_items": [public_item(item) for item in state.get("auto_submitted_items", [])],
            "wallet": state.get("wallet", {}),
            "earnings": state.get("earnings", {}),
            "progress": state.get("progress", {}),
            "next_action": state.get("next_action", ""),
            "updated_at": state.get("updated_at", ""),
        },
    }


def ensure_state_repo(owner: str, repo: str, cache_dir: Path) -> Path:
    full = f"{owner}/{repo}"
    exists = run(["gh", "repo", "view", full, "--json", "nameWithOwner"], check=False)
    if exists.returncode != 0:
        run(["gh", "repo", "create", full, "--private", "--description", "Private state sync for Codex Bounty Autopilot"])
    if cache_dir.exists() and not (cache_dir / ".git").exists() and not any(cache_dir.iterdir()):
        cache_dir.rmdir()
    if cache_dir.exists() and not (cache_dir / ".git").exists():
        raise RuntimeError(f"State cache exists but is not a git repo: {cache_dir}")
    if not cache_dir.exists():
        run(["gh", "repo", "clone", full, str(cache_dir)], attempts=3)
    else:
        run(["git", "pull", "--rebase"], cwd=cache_dir, attempts=3)
    return cache_dir


def commit_if_needed(repo_dir: Path, message: str) -> bool:
    status = run(["git", "status", "--short"], cwd=repo_dir).stdout.strip()
    if not status:
        return False
    run(["git", "add", "account_state.json", "README.md"], cwd=repo_dir)
    run(["git", "commit", "-m", message], cwd=repo_dir)
    run(["git", "push"], cwd=repo_dir, attempts=3)
    return True


def cmd_push(args: argparse.Namespace) -> int:
    login = gh_login()
    owner = args.owner or login
    ensure_remote_repo(owner, args.repo)
    payload = make_payload(login)
    payload_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    readme_text = (
        "# Codex Bounty Autopilot State\n\n"
        "Private sync repository for one GitHub account. Do not make this repository public.\n\n"
        "This repository may contain wallet/miner id, tracked PRs, progress, earnings estimates, "
        "and next-action state. It does not contain passwords, private keys, seed phrases, or tokens.\n\n"
        f"- GitHub login: `{login}`\n"
        f"- Last sync: `{payload['synced_at']}`\n"
        f"- Tracked items: `{len(payload['tracked_items'])}`\n"
    )
    changed = False
    changed |= api_write_file(owner, args.repo, "README.md", readme_text, f"sync bounty state readme {payload['synced_at']}")
    changed |= api_write_file(owner, args.repo, "account_state.json", payload_text, f"sync bounty state {payload['synced_at']}")
    print(f"State repo: {owner}/{args.repo}")
    print(f"Tracked items: {len(payload['tracked_items'])}")
    print("Pushed changes through GitHub API." if changed else "No state changes to push.")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    login = gh_login()
    owner = args.owner or login
    ensure_remote_repo(owner, args.repo)
    remote_file = api_read_file(owner, args.repo, "account_state.json")
    if not remote_file:
        print(f"No account_state.json found in {owner}/{args.repo}. Run sync-push on the old computer first.")
        return 1
    payload = json.loads(remote_file["content"])
    if not CONFIG.exists():
        shutil.copyfile(CONFIG_EXAMPLE, CONFIG)
    config = load_config()
    if payload.get("wallet_id") and not config.get("wallet_id"):
        config["wallet_id"] = payload["wallet_id"]
    existing = {item_key(item): item for item in config.get("active_items", []) if item.get("repo") and item.get("number")}
    for item in payload.get("tracked_items", []):
        existing[item_key(item)] = {**existing.get(item_key(item), {}), **public_item(item)}
    config["active_items"] = list(existing.values())
    save_config(config)

    state = read_state()
    remote_state = payload.get("workflow_state", {})
    for key in ("active_items", "auto_submitted_items", "wallet", "earnings", "progress", "next_action"):
        if key in remote_state:
            state[key] = remote_state[key]
    state["account_sync"] = {
        "repo": f"{owner}/{args.repo}",
        "pulled_at": now_iso(),
        "remote_synced_at": payload.get("synced_at", ""),
    }
    write_state(state)
    print(f"Pulled state from {owner}/{args.repo}")
    print(f"Restored tracked items: {len(config.get('active_items', []))}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    login = gh_login()
    owner = args.owner or login
    ensure_remote_repo(owner, args.repo)
    remote_file = api_read_file(owner, args.repo, "account_state.json")
    if not remote_file:
        print(f"State repo exists but has no account_state.json: {owner}/{args.repo}")
        return 1
    payload = json.loads(remote_file["content"])
    print(json.dumps(
        {
            "repo": f"{owner}/{args.repo}",
            "synced_at": payload.get("synced_at"),
            "github_login": payload.get("github_login"),
            "wallet_id": payload.get("wallet_id"),
            "tracked_items": len(payload.get("tracked_items", [])),
            "progress": payload.get("workflow_state", {}).get("progress", {}),
            "earnings": payload.get("workflow_state", {}).get("earnings", {}),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync bounty workflow state through a private GitHub repository.")
    parser.add_argument("command", choices=["push", "pull", "status"])
    parser.add_argument("--repo", default=DEFAULT_STATE_REPO)
    parser.add_argument("--owner", default="")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    args = parser.parse_args()
    if args.command == "push":
        return cmd_push(args)
    if args.command == "pull":
        return cmd_pull(args)
    return cmd_status(args)


if __name__ == "__main__":
    raise SystemExit(main())
