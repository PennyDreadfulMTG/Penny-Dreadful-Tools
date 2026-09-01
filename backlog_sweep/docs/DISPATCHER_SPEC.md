# DISPATCHER_SPEC — Deterministic, Restartable, Zero-Token Coordinator

> **Historical note (2026-09):** written for the original `.context/backlog-sweep/` layout (code in `bin/`, prompts at the root). The committed layout is `backlog_sweep/` with prompts beside `dispatcher.py` and state in `backlog_sweep/state/` (gitignored). See `../README.md` and `../RUNBOOK.md`.


A single-file Python 3 program, `.context/backlog-sweep/bin/dispatcher.py`, stdlib
only. It consumes **no model tokens**: it shells out to the `conductor` CLI (already
authenticated via `CONDUCTOR_API_*` env vars — never read or printed by the
dispatcher) and to `gh`/`git`. The only model-token-consuming things it triggers are
(a) worker sessions it creates, (b) corrective nudges to those sessions, and (c)
compact bundles sent to the Opus manager session — all by design.

## 1. CLI verbs

```
dispatcher.py init                      # enumerate queue from GitHub, write CAMPAIGN_INIT
dispatcher.py tick [--dry-run]          # one pass of the loop in §3
dispatcher.py daemon [--interval 60]    # tick forever; SIGTERM-safe
dispatcher.py status                    # human-readable one-screen summary from snapshot
dispatcher.py config set K=V …          # journal CONFIG_CHANGED, update config.json
dispatcher.py adjudicate <issue> <verb> [--comment-file F] [--note …]
                                        # verbs: close-completed, close-not-planned,
                                        #        queue-fix, report-only, retry-triage,
                                        #        retry-verify, defer-to-human, mark-failed
dispatcher.py recover                   # post-crash/post-sandbox-death reconciliation (§9)
dispatcher.py mirror                    # force a mirror push
dispatcher.py report daily              # write reports/daily-<date>.md from snapshot
```

Every verb: acquire `flock` on `state/.lock` (non-blocking; exit 75 if held), load
snapshot, replay journal tail, act, append events, release. `tick` and `daemon` are
the same code path; `daemon` also writes `metrics.json` heartbeat each pass and
traps SIGTERM to finish the current step, snapshot, mirror, and exit 0.

Determinism: no randomness; all ordering by issue number descending (the sweep
direction) and by `seq`. Timestamps come from the wall clock but decisions depend
only on comparisons against configured durations, so replays reconverge.

## 2. init

1. `gh issue list --state open --limit 1000 --json number,title,labels,updatedAt
   --search "sort:created-desc"` filtered to `number <= config.frontier_max`
   (12786) and `>= frontier_min` (790).
2. Journal `CAMPAIGN_INIT` + one `ISSUE_ENQUEUED` per issue, status `pending`,
   ordered descending. `pilot_limit` N>0 means only the N highest numbers are
   eligible for leasing; the rest stay `pending` but unleasable until Phase 2.
3. Re-running `init` is idempotent: already-known issues are untouched; newly-closed
   ones journal to `skipped`.

## 3. tick loop (each pass, in this order)

1. **Harvest** (§5): poll every workspace in state `creating|running|nudged`;
   parse finished sessions; record results; archive harvested workspaces.
2. **Expire leases** (§6.4).
3. **Execute mutations** (§8): closures for `verified`, PRs for `fix_pushed` —
   respecting `mutations_enabled`, daily caps, and idempotency checks.
4. **Watch CI** (§8b): poll the Mergify-required checks on every `pr_open` PR.
5. **Bundle escalations** to Opus (§10).
6. **Replenish pool** (§6): while `active_workspaces < concurrency_cap` and not
   paused and `total_workspaces_created < max_total_workspaces`, spawn the
   highest-priority pending work: verify batches, then fix tasks, then triage
   batches (descending issue number within each).
