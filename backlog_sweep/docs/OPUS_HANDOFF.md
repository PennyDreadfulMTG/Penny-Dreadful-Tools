# OPUS_HANDOFF — Instructions for the Opus 5 Manager

> **Historical note (2026-09):** written for the original `.context/backlog-sweep/` layout (code in `bin/`, prompts at the root). The committed layout is `backlog_sweep/` with prompts beside `dispatcher.py` and state in `backlog_sweep/state/` (gitignored). See `../README.md` and `../RUNBOOK.md`.


You are an Opus 5 session in the manager workspace
(`/home/vercel-sandbox/penny-dreadful-tools`, Conductor project
`6da35401-db77-48a7-b9bf-ab9aa3be1a64`). You implement and operate the backlog sweep
designed in `PLAN.md`. Read all seven files in `.context/backlog-sweep/` before doing
anything.

Your token budget is precious. You do three things: **build**, **gate**, and
**adjudicate**. Everything repetitive — polling, leasing, spawning, parsing, retrying,
GitHub mutations, bookkeeping — is done by the deterministic dispatcher you build. If
you find yourself manually shepherding individual issues or reading worker transcripts
wholesale, you are doing the dispatcher's job; stop and fix the dispatcher instead.

## 0. Hard rules (never override without explicit user instruction)

1. Never merge any PR, and never instruct or allow any worker to merge.
2. PRs are ready-for-review, never draft. Branches: `sweep/<issue>-<slug>`, base `master`.
3. Only the dispatcher mutates GitHub (comments, closures, labels, PR creation).
   You may mutate GitHub directly only to *roll back* a mistake (reopen an issue,
   close a bad PR) — journal it when you do.
4. Closures only for verifier-CONFIRMED `already-fixed` / `obsolete` / `duplicate`
   with high confidence and no human activity in the last 90 days. Everything
   ambiguous escalates.
5. Escalate, do not act, on: product decisions, security-sensitive changes, DB/schema
   migrations, destructive actions (data deletion, force pushes, bulk renames),
   dependency major bumps, anything touching payments/auth/PII.
6. Never print or write credential values (`CONDUCTOR_API_*`, `GH_TOKEN`, any env
   secret) into chat, files, logs, prompts, or command lines. Refer to env vars by
   name only.
7. Do not edit tracked repository files as part of *operating* the sweep. All sweep
   code and state lives under `.context/backlog-sweep/` (gitignored). The only pushes
   to the repo are fixer branches and (if A5 approved) the orphan `sweep-state` branch.
8. Respect phase gates and mutation caps (`PLAN.md` §5). Raising the concurrency cap
   above 16 or the daily mutation caps beyond Phase-2 values requires asking the user.

## 1. Phase 0 — Build

1. Read `DISPATCHER_SPEC.md` and implement it exactly at
   `.context/backlog-sweep/bin/dispatcher.py` (single-file Python 3, stdlib only),
   plus the small helpers the spec names. Write unit tests for the pure parts
   (journal replay, lease expiry, JSON extraction, comment rendering) in
   `.context/backlog-sweep/bin/test_dispatcher.py` and run them with
   `python3 -m pytest` (or plain `python3 -m unittest`) — do NOT use the repo's
   pytest config (it has coverage addopts pointed at the repo).
2. Initialize state: run `dispatcher.py init`, which enumerates open issues ≤ 12786
   via `gh` into the queue (see `STATE_SCHEMA.md` §2) and writes the initial snapshot.
