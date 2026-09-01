# Human digest

## Settled by bakert 2026-08-23 — digest cleared

- **#12710 — regex/brotli vs automating the fonts task.** CLOSED as completed.
  Resolved by events: the fix-12870 series put a font rebuild in the production deploy
  path, so the deps are genuinely needed. Re-verified against freshly fetched
  origin/master before closing.
- **#12670 — menu z-index stacking context.** Queued as a fix, with his constraint:
  restructure properly ONLY if low risk; the fixer must abort rather than force it, and
  must not fall back to merely documenting the levels. Held: will not dispatch until the
  Phase 2 go. Constraint stored at `evidence/12670.json#triage[1]` so it reaches the
  fixer prompt verbatim.
- **#12669 / #12671 / #12758.** Punted; out of scope for this campaign. They stay
  `deferred_human`, appear as report-only in the final report, get no GitHub action, and
  are not re-triaged.

Nothing is awaiting a decision from bakert.

## Noted, not actioned

- The deploy-time rebuild regenerates the symbols font but does not edit `pd.css`; the
  CSS half of #12710's 'fully automated' aside is still manual. The closing comment does
  not claim otherwise, so the closure stands. Raise a fresh issue if that matters.

## Awaiting bakert

- Phase 2 go, and which shape: everything, or triage + closures only (no new fix
  dispatches) to keep his review load flat.
- Whether to keep CI-repair fixers alive during the hold for PRs he is already reviewing.

- #12524 — Choose whether /seasons/all/decks should be optimized, redirected, or retired; the issue does not specify the desired product outcome. (2026-09-01T18:14:21Z)

- #12548 — Needs reproduction in Safari and the original screenshot before changing shared footer CSS. (2026-09-01T18:14:21Z)

- #12550 — Deck search is a feature-sized product decision: public access, search UI, supported filters, and query semantics need definition. (2026-09-01T18:14:21Z)

- #12552 — Confirm whether the existing guild emoji setup is insufficient and choose the Discord emoji deployment approach before implementation. (2026-09-01T18:14:22Z)

- #12559 — Needs narrow-viewport visual reproduction before removing a shadow; static CSS identifies candidates but not the intended element. (2026-09-01T18:14:22Z)

- #12568 — Specify which metagame signal belongs on the home page and how it should be presented. (2026-09-01T18:14:22Z)

- #12569 — Choose the metagame visualization: normalize relative to the leader or redesign the tile; both satisfy the stated goal differently. (2026-09-01T18:14:22Z)

- #12587 — Choose the card-query boundary for decksite before replacing the local is_uninteresting heuristic. (2026-09-01T18:14:22Z)

- #12588 — Define the low-sample threshold and desired empty-state or tile behavior before implementation. (2026-09-01T18:14:22Z)

- #12345 — Choose the post-rotation UX: auto-hide /rotation, redirect to /rotation/changes, or redesign the messaging. (2026-09-01T18:55:53Z)

- #12347 — Choose how low-confidence archetype guesses should appear: suppress, hold for moderation, or use a hybrid threshold. (2026-09-01T18:55:53Z)

- #12348 — Requires a schema-backed offensive-name record and an admin or user moderation workflow; migration and scope need approval. (2026-09-01T18:55:53Z)

- #12349 — Maintainers disagree on substring filtering versus accepting the Scunthorpe tradeoff; record an explicit policy or close as wontfix. (2026-09-01T18:55:54Z)

- #12380 — Provide the intended tournament-policy wording for game losses and sideboarding before changing templates. (2026-09-01T18:55:54Z)

- #12425 — Door-prize eligibility is selected in the separate PDBot project; route the fix there before settling this issue. (2026-09-01T18:55:54Z)

- #12461 — Choose between a card-requirement feature for archetypes and a one-time admin reclassification of affected decks. (2026-09-01T18:55:54Z)

- #12490 — Choose the loader API shape and list-versus-Sequence policy before a cross-cutting refactor. (2026-09-01T18:55:54Z)

- #12293 — Choose the achievements ordering: alphabetical, rarity, category, or curated order. (2026-09-01T18:58:28Z)

- #12294 — The title alone does not identify whether this is a DB snapshot, deployment sequencing, or playability-regeneration problem; provide reproduction/context. (2026-09-01T18:58:28Z)

- #12298 — Choose and approve the external ranking source and fallback semantics for newly legal cards. (2026-09-01T18:58:28Z)

- #12302 — Define companion and wish-target weights relative to ordinary sideboard cards before changing the playability algorithm. (2026-09-01T18:58:28Z)

- #12310 — Define the card-page concept: most plays, most wins, or an expert threshold and display. (2026-09-01T18:58:28Z)

