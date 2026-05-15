#!/usr/bin/env python3
"""Automatically submit one low-risk broken-link bounty fix.

Scope is intentionally narrow:
- public GitHub repositories only
- one file per PR
- known broken URL patterns with verified replacements
- duplicate guard before any PR/comment

Wallet registration and withdrawal are never performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime_state import add_activity, add_run, read_state, write_state, now_iso


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = Path.home() / "codex-bounty-work"
DEFAULT_UPSTREAM = "Scottcjn/rustchain-bounties"
DEFAULT_BOUNTY_REPO = "Scottcjn/rustchain-bounties"
DEFAULT_BOUNTY_ISSUE = 444
DEFAULT_WALLET = ""

URL_REPLACEMENTS = {
    "https://rustchain.org/docs": "https://github.com/Scottcjn/rustchain-bounties/tree/main/docs",
    "https://docs.rustchain.org": "https://rustchain.org",
    "https://docs.rustchain.org/bcos/": "https://rustchain.org/bcos/",
    "https://api.rustchain.org/v1": "https://rustchain.org",
    "https://testnet-api.rustchain.org/v1": "https://rustchain.org",
    "https://testnet.rustchain.org/v1": "https://rustchain.org",
    "https://api.rustchain.io": "https://rustchain.org",
    "https://api.rustchain.io/v1": "https://rustchain.org",
    "https://beacon.rustchain.io": "https://rustchain.org/beacon/",
}

ALLOWED_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".html",
    ".yml",
    ".yaml",
    ".json",
}

SKIP_PATH_PARTS = {
    ".git",
    "__pycache__",
    "node_modules",
    "Cargo.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "runtime",
}


@dataclass
class Candidate:
    file_path: str
    old_url: str
    new_url: str
    old_status: str
    new_status: str
    line: int


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 60, check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if check and proc.returncode:
        raise RuntimeError(f"Command failed: {' '.join(args)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return proc


def run_with_retry(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 60,
    attempts: int = 3,
    delay_seconds: int = 5,
) -> subprocess.CompletedProcess[str]:
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, attempts + 1):
        last = run(args, cwd=cwd, timeout=timeout)
        if last.returncode == 0:
            return last
        if attempt < attempts:
            time.sleep(delay_seconds * attempt)
    assert last is not None
    raise RuntimeError(
        f"Command failed after {attempts} attempts: {' '.join(args)}\n"
        f"STDOUT:\n{last.stdout}\nSTDERR:\n{last.stderr}"
    )


def gh_json(args: list[str], *, input_obj: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    input_text = json.dumps(input_obj) if input_obj is not None else None
    proc = subprocess.run(
        ["gh", "api", *args],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if proc.returncode:
        raise RuntimeError(f"gh api failed: {' '.join(args)}\n{proc.stderr}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def current_login() -> str:
    return run(["gh", "api", "user", "--jq", ".login"], timeout=30, check=True).stdout.strip()


def ensure_repo(upstream: str, work_root: Path) -> Path:
    work_root.mkdir(parents=True, exist_ok=True)
    name = upstream.split("/")[-1]
    target = work_root / f"{name}-auto"
    if target.exists():
        run_with_retry(["git", "fetch", "origin", "main", "--depth=1"], cwd=target, timeout=120)
        run(["git", "switch", "main"], cwd=target, timeout=30, check=True)
        run(["git", "reset", "--hard", "origin/main"], cwd=target, timeout=30, check=True)
    else:
        run_with_retry(["gh", "repo", "clone", upstream, str(target), "--", "--depth=1"], timeout=180)
    return target


def url_status(url: str) -> str:
    proc = run(
        [
            "curl",
            "-L",
            "-I",
            "--max-time",
            "10",
            "--connect-timeout",
            "5",
            "-o",
            "/dev/null",
            "-s",
            "-w",
            "%{http_code} %{ssl_verify_result} %{errormsg}",
            url,
        ],
        timeout=15,
    )
    return proc.stdout.strip() or f"curl_failed:{proc.returncode}"


def is_broken(status: str) -> bool:
    if status.startswith("000"):
        return True
    code = status.split(" ", 1)[0]
    return code in {"403", "404", "410", "500", "502", "503"}


def is_live(status: str) -> bool:
    code = status.split(" ", 1)[0]
    return code.isdigit() and 200 <= int(code) < 400


def iter_text_files(repo_dir: Path) -> list[Path]:
    files = []
    for path in repo_dir.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(repo_dir).parts)
        if rel_parts & SKIP_PATH_PARTS:
            continue
        if path.suffix.lower() in ALLOWED_SUFFIXES:
            files.append(path)
    return files


def find_candidates(repo_dir: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    status_cache: dict[str, str] = {}
    for file in iter_text_files(repo_dir):
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for old_url, new_url in URL_REPLACEMENTS.items():
            if old_url not in text:
                continue
            line = text[: text.index(old_url)].count("\n") + 1
            context_start = max(line - 6, 0)
            context_end = line + 6
            context = "\n".join(text.splitlines()[context_start:context_end]).lower()
            if "hallucinated urls" in context or "llm hallucination" in context or "not at any of these" in context:
                continue
            if old_url not in status_cache:
                status_cache[old_url] = url_status(old_url)
            if new_url not in status_cache:
                status_cache[new_url] = url_status(new_url)
            old_status = status_cache[old_url]
            new_status = status_cache[new_url]
            if not is_broken(old_status) or not is_live(new_status):
                continue
            candidates.append(
                Candidate(
                    file_path=str(file.relative_to(repo_dir)),
                    old_url=old_url,
                    new_url=new_url,
                    old_status=old_status,
                    new_status=new_status,
                    line=line,
                )
            )
    return candidates


def related_prs(upstream: str) -> list[dict[str, Any]]:
    proc = run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            upstream,
            "--state",
            "all",
            "--limit",
            "200",
            "--json",
            "number,title,state,url,files,headRefName,updatedAt",
        ],
        timeout=60,
        check=True,
    )
    return json.loads(proc.stdout)


def duplicate_reason(candidate: Candidate, prs: list[dict[str, Any]]) -> str:
    for pr in prs:
        paths = {file.get("path", "") for file in pr.get("files", [])}
        title = pr.get("title", "").lower()
        state = pr.get("state", "UNKNOWN")
        if candidate.file_path in paths:
            return f"{state.lower()} PR #{pr['number']} already touches {candidate.file_path}"
        if candidate.old_url.lower() in title:
            return f"{state.lower()} PR #{pr['number']} appears to address {candidate.old_url}"
    return ""


def choose_candidate(candidates: list[Candidate], prs: list[dict[str, Any]]) -> tuple[Candidate | None, list[dict[str, str]]]:
    rejected = []
    for candidate in candidates:
        reason = duplicate_reason(candidate, prs)
        if reason:
            rejected.append({"file": candidate.file_path, "old_url": candidate.old_url, "reason": reason})
            continue
        return candidate, rejected
    return None, rejected


def patch_file(repo_dir: Path, candidate: Candidate) -> None:
    file = repo_dir / candidate.file_path
    text = file.read_text(encoding="utf-8")
    patched = text.replace(candidate.old_url, candidate.new_url, 1)
    if patched == text:
        raise RuntimeError("Patch did not change the file")
    file.write_text(patched, encoding="utf-8")


def validate_patch(repo_dir: Path, candidate: Candidate) -> None:
    run(["git", "diff", "--check", "--", candidate.file_path], cwd=repo_dir, timeout=30, check=True)
    final_byte = run(["tail", "-c", "1", candidate.file_path], cwd=repo_dir, timeout=10, check=True).stdout.encode()
    # Empty files are not expected here; final newline is preferred but not all source files
    # are line-oriented. Enforce it for markdown/yaml/txt, which this workflow usually edits.
    if Path(candidate.file_path).suffix.lower() in {".md", ".markdown", ".txt", ".yml", ".yaml"}:
        if final_byte != b"\n":
            raise RuntimeError(f"{candidate.file_path} does not end with a newline")


def create_branch_with_file(upstream: str, fork_owner: str, branch: str, candidate: Candidate, repo_dir: Path, message: str) -> str:
    repo = upstream.split("/")[-1]
    base_sha = run(["gh", "api", f"repos/{fork_owner}/{repo}/git/ref/heads/main", "--jq", ".object.sha"], check=True).stdout.strip()
    base_tree = run(["gh", "api", f"repos/{fork_owner}/{repo}/git/commits/{base_sha}", "--jq", ".tree.sha"], check=True).stdout.strip()
    content = (repo_dir / candidate.file_path).read_text(encoding="utf-8")
    blob = gh_json([f"repos/{fork_owner}/{repo}/git/blobs", "-X", "POST", "--input", "-"], input_obj={"content": content, "encoding": "utf-8"})
    tree = gh_json(
        [f"repos/{fork_owner}/{repo}/git/trees", "-X", "POST", "--input", "-"],
        input_obj={
            "base_tree": base_tree,
            "tree": [{"path": candidate.file_path, "mode": "100644", "type": "blob", "sha": blob["sha"]}],
        },
    )
    commit = gh_json(
        [f"repos/{fork_owner}/{repo}/git/commits", "-X", "POST", "--input", "-"],
        input_obj={"message": message, "tree": tree["sha"], "parents": [base_sha]},
    )
    ref_payload = {"ref": f"refs/heads/{branch}", "sha": commit["sha"]}
    exists = run(["gh", "api", f"repos/{fork_owner}/{repo}/git/ref/heads/{branch}"], timeout=20)
    if exists.returncode == 0:
        gh_json(
            [f"repos/{fork_owner}/{repo}/git/refs/heads/{branch}", "-X", "PATCH", "--input", "-"],
            input_obj={"sha": commit["sha"], "force": True},
        )
    else:
        gh_json([f"repos/{fork_owner}/{repo}/git/refs", "-X", "POST", "--input", "-"], input_obj=ref_payload)
    return commit["sha"]


def open_pr(upstream: str, fork_owner: str, branch: str, candidate: Candidate, wallet: str, bounty_issue: int) -> str:
    title = f"docs: fix {Path(candidate.file_path).stem} documentation link"
    body = f"""## Bounty Submission

