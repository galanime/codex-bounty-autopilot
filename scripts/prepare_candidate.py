#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "outputs" / "latest" / "candidates.json"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("selector", help="repo#issue, for example owner/repo#123")
    parser.add_argument("--workdir", default=str(Path.home() / "codex-bounty-work"))
    parser.add_argument("--clone", action="store_true", help="Clone the repo after local approval.")
    args = parser.parse_args()

    if "#" not in args.selector:
        raise SystemExit("selector must look like owner/repo#123")
    repo, issue = args.selector.split("#", 1)
    issue_ref = f"#{issue}"

    if not LATEST.exists():
        raise SystemExit(f"Run bounty_pipeline.py first. Missing {LATEST}")

    rows = json.loads(LATEST.read_text(encoding="utf-8"))
    match = next((row for row in rows if row["repo"] == repo and row["issue"] == issue_ref), None)
    if not match:
        raise SystemExit(f"Candidate {args.selector} was not found in latest scan")
    if match["github_state"] != "OPEN":
        raise SystemExit(f"Candidate is not open on GitHub: {match['github_state']}")
    if match["verdict"] == "avoid":
        raise SystemExit("Candidate verdict is avoid; inspect manually before proceeding")

    workdir = Path(args.workdir).expanduser()
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"Candidate: {repo}{issue_ref}")
    print(f"Score: {match['score']} ({match['verdict']})")
    print(f"Issue: {match['url']}")
    print("Reasons:")
    for reason in match["reasons"]:
        print(f"- {reason}")

    print("\nInspection commands:")
    print(f"gh issue view {issue} --repo {repo} --comments")
    print(f"gh pr list --repo {repo} --search '{issue}' --state all --json number,title,state,url,mergedAt,updatedAt")

    if args.clone:
        repo_dir = workdir / repo.split("/")[-1]
        if repo_dir.exists():
            print(f"Repo already exists: {repo_dir}")
        else:
            run(["gh", "repo", "clone", repo], cwd=workdir)
        print(f"Prepared local repo: {repo_dir}")
    else:
        print("\nNo clone performed. Re-run with --clone after choosing this candidate.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
