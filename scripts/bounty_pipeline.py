#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import bounty_scout


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"


GOOD_KEYWORDS = [
    "doc",
    "documentation",
    "readme",
    "broken link",
    "link",
    "typo",
    "lint",
    "ci",
    "test",
    "tests",
    "typescript",
    "type",
    "small",
    "bug",
]

RISK_KEYWORDS = [
    "milestone",
    "multi-user",
    "mobile application",
    "photo editing",
    "remote database",
    "facial recognition",
    "search",
    "batch",
    "viewer",
    "support for",
    "web app",
    "sync",
    "availability",
    "security",
    "exploit",
    "payment",
    "login",
]


@dataclass
class EnrichedCandidate:
    source: str
    amount: str
    amount_usd: float
    repo: str
    issue: str
    github_state: str
    title: str
    url: str
    signal: str
    repo_language: str
    repo_archived: bool
    repo_pushed_at: str
    issue_updated_at: str
    issue_labels: list[str]
    pr_count: int
    pr_urls: list[str]
    score: int
    verdict: str
    reasons: list[str]
    next_action: str


def run_json(cmd: list[str], timeout: int = 20) -> dict | list | None:
    try:
        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=True,
        )
        return json.loads(result.stdout)
    except Exception:
        return None


def parse_amount(amount: str) -> float:
    match = re.search(r"[\d,.]+", amount)
    if not match:
        return 0.0
    return float(match.group(0).replace(",", ""))


def parse_count(signal: str, label: str) -> int:
    match = re.search(rf"(\d+)\s+{label}", signal)
    return int(match.group(1)) if match else 0


def get_repo(repo: str) -> dict:
    data = run_json(
        [
            "gh",
            "repo",
            "view",
            repo,
            "--json",
            "isArchived,primaryLanguage,pushedAt",
        ]
    )
    return data if isinstance(data, dict) else {}


def get_issue(repo: str, issue: str) -> dict:
    number = issue.lstrip("#")
    data = run_json(
        [
            "gh",
            "issue",
            "view",
            number,
            "--repo",
            repo,
            "--json",
            "state,updatedAt,labels,body",
        ]
    )
    return data if isinstance(data, dict) else {}


def get_prs(repo: str, issue: str) -> list[dict]:
    number = issue.lstrip("#")
    data = run_json(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--search",
            number,
            "--state",
            "all",
            "--json",
            "number,title,state,url,mergedAt,updatedAt",
        ],
        timeout=25,
    )
    return data if isinstance(data, list) else []


def score_candidate(candidate: bounty_scout.Candidate) -> EnrichedCandidate:
    repo = get_repo(candidate.repo)
    issue = get_issue(candidate.repo, candidate.issue)
    prs = get_prs(candidate.repo, candidate.issue)

    amount_usd = parse_amount(candidate.amount)
    github_state = issue.get("state") or bounty_scout.github_issue_state(candidate.repo, candidate.issue)
    language = (repo.get("primaryLanguage") or {}).get("name", "")
    labels = [label.get("name", "") for label in issue.get("labels", [])]
    issue_body = issue.get("body") or ""
    title_l = candidate.title.lower()
    label_l = " ".join(labels).lower()
    signal_l = candidate.signal.lower()

    score = 50
    reasons = []

    if github_state == "OPEN":
        score += 25
        reasons.append("GitHub issue is open")
    elif github_state == "CLOSED":
        score -= 120
        reasons.append("GitHub issue is closed")
    else:
        score -= 25
        reasons.append("GitHub state could not be verified")

    if repo.get("isArchived"):
        score -= 120
        reasons.append("Repository is archived")

    if amount_usd <= 0:
        score -= 10
    elif amount_usd <= 25:
        score += 8
        reasons.append("Small bounty is suitable for a first loop")
    elif amount_usd <= 100:
        score += 4
    else:
        score -= 8
        reasons.append("Large bounty likely means larger scope")

    visible_prs = max(len(prs), parse_count(candidate.signal, "PRs?"))
    if visible_prs == 0:
        score += 18
        reasons.append("No existing PRs found by quick scan")
    elif visible_prs <= 2:
        score -= 8
        reasons.append("Some competing or stale PRs exist")
    else:
        score -= 25
        reasons.append("Many competing or stale PRs exist")

    claim_count = parse_count(candidate.signal, "visible claims")
    request_count = parse_count(candidate.signal, "bounty requests?")
    crowding = max(claim_count, request_count)
    if crowding >= 5:
        score -= 20
        reasons.append("Crowded bounty thread")
    elif crowding >= 1:
        score -= 6

    if any(keyword in title_l or keyword in label_l for keyword in GOOD_KEYWORDS):
        score += 18
        reasons.append("Scope keywords look automation-friendly")
    if any(keyword in title_l for keyword in RISK_KEYWORDS):
        score -= 18
        reasons.append("Scope keywords suggest product or risk-heavy work")

    low_info_title = title_l.strip() in {"test", "testing", "测试"} or len(candidate.title.strip()) < 8
    low_info_body = len(issue_body.strip()) < 80
    if low_info_title:
        score -= 45
        reasons.append("Issue title is too low-information")
    if low_info_body:
        score -= 25
        reasons.append("Issue body is too sparse to automate safely")

    if language in {"Python", "TypeScript", "JavaScript", "Go", "Markdown", "Shell"}:
        score += 8
        reasons.append(f"Language is familiar: {language}")
    elif language in {"C++", "Java", "C", "Kotlin", "Swift"}:
        score -= 4
        reasons.append(f"Language may require heavier setup: {language}")

    if score >= 80:
        verdict = "inspect-now"
        next_action = f"Inspect issue and clone only after confirming scope: gh issue view {candidate.issue.lstrip('#')} --repo {candidate.repo} --comments"
    elif score >= 55:
        verdict = "maybe"
        next_action = "Read maintainer discussion and look for a smaller subtask before cloning."
    else:
        verdict = "avoid"
        next_action = "Skip for now; keep as evidence of a filtered-out lead."

    return EnrichedCandidate(
        source=candidate.source,
        amount=candidate.amount,
        amount_usd=amount_usd,
        repo=candidate.repo,
        issue=candidate.issue,
        github_state=github_state,
        title=candidate.title,
        url=candidate.url,
        signal=candidate.signal,
        repo_language=language,
        repo_archived=bool(repo.get("isArchived")),
        repo_pushed_at=repo.get("pushedAt", ""),
        issue_updated_at=issue.get("updatedAt", ""),
        issue_labels=labels,
        pr_count=visible_prs,
        pr_urls=[pr.get("url", "") for pr in prs[:5]],
        score=score,
        verdict=verdict,
        reasons=reasons[:5],
        next_action=next_action,
    )


