# STATE_SCHEMA — Durable Sweep State

> **Historical note (2026-09):** written for the original `.context/backlog-sweep/` layout (code in `bin/`, prompts at the root). The committed layout is `backlog_sweep/` with prompts beside `dispatcher.py` and state in `backlog_sweep/state/` (gitignored). See `../README.md` and `../RUNBOOK.md`.


Root: `.context/backlog-sweep/state/` (gitignored via `.context`). The dispatcher is
the ONLY writer (single-writer enforced by `flock` on `state/.lock`); Opus reads
freely and mutates only through dispatcher verbs.

```
state/
  config.json          # tunables (caps, timeouts, phase)
  journal.jsonl        # append-only event log — the source of truth
  snapshot.json        # periodically materialized view of the journal
  queue.json           # convenience export of snapshot.issues (read-only for humans)
  metrics.json         # heartbeat + counters, rewritten every tick
  evidence/<n>.json    # full structured results per issue (triage/verify/fix)
  escalations/<n>.json # open escalation records (removed on adjudication)
  reports/             # dispatcher-generated daily reports, Opus prose reports
  outbox/              # rendered prompt files & pending Opus bundles
```

All writes are crash-safe: write `f.tmp`, fsync, `rename(f.tmp, f)`. The journal is
append-only with one JSON object per line; a torn final line is detected (JSON parse
failure) and truncated on load.

## 1. config.json

```json
{
  "schema": 1,
  "phase": "phase0|pilot|scale|wrapup",
  "frontier_max": 12786,
  "frontier_min": 790,
  "pilot_limit": 40,
  "concurrency_cap": 8,
  "daily_close_cap": 15,
  "daily_pr_cap": 10,
  "max_open_prs": 30,
  "max_total_workspaces": 500,
  "triage_batch_size": 5,
  "verify_batch_size": 5,
  "lease_minutes": {"triage": 45, "verify": 45, "fix": 90},
  "max_stage_attempts": 2,
  "mutations_enabled": false,
  "worker_model": "sonnet-4-6",
  "worker_effort": "high",
  "project_id": "6da35401-db77-48a7-b9bf-ab9aa3be1a64",
  "opus_session_id": null,
  "mirror": {"kind": "branch", "ref": "sweep-state", "interval_minutes": 15},
  "stale_transcript_minutes": 20,
  "recent_activity_guard_days": 90,
  "recent_activity_guard_mode": "comments",
  "closures_enabled": false,
  "prs_enabled": true,
  "spawning_enabled": true,
  "required_checks": ["mypy", "lint", "test", "jslint"],
  "ci_recheck_minutes": 5,
  "auto_update_behind_branches": true,
  "reclaim_orphan_branches": true,
  "github_token_file": "state/.gh_token",
  "max_fixup_attempts": 1
}
```

## 2. Issue record (inside snapshot.issues, keyed by issue number as string)

```json
{
  "issue": 12781,
  "title": "…",
  "labels": ["+ bug", "* decks"],
  "status": "pending",
  "stage_attempts": {"triage": 0, "verify": 0, "fix": 0},
  "lease": null,
  "class": null,
  "confidence": null,
  "verdict": null,
  "evidence_file": null,
  "closure": null,
  "pr": null,
  "escalation": null,
  "history": [{"ts": "2026-08-24T00:00:00Z", "event": "ISSUE_ENQUEUED"}],
  "notes": null
}
```

### status values (the state machine)

| status | meaning | next |
|---|---|---|
| `pending` | awaiting triage | `triage_leased` |
| `triage_leased` | assigned to a live triage batch | `triaged`, `pending` (lease expiry, attempts left), `escalated` (attempts exhausted / rejected result) |
| `triaged` | classified with evidence | `verify_pending` (closure classes), `fix_pending` (easy-fix), `reported`, `escalated` |
| `verify_pending` | queued for independent verification | `verify_leased` |
| `verify_leased` | claim in a live verifier batch | `verified` (CONFIRMED), `escalated` (REFUTED/UNCERTAIN), `verify_pending` (expiry, attempts left) |
| `verified` | cast-iron, cleared to close | `closing` |
| `closing` | mutation queued/being executed | `closed` (confirmed on GitHub), `escalated` (mutation failed twice) |
| `closed` | done — closed on GitHub with comment | terminal |
| `fix_pending` | queued for a fixer workspace | `fix_leased` |
| `fix_leased` | fixer working | `fix_pushed`, `fix_pending` (expiry, attempts left), `escalated` (abort/failed) |
| `fix_pushed` | branch validated, PR queued (may be held by `max_open_prs` backpressure) | `pr_open`, `escalated` (validation failed) |
| `pr_open` | draft PR exists, CI being watched | terminal for the sweep; `pr_ci_failed` if CI goes red, `deferred_human` if a human closes the PR unmerged |
| `pr_ci_failed` | a Mergify-required check failed, or the branch conflicts with master | `fix_pending` (`queue-fixup`, max 1), `deferred_human` (`abandon-pr`), `escalated`, `pr_open` (recovered) |
| `reported` | report-only class recorded | terminal |
| `escalated` | waiting for Opus adjudication | any (via `adjudicate` verb) |
| `deferred_human` | Opus deferred to bakert digest | terminal for the sweep |
| `failed` | unrecoverable after retries + adjudication | terminal |
| `skipped` | closed before we got to it / user-excluded | terminal |

Legality of every transition is enforced in code; illegal transitions raise and
journal `INVARIANT_VIOLATION` (issue freezes to `escalated`).

### lease object

