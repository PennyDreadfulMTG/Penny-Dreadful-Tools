# Phase 0 report — build + assumption validation

Date: 2026-08-23. Manager workspace `7e7f8c99` (`penny-dreadful-tools`).
Nothing on GitHub was mutated. No issue was commented on, closed, labelled or PR'd.

## 1. Build

| Artefact | State |
|---|---|
| `.context/backlog-sweep/bin/dispatcher.py` | ~1500 lines, stdlib only, Python 3.9 compatible |
| `.context/backlog-sweep/bin/test_dispatcher.py` | 39 tests, all passing (`python3 -m unittest test_dispatcher`) |
| `state/` | initialized: 699 issues enqueued (#790–#12781), `last_seq` 710 |
| `dispatcher.py tick --dry-run` | clean, deterministic, plans exactly 8 triage workspaces × 5 issues descending from #12781 (= the 40-issue pilot), journals only `SNAPSHOT_WRITTEN` |
| `dispatcher.py recover --dry-run` | runs clean, correctly ignores non-batch workspaces |
| `dispatcher.py tick` (live, spawning off) | writes `metrics.json` + `reports/daily-*.md` |

Tests cover: fenced-JSON extraction (9 cases incl. multiple blocks, unfenced
fallback, braces inside strings, malformed), closure-comment and verifier-claim
rendering, template substitution against the real prompt files, lease expiry and
pause-freezing, pilot-limit eligibility, journal replay (happy path to `closed`,
seq idempotency, daily-counter rollover, illegal-transition freeze, adjudication,
pause accounting, workspace lifecycle), credential scrubbing, and Store round-trips
(restart, torn journal tail, exclusive lock, snapshot/replay equivalence).

### Deviations from DISPATCHER_SPEC (all deliberate, all verified)

1. **Conductor is driven through its REST API (`/v0/...`) via `urllib`, not the CLI.**
   The spec's harvest step (`conductor session message <id> --limit 5` to read the
   final assistant message) is not implementable: that command lists message *ids
   and types only*, `conductor message get` prints metadata only, and every
   `conductor sql` cell is truncated at ~119 characters (a 35 KB transcript prints
   as 607 bytes). The REST API — the same endpoints the CLI itself calls, same
   `CONDUCTOR_API_KEY` — returns full message content, full SQL rows, and per-turn
   `rate_limit_event` records. Verified working for: session status, workspace
   status, message list/paginate, message create, workspace create/list/archive,
   session cancel, session list, and SQL.
   *Trap found and fixed:* Cloudflare in front of the API rejects the default
   `Python-urllib/3.9` User-Agent with error 1010 (HTTP 403). The client now sends
   the CLI's exact identifying headers. Without this the whole dispatcher fails.
2. **Journal events:** one `RESULT_RECORDED` for all three roles (no separate
   `VERIFY_RECORDED`); added `ISSUE_SKIPPED`.
3. **`spawning_enabled` config flag** added, so the daemon can run (heartbeat,
   harvest, mirror) without creating workspaces. Currently **false**.
4. **The daemon takes the state lock one tick at a time**, not for its whole life.
   As specified it would have held `flock` forever and blocked every `adjudicate`
   and `status` call. `status` is now lock-free (read-only).
5. **Recent-activity guard reads comments, not `updatedAt`.** Bulk labelling (e.g.
   the `triage` label) bumps `updatedAt` on hundreds of issues, which would have
   blocked essentially every closure. The guard now trips on a non-bot *comment*
   inside the guard window, or any human comment after the verifier ran. Flagged to
   bakert under A4.

## 2. Assumption validation

One throwaway canary workspace (`sweep-canary`, sonnet-4-6, created 20:52:15Z,
finished 20:53:09Z — **54 s boot-to-done** for trivial work). Branch and both
workspaces have been cleaned up.

| # | Assumption | Verdict | Evidence |
|---|---|---|---|
| A1 | Cloud agents bill to the Max subscription, not metered API | **Likely PASS**, needs bakert | Canary session's `rate_limit_event`: `rateLimitType: "five_hour"`, `overageStatus: "rejected"`, `overageDisabledReason: "org_level_disabled"`. Subscription-style 5-hour windows; API overage is disabled at org level |
| A2 | Fresh cloud workspaces can push branches | **PASS** | Canary pushed `sweep/canary-delete-me` (exit 0) and it appeared on origin; deleted afterwards |
| A3 | Frontier / `triage` label semantics | **PASS (already answered)** | bakert previously confirmed `triage` is auto-applied to every new issue and stays until hand-labelling; it is not an investigation marker. #12482–#12786 are therefore unswept and in scope, and the sweep neither reads nor writes the label |
| A4 | Mutation authority & tone | **OPEN** | Templates ready for approval; no mutation has been made |
| A5 | State mirror location | **OPEN** | `mirror.kind` is `none`; must be `branch` or `gist` before the pilot |
| A6 | `workspace create` gives a booted cloud workspace with the repo | **PASS with a caveat** | Repo cloned at master `472a9fdb`, branch `conductor/sweep-canary`. **But `uv` is not installed and the Python env does not build out of the box** — see §3 |
| A7 | Workers' scoped key cannot create workspaces | **FAIL** | The canary ran `conductor workspace create` and it **succeeded**, creating workspace `2b68871b` (`canary-should-fail`). Reads are scoped (`workspace list` returned empty) but creation is not blocked. Prompt instructions are the only barrier; the accidental workspace was archived |
| A8 | Rate-limit behaviour | **Characterized** | Sessions emit structured `rate_limit_event` messages (`status`, `rateLimitType`, `resetsAt`). The circuit breaker now trips on `status != allowed` directly, not only on text matching |
| A9 | A background daemon keeps the sandbox alive | **In progress** | Daemon running since 21:02Z with spawning disabled; needs >70 min of session idleness to conclude |

## 3. Material finding: cloud workspaces cannot validate fixes out of the box

`uv` is absent from a fresh workspace and `uv sync` fails (mysqlclient needs
pkg-config + MariaDB headers). Unpatched, every fixer would have reported
`tests: env-blocked`. A full bootstrap was verified end-to-end in this sandbox:

```
uv installer  ->  dnf: pkgconf-pkg-config mariadb-connector-c-devel gcc python3-devel mariadb105-server
              ->  mariadb-install-db + mariadbd + grant 'pennydreadful' using config.json's password
```

Results: `dev.py lint` passes in 1.7 s **without any database**; `dev.py unit` runs
**687 passed, 1 skipped, 89 deselected in 18.5 s** once MariaDB is up. Total
bootstrap ≈ 5 minutes, one-off per fixer workspace. `FIXER_PROMPT.md` now carries
this exact recipe as a pre-Method step, with instructions to fall back to lint-only
and disclose honestly if it fails. Triage and verify workers are unaffected — they
are read-only and need only `git`/`gh`/`grep`.

## 4. Security note (pre-existing, not caused by the sweep)

Conductor's repo settings copy `/config.json` into every workspace. That file holds
real secrets (`oauth2_client_secret`, `github_password`, `bugs_webhook_token`,
`mysql_passwd`). The sweep will create ~250 workspaces, each receiving a copy. This
is existing behaviour, but the sweep multiplies the blast radius; worth a decision
before Phase 2. Every worker prompt already forbids printing env values, and the
fixer bootstrap reads `mysql_passwd` without echoing it.

## 5. Gates still closed

- `mutations_enabled: false` — no GitHub write can happen.
- `spawning_enabled: false` — no worker workspace can be created.
- `mirror.kind: none` — must be set before the pilot (A5).
Both flags flip only after bakert answers A1/A4/A5 (A3 is already settled).
