# Automation Policy

This workflow automates discovery, validation, monitoring, and narrowly scoped low-risk submissions only after local config opt-in. It does not automate financial, wallet, bank, tax, exchange, credential, or private-key actions.

## Fully Automated

- Fetch public bounty listings.
- Verify GitHub issue state.
- Check related PRs.
- Score candidates.
- Generate reports and action packs.
- Refresh wallet balance by public wallet/miner ID.
- Update local dashboard state.
- Run local tests and collect logs.

## Config Opt-In Required

These external GitHub actions require explicit local config:

- Opening or updating a low-risk PR.
- Commenting on GitHub for the matching claim.
- Claiming a bounty for the submitted PR.

Required config:

```json
{
  "automation": {
    "external_actions": "auto_submit_except_wallet_withdrawal",
    "auto_submit_low_risk_link_fixes": true
  }
}
```

The automated submission path still requires:

- successful GitHub login
- duplicate checks
- old target verified broken
- replacement verified live
- no negative-example / hallucination-warning context
- validation command evidence
- small single-file diff

## Human Action Required

- Logging into GitHub when `doctor` reports auth is missing.
- Logging into IssueHunt, Algora, or another bounty platform.
- Connecting wallets, bank accounts, Stripe, PayPal, tax forms, or payment profiles.
- Uploading files or transmitting personal data.
- Registering wallets, withdrawing, bridging, transferring, or exchanging funds.
- Entering passwords, verification codes, private keys, or seed phrases.

## Target Strategy

The first profitable loop should optimize for completion probability, not payout size.

Best first targets:

- broken documentation links
- typo/lint/test failures
- narrow bug fixes with reproduction steps
- small TypeScript, JavaScript, Python, Go, or docs tasks

Avoid first:

- broad product features
- large UI redesigns
- security exploit tasks
- stale bounty platform entries with closed GitHub issues
- tasks with many competing PRs