7. **Snapshot** if ≥50 new journal events or ≥5 min since last; **mirror** if
   interval elapsed; rewrite `metrics.json`; emit `report daily` at first tick past
   midnight UTC.

`--dry-run`: steps 3 and 6 print their exact planned commands to stdout instead of
executing; nothing is journaled except `SNAPSHOT_WRITTEN`.

## 4. Spawning workspaces

Prompt files are rendered from the templates in `WORKER_PROMPT.md` /
`VERIFIER_PROMPT.md` / `FIXER_PROMPT.md` into `state/outbox/<batch_id>.md`
(placeholders substituted; nothing else altered — treat the templates as code).

```
conductor workspace create \
  --project-id <config.project_id> \
  --agent claude --model <config.worker_model> --effort <config.worker_effort> \
  --name "sweep-<batch_id>" --session-name "sweep-<batch_id>" \
  --message-file state/outbox/<batch_id>.md
```

Parse workspace/session ids from stdout (the CLI prints them; if parsing fails, run
`conductor workspace list --name sweep-<batch_id>` to recover the id — batch ids are
unique, which makes creation idempotent-checkable). Journal `WORKSPACE_CREATED` +
`LEASE_GRANTED` per issue. Creation failure: journal `WORKSPACE_FAILED`, return the
issues to their pending state without consuming an attempt, count toward the circuit
breaker (§7).

Lease durations from `config.lease_minutes` by kind, measured from creation.

## 5. Harvest

For each active workspace: `conductor session status <session_id>`.

- **Still running** and transcript advancing (`transcript_updated_at` via
  `conductor sql "SELECT transcript_updated_at FROM session_transcripts_view WHERE
  session_id = '<id>'"`, or `session status` if it carries the field): continue.
- **Still running but stale** (> `stale_transcript_minutes` with no transcript
  change): treat as hung — `conductor session cancel`, journal `WORKSPACE_FAILED`,
  handle like lease expiry (§6.4).
