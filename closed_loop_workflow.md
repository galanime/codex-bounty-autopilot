# Bounty Closed-Loop Automation Workflow

Advanced domain note: this document describes the internal bounty execution loop. It is not required for one-command installation, and it should not be used as a place to store private payout details, credentials, seed phrases, private keys, or personal financial records.

This workflow abstracts the current RustChain bounty run into a repeatable earning loop. It is optimized for legitimate, low-risk, reviewable contributions that can actually be accepted and paid.

## Goal

Turn each opportunity into a tracked state transition:

`candidate -> verified issue -> patch -> PR -> claim -> review -> merge -> payout -> ledger`

The workflow should maximize accepted payouts, not PR volume.

## Core Lessons From The Current Run

1. A submitted PR is not earned money.
2. A CI-passing PR is not earned money.
3. An approved PR is still not earned money until it is merged and the wallet or ledger shows payout.
4. Small docs fixes can move fast, but duplicates are common. Duplicate checking is the main quality gate.
5. Evidence matters more than confidence. Every claim should include old URL result, new URL result, file scope, and validation commands.
6. Review feedback is part of the loop. Fast, precise follow-up can turn `CHANGES_REQUESTED` into `APPROVED`.
7. Payment identity must be registered early, but money is only real after wallet balance or bounty ledger changes.

## State Machine

| State | Meaning | Entry Evidence | Exit Condition |
|---|---|---|---|
| `SCOUTED` | Candidate found by scanner or repo search | issue URL, bounty amount, repo | passes basic filter |
| `INSPECTING` | Issue and repo are being checked | issue body, labels, open/closed state | valid target or rejected |
| `DUPLICATE_CHECK` | Existing PRs and claims are checked | PR list, issue comments, file search | no active duplicate found |
| `VERIFIED_BROKEN` | Bug/link/problem is reproducible | command output showing failure | minimal fix identified |
| `PATCHED_LOCAL` | Local branch has smallest fix | `git diff`, changed files | validation passes |
| `SUBMITTED` | PR opened | PR URL, wallet in body | CI/review starts |
| `CLAIMED` | Bounty issue comment posted | claim comment URL | maintainer review |
| `CHANGES_REQUESTED` | Reviewer asked for changes | review URL/body | patch update and reply |
| `APPROVED` | Reviewer approved latest head | review state | maintainer merge |
| `MERGED` | PR merged | `mergedAt` | payout processing |
| `PAID` | Wallet/ledger updated | wallet balance or ledger line | record final amount |
| `REJECTED` | Closed, duplicate, invalid, stale | close reason | stop or learn |

## Candidate Filters

Prefer:

- One-file docs/readme fixes.
- Broken links with a clear old/new HTTP result.
- Typos, conflict markers, stale examples, or small config fixes.
- Repos where GitHub CLI can open PRs and checks are quick.
- Bounties with explicit amount and claim format.

Avoid:

- Broad product features.
- Changes touching payment, auth, security exploit paths, or live abuse testing.
- Tasks with hardware requirements.
- Files already touched by an open PR.
- Issues where comments show the same claim already made.
- Fixes that rely on guesswork instead of reproducible evidence.

## Duplicate Check Gate

Before editing, run all applicable checks:

```bash
gh pr list --repo OWNER/REPO --state open --limit 100 \
  --json number,title,url,files,headRefName,updatedAt

gh pr list --repo OWNER/REPO --state all --limit 200 \
  --search 'TARGET_FILE OR TARGET_URL OR KEYWORD' \
  --json number,title,state,url,files

gh issue view ISSUE --repo OWNER/REPO --comments

rg -n 'TARGET_URL|TARGET_KEYWORD' .
```

Reject the candidate if an open PR already fixes the same file and same issue. If a closed PR exists, inspect why it closed before reusing the idea.

## Broken Link Evidence Standard

For every broken link fix, capture:

```bash
curl -L -I --max-time 10 --connect-timeout 5 OLD_URL
curl -L -I --max-time 10 --connect-timeout 5 NEW_URL
git diff --check -- TARGET_FILE
tail -c 1 TARGET_FILE | od -An -tx1
```

Rules:

- `000`, DNS failure, 403, 404, or TLS failure can count as broken only when the replacement is clearly better.
- Prefer canonical HTTPS hosts with valid TLS for OpenAPI or generated-client docs.
- Raw IPs are acceptable in curl examples only when the repo explicitly documents `-k` or certificate limitations.
- Preserve final newline.

## Patch Rules

