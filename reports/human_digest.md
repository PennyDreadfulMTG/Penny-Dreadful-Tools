# Human digest

## Settled by bakert 2026-08-23

- **#12670 — menu z-index stacking context.** Queued as a fix, with his constraint:
  restructure properly ONLY if low risk; the fixer must abort rather than force it, and
  must not fall back to merely documenting the levels. Held: will not dispatch until the
  Phase 2 go. Constraint is stored at `evidence/12670.json#triage[1]` so it reaches the
  fixer prompt verbatim.
- **#12669 — `<span>` in `<ol>` / `<label>` wrapping `<ol>`.** Punted; out of scope.
- **#12671 — needs a site colour scheme first.** Punted; out of scope.
- **#12758 — multilingual font in the language switcher.** Punted; out of scope.

Punted items stay `deferred_human`, appear as report-only in the final campaign report,
get no GitHub action, and are not re-triaged.

## Still open

- **#12710 — regex/brotli deps vs automating the fonts task.** bakert is checking whether
  a post-deploy fonts run already exists in server-side deploy infrastructure outside this
  repo. Not settled; do not report as decided.

## Awaiting bakert

- Phase 2 go, and which shape: everything, or triage + closures only (no new fix
  dispatches) to keep his review load flat.
- Whether to keep CI-repair fixers alive during the hold for PRs he is already reviewing.
