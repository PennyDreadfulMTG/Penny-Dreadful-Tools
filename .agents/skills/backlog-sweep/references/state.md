# Backlog sweep handoff

Last updated: 2026-09-09.

## Evidence source

`origin/sweep-state` contains a snapshot, reports, a journal, and supporting
evidence. Its 2026-09-06 snapshot produced false positives. Recheck the
original request, current behavior, and later regressions before acting on any
classification.

## Must remain open

- #6976: admin retirement was implemented but regressed in #14052; admins now
  see only unassociated runs.
- #7164: the request likely concerns guesses at or above 90% archetype
  similarity. Existing rule-based preselection is not equivalent.
- #7524: a permission-change workaround exists, but the requested DB-backed
  session design and admin UI do not.
- #11685: correct storage and handling of multiword subtypes such as `Time Lord`
  has not been proven.
- #15273: show whether a searched card was actually played in each matchup
  result.

## Verified outcomes

- #6651 was closed as obsolete rather than literally implemented.
- #7133, #7496, #7716, #7828, #8056, #8285, #8627, #8727, #11193,
  #11220, #11223, and #11229 were verified, commented on, and closed.
- #8727 was verified in `PennyDreadfulMTG/PDBot`; `TestWeirdCards.cs`
  explicitly tests both Erayo's Essence spellings.
- #5039, #7738, #11291, #11721, #12244, and #12421 were reviewed but were
  not safe to close.
- #11747, #11307, and #12463 may merit fuller investigation.

## Merged fixes

- PR #15275, `Use GeoNames for local time lookups`, was corrected after review
  and merged.
- Issue #7206 was fixed by PR #15287, `Fix display time rounding across unit
  boundaries`, merged on 2026-09-08.

## GitHub authentication

As of 2026-09-09, Conductor Cloud GitHub mutations returned
`Resource not accessible by integration` for both an approved fine-grained PAT
and the exact classic `repo`-scoped PAT that succeeded from the Mac. The Cloud
secret value and token type were verified by hashes without printing them.
PennyDreadfulMTG is on the Free plan and has no organization IP allow-list
control. Use `RunLocalCommand` for GitHub mutations unless a fresh Cloud test
demonstrates that the restriction is gone. Do not repeat token rotations or
Cloud Computer rebuilds without new evidence.