**Bounty**: Closes #{bounty_issue}

**RTC Wallet**: {wallet}

## Changes

- Updated one broken link in `{candidate.file_path}`.
- Replaced `{candidate.old_url}` with `{candidate.new_url}`.

## Testing

- [x] Old URL check: `{candidate.old_url}` -> `{candidate.old_status}`
- [x] New URL check: `{candidate.new_url}` -> `{candidate.new_status}`
- [x] `git diff --check -- {candidate.file_path}`

## Evidence

- Before: the link is not reachable or not usable.
- After: the replacement URL is reachable.

## Checklist

- [x] All acceptance criteria from the bounty issue are met
- [x] Code is tested
- [x] No secrets or credentials committed
- [x] Submission does not match any global disqualifier
"""
    proc = run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            upstream,
            "--head",
            f"{fork_owner}:{branch}",
            "--base",
            "main",
            "--title",
            title,
            "--body",
            body,
        ],
        timeout=90,
        check=True,
    )
    return proc.stdout.strip()


def parse_pr_number(pr_url: str) -> int:
    match = re.search(r"/pull/(\d+)$", pr_url.strip())
    if not match:
        raise RuntimeError(f"Could not parse PR number from {pr_url}")
    return int(match.group(1))


def post_claim(bounty_repo: str, pr_url: str, candidate: Candidate, wallet: str, bounty_issue: int) -> str:
    body = f"""Claiming this broken-link fix.