def collect_candidates(limit: int, issuehunt_pages: int) -> list[bounty_scout.Candidate]:
    candidates: list[bounty_scout.Candidate] = []
    for parser_fn in (
        bounty_scout.parse_algora_projectdiscovery,
        lambda: bounty_scout.parse_issuehunt(issuehunt_pages),
    ):
        try:
            candidates.extend(parser_fn())
        except Exception as exc:
            print(f"warning: {parser_fn.__name__} failed: {exc}", file=sys.stderr)
    return candidates[:limit]


def write_markdown(path: Path, rows: list[EnrichedCandidate]) -> None:
    lines = [
        "# Bounty Automation Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Top Candidates",
        "",
        "| Score | Verdict | Amount | Repo | Issue | State | PRs | Title | Next Action |",
        "| ---: | --- | ---: | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        title = row.title.replace("|", "\\|")
        action = row.next_action.replace("|", "\\|")
        lines.append(
            f"| {row.score} | {row.verdict} | {row.amount} | `{row.repo}` | `{row.issue}` | {row.github_state} | {row.pr_count} | {title} | {action} |"
        )

    lines.extend(["", "## Notes", ""])
    for row in rows[:10]:
        lines.append(f"### {row.repo}{row.issue} - {row.verdict}")
        lines.append(f"- URL: {row.url}")
        lines.append(f"- Reasons: {'; '.join(row.reasons) if row.reasons else 'No strong signals'}")
        if row.pr_urls:
            lines.append(f"- Related PRs: {', '.join(row.pr_urls)}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_action_pack(path: Path, rows: list[EnrichedCandidate]) -> None:
    inspectable = [row for row in rows if row.verdict in {"inspect-now", "maybe"} and row.github_state == "OPEN"]
    lines = [
        "# Next Action Pack",
        "",
        "This file is intentionally pre-PR. Do not claim, comment, or submit without user approval.",
        "",
    ]
    if not inspectable:
        lines.append("No clean candidate found in this scan. Widen sources or wait for a better lead.")
    for row in inspectable[:5]:
        issue_number = row.issue.lstrip("#")
        lines.extend(
            [
                f"## {row.repo}{row.issue}",
                "",
                f"- Score: {row.score}",
                f"- Bounty: {row.amount}",
                f"- Issue: {row.url}",
                f"- Why: {'; '.join(row.reasons)}",
                "",
                "Inspect:",
                "",
                "```bash",
                f"gh issue view {issue_number} --repo {row.repo} --comments",
                f"gh pr list --repo {row.repo} --search '{issue_number}' --state all --json number,title,state,url,mergedAt,updatedAt",
                "```",
                "",
                "Prepare only after approval:",
                "",
                "```bash",
                'mkdir -p "$HOME/codex-bounty-work"',
                'cd "$HOME/codex-bounty-work"',
                f"gh repo clone {row.repo}",
                f"cd {row.repo.split('/')[-1]}",
                "```",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--issuehunt-pages", type=int, default=3)
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else OUTPUTS / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = collect_candidates(args.limit, args.issuehunt_pages)
    enriched = [score_candidate(candidate) for candidate in candidates]
    enriched.sort(key=lambda row: row.score, reverse=True)

    (out_dir / "candidates.json").write_text(
        json.dumps([asdict(row) for row in enriched], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(out_dir / "report.md", enriched)
    write_action_pack(out_dir / "next_action_pack.md", enriched)

    latest = OUTPUTS / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    write_markdown(latest / "report.md", enriched)
    write_action_pack(latest / "next_action_pack.md", enriched)
    (latest / "candidates.json").write_text(
        json.dumps([asdict(row) for row in enriched], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {out_dir}")
    print(f"Latest report: {latest / 'report.md'}")
    print(f"Latest action pack: {latest / 'next_action_pack.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