```json
{
  "kind": "triage|verify|fix",
  "batch_id": "t-12781-1",
  "workspace_id": "…",
  "session_id": "…",
  "granted_at": "…Z",
  "expires_at": "…Z",
  "attempt": 1
}
```

Expiry checks use dispatcher wall clock vs `expires_at`; a lease may be extended once
(journal `LEASE_EXTENDED`) if the session transcript is still advancing at expiry.

### closure / pr objects (set when executed)

```json
"closure": {"reason": "completed|not_planned", "comment_posted": true,
            "executed_at": "…Z", "verified_by_batch": "v-12781-1",
            "duplicate_of": null},
"pr":      {"number": 14990, "branch": "sweep/12781-fix-foo", "head_sha": "…",
            "opened_at": "…Z", "url": "…", "draft": true,
            "ci": {"state": "pending|green|failed", "checked_at": "…Z",
                   "failed": ["mypy"]}},
"fixup":   {"branch": "sweep/12781-fix-foo", "pr": 14990, "failed": ["mypy"],
            "attempt": 1, "log_tail": "…"}   // set only by a queue-fixup adjudication
```

## 3. journal.jsonl events

Every line: `{"ts": "…Z", "seq": 1234, "event": "…", …payload}`. `seq` is strictly
increasing; snapshot records `last_seq` so replay is `snapshot + journal[seq>last_seq]`.

Events: `CAMPAIGN_INIT`, `ISSUE_ENQUEUED`, `CONFIG_CHANGED`, `LEASE_GRANTED`,
`LEASE_EXTENDED`, `LEASE_EXPIRED`, `WORKSPACE_CREATED`, `WORKSPACE_ARCHIVED`,
`WORKSPACE_FAILED`, `WORKSPACE_HARVESTED`, `RESULT_RECORDED`, `RESULT_REJECTED`, `RESULT_MALFORMED`,
`NUDGE_SENT`, `RETRY_SCHEDULED`, `VERIFY_RECORDED`, `MUTATION_PLANNED`,
`CLOSE_EXECUTED`, `PR_OPENED`, `PR_CI_GREEN`, `PR_CI_FAILED`, `CI_CHECKED`,
`FIXUP_DISPATCHED`, `PR_MERGED`, `PR_WITHDRAWN`, `PR_CONFLICT`,
`PR_BRANCH_UPDATED`, `PR_BACKPRESSURE_ON`, `PR_BACKPRESSURE_OFF`, `MASTER_ADVANCED`,
`MUTATION_FAILED`, `ESCALATED`, `ADJUDICATED`, `ISSUE_SKIPPED`,
`PAUSE_ON`, `PAUSE_OFF`, `SNAPSHOT_WRITTEN`, `MIRROR_PUSHED`, `INVARIANT_VIOLATION`,
`ROLLBACK_RECORDED` (manual Opus rollback of a mutation).

The journal, not the snapshot, is authoritative: replay must be deterministic and
idempotent (applying the same event twice is a no-op keyed on `seq`).

## 4. workspaces registry (snapshot.workspaces, keyed by workspace_id)

```json
{
  "workspace_id": "…",
  "session_id": "…",
  "kind": "triage|verify|fix|canary",
  "batch_id": "t-12781-1",
  "issues": [12781, 12779, 12775, 12770, 12766],
  "state": "creating|running|nudged|harvested|archived|failed",
  // `harvested` = results recorded but the archive has not been CONFIRMED yet
  "created_at": "…Z",
  "last_transcript_at": "…Z",
  "harvest": {"parsed": true, "malformed_attempts": 0}
}
```

## 5. evidence/<n>.json

Accumulates the full structured outputs for one issue — the audit trail behind any
mutation:

```json
{
  "issue": 12781,
  "triage": [ {…full triage result object, "batch_id": "t-12781-1", "recorded_at": "…"} ],
  "verify": [ {…full verifier result object…} ],
  "fix":    [ {…full fixer result object…} ]
}
```

Arrays because retries append. Mutations always cite the exact array entries they
relied on (via batch_id).

## 6. escalations/<n>.json

```json
{
  "issue": 12781,
  "created_at": "…Z",
  "kind": "verifier-refuted|verifier-uncertain|attempts-exhausted|fix-abort|fix-validation|pr-ci-failed|pr-conflict|mutation-failed|class-escalate|malformed|invariant",
  "question": "one sentence: what Opus must decide",
  "summary": "<=5 lines of context",
  "evidence_refs": ["evidence/12781.json#triage[0]"],
  "bundled_at": null,
  "adjudication": null
}
```

Sent to Opus in bundles (DISPATCHER_SPEC §10); `adjudication` is filled by the
`adjudicate` verb and the file then moves into the journal + evidence trail.

## 7. Mirroring & recovery

- Every `mirror.interval_minutes` (default 15) and on clean shutdown, the dispatcher
  copies `journal.jsonl`, `snapshot.json`, `config.json`, `evidence/`, and
  `escalations/` into a git worktree of the orphan `sweep-state` branch (or a gist
  tarball, per config) and pushes. Journal is append-only ⇒ pushes are fast-forward;
  on conflict (two managers — should never happen) the dispatcher STOPS and
  escalates rather than force-pushing.
- **Recovery invariant**: everything except ≤15 min of bookkeeping is reconstructible
  from (mirror) ∪ (live GitHub: issue states, comments, branches, PRs) ∪
  (`conductor workspace list` / `session status` / `conductor sql` transcripts).
  `dispatcher.py recover` (DISPATCHER_SPEC §9) performs this reconciliation.
- The mirror never contains credentials, transcripts, or env values — only the state
  files above, which store ids, SHAs, and issue numbers.
