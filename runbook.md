# Bounty Execution Runbook

## Phase 1: Scout

Run:

```bash
python3 scripts/bounty_scout.py --limit 20 --verify-github
```

For the full scoring pass:

```bash
python3 scripts/bounty_pipeline.py --limit 40 --issuehunt-pages 5
```

Review the output for:

- bounty amount
- repository
- issue title
- PR count
- claim count when visible
- age and staleness
- whether the issue is still open on GitHub
- whether the repo has clear contribution and test commands

## Phase 2: Pick

Use this preference order:

1. Documentation, test, typing, lint, CI, or narrow bug fix.
2. Active maintainer discussion within the last 90 days.
3. Zero or low competing PR count.
4. Clear reproduction steps.
5. Local test suite can run without paid services or special hardware.

Use `outputs/latest/next_action_pack.md` as the operating queue.

Avoid:

- exploit-writing or live-target security testing
- bounty issues with many claims and unclear ownership
- stale issues with many abandoned PRs
- huge feature milestones disguised as small bounties
- payment or account setup before the PR is accepted

## Phase 3: Prepare Locally

Dry-run preparation first:

```bash
python3 scripts/prepare_candidate.py 'OWNER/REPO#123'
```

Clone into a no-space working directory:

```bash
mkdir -p "$HOME/codex-bounty-work"
cd "$HOME/codex-bounty-work"
gh repo clone OWNER/REPO
cd REPO
```

Or let the helper clone after approval:

```bash
python3 scripts/prepare_candidate.py 'OWNER/REPO#123' --clone
```

Then inspect:

```bash
gh issue view ISSUE_NUMBER --repo OWNER/REPO --comments
rg --files | sed -n '1,120p'
```

Find project commands:

```bash
rg -n "test|lint|build|contributing|pnpm|npm|yarn|pytest|cargo test|go test|make test" README* CONTRIBUTING* package.json pyproject.toml Cargo.toml go.mod Makefile 2>/dev/null
```

## Phase 4: Implement

Before editing, write a short intent:

- expected behavior
- suspected code path
- smallest test that proves it
- rollback plan

After editing:

```bash
git diff --check
git status --short
```

Run the narrowest relevant tests first, then broader tests only when feasible.

## Phase 5: Human Approval Gate

Stop before:

- claiming a bounty
- logging into a bounty platform
- submitting a PR
- commenting on GitHub
- uploading files
- adding payment details

Prepare a PR draft instead:

```md
## Summary
- ...

## Verification
- ...

## Risk
- ...

Fixes #ISSUE_NUMBER
```
