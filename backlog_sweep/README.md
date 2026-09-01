# Backlog Sweep

Tooling for running an AI-assisted sweep of this repo's GitHub issue backlog:
triaging old issues with evidence, closing dead ones, and turning small isolated
fixes into draft PRs — at a scale a human wouldn't attempt alone, under controls a
human stays firmly in charge of.

This directory is the reusable machinery plus the design docs from the first
campaign (August 2026). It is plain Python (stdlib only), imports nothing from the
rest of the repo, and nothing in the repo imports it.

## What it did in its first outing (pilot, Aug 2026)

- Read the 40 newest open issues below the previously-triaged frontier (#12787).
- Closed 7 as verifiably already-fixed/obsolete — each with a comment citing the
  fixing commit/PR, each independently re-verified by a second agent prompted to
  refute the claim, and each carrying a "wrongly closed? please reopen" footer.
- Opened ~20 small draft PRs (one issue per PR, ≤150 lines, lint/tests run and
  honestly disclosed), all human-reviewed before merging.
- Deferred every product decision, design call, data-retention change, and
  ambiguous closure to a human digest instead of acting.

## Safety properties (the important part)

- **Nothing merges automatically.** PRs are opened as drafts, which neither GitHub
  nor Mergify will merge. A human reviews and marks ready; Mergify takes it from
  there. The dispatcher verifies `isDraft` after creation and closes the PR if
  that ever fails.
- **Closures are evidence-gated and double-checked.** A triage agent must cite a
  commit/PR/code location; an independent verifier agent re-derives the claim from
  scratch; the dispatcher re-checks for recent human activity before acting; caps
  limit closures per day. "Cannot reproduce" never auto-closes.
- **One issue per PR, structurally.** Each fix runs in its own throwaway
  workspace on its own `sweep/<issue>-*` branch.
- **The coordinator is deterministic.** `dispatcher.py` is a plain state machine —
  no model calls — so leasing, retries, caps, circuit breakers, and audit logging
  are exact and replayable. Agents only ever act inside contracts defined by the
  prompt files here.
- **Everything is auditable.** An append-only journal, plus per-issue evidence
  files, mirrored to the never-merged `sweep-state` branch. Closure comments on
  the issues themselves cite the evidence.

## Layout

| File | Purpose |
|---|---|
| `dispatcher.py` | Deterministic coordinator (queue, leases, workspaces, GitHub writes, CI watch) |
| `test_dispatcher.py` | Unit tests for the pure parts (111 tests, no network/DB) |
| `WORKER_PROMPT.md`, `VERIFIER_PROMPT.md`, `FIXER_PROMPT.md`, `FIXUP_PROMPT.md` | Contracts handed to worker agents |
| `config.example.json` | All tunables, shipped with every gate closed |
| `RUNBOOK.md` | How to run a campaign |
| `docs/` | Design docs from the first campaign (spec, state schema, plan, manager handoff) |

Runtime state lives in `backlog_sweep/state/` (gitignored) and is mirrored to the
`sweep-state` orphan branch. Issues, closures, and PRs all live in GitHub itself —
this directory holds no issue data.

Note: `docs/` reference the original `.context/backlog-sweep/` layout the first
campaign ran from; the code now lives here, with prompts as siblings of
`dispatcher.py` and state under `backlog_sweep/state/`.

## Running it

See `RUNBOOK.md`. Short version: it runs from a Conductor cloud workspace, spawns
small worker agents in throwaway workspaces, and needs a human on the other end
reviewing drafts and answering escalations. Every mutating capability
(`spawning_enabled`, `mutations_enabled`, `closures_enabled`, `prs_enabled`)
ships off in `config.example.json` and must be deliberately switched on.
