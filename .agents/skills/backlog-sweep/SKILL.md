---
name: backlog-sweep
description: Orchestrate the Penny Dreadful GitHub backlog sweep by verifying stale candidates, closing proven completed or obsolete issues, and implementing narrowly scoped fixes. Use when asked to start, resume, or continue backlog cleanup.
---

# Backlog Sweep

Read [references/state.md](references/state.md) before selecting work. Treat it
as a dated handoff, not as proof that an issue is currently resolved.

## Work as the master

- Work from `origin/master` and read the repository `AGENTS.md` first.
- Delegate bounded, independent issue investigations when parallel work is
  useful. Keep GitHub mutations and final judgments in the master workspace.
- Use `origin/sweep-state` as an evidence index. Its snapshot, reports, journal,
  and classifications can be stale and are never sufficient grounds to close
  an issue.
- Prefer genuinely low-effort completed, obsolete, or narrowly fixable open
  issues. Avoid turning the sweep into speculative redesign work.

## Verify before acting

For each candidate, read the original issue and later discussion, trace the
current end-to-end behavior, inspect relevant code and tests, and check for
later regressions. For behavior owned by another repository, inspect that
repository rather than inferring from this one.

Classify the result as one of:

- verified complete;
- obsolete, with a concrete reason;
- narrow fix worth implementing now;
- still open or insufficiently proven.

Do not close an issue because a related component exists, a workaround exists,
or an old sweep classification says it is complete.

## GitHub access

Before relying on Cloud GitHub writes, verify them with a reversible operation
that is already part of the selected issue workflow. Do not change live issue
state solely as an authentication test. Never print credentials.

If Cloud writes return `Resource not accessible by integration`, use
Conductor's `RunLocalCommand` with the Mac's working `gh` authentication for
comments, closures, PR creation, and Mergify queueing. Continue read-only
investigation in Cloud.

For a verified closure, leave a concise evidence-based comment explaining the
current behavior and why closure is appropriate, then close the issue. For a
narrow code fix, test it proportionally, open a PR against `master`, and follow
the repository's merge instructions.

## Maintain the handoff

Before ending a substantial sweep, update `references/state.md` with the date,
new durable conclusions, merged fixes, unresolved regressions, and promising
next candidates. Remove conclusions that have become stale or were disproved.
