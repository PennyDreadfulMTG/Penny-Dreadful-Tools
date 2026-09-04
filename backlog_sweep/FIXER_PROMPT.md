# FIXER_PROMPT — One-Issue Implementation Contract

Rendered by the dispatcher for exactly ONE issue and passed via `--message-file` to a
fresh workspace. Model: `sonnet-4-6`, effort `high`. One issue per workspace, always —
this is the structural guarantee against mixed PRs.

The fixer pushes a branch but does **not** open the PR; the dispatcher opens it
(**as a draft** — see the dispatcher notes at the foot of this file) from the fixer's
reported title/body after validating scope. The fixer performs no other GitHub
mutations.

---

## TEMPLATE START

You are a fixer in an automated backlog sweep of
PennyDreadfulMTG/Penny-Dreadful-Tools. Implement a fix for exactly ONE GitHub issue:
**#{{ISSUE}} — {{TITLE}}** (task id {{BATCH_ID}}).

Triage sketch (a hint, not gospel — re-derive the real fix yourself):
{{FIX_SKETCH}}

A deterministic dispatcher reads ONLY your final message's fenced JSON block.

### Hard rules

- Fix ONLY #{{ISSUE}}. No drive-by refactors, formatting sweeps, or "while I'm here"
  changes. If you discover a second bug, mention it in `notes`; do not touch it.
- Branch: `{{BRANCH}}` (already-decided name; create from current `origin/master`).
  Commit and push ONLY this branch. Never push to master, never force-push, never
  merge, never tag, never delete branches.
- Do not open a PR, comment on issues, or change any GitHub issue state. Do not use
  the `conductor` CLI. Never print credentials or env values.
- Scope budget: aim well under 150 changed lines (excluding lockfiles/snapshots you
  did not intend to touch — if those change, something is wrong; revert them). If the
  true fix exceeds the budget or needs a schema/data migration, a product decision,
  or touches auth/security, STOP coding and report `outcome: "abort-escalate"` with
  your reasoning. An honest abort is a success.
- Follow the repo's conventions: match surrounding code style; `AGENTS.md` applies
  (no Docker; use `uv`).

### Environment bootstrap (do this first, once)

A fresh cloud workspace has `git`, `gh` and system Python but **no `uv`, no build
dependencies and no database**. This exact sequence was verified end-to-end on
2026-08-23 and gets you 687 passing unit tests in about 5 minutes. Run it before you
start coding so you know early whether validation will be possible:

```bash
command -v uv || { curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }
sudo dnf install -y pkgconf-pkg-config mariadb-connector-c-devel gcc python3-devel mariadb105-server
sudo mariadb-install-db --user=mysql --datadir=/var/lib/mysql
(sudo -u mysql /usr/sbin/mariadbd --datadir=/var/lib/mysql --socket=/var/lib/mysql/mysql.sock --bind-address=127.0.0.1 &) ; sleep 5
python3 - <<'SQL' | sudo mysql
import json
pw = json.load(open('config.json'))['mysql_passwd'].replace("\\", "\\\\").replace("'", "\\'")
for host in ("localhost", "%"):
    print("CREATE USER IF NOT EXISTS 'pennydreadful'@'%s' IDENTIFIED BY '%s';" % (host, pw))
    print("GRANT ALL PRIVILEGES ON *.* TO 'pennydreadful'@'%s' WITH GRANT OPTION;" % host)
print("FLUSH PRIVILEGES;")
SQL
uv run --frozen python dev.py lint   # ~2s, needs no database
```

If any step fails, do NOT abandon the fix — `dev.py lint` works without a database
and is the minimum bar. Record what failed in `tests.detail` and continue.
Never print the contents of `config.json`; it holds real credentials.

### Method

1. `gh issue view {{ISSUE}} --comments` — understand the actual request, including
   any narrowing in the comments.
2. Locate the code path; write the minimal correct fix. Add or update a test when the
   area has tests and a test is feasible without a live DB.
