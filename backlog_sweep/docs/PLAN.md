# Penny-Dreadful-Tools Backlog Sweep — Architecture & Operating Procedure

Status: HISTORICAL DESIGN DOC from the first campaign (August 2026), kept as the
architecture reference. The pilot described in §5 ran successfully 2026-08-23/24;
Phase 2 (the remaining backlog) awaits the owner's go. File paths below refer to the
original `.context/backlog-sweep/` layout; the code now lives in `backlog_sweep/`
(see ../README.md). Operated by a manager agent per `OPUS_HANDOFF.md`.

## 1. Mission

Autonomously triage every open GitHub issue in `PennyDreadfulMTG/Penny-Dreadful-Tools`
older than the already-investigated frontier (#12787), working backwards to the oldest
open issue (#790). For each issue, with evidence:

- Close it (with a concise evidence-based comment) if the closure is cast-iron and
  independently verified.
- Fix it (branch → commits → push → **draft** PR (bakert 2026-08-23: draft is the Mergify brake), never merged) if
  the fix is isolated and low-risk.
- Otherwise classify it and report; escalate anything requiring product decisions,
  security judgment, migrations, destructive actions, or ambiguous closure calls.

## 2. Verified facts (checked 2026-08-23 from this workspace, read-only)

| Fact | Value |
|---|---|
| Repo | `PennyDreadfulMTG/Penny-Dreadful-Tools`, default branch `master` |
| Open issues (total) | 754 |
| Open issues below #12787 (the sweep universe) | **699** (oldest #790, newest #12781) |
| Conductor project id | `6da35401-db77-48a7-b9bf-ab9aa3be1a64` (`penny-dreadful-tools`) |
| Conductor API env vars | `CONDUCTOR_API_URL`, `CONDUCTOR_API_KEY`, `CONDUCTOR_API_TOKEN` all present in this workspace (values never printed) |
| Conductor CLI | `conductor` CLI works here: project/workspace/session/message CRUD, `conductor model`, `conductor sql` (read-only transcript view) |
| Claude agent models in Conductor | `fable-5, opus-5-1m, opus-4-8[-1m], opus-4-7[-1m], opus-4-6-1m, sonnet-5-1m, sonnet-4-6[-1m], haiku-4-5`; default `sonnet-4-6` @ `high` |
| `gh` auth | Authenticated as `bakert` (GH_TOKEN) with push access to origin |
| This sandbox's lifetime | idle timeout 60 min, max lifetime ~23.8 h (`CONDUCTOR_INTERNAL_IDLE_TIMEOUT_MS=3600000`, `MAX_LIFETIME_MS=85800000`) — **the manager sandbox is ephemeral; state must survive its death** |
| `triage` label | Auto-applied to ALL new issues; removed only when humans hand-add area/type labels (confirmed by bakert 2026-08-25). It carries NO information about prior investigation. The sweep must never add, remove, or interpret it |
| Recent closure style | Issues closed as `COMPLETED` (fixed) or `NOT_PLANNED`; e.g. #12925 closed NOT_PLANNED |
| Label taxonomy | Component labels `* decks`, `* discord bot`…; type labels `+ bug`, `+ improvement`, `+ feature`…; `- backlog`, `- important`, `triage` |
| Test/lint entry points | `uv run --frozen python dev.py lint` / `unit` / `test`; pytest markers exclude `functional`/`perf` etc. Full tests likely need MariaDB, which fresh cloud workspaces may not have |
| Dev conventions | `AGENTS.md`: no Docker; use `uv`, npm. Conductor repo settings copy `.env*`, `/config.json`, `/AGENTS.md` into workspaces |

## 3. Architecture

Four roles. **All model tokens are spent in worker/verifier/fixer sessions (sonnet-4-6)
and in rare Opus adjudications. The dispatcher is a deterministic script and spends
zero model tokens.**

```
┌────────────────────────────── manager workspace (this sandbox) ─────────────────────────────┐
│  Opus 5 Manager (session)          Dispatcher (bash/python daemon, no model)                │
│  - builds & starts dispatcher      - owns state under .context/backlog-sweep/state/         │
│  - validates assumptions           - leases exact issue numbers to workers                  │
│  - adjudicates escalation bundles  - creates/polls/harvests/archives cloud workspaces       │
│  - approves scale-up               - performs ALL GitHub mutations (comments/closures/PRs)  │
│  - restarts stack after sandbox    - retries, backoff, circuit breaker, state mirroring     │
│    death                           - sends compact bundles to the Opus session              │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
            │ conductor workspace create / session message / archive
            ▼
   Triage workers (sonnet-4-6, 5 issues each, read-only, JSON verdicts + evidence)
   Verifiers      (sonnet-4-6, independent re-check of proposed closures, JSON verdicts)
   Fixers         (sonnet-4-6, ONE issue per workspace, branch+commit+push; no PR, no gh writes)
```

### Design decisions and why

1. **Centralized GitHub writes.** Only the dispatcher (running as `bakert`'s gh auth in
   this workspace) posts comments, closes issues, applies labels, and opens PRs.
   Workers never mutate GitHub. This gives: one audit log, consistent comment
   formatting, idempotency (dispatcher checks live GitHub state before acting), and
   immunity to per-worker auth uncertainty. Fixers only push branches
   (`sweep/<issue>-<slug>`); the dispatcher opens the ready-for-review PR from the
   fixer's reported title/body.

2. **Continuously replenished pool, not waves.** The dispatcher keeps
   `active_workspaces < concurrency_cap` on every tick, topping up with whichever work
   is highest priority (verify > fix > triage). No barriers; a slow fixer never blocks
   forty triage batches.

3. **Exact issue-number assignment + leases.** The queue is the single source of truth.
   An issue is dispatched only via a lease (worker id, expiry). Expired leases are
   reclaimed with a retry counter. Duplicate work is impossible while the single
   dispatcher holds the state lock; cross-restart duplication is prevented by the
   journal + a live-GitHub idempotency check before each mutation.

4. **Evidence-first, verify-before-close.** Every classification must cite evidence
   (commit SHA, file:line of current code, PR link, duplicate issue number, repro
   attempt). Closures additionally require an independent verifier session that is
   given only the claim — not the triage worker's reasoning — and must reconfirm from
   scratch. Verifier refutation or uncertainty ⇒ escalation, never closure.

5. **Batching triage (5 issues/worker) but fixing 1 issue/workspace.** Triage is cheap
   and read-only, so batching amortizes workspace boot cost (~140 triage workspaces for
   699 issues). Fixes mutate the tree, so isolation is one-issue-per-workspace to
   guarantee no mixed PRs.

6. **Durable, event-sourced state.** Append-only `journal.jsonl` + periodic snapshot,
   mirrored off-sandbox (see `STATE_SCHEMA.md` §7) because this sandbox dies within
   24 h. Full recovery procedure reconstructs state from mirror + live GitHub +
   `conductor sql` transcripts.

7. **Token economy.** Sonnet for all volume work. Opus receives only compact JSON
   bundles (escalations, phase reports, exception digests) — never transcripts. Fable
   is not used at all after this design turn.

## 4. Issue lifecycle

```
pending ─► triage_leased ─► triaged ──┬─ closure candidate ─► verify_leased ─► verified ─► closing ─► closed
                                      │                                   └► refuted/uncertain ─► escalated
                                      ├─ easy_fix ─► fix_leased ─► fix_pushed ─► pr_open
                                      ├─ report-only class ─► reported            └► fix failed ─► escalated
                                      └─ escalation class ─► escalated
(any stage) ─ lease expiry / malformed output ─► retry (max 2 per stage) ─► failed ─► escalated
```

Classifications (full definitions in `WORKER_PROMPT.md`):

- **Closure candidates** (cast-iron only): `already-fixed` (close COMPLETED),
  `obsolete` (close NOT_PLANNED), `duplicate` of another *open* issue (close
  NOT_PLANNED with cross-link; keep the older/better-specified issue).
- **`easy-fix`**: isolated, low-risk, no product judgment, no schema/data migration,
  roughly ≤150 changed lines, tests feasible ⇒ fixer queue.
- **Report-only**: `needs-work` (real, non-trivial), `question`, `cannot-reproduce`
  (never auto-closed) ⇒ recorded in campaign report, no GitHub writes.
- **Escalate**: `needs-product-decision`, `security-sensitive`, `migration-required`,
  `destructive-action`, `unclear`, plus any closure candidate with recent (≤90 days)
  human activity or medium/low confidence.

## 5. Rollout

- **Phase 0 — implementation & assumption validation** (Opus): build dispatcher per
  `DISPATCHER_SPEC.md`, run its dry-run mode, validate assumptions A1–A8 below.
- **Phase 1 — pilot, 40 issues**: the 40 highest open issue numbers ≤ 12786.
  Concurrency cap **8** workspaces. GitHub mutations enabled but with per-day caps
  (≤15 closures, ≤10 PRs). Exit criteria: malformed-output rate <10%, zero bad
  closures in Opus's spot-check of *every* executed closure and PR, verifier
  refutation rate understood.
- **Phase 2 — scale**: cap raised to **16** (higher only with explicit user approval),
  daily caps raised (≤40 closures, ≤20 PRs), sweep continues descending to #790.
- **Phase 3 — wrap-up**: final campaign report (per-issue disposition table),
  escalation digest for bakert, workspaces archived, state mirror finalized.

Throughput estimate: 699 issues ≈ 140 triage + ~100–200 verify/fix workspaces. At cap
16 and ~15–30 min per workspace, the sweep is multi-day; the constraint will likely be
Max-plan rate limits (Assumption A1/A8), which the circuit breaker handles by pausing.

## 6. Safeguard summary

| Risk | Safeguard |
|---|---|
| Duplicate work | Single dispatcher, exact-number leases, journal, pre-mutation live GitHub check, PR/branch existence check before fixer dispatch |
| Bad closures | Cast-iron classes only; independent verifier; recent-activity guard; per-day closure cap; every pilot closure spot-checked; closure comments cite evidence so humans can audit; `gh issue reopen` is the documented rollback |
| Mixed/unrelated PRs | One issue per fixer workspace; branch naming `sweep/<issue>-<slug>`; dispatcher rejects fixer results touching >1 issue or exceeding line budget |
| Lost state | Event journal + snapshots + off-sandbox mirror + documented full-recovery procedure |
| Agent exits / stalls | Lease expiry + transcript-staleness detection + bounded retries + fresh-workspace retry |
| Rate limits | Circuit breaker: pause spawning with exponential backoff (30 min → 4 h), leases frozen during pause |
| Malformed worker output | Strict fenced-JSON contract; one in-session corrective nudge; one fresh-workspace retry; then escalate |
| Coordinator death | Idempotent restart from journal (see `DISPATCHER_SPEC.md` §9); sandbox-death recovery from mirror |
| Runaway spend | Concurrency cap, per-day mutation caps, total-workspace cap (default 500), Opus-approved phase gates |
| Credential exposure | Dispatcher never echoes env; logs scrub `Authorization|token|key` patterns; worker prompts contain no secrets; state files store ids only |
| Merges | Nothing in the system ever merges; `merge` is absent from every prompt's allowed actions and the dispatcher has no merge code path |

## 7. Assumptions — status as of 2026-08-25

**RESOLVED by bakert (2026-08-25):**

- **A1 — Subscription billing. ✅ CONFIRMED.** Cloud `claude` workers bill to the
  Claude Max subscription, not metered Anthropic API. Cleared to scale (rate-limit
  behavior A8 still needs pilot characterization).
- **A3 — Frontier & `triage` label. ✅ RESOLVED.** `triage` is auto-applied to all
  new issues and removed only when humans hand-label area/type. It does NOT mark
  prior investigation. Frontier stands at #12787: the sweep covers all 699 open
  issues ≤ #12786 down to #790. The sweep never touches the `triage` label.
- **A4 — Mutation authority & tone. ✅ APPROVED.** Closures/comments/PRs go out under
  bakert's gh identity using the templates in `DISPATCHER_SPEC.md` §8.
- **A5 — State mirror. ✅ DECIDED.** Orphan branch `sweep-state` in the repo (never
  PRed, never merged). Configure `mirror: {"kind": "branch", "ref": "sweep-state"}`.

**STILL OPEN — Opus MUST validate before Phase 1 (see OPUS_HANDOFF.md §2):**

- **A2 — Worker git push auth.** Fresh cloud workspaces can `git push` branches to
  origin (Conductor git auth shim). Required by fixers. Validate with a throwaway
  branch push (then delete the branch).
- **A6 — Workspace creation semantics.** `conductor workspace create --project-id …`
  from this sandbox produces a booted *cloud* workspace whose repo is cloned and where
  `uv run --frozen` works. Validate with one throwaway workspace; measure boot time to
  tune lease durations.
- **A7 — Scoped worker API.** Workers' scoped `CONDUCTOR_API_KEY` cannot create
  workspaces or read other sessions (defense in depth; workers are instructed to never
  touch the `conductor` CLI regardless).
- **A8 — Rate-limit behavior.** How Max-plan limits surface (session error state?
  stalled transcript?) and whether multiple Max accounts are pooled by Conductor.
  Characterize during the pilot; tune circuit-breaker signatures.
- **A9 — Manager persistence.** Whether a running background dispatcher process keeps
  the sandbox alive past the idle timeout, and what survives a sandbox restart.
  Determines Opus's keep-alive cadence (`OPUS_HANDOFF.md` §6).

## 8. File map

| File | Purpose |
|---|---|
| `PLAN.md` | This document |
| `OPUS_HANDOFF.md` | Exact instructions for the Opus 5 manager |
| `WORKER_PROMPT.md` | Triage worker contract + structured output |
| `VERIFIER_PROMPT.md` | Independent closure-verification contract |
| `FIXER_PROMPT.md` | One-issue implementation contract |
| `FIXUP_PROMPT.md` | CI remediation contract (follow-up fixer on an existing branch) |
| `STATE_SCHEMA.md` | Durable state: queue, leases, retries, workspaces, evidence, closures, PRs |
| `DISPATCHER_SPEC.md` | Deterministic, restartable, zero-token dispatcher spec |
