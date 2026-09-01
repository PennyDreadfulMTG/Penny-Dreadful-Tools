# Backlog Sweep Runbook

How to run a sweep campaign. The first campaign (Aug 2026) piloted 40 issues; the
remaining backlog (open issues #790–#12786) is queued for a Phase 2 whenever the
owner says go. This runbook is written so a fresh manager agent, or a human, can
start from zero.

## Prerequisites

1. **A Conductor cloud workspace on this repo** — the "manager". The dispatcher
   daemon and campaign state live here. Cloud sandboxes have a ~24 h max
   lifetime, which is why state mirrors off-sandbox (step 4) and why recovery
   (below) exists.
2. **Claude Max subscription auth** for Conductor's cloud `claude` agents
   (workers bill to subscription, not metered API — verify before scaling).
3. **A classic GitHub PAT with `repo` scope.** This is the credential exercised
   end-to-end by the pilot. Conductor's own GitHub token can push branches and
   manage PRs but cannot comment on or close issues; once the PAT is present, the
   dispatcher uses it for all `gh` operations, including PR operations. Put it in
   `backlog_sweep/state/.gh_token` (gitignored; never mirrored). It dies with
   the sandbox; re-paste on recovery.
4. **A manager agent** (Opus-class recommended) in the manager workspace, given
   `docs/OPUS_HANDOFF.md`. Humans talk to the manager; nobody talks to workers.

## Start a campaign

```bash
cd <repo>
python3 backlog_sweep/dispatcher.py --help       # sanity check
cp backlog_sweep/config.example.json backlog_sweep/state/config.json  # after mkdir -p backlog_sweep/state
# edit config: frontier_max/min for this campaign's issue range, pilot_limit, caps
python3 backlog_sweep/dispatcher.py init         # enumerate the queue from GitHub
python3 backlog_sweep/dispatcher.py tick --dry-run   # inspect the plan; journals nothing
```

Then, deliberately and in this order (see `docs/OPUS_HANDOFF.md` for the full
gate discipline):

1. Run one **canary worker** to validate workspace boot, git push auth, and
   output parsing.
2. Create/confirm the **`sweep-state` mirror branch** and set `mirror` in config.
   Do not proceed on local-only state.
3. `config set spawning_enabled=true` — triage begins (read-only, safe).
4. `config set mutations_enabled=true prs_enabled=true closures_enabled=true`
   only with the owner's explicit sign-off, starting with pilot-sized caps
   (`daily_close_cap=15 daily_pr_cap=10 pilot_limit=40`).
5. Start the daemon: `python3 backlog_sweep/dispatcher.py daemon` (backgrounded).
   It ticks every 60 s; it is safe to kill and restart at any time.
6. **Spot-check everything the pilot mutates** before raising any cap.

## Operating rules that are not optional

- PRs are **drafts, always** (Mergify auto-merges non-draft green PRs authored by
  the automerge team — draft is the merge brake). The owner's review action is
  marking ready-for-review.
- The sweep **never merges, never force-pushes, never touches labels**, never
  edits `.github/workflows/`, migrations, or dependency manifests.
- Product decisions, security-sensitive work, migrations, data-retention changes,
  and ambiguous closures **escalate to a human digest** — no exceptions.
- Humans should never chat with `sweep-*` worker windows; anything typed there is
  invisible to the system. Talk to the manager session.

## Monitoring

`state/metrics.json` (rewritten every tick) is the whole dashboard: counts by
status, caps used, pause state, alerts (including unregistered `sweep-*`
workspaces). `dispatcher.py status` prints a one-screen summary.
`state/reports/` holds daily reports and the human digest.

## Recovery (sandbox died, daemon crashed, anything)

1. Fresh workspace on this repo. Restore state: check out `sweep-state` into
   `backlog_sweep/state/` (journal + snapshot + evidence survive; ≤15 min loss).
2. Re-create `state/.gh_token` (step 3 above).
3. `python3 backlog_sweep/dispatcher.py recover` — replays the journal and
   reconciles against live GitHub and live Conductor workspaces (adopts running
   workers, expires dead leases, settles half-executed mutations, skips issues
   humans closed meanwhile).
4. Restart the daemon.

## Ending a campaign

`report daily` one last time; write the campaign report from the journal; archive
all `sweep-*` workspaces (verify they actually archived — the CLI can fail
silently); push a final mirror; revoke the PAT. Fold any new calibration lessons
into the prompt files here via a normal PR.

## Lessons register (hard-won, do not relearn)

- The "do not merge" label does nothing in this repo; drafts are the only brake.
- `updatedAt` is useless as an activity guard (bulk labelling touches everything);
  use non-bot comments.
- Data-retention changes are never easy-fixes (#12781).
- Workers classify off the issue's framing; make them check whether recent
  commits already settled the question before classifying.
- Trust nothing you didn't verify: check `isDraft` after PR creation, check
  workspace state after archiving, fetch before verifying claims against master.