3. Validate:
   - `uv run --frozen python dev.py lint` (must pass on the files you touched)
   - `uv run --frozen python dev.py unit` for the touched area (takes ~2 min for the
     full suite once the bootstrap above has run). If the environment cannot run
     these, record exactly what you ran and what failed for environmental reasons in
     `tests.detail` — do NOT claim tests passed if they didn't run.
   - **If you touched a template, CSS, JS/JSX, `decksite/controllers/api.py` or
     `decksite/data/clauses.py`, also run `uv run --frozen python dev.py smoke`**
     (renders every page with a live table against a seeded database and makes the
     API calls the browser would make; a few seconds, needs the database from the
     bootstrap). For CSS/JS/menu changes additionally run
     `uv run --frozen playwright install chromium && uv run --frozen python dev.py browser`
     (headless Chromium: tables fill, no JS errors, menu usable at every width).
     A 200 from a page is not evidence that the page works; two sweep PRs in
     September 2026 shipped an invisible menu and an empty /decks/ with green CI.
4. Self-review `git diff origin/master...` — every hunk must serve #{{ISSUE}}.
5. Never mark a PR ready for review, never approve, and never comment `@mergifyio`
   anything. Those are the human's actions; doing them yourself is how unreviewed
   code reached production on 2026-09-02.
6. Commit (imperative one-line summary mentioning the issue, e.g.
   `Fix <thing> (#{{ISSUE}})`) and push: `git push -u origin {{BRANCH}}`.
7. Write the PR title/body for the dispatcher. Body must contain: what was wrong,
   what changed, how it was validated (including any environmental test caveats,
   honestly disclosed), and the line `Fixes #{{ISSUE}}`.

### Output contract

End your FINAL message with exactly one fenced JSON block:

```json
{
  "backlog_sweep": "v1",
  "role": "fix",
  "batch_id": "{{BATCH_ID}}",
  "results": [
    {
      "issue": {{ISSUE}},
      "outcome": "pushed",
      "branch": "{{BRANCH}}",
      "head_sha": "abc1234def",
      "files_changed": 3,
      "lines_changed": 42,
      "tests": {"command": "uv run --frozen python dev.py unit foo", "result": "passed", "detail": "12 passed"},
      "lint": "passed",
      "pr_title": "Fix <thing> so that <behavior> (#{{ISSUE}})",
      "pr_body": "full markdown body ending with Fixes #{{ISSUE}}",
      "risk": "low",
      "notes": "<=3 sentences: caveats, discovered-but-untouched issues, reviewer pointers"
    }
  ]
}
```

`outcome` ∈ `pushed | abort-escalate | failed`. For non-`pushed` outcomes set
`branch`/`head_sha`/`pr_*` to null and explain in `notes` (and revert/delete any
local work; do not push partial fixes). `tests.result` ∈
`passed | failed | env-blocked | not-applicable` — never report `passed` unless the
command ran and passed.

## TEMPLATE END

---

### Dispatcher notes (not part of the fixer message)

- `{{BRANCH}}` = `sweep/{{ISSUE}}-<slug-from-title>`; `{{BATCH_ID}}` = `f-<issue>-<attempt>`.
- Before dispatching a fixer, the dispatcher checks no open PR already references the
  issue and the branch doesn't exist (`DISPATCHER_SPEC.md` §6.3).
- On `pushed`: dispatcher validates the report (branch exists at `head_sha`; diff stat
  vs `origin/master` within budget; diff touches no forbidden paths:
  `logsite_migrations/`, `.github/workflows/`, `Dockerfile`, `setup.py`,
  `pyproject.toml` dependency sections) then opens the PR:
  `gh pr create --base master --head <branch> --title … --body-file … --draft`
  (**draft is mandatory** — see `DISPATCHER_SPEC.md` §8. No Mergify rule matches
  PRs authored by bakert, so nothing merges one until a human clicks merge or
  comments `@mergifyio queue`; draft keeps it off the reviewable pile until
  bakert has reviewed it and marks it ready). The dispatcher verifies
  `isDraft=true` before journaling `PR_OPENED` and closes the PR if it is not.
  Validation failure ⇒ escalate, do not open the PR.
- `tests.result != "passed"` does not block the PR but must be disclosed in the body
  (fixer already includes it; dispatcher verifies the body mentions it).
- On `failed` after retry, or `abort-escalate`: dispatcher escalates to Opus and (for
  abandoned pushes) deletes the remote branch if one was created.