- **Completed**: fetch the final assistant message via
  `conductor session message <session_id> --limit 5` (newest messages; fall back to
  the `conductor sql` transcript column). Extract the LAST fenced ```json block;
  require `backlog_sweep == "v1"`, matching `role` and `batch_id`, and one result
  per leased issue. Then per result: validate against the role's schema (§7 of the
  role's prompt file); write into `evidence/<n>.json`; journal `RESULT_RECORDED`;
  apply the state transition (triage class → `triaged` then route; verify verdict →
  `verified`/escalate; fix outcome → `fix_pushed`/escalate). Results for non-leased
  issues journal `RESULT_REJECTED` and are dropped. Missing results consume that
  issue's attempt as if expired.
- After recording (or exhausting the malformed protocol below): archive the
  workspace, then **confirm it** with `GET /v0/workspaces/<id>/status` before
  journaling `WORKSPACE_ARCHIVED`. If the state is not `archived`/`deleted`, journal
  `WORKSPACE_HARVESTED` instead and let `retry_archives()` try again on a later tick.
  Journaling an unverified archive is how 39 workspaces sat in `sleeping` while state
  claimed otherwise; the archive POST was returning HTTP 400
  (`FST_ERR_CTP_EMPTY_JSON_BODY`) because the client set `Content-Type:
  application/json` on a body-less request. `recover` re-checks every workspace the
  registry believes is archived and re-archives any that are not.

**Malformed output protocol**: if no valid block is found — journal
`RESULT_MALFORMED`; if `malformed_attempts == 0`, send ONE corrective nudge and
re-poll on later ticks:

```
conductor message create --session <id> --message-id nudge-<batch_id> \
  --message "Your final message must end with the single fenced ```json block \
specified in your instructions (backlog_sweep v1, role <role>, batch_id <batch_id>, \
one result per assigned issue). Reply with ONLY that block."
```

(`--message-id` makes the nudge exactly-once across dispatcher restarts.) If still
malformed: archive the workspace, consume one attempt for each leased issue, and let
the retry ladder (§6.4) decide fresh-workspace retry vs escalation.

## 6. Leasing rules

1. **Triage batches**: up to `triage_batch_size` issues in `pending` (eligible under
   `pilot_limit`), highest numbers first, `batch_id = t-<first_issue>-<attempt>`.
2. **Verify batches**: issues in `verify_pending`, batched up to
   `verify_batch_size`, `batch_id = v-<first_issue>-<attempt>`. The rendered claims
   include only class, cited evidence refs, and proposed comment — never triage
   notes (independence rule).
3. **Fix tasks**: one issue in `fix_pending` per workspace. Pre-dispatch guards, all
   via live GitHub: issue still open; no open PR referencing it
   (`gh pr list --state open --search "<n> in:title,body" --json number` plus
   `gh api repos/{owner}/{repo}/issues/<n>/timeline` cross-reference check is
   optional-nice-to-have; the search check is mandatory); branch
   `sweep/<n>-<slug>` absent (`git ls-remote origin refs/heads/sweep/<n>-*`). Guard
   failure ⇒ journal + escalate (a human or earlier run is already on it).
4. **Expiry**: lease past `expires_at` → if transcript advanced in the last 10 min,
   extend once (`LEASE_EXTENDED`, +50% duration); else `conductor session cancel`,
   archive workspace, `LEASE_EXPIRED`, `stage_attempts[kind] += 1`. If
   `stage_attempts[kind] < max_stage_attempts` ⇒ back to the stage's pending status
   (`RETRY_SCHEDULED`, fresh workspace on a later tick). Else ⇒ `escalated`
   (`kind: attempts-exhausted`).

## 7. Failure handling & circuit breaker

- Every `conductor`/`gh` subprocess: timeout 120 s, up to 3 attempts with
  exponential backoff (5 s, 25 s, 125 s) on nonzero exit/timeout; then count one
  **infrastructure failure**.
- **Circuit breaker**: ≥3 infrastructure failures within 10 min, OR ≥2 workspace
  creations failing in a row, OR any session/CLI output matching rate-limit
  signatures (`rate.?limit|overloaded|429|usage limit|quota`, case-insensitive) ⇒
  `PAUSE_ON`: stop spawning and nudging; freeze lease-expiry clocks (record pause
  intervals and add them to `expires_at`); keep harvesting already-finished work and
  keep mirroring. Retry probe after 30 min; on repeated failure double up to 4 h
  cap. Success ⇒ `PAUSE_OFF`. Pause longer than 4 h sets `metrics.alert` for Opus.
- GitHub mutation failure: retry ladder as above; two full failures ⇒
  `MUTATION_FAILED` + escalate that issue; never leave `closing` silently.
- Crash safety: every state change is journaled before its side effect where
  possible (`MUTATION_PLANNED` precedes the `gh` call; `CLOSE_EXECUTED`/`PR_OPENED`
  after). Replay + the idempotency checks in §8 make the crash window safe.

## 8. GitHub mutations (the only writers)

Gated on `config.mutations_enabled`, the sub-gates `closures_enabled` /
`prs_enabled`, and daily caps (counted from journal events since midnight UTC; at
cap, work queues in `verified`/`fix_pushed` until tomorrow).

**Open-PR backpressure (`config.max_open_prs`, default 30).** `daily_pr_cap` bounds
the *rate* at which PRs appear; it does nothing about the *pile* awaiting review. At
the pilot's 58% easy-fix rate Phase 2 would produce 300–400 PRs, so before opening
any PR the dispatcher counts sweep PRs currently open **live on GitHub**
(`gh pr list --state open --json number,headRefName`, filtered to `sweep/` heads) —
deliberately not from internal state, because bakert merges and closes PRs outside
the sweep and our own `pr_open` count drifts high. At or above the cap, `fix_pushed`
branches simply stay queued.

This is normal flow control, not a fault: it journals `PR_BACKPRESSURE_ON` **once**
on entering the held state and `PR_BACKPRESSURE_OFF` once on leaving it, never
escalates, and never touches a branch. If the count query itself fails the
dispatcher holds for that tick rather than risking a flood. `metrics.json` reports
`pr_backpressure`, `open_sweep_prs` and `max_open_prs`.

**Closure** (status `verified`):
1. Idempotency + guards, live: `gh issue view <n> --json state,updatedAt,comments`.
   Already closed ⇒ journal `CLOSE_EXECUTED {external: true}` → `closed`.
   **Recent-activity guard (revised 2026-08-23, approved by bakert):** the guard
   reads *comments*, not `updatedAt`. Bulk labelling in this repo (the `triage`
   label alone covers 133 open issues below the frontier) bumps `updatedAt` on
   hundreds of issues, which would have blocked essentially every closure while
   telling us nothing about human attention. The guard therefore escalates when
   either: (a) a non-bot comment exists within `recent_activity_guard_days`
   (90 days), or (b) any human comment appeared after the verifier ran. Bot authors
   (`config.bot_logins` plus any login ending in `[bot]`) are ignored. `updatedAt`
   is still fetched and journaled for the audit trail but is not load-bearing.
2. Comment + close in one call, using the verifier's `final_comment`:
   `gh issue close <n> --reason <completed|"not planned"> --comment "<final_comment> <tag>"`
   where `<tag>` = `\n\n<sub>Automated backlog sweep; independently verified.
   Wrongly closed? Please reopen.</sub>` — template approved by bakert (A4,
   2026-08-25).
3. Verify: `gh issue view <n> --json state` shows `CLOSED` ⇒ `CLOSE_EXECUTED` ⇒
   `closed`. Rollback procedure (Opus-initiated only): `gh issue reopen <n>` +
   `ROLLBACK_RECORDED`.

**PR creation** (status `fix_pushed`): after the validations in `FIXER_PROMPT.md`'s
dispatcher notes (branch at reported SHA via `git ls-remote`; diff stat within
budget via `gh api repos/{owner}/{repo}/compare/master...<branch>`; no forbidden
paths; body discloses test caveats):
`gh pr create --base master --head <branch> --title "<pr_title>" --body-file <tmp>
--draft`.

**DRAFT IS MANDATORY (bakert, 2026-08-23) — this REVERSES the original
"ready for review, never draft" rule.** This repo runs Mergify
(`.mergify.yml`), which merges any PR whose author is in the
`@PennyDreadfulMTG/automerge` team — bakert is a member — as soon as `mypy`,
`lint`, `test` and `jslint` pass, typically ~10 minutes after creation. Sweep PRs
are authored under bakert's identity, so a non-draft sweep PR auto-merges itself
and breaks the campaign's first hard rule. The `do not merge` label is **not** a
brake: `.mergify.yml` never references it. Draft is a real brake, because both
GitHub and Mergify refuse to merge a draft PR. bakert's review action is clicking
"Ready for review", which hands the PR to Mergify deliberately.

After creation the dispatcher MUST confirm `gh pr view <n> --json isDraft` returns
`true` **before** journaling `PR_OPENED`. If it is false: close the PR immediately,
set `prs_enabled=false`, journal `MUTATION_FAILED`, and escalate. Parse PR
number/URL ⇒ `PR_OPENED` ⇒ `pr_open`. Idempotency: if a PR for the branch already
exists (`gh pr list --head <branch>`), adopt it instead of creating — and if the
adopted PR is not a draft, escalate rather than close, since it may be a human's.

**Labels**: none, ever, in v1. In this repo `triage` is auto-applied to all new
issues and removed only by hand human labeling — the sweep must not add, remove, or
read meaning into it or any other label.

## 8b. CI watch (added 2026-08-23 at bakert's request)

`pr_open` is terminal *for the sweep*, but a red draft PR would otherwise sit
unnoticed until bakert opened it at review time. Every tick, for each issue in
`pr_open`:

1. `gh pr checks <n> --json name,state,bucket,link`, aggregated per required check
   (`config.required_checks` = `mypy, lint, test, jslint` — exactly the four
   `.mergify.yml` requires). A check appears once per workflow run, so a name is
   `pass` only when every instance passed and `fail` if any instance failed;
   unrelated checks (CodeQL, snyk, pre-commit) are ignored.
2. Poll every tick while any required check is pending. Once green, re-poll on
   either trigger: `config.ci_recheck_minutes` (5) has elapsed, **or master has
   advanced**. The second is the important one — conflicts and `BEHIND` states are
   *caused* by master moving, so the dispatcher compares `git ls-remote origin
   master` against `state.last_master_sha` each tick (a git call, so it costs no
   REST quota) and journals `MASTER_ADVANCED`. When master moves, every open sweep
   PR is rechecked on that tick rather than waiting out its timer, which makes
   conflict detection immediate instead of interval-bound. The first observation of
   a SHA on a fresh campaign is recorded but does not count as movement.
3. **All four pass** ⇒ journal `PR_CI_GREEN` once; status stays `pr_open`.
4. **Any of the four fails** ⇒ status `pr_ci_failed`, journal `PR_CI_FAILED`, and
   escalate to Opus with the failing check names and a best-effort log tail (from
   the check run's `output.summary`/`output.text` — no Actions log scope needed).
   Opus adjudicates per PR:
   - `queue-fixup` ⇒ journal `FIXUP_DISPATCHED`, status `fix_pending` with
     `issue.fixup` set. The next fixer renders `FIXUP_PROMPT.md` instead of
     `FIXER_PROMPT.md`, gets batch id `u-<issue>-<attempt>`, and pushes to the
     **existing** branch. This is the ONLY sanctioned bypass of the
     branch-must-not-exist and no-open-PR guards in §6.3, keyed on `issue.fixup`.
     Capped at `config.max_fixup_attempts` (1) per PR.
   - `abandon-pr` ⇒ close the PR, delete the remote branch, issue to
     `deferred_human` and into bakert's digest.
5. **Mergeability** (same call as human settlement). Master moves under long-lived
   sweep PRs, so a green PR can still be unmergeable.
   - `mergeStateStatus: BEHIND` ⇒ mechanical: `gh pr update-branch <n>` merges master
     in, journal `PR_BRANCH_UPDATED`, no escalation (rate-limited to once per 15 min
     per PR). If that call reports a conflict, do not journal success; the next pass
     sees `CONFLICTING` and escalates properly.
   - `mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` ⇒ status `pr_ci_failed`,
     journal `PR_CONFLICT`, escalate `pr-conflict`. Opus adjudicates with the same
     two verbs as a red check: `queue-fixup` (the fixer merges master into the branch
     and resolves — **merge, never rebase**, so no force-push is ever needed on a
     branch the sweep has already published) or `abandon-pr`.

6. **Human settlement** (checked before the CI poll, same cadence). If the PR is
   `MERGED`, journal `PR_MERGED` and stop polling; the issue stays `pr_open`
   (terminal). If the PR is `CLOSED` **without** merging, that is bakert rejecting
   the fix: journal `PR_WITHDRAWN`, delete `sweep/<n>-*` from origin if it still
   exists, and move the issue to `deferred_human` — **never retried**, because a
   human has settled it. This makes rejecting a sweep PR a two-click operation.

## 9. recover (restart & disaster procedure)

Safe to run any time; required after sandbox death (state restored from mirror
first — see `OPUS_HANDOFF.md` §6):

1. Load snapshot + journal (truncating a torn tail line).
2. **Reconcile mutations**: for every issue in `closing` re-check GitHub and settle
   to `closed` or back to `verified`; for every `fix_pushed` re-check for an
   existing PR (adopt) or missing branch (escalate).
3. **Reconcile workspaces**: `conductor workspace list --name sweep-` ∪ registry.
   For each: `session status` — completed sessions get harvested normally; running
   ones are re-adopted with leases intact; unknown-to-registry `sweep-*` workspaces
   (crash between create and journal) are matched by batch-id naming and adopted,
   or cancelled+archived if their batch already completed elsewhere.
4. **Reconcile queue against GitHub**: any queue issue now closed externally ⇒
   `skipped` (if we didn't close it) — never re-triage a human-closed issue.
5. Journal everything, snapshot, mirror, print a reconciliation summary. Exit; the
   operator restarts `daemon`.

## 10. Escalation bundles to Opus (token-frugal by construction)

- Trigger: ≥10 unbundled escalations, or oldest unbundled >6 h, or phase gate
  reached, or `metrics.alert` set. At most one bundle per 2 h.
- Content: `state/outbox/bundle-<ts>.md` — one line of campaign vitals (counts by
  status, caps used, pause state) + per escalation ≤15 lines: issue, kind, one-line
  question, evidence refs (file paths into `state/evidence/`, not contents), and the
  dispatcher's suggested default. Never transcripts, never diffs, never env values.
- Send: `conductor message create --session <config.opus_session_id>
  --message-id bundle-<ts> --message-file <bundle>` (exactly-once via message-id).
  If `opus_session_id` is unset, bundles queue in outbox and `metrics.alert` is set.
- Opus responds by running `adjudicate` verbs (§1), which journal `ADJUDICATED`,
  apply the transition, and delete the escalation file.

## 8c. Operator GitHub token

The Conductor-issued `GH_TOKEN` in the manager sandbox is a GitHub App
user-to-server token with `issues: read` / `pull_requests: write`, so it can open,
label and close PRs but cannot close or comment on issues. To enable the
`already-fixed` / `obsolete` / `duplicate` closures, the operator drops a PAT at
`config.github_token_file` (default `state/.gh_token`).

Deliberately a file, not an environment variable:

- it stays in the manager workspace — the dispatcher never passes `--env` to a
  worker `workspace create`, so no worker ever receives it;
- it is not in `file_include_globs`, so Conductor does not copy it into new
  workspaces the way it copies `.env*` and `/config.json`;
- `_mirror_payload` copies an explicit list of files, which does not include it, so
  it never reaches the `sweep-state` branch;
- it reaches `gh` through the subprocess environment, never argv, and argv is the
  only thing the dispatcher logs;
- loading it registers the value with the log scrubber, so it is redacted even if a
  subprocess echoes it.

Required PAT permissions (fine-grained, this repository only): Metadata read,
Contents read, Issues read+write, Pull requests read+write. The dispatcher warns if
the file is group- or world-readable.

## 11. Logging & secrecy

- `state/dispatcher.log`, rotated at 10 MB ×5. Every subprocess logged as argv +
  exit code + duration; stdout/stderr logged **after scrubbing**: any token matching
  `(?i)(token|key|secret|authorization|bearer)[=:\s]\S+` is replaced with
  `[REDACTED]`, and the values of `CONDUCTOR_API_KEY`/`CONDUCTOR_API_TOKEN`/
  `GH_TOKEN` (read at startup solely to build the scrub list, kept only in memory)
  are blanked wherever they appear.
- The dispatcher never writes env values to state, outbox, mirror, prompts, or
  reports; subprocesses inherit the environment rather than receiving credentials
  as arguments (argv is logged; env is not).

## 12. metrics.json (rewritten every tick)

```json
{"heartbeat": "…Z", "phase": "pilot", "paused": false, "pause_until": null,
 "active_workspaces": 7, "counts": {"pending": 620, "triaged": 31, "closed": 6, "pr_open": 3, "escalated": 4, "…": 0},
 "caps": {"closures_today": 6, "prs_today": 3},
 "totals": {"workspaces_created": 19, "nudges": 2, "infra_failures": 1},
 "alert": null}
```

Opus's monitoring loop reads only this file plus `escalations/` — that is the whole
point: campaign health in <1 KB.