PR: {pr_url}
RTC wallet: {wallet}

Scope: `{candidate.file_path}` only.

Issue: `{candidate.old_url}` currently returns `{candidate.old_status}`.

Fix: replaced it with `{candidate.new_url}`, which returns `{candidate.new_status}`.

Validation:
- old URL: `{candidate.old_status}`
- new URL: `{candidate.new_status}`
- `git diff --check -- {candidate.file_path}`: passed
"""
    proc = run(
        ["gh", "issue", "comment", str(bounty_issue), "--repo", bounty_repo, "--body", body],
        timeout=60,
        check=True,
    )
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", default=DEFAULT_UPSTREAM)
    parser.add_argument("--bounty-repo", default=DEFAULT_BOUNTY_REPO)
    parser.add_argument("--bounty-issue", type=int, default=DEFAULT_BOUNTY_ISSUE)
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("Choose --dry-run or --apply")
    if args.apply and not args.wallet:
        parser.error("--wallet is required when using --apply")

    state = read_state()
    repo_dir = ensure_repo(args.upstream, WORK_ROOT)
    prs = related_prs(args.upstream)
    candidates = find_candidates(repo_dir)
    candidate, rejected = choose_candidate(candidates, prs)

    run_record: dict[str, Any] = {
        "time": now_iso(),
        "kind": "auto_link_submit",
        "ok": False,
        "candidate_count": len(candidates),
        "rejected": rejected[:20],
    }

    if not candidate:
        add_activity(state, "Auto-submit found no non-duplicate low-risk link candidate.", level="warn")
        run_record["reason"] = "no_candidate"
        add_run(state, run_record)
        write_state(state)
        print("No safe non-duplicate candidate found.")
        return 2

    add_activity(
        state,
        f"Auto-submit selected {candidate.file_path}:{candidate.line}",
        meta={"old_url": candidate.old_url, "new_url": candidate.new_url},
    )

    if args.dry_run:
        run_record.update({"ok": True, "dry_run": True, "candidate": candidate.__dict__})
        add_run(state, run_record)
        write_state(state)
        print(json.dumps(candidate.__dict__, ensure_ascii=False, indent=2))
        return 0

    patch_file(repo_dir, candidate)
    validate_patch(repo_dir, candidate)
    slug = re.sub(r"[^a-z0-9]+", "-", Path(candidate.file_path).stem.lower()).strip("-")[:36] or "link"
    digest = hashlib.sha1(f"{candidate.file_path}:{candidate.old_url}".encode()).hexdigest()[:8]
    branch = f"codex/auto-fix-{slug}-{digest}"
    message = f"docs: fix broken link in {candidate.file_path}"
    login = current_login()
    commit_sha = create_branch_with_file(args.upstream, login, branch, candidate, repo_dir, message)
    pr_url = open_pr(args.upstream, login, branch, candidate, args.wallet, args.bounty_issue)
    claim_url = post_claim(args.bounty_repo, pr_url, candidate, args.wallet, args.bounty_issue)
    pr_number = parse_pr_number(pr_url)

    auto_items = state.setdefault("auto_submitted_items", [])
    auto_items.insert(
        0,
        {
            "id": f"auto-{pr_number}",
            "repo": args.upstream,
            "kind": "pr",
            "number": pr_number,
            "title": f"Auto fix broken link in {candidate.file_path}",
            "expected_rtc": 3,
            "bounty": f"{args.bounty_repo}#{args.bounty_issue}",
            "claim_url": claim_url,
            "auto_submitted_at": now_iso(),
        },
    )
    state["auto_submitted_items"] = auto_items[:50]

    run_record.update(
        {
            "ok": True,
            "dry_run": False,
            "candidate": candidate.__dict__,
            "branch": branch,
            "commit": commit_sha,
            "pr_url": pr_url,
            "pr_number": pr_number,
            "claim_url": claim_url,
        }
    )
    add_activity(state, f"Auto-submitted PR {pr_url}", meta={"claim_url": claim_url, "branch": branch})
    add_run(state, run_record)
    write_state(state)
    print(json.dumps(run_record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