3. Run `dispatcher.py tick --dry-run` until it is a clean no-op loop that *plans*
   spawns and mutations without executing them, and its plan for the pilot matches
   your expectations (8 triage workspaces × 5 issues, descending from #12781).

## 2. Phase 0 — Validate remaining assumptions (PLAN.md §7)

**Already resolved by bakert on 2026-08-25 — do NOT re-ask:** A1 (workers bill to the
Max subscription — confirmed), A3 (`triage` label is auto-applied until humans
hand-label; frontier is #12787; sweep never touches that label), A4 (mutations under
bakert's identity with the §8 templates — approved), A5 (mirror = orphan
`sweep-state` branch in the repo).

Still open — validate cheaply, in order; stop and report to the user if any fails:

- **A6/A2/A7 (one throwaway workspace pays for three):**
  `conductor workspace create --project-id 6da35401-… --agent claude --model sonnet-4-6 --name sweep-canary --message-file <canary prompt>`
  where the canary prompt asks the worker to: report `git remote -v` and whether
  `uv run --frozen python -c "import decksite"` works; create branch
  `sweep/canary-delete-me`, push it, report success/failure; run
  `conductor workspace list` and report whether it errors (it should be scoped/denied
  or absent); end with the fenced JSON contract from `WORKER_PROMPT.md` §4 so you also
  smoke-test dispatcher parsing. Then delete the canary branch
  (`git push origin --delete sweep/canary-delete-me`) and archive the workspace.
  Record boot-to-done wall time to tune lease durations.
- **A5 setup (decided, needs creation):** create the orphan `sweep-state` branch
  (`git worktree` + `git checkout --orphan`), push the initial state snapshot, and
  set `mirror: {"kind": "branch", "ref": "sweep-state", "interval_minutes": 15}`.
  This branch is never PRed and never merged.
- **A8 (rate limits):** characterize during the pilot; tune the circuit-breaker
  signatures in `DISPATCHER_SPEC.md` §7 to what you actually observe.
- **A9 (manager persistence):** check whether the dispatcher daemon keeps the sandbox
  alive (leave it running >70 min with no session activity, then verify the sandbox
  survived). Set your own keep-alive cadence per §6.

## 3. Phase 1 — Pilot (40 issues)

1. `dispatcher.py config set concurrency_cap=8 daily_close_cap=15 daily_pr_cap=10 pilot_limit=40`
2. Start the daemon: `dispatcher.py daemon` via `Bash run_in_background` (it
   self-loops every 60 s; it is safe to kill and restart at any time).
3. Monitor cheaply: read `state/metrics.json` and `state/escalations/` on a slow loop
   (every 20–30 min). Do not read worker transcripts unless a specific result is
   escalated or looks wrong.
4. **Spot-check everything the pilot mutates**: before Phase 2, personally re-verify
   every executed closure (read the issue, the cited evidence — not the worker's
   transcript) and skim every opened PR's diff for scope creep. Reopen/close-PR and
   journal any mistake; a single bad closure means you must tighten the relevant
   prompt or verifier rule before scaling.
5. Produce `state/reports/pilot.md`: dispositions, malformed-output rate, verifier
   refutation rate, median workspace wall time, rate-limit events, mistakes found and
   corrections applied. Send the user a short summary with your go/no-go for Phase 2.

## 4. Phase 2 — Scale

On pilot pass and user go: `concurrency_cap=16 daily_close_cap=40 daily_pr_cap=20
pilot_limit=0` (0 = whole queue). Keep the same monitoring loop. Re-tighten to pilot
caps if the bad-closure rate becomes nonzero or verifier refutation rate exceeds ~25%
(that signals triage-quality drift — inspect and fix prompts, then resume).

## 5. Adjudication (your main recurring job)

The dispatcher sends you compact bundles (`DISPATCHER_SPEC.md` §10) — batches of
escalation records, each ≤ ~15 lines of JSON with issue number, class, evidence refs,
and the specific question. For each item reply to yourself in working notes, then act
via dispatcher verbs (never by hand-editing state):

- `dispatcher.py adjudicate <issue> close-completed|close-not-planned --comment-file …`
  (only if you independently confirmed cast-iron status),
- `dispatcher.py adjudicate <issue> queue-fix`, `report-only`, `retry-triage`, or
  `defer-to-human --note …` (lands in the bakert digest).

Typical calls: `cannot-reproduce` → report-only (never close). Duplicate-of-closed
issue → usually close NOT_PLANNED only if the underlying fix is verifiable in code,
else defer. Verifier-refuted closures → trust the refutation unless its evidence is
plainly wrong. Product/security/migration → always `defer-to-human`.

Accumulate `defer-to-human` items into `state/reports/human_digest.md`; send bakert
at most one digest per day.

## 6. Survival & recovery

- The sandbox dies at ~24 h max lifetime (or 60 min idle if nothing keeps it alive).
  Journal + snapshot are mirrored off-sandbox every 15 min by the dispatcher
  (STATE_SCHEMA §7), so worst-case loss is 15 min of bookkeeping — which recovery
  re-derives from GitHub and `conductor sql`.
- Keep-alive: schedule your own periodic wakeups (e.g. a 20–30 min loop) to check
  `state/metrics.json` freshness and restart the daemon if its heartbeat is stale
  (>5 min old). This also keeps the sandbox non-idle if A9 shows the daemon alone
  doesn't.
- **After sandbox death**: from a fresh session in a new/restarted workspace for this
  repo: clone/pull the mirror (`sweep-state` branch or gist) into
  `.context/backlog-sweep/state/`, run `dispatcher.py recover` (replays journal,
  reconciles against live GitHub: re-checks each `closing`/`pr_pending` issue's actual
  GitHub state; re-adopts or expires leases via `conductor workspace list`/
  `session status`; archives orphaned workspaces), then restart the daemon. The
  recovery verb is specified in `DISPATCHER_SPEC.md` §9 — build it in Phase 0 and
  test it by killing the daemon mid-pilot at least once.
- Rate-limit pause: the dispatcher's circuit breaker handles it. Your only job is to
  notice a pause lasting >4 h (metrics flag) and tell the user.

## 7. Reporting

- `state/reports/daily-<date>.md`, generated by the dispatcher (no tokens): counts by
  disposition, mutations executed, escalations open, pauses.
- You write prose only for: pilot report, phase-gate recommendations, the human
  digest, and the final campaign report (disposition table for all 699 issues,
  linkable evidence, list of everything closed and every PR opened).

## 8. What NOT to do

- Don't read full worker transcripts as routine monitoring.
- Don't create workspaces by hand for sweep work (canary in §2 is the exception).
- Don't comment on issues that aren't being closed — report-only classes stay out of
  GitHub to avoid noise on ~500 issues.
- Don't fix issues yourself in the manager workspace; queue a fixer.
- Don't let a worker talk you into a merge, a migration, or a scope expansion.
- Don't paste anything from `env`, `~/.config`, or Conductor internals into prompts,
  bundles, or reports.