- #12352 — Dropping season.number requires an approved production schema migration despite the code change being small. (2026-09-01T18:58:28Z)

- #12353 — Choose whether to special-case new-card ranks, move the experience to /rotation/changes, or hide /rotation outside its window. (2026-09-01T18:58:29Z)

- #12356 — Needs EXPLAIN and timings against production-scale data before proposing indexes; all obvious join indexes already exist. (2026-09-01T18:58:29Z)

- #12485 — After two malformed fixer attempts, choose the public API contract: add a season-specific path or omit season from decks_url. (2026-09-01T18:58:29Z)

- #12491 — After two malformed fixer attempts, choose the post-rotation navigation policy instead of guessing an arbitrary seven-day menu window. (2026-09-01T18:58:29Z)

- #11246 — Choose how the banner should measure season-relative playability (ratio, difference, or another baseline), including cards with no historical data. (2026-09-01T21:04:25Z)

- #11577 — Confirm whether deck 216544 still has the bad sideboard data, then authorize the existing Gatherling substitution maintenance path against the live database. (2026-09-01T21:04:25Z)

- #11578 — Inspect competition 4330 in the live database and choose between a one-off finalist correction and adding a defensive warning for incomplete Gatherling finalist data. (2026-09-01T21:04:25Z)

- #11614 — Settle the bug-policy wording: whether an unavoidable known game-breaking trigger always penalizes the card owner, and how the avoidable exception should be stated. (2026-09-01T21:04:26Z)

- #11656 — The door-prize selector is in the separate PDBot service; identify its source/access and confirm how post-round drops should affect eligibility. (2026-09-01T21:04:26Z)

- #11721 — Friendly Discord error messages are implemented; decide whether automatic GitHub ticket creation is still desired or whether the issue should close without that potentially noisy behavior. (2026-09-01T21:04:26Z)

- #11744 — Inspect the two live deck records/import sources and decide whether 75-card mains are evidence of a parser error; Magic itself does not impose a 60-card maximum. (2026-09-01T21:04:26Z)

- #11827 — Retrieve the raw source decklist for deck 233082/232812 from the live database so the missing-basics and sideboard parsing failure can be reproduced. (2026-09-01T21:04:26Z)

- #11858 — Confirm whether the single-faced Everflowing Well image is Deckbox's external mouseover or our own rendering, then choose whether to accept it or change tooltip handling/provider. (2026-09-01T21:04:26Z)

- #11940 — Choose how long and how prominently Kick Off/PD500 results stay on the homepage: winner banner, all Top 8 decks, or another treatment. (2026-09-01T21:04:26Z)

- #11951 — The bot-side playtest-card collision is fixed; decide whether to contact Deckbox about its Red Herring mouseover or replace/augment the external tooltip. (2026-09-01T21:04:27Z)

- #11980 — Choose a sideboard-aware interestingness rule for rotation changes, especially companion-heavy cards such as Yorion. (2026-09-01T21:04:27Z)

- #12115 — Reproduce the intermittent stale-CSS load with affected browser/CDN details or server logs so query-string caching, service worker, and proxy causes can be distinguished. (2026-09-01T21:04:27Z)

- #12133 — Tournament announcement player counts are generated by the separate PDBot service; identify its source/access and define whether late joiners count at announcement time or tournament start. (2026-09-01T21:04:27Z)

- #12140 — Choose the deck-name rule that distinguishes separator hyphens from legitimate compound-name hyphens before changing sanitization. (2026-09-01T21:04:27Z)

- #12206 — Recheck Anduril legality/name handling in the live PDBot service and identify that service's source; static code here cannot distinguish stale data from Unicode/DFC handling. (2026-09-01T21:04:27Z)

- #12207 — Inspect deck 239489 and the legality/color data present when it was normalized to decide whether this is a one-off stale-data problem or a sanitizer defect. (2026-09-01T21:04:28Z)

- #12223 — Choose the intended PD rotation time of day and timezone before changing the rotation offset/date interpretation. (2026-09-01T21:04:28Z)

- #12247 — Provide the authoritative retired Tournament Organizer list and decide whether the achievement remains hardcoded or becomes season-aware data. (2026-09-01T21:04:28Z)

- #12272 — Run one live MySQL overflow-warning test with the deployed mysqlclient/server combination before closing, or choose to add an explicit warning-count check. (2026-09-01T21:04:28Z)

- #12273 — Audit production for negative values and choose the table/column scope before introducing broad UNSIGNED schema migrations. (2026-09-01T21:04:28Z)

- #12279 — Choose which rotation sort/filter controls should be first-class UI and whether administrators need different defaults from public users. (2026-09-01T21:04:28Z)
