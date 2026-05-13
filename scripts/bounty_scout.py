#!/usr/bin/env python3
import argparse
import html
import json
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Iterable


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X) CodexBountyScout/0.1"


@dataclass
class Candidate:
    source: str
    amount: str
    repo: str
    issue: str
    title: str
    url: str
    signal: str

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "amount": self.amount,
            "repo": self.repo,
            "issue": self.issue,
            "title": self.title,
            "url": self.url,
            "signal": self.signal,
        }


def github_issue_state(repo: str, issue_number: str) -> str:
    number = issue_number.lstrip("#")
    try:
        result = subprocess.run(
            ["gh", "issue", "view", number, "--repo", repo, "--json", "state"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
        )
        return json.loads(result.stdout).get("state", "unknown")
    except Exception:
        return "unknown"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last_exc = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_exc = exc
            time.sleep(0.5 * (attempt + 1))
    raise last_exc


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_algora_projectdiscovery() -> Iterable[Candidate]:
    url = "https://algora.io/projectdiscovery/bounties?status=open"
    page = fetch(url)
    rows = re.findall(r"<tr\b.*?</tr>", page, flags=re.S)
    for row in rows:
        amount = re.search(r">\s*(\$\d[\d,]*)\s*<", row)
        link = re.search(r'href="(https://github\.com/([^/]+/[^/]+)/issues/(\d+))"', row)
        title = re.search(r'<p class="line-clamp-2[^"]*">\s*(.*?)\s*</p>', row, flags=re.S)
        claims = re.search(r"(\d+)\s+claims?", clean_text(row))
        if amount and link and title:
            yield Candidate(
                source="Algora ProjectDiscovery",
                amount=amount.group(1),
                repo=link.group(2),
                issue=f"#{link.group(3)}",
                title=clean_text(title.group(1)),
                url=link.group(1),
                signal=f"{claims.group(1)} visible claims" if claims else "open bounty",
            )


def parse_issuehunt(pages: int = 3) -> Iterable[Candidate]:
    for page_num in range(1, pages + 1):
        url = "https://oss.issuehunt.io/issues" if page_num == 1 else f"https://oss.issuehunt.io/issues?page={page_num}"
        yield from parse_issuehunt_page(url)


def parse_issuehunt_page(url: str) -> Iterable[Candidate]:
    page = fetch(url)
    match = re.search(r"__NEXT_DATA__\s*=\s*(\{.*?\});__NEXT_LOADED_PAGES__", page, flags=re.S)
    if not match:
        return
    data = json.loads(match.group(1))
    issues = data.get("props", {}).get("pageProps", {}).get("issues", [])
    for issue in issues:
        if issue.get("githubState") != "open":
            continue
        owner = issue.get("repositoryOwnerName", "")
        repo_name = issue.get("repositoryName", "")
        number = issue.get("number", "")
        amount_cents = issue.get("depositAmount", 0)
        amount = f"${amount_cents / 100:.2f}"
        repo = f"{owner}/{repo_name}"
        yield Candidate(
            source="IssueHunt",
            amount=amount,
            repo=repo,
            issue=f"#{number}",
            title=issue.get("title", ""),
            url=f"https://github.com/{repo}/issues/{number}",
            signal=f"{issue.get('pullRequestCount', 0)} PRs, {issue.get('depositRequestCount', 0)} bounty requests",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--issuehunt-pages", type=int, default=3)
    parser.add_argument("--verify-github", action="store_true")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    candidates = []
    parsers = (
        parse_algora_projectdiscovery,
        lambda: parse_issuehunt(args.issuehunt_pages),
    )
    for parser_fn in parsers:
        try:
            candidates.extend(parser_fn())
        except Exception as exc:
            print(f"warning: {parser_fn.__name__} failed: {exc}", file=sys.stderr)

    if args.format == "json":
        rows = []
        for c in candidates[: args.limit]:
            row = c.to_dict()
            row["github_state"] = github_issue_state(c.repo, c.issue) if args.verify_github else "not checked"
            rows.append(row)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("| Source | Amount | Repo | Issue | GitHub State | Title | Signal | URL |")
    print("| --- | ---: | --- | --- | --- | --- | --- | --- |")
    for c in candidates[: args.limit]:
        state = github_issue_state(c.repo, c.issue) if args.verify_github else "not checked"
        title = c.title.replace("|", "\\|")
        print(f"| {c.source} | {c.amount} | `{c.repo}` | `{c.issue}` | {state} | {title} | {c.signal} | {c.url} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
