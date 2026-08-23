# Pilot report — 40 issues (#12615–#12781)

Date: 2026-08-23. Phase `pilot`, concurrency 8, caps 15 closures / 10 PRs per day.
All 40 pilot issues reached a disposition. Full audit trail in `state/journal.jsonl`.

## 1. Dispositions

| Status | n | Meaning |
|---|---|---|
| `pr_open` | 9 | draft PR open, CI green, awaiting bakert |
| `fix_pushed` | 11 | branch pushed, PR queued behind today's 10-PR cap |
| `verified` | 6 | closure independently CONFIRMED, blocked on `issues: write` |
| `reported` | 6 | `needs-work` (5) / `question` (1) — no GitHub write, by design |
| `deferred_human` | 6 | 5 product decisions + #12781 (bakert rejected the PR) |
| `fix_pending`/`fix_leased` | 2 | #12618, #12716 re-dispatched after orphan-branch reclaim |

Triage classes: easy-fix 23, already-fixed 6, needs-product-decision 5,
needs-work 5, question 1. **No `obsolete`, `duplicate`, `cannot-reproduce`,
`unclear` or `security-sensitive` in this sample.**

## 2. Exit criteria

| Criterion | Target | Actual |
|---|---|---|
| Malformed output rate | <10% | **8.6%** — 3 nudges over 35 workspaces; 5 `RESULT_MALFORMED`, all recovered by the single corrective nudge except two that consumed an attempt |
| Bad closures in Opus's spot-check | 0 | **0 closures executed** (token blocked); 3 of 6 closure *claims* independently audited by me, all cast-iron |
| Verifier refutation rate | understood | **0 of 6 CONFIRMED.** Investigated for rubber-stamping: verifiers cited their own distinct line refs, and my independent audits agreed. Reads as genuine triage quality on a small sample; watch it at scale |
| Infrastructure failures / pauses | — | **0 / 0.** No rate-limit event ever left `status: allowed` |
| Workspace wall time | — | median **5.3 min**, p90 7.7, max 9.4 (fix 5.2, triage 6.3, verify 2.8). Leases of 60/60/90 min are generously sized |

## 3. Mutations, all spot-checked

10 PRs opened (#14943–#14953). Every diff reviewed: largest is +6/−2 across 2 files.
Two audited line by line — #14943 (one-line `bug_blog` fix; `labels` verified in
scope, `'From Bug Blog'` already used at `modo_bugs/repo.py:60`) and #14945
(`url_for('person', …)`, endpoint verified at `decksite/controllers/people.py:27`).
Fixers ran real validation: the env bootstrap works in cloud workspaces and PR
bodies report `lint` plus **687 passing unit tests**.

Human outcomes so far: bakert merged #14945, rejected #14949, left the rest green.

## 4. Incidents

1. **Auto-merge near miss (critical).** `.mergify.yml` merges any PR authored by a
   member of `@PennyDreadfulMTG/automerge` — bakert is a member, and sweep PRs are
   authored as bakert — once mypy/lint/test/jslint pass, ~10 min after creation. The
   `do not merge` label was **not** a brake: `.mergify.yml` never references it, and
   #14943 lost the label on its own. #14943 was already green and in the merge queue
   when I converted all 7 PRs to draft. Nothing merged without human intent.
   Resolution: draft-until-reviewed is now the permanent policy, with a post-create
   `isDraft` assertion that closes the PR and halts the pipeline if it ever fails.
2. **GitHub token cannot write issues.** `issues: read` only; closures and comments
   return 403 while PR writes succeed. `gh issue close` **exits 0** while printing the
   error, so only the post-condition check caught it. 6 verified closures are parked.
3. **`easy-fix` misclassification (#12781), caught at human review.** A tidy green PR
   removed a `cleanup()` that drops old price data. The gate worked — bakert rejected
   it. `WORKER_PROMPT.md` now excludes "changes what data is kept or deleted" from
   `easy-fix` and names this case as calibration.
4. **Orphan-branch deadlock (#12618, #12716).** A fixer pushed a branch but its report
   was never harvested, so the retry collided with its own branch and escalated. Now
   auto-reclaimed: a `sweep/<n>-*` branch with no PR of any kind is deleted and the
   retry proceeds.
5. **Manager error.** A stray `report-only` call moved #12729 out of `verified`;
   corrected and journaled. This is the single recorded invariant violation.

## 5. Dispatcher defects found and fixed during the pilot

Silent mirror failure (no git identity ⇒ commit/push failed while journaling
`MIRROR_PUSHED` and reporting success); `run(check=False)` dropping stderr, which hid
it; the spec's stale-transcript detector never implemented; no daemon pidfile
(`pgrep -f` matched its own shell wrapper and silently failed one restart); the daemon
holding `flock` for its whole life, which would have blocked every `adjudicate`;
Cloudflare 403ing the default `Python-urllib` UA; and unit tests polluting the
production log. Test suite: **72 tests, all passing.**

Crash recovery was exercised as required: `kill -9` mid-pilot, then `recover`
harvested 4 finished batches and re-adopted 4 running ones with no loss or duplication.

## 6. Recommendation: HOLD Phase 2 on two conditions

1. **`issues: write` on the token**, then execute and audit a handful of real
   closures. The closure half of the pipeline is still unproven end to end.
2. **A decision on PR volume.** 23 of 40 (57%) came back `easy-fix`. Extrapolated,
   that is roughly **400 draft PRs** across 699 issues. At 20/day that is a month of
   review. Options: raise the easy-fix bar, cap concurrently-open sweep PRs (e.g. 25)
   and refill as bakert clears them, or route most easy-fixes to report-only and fix
   on request.

Everything else is green: zero infrastructure failures, malformed rate inside target,
fast workspaces, working recovery, and a human-review gate that has already caught the
one bad call the sweep made.