- One bounty issue per PR.
- One file per PR when bounty says single-file scope.
- Minimal diff, no formatting churn.
- No unrelated refactors.
- No secrets, tokens, or personal data.
- Use a fresh branch off upstream `main`.

Branch pattern:

```text
codex/fix-<short-target>
```

Commit pattern:

```text
docs: fix <specific thing>
```

## PR Body Template

```md
## Bounty Submission

**Bounty**: Closes #ISSUE_NUMBER

**RTC Wallet**: YOUR_WALLET_ID

## Changes

- ...

## Testing

- [x] `git diff --check -- TARGET_FILE`
- [x] Old URL check: ...
- [x] New URL check: ...
- [x] Final newline preserved when relevant

## Evidence

- Before: ...
- After: ...

## Checklist

- [x] All acceptance criteria from the bounty issue are met
- [x] Code is tested
- [x] No secrets or credentials committed
- [x] Submission does not match any global disqualifier
```

## Claim Comment Template

```md
Claiming this <bounty name> fix.

PR: PR_URL
RTC wallet: YOUR_WALLET_ID

Scope: `TARGET_FILE` only.

Issue: ...

Fix: ...

Validation:
- old URL / old behavior: ...
- new URL / new behavior: ...
- `git diff --check -- TARGET_FILE`: passed
```

## Review Response Loop

When review feedback arrives:

1. Classify it as `correct`, `optional`, `wrong`, or `unclear`.
2. If correct, patch immediately and add stronger evidence.
3. If optional, only change if it improves acceptance probability without expanding scope.
4. If wrong or unclear, reply with evidence and ask for confirmation.
5. After patching, reply to the PR with exact validation output.

Example lesson:

- `https://50.28.86.131` worked with `curl -k`, but OpenAPI clients verify TLS by default.
- Reviewer correctly asked to use `https://rustchain.org`.
- Fixing fast turned the PR back into approved state.

## Payout Accounting

Track three numbers separately:

| Bucket | Meaning |
|---|---|
| `received` | Wallet/ledger confirms payout |
| `approved_pending` | Approved but not merged/paid |
| `submitted_pending` | PR opened and claimed, but not approved |

Never report `approved_pending` or `submitted_pending` as money earned.

Wallet check:

```bash
curl -sk 'https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_ID'
curl -s 'https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_ID'
```

Ledger check:

```bash
rg -n 'YOUR_GITHUB_USERNAME|YOUR_WALLET_ID|PR_NUMBER' BOUNTY_LEDGER.md badges claims submissions -S
```

PR check:

```bash
gh pr view PR_NUMBER --repo OWNER/REPO \
  --json number,title,state,mergedAt,mergeStateStatus,reviewDecision,latestReviews,statusCheckRollup,url
```

## Current Manual-Automation Split

Fully automate:

- Candidate scanning.
- Link extraction.
- HTTP checks.
- Duplicate PR search.
- Local patch generation for one-line docs fixes.
- PR body and claim comment draft generation.
- Status monitoring and payout ledger checks.

Require explicit human approval or active user confirmation:

- Opening PRs.
- Posting comments.
- Registering wallets.
- Adding payment information.
- Any externally visible action on non-test accounts.

## Next Scriptable Modules

1. `link_candidate_scanner.py`
   - Extract URLs from repo files.
   - Filter obvious placeholders.
   - Run bounded HTTP checks.
   - Output candidates with file, line, old URL, failure mode.

2. `duplicate_guard.py`
   - Search open/all PRs by file path and URL.
   - Search bounty issue comments by file path and URL.
   - Return `safe`, `duplicate`, or `needs_manual_review`.

3. `patch_builder.py`
   - For approved candidates only.
   - Apply one-file replacement.
   - Validate diff and newline.
   - Generate PR body and claim comment.

4. `bounty_status_monitor.py`
   - Poll PRs, claim comments, wallet balance, and ledger.
   - Classify into `submitted_pending`, `approved_pending`, `merged_pending_payout`, `paid`, `rejected`.

5. `earnings_report.py`
   - Produce received RTC, pending RTC, USD estimate, blockers, and next action.

## Quality Score

Use this before submitting:

| Check | Points |
|---|---:|
| Single-file scope | 2 |
| Reproducible old failure | 3 |
| Replacement verified live | 3 |
| No duplicate PR/claim | 4 |
| Diff is minimal | 3 |
| Validation commands included | 3 |
| Wallet and claim format correct | 2 |

Minimum submit score: 17/20.

Anything below 17 should stay as a draft candidate.
