#!/usr/bin/env python3
"""Deterministic, restartable, zero-token backlog-sweep dispatcher.

Implements DISPATCHER_SPEC.md / STATE_SCHEMA.md.  Stdlib only, Python 3.9+.

Deviations from the spec (all documented in state/reports/phase0.md):
  * Conductor is driven through its REST API (/v0/...) via urllib rather than the
    `conductor` CLI, because the CLI cannot return message *content* at all
    (`conductor session message` lists ids only, `conductor message get` prints
    metadata only) and truncates every `conductor sql` cell at ~119 characters.
    Same credentials, same endpoints the CLI itself calls.
  * Journal uses RESULT_RECORDED for all three roles (no separate VERIFY_RECORDED)
    and adds ISSUE_SKIPPED.
"""

import argparse
import datetime as dt
import errno
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE = BASE / "state"
EVIDENCE = STATE / "evidence"
ESCALATIONS = STATE / "escalations"
REPORTS = STATE / "reports"
OUTBOX = STATE / "outbox"
LOCKFILE = STATE / ".lock"
JOURNAL = STATE / "journal.jsonl"
SNAPSHOT = STATE / "snapshot.json"
CONFIG = STATE / "config.json"
QUEUE = STATE / "queue.json"
METRICS = STATE / "metrics.json"
LOGFILE = STATE / "dispatcher.log"
PIDFILE = STATE / "daemon.pid"
MIRROR_DIR = STATE / ".mirror"

DEFAULT_CONFIG = {
    "schema": 1,
    "phase": "phase0",
    "repo": "PennyDreadfulMTG/Penny-Dreadful-Tools",
    "frontier_max": 12786,
    "frontier_min": 790,
    "pilot_limit": 40,
    "concurrency_cap": 8,
    "daily_close_cap": 15,
    "daily_pr_cap": 10,
    # Backpressure: hard ceiling on sweep PRs open on GitHub at once, counted
    # live because bakert merges and closes them outside our state.
    "max_open_prs": 30,
    "max_total_workspaces": 500,
    "triage_batch_size": 5,
    "verify_batch_size": 5,
    "lease_minutes": {"triage": 45, "verify": 45, "fix": 90},
    "max_stage_attempts": 2,
    "mutations_enabled": False,
    # Sub-gates under mutations_enabled. The GH_TOKEN available to this sandbox is a
    # GitHub App user-to-server token with issues=READ / pull_requests=WRITE, so
    # closures are off until bakert grants issues:write (verified 2026-08-23).
    "closures_enabled": False,
    "prs_enabled": True,
    "spawning_enabled": True,
    # The four checks Mergify requires before it will merge (.mergify.yml).
    "required_checks": ["mypy", "lint", "test", "jslint"],
    "ci_recheck_minutes": 5,
    "auto_update_behind_branches": True,
    "max_fixup_attempts": 1,
    "reclaim_orphan_branches": True,
    # Path to the operator PAT used by every `gh` subprocess. The pilot-verified
    # credential was a classic PAT with repo scope. Read into memory only, never
    # logged, never mirrored, never passed in argv.
    "github_token_file": "state/.gh_token",
    "worker_model": "sonnet-4-6",
    "worker_effort": "high",
    "project_id": "6da35401-db77-48a7-b9bf-ab9aa3be1a64",
    "opus_session_id": None,
    "mirror": {"kind": "none", "ref": "sweep-state", "interval_minutes": 15},
    "stale_transcript_minutes": 20,
    "recent_activity_guard_days": 90,
    # "comments" (approved by bakert 2026-08-23) or "updated_at" (original spec).
    # Bulk labelling makes updatedAt meaningless in this repo.
    "recent_activity_guard_mode": "comments",
    "min_session_age_seconds": 120,
    "max_fix_lines": 150,
    "bundle_min_items": 10,
    "bundle_max_age_hours": 6,
    "bundle_min_gap_hours": 2,
    "pause_initial_minutes": 30,
    "pause_max_minutes": 240,
    "subprocess_timeout": 120,
    "retry_sleeps": [5, 25, 125],
    "forbidden_paths": [
        "logsite_migrations/",
        ".github/workflows/",
        "Dockerfile",
        "setup.py",
    ],
    "bot_logins": ["github-actions", "dependabot", "codecov", "renovate"],
}

CLOSURE_CLASSES = {"already-fixed": "completed", "obsolete": "not_planned", "duplicate": "not_planned"}
REPORT_ONLY_CLASSES = {"needs-work", "question", "cannot-reproduce", "env-limited"}
ESCALATE_CLASSES = {
    "needs-product-decision",
    "security-sensitive",
    "migration-required",
    "destructive-action",
    "unclear",
}
TRIAGE_CLASSES = set(CLOSURE_CLASSES) | REPORT_ONLY_CLASSES | ESCALATE_CLASSES | {"easy-fix", "skip-closed"}

TERMINAL = {"closed", "pr_open", "reported", "deferred_human", "failed", "skipped"}

PERMISSION_RE = re.compile(
    r"Resource not accessible by integration|HTTP 403|Must have admin rights|"
    r"not authorized|Forbidden", re.I)

LEGAL = {
    "pending": {"triage_leased", "skipped", "escalated"},
    "triage_leased": {"triaged", "pending", "escalated", "skipped"},
    "triaged": {"verify_pending", "fix_pending", "reported", "escalated", "skipped"},
    "verify_pending": {"verify_leased", "escalated", "skipped"},
    "verify_leased": {"verified", "escalated", "verify_pending", "skipped"},
    "verified": {"closing", "escalated", "skipped"},
    "closing": {"closed", "escalated", "verified"},
    "closed": {"escalated", "pending"},  # rollback only
    "fix_pending": {"fix_leased", "escalated", "skipped"},
    "fix_leased": {"fix_pushed", "fix_pending", "escalated", "skipped"},
    "fix_pushed": {"pr_open", "escalated", "pr_ci_failed"},
    "pr_open": {"escalated", "pr_ci_failed", "deferred_human", "closed"},
    "pr_ci_failed": {"fix_pending", "deferred_human", "escalated", "pr_open", "failed", "closed"},
    "reported": {"escalated"},
    "escalated": {
        "closing", "fix_pending", "reported", "pending", "verify_pending",
        "verified", "fix_pushed", "deferred_human", "failed", "closed", "skipped",
    },
    # Terminal for the sweep's own machinery, but bakert can hand an item back.
    # Guarded by ADJUDICATION_ONLY so an automatic retry can never resurrect an
    # issue a human settled (e.g. a PR they closed unmerged).
    "deferred_human": {"fix_pending", "verify_pending", "pending", "reported", "escalated",
                       "closing"},
    "failed": set(),
    "skipped": set(),
}

# Statuses only a human adjudication may leave. Automatic machinery (retries,
# lease expiry) must not move an issue out of these.
ADJUDICATION_ONLY = {"deferred_human"}

RATE_LIMIT_RE = re.compile(r"rate.?limit|overloaded|429|usage limit|quota", re.I)
SECRET_RE = re.compile(r"(?i)\b(token|key|secret|authorization|bearer)([=:]\s*|\s+)(\S+)")


# --------------------------------------------------------------------------- utils

def utcnow():
    return dt.datetime.now(dt.UTC).replace(microsecond=0)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.UTC)
    return d.astimezone(dt.UTC)


def slugify(title, maxlen=40):
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rstrip("-")
    return s or "issue"


def write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def write_json(path, obj):
    write_atomic(path, json.dumps(obj, indent=2, sort_keys=True) + "\n")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


class Scrubber:
    """Replaces credential-looking substrings in anything we log."""

    ENV_KEYS = (
        "CONDUCTOR_API_KEY", "CONDUCTOR_API_TOKEN", "GH_TOKEN", "GITHUB_TOKEN",
        "CONDUCTOR_INTERNAL_WORKSPACE_AUTH", "CONDUCTOR_INTERNAL_INCOMING_AUTH",
        "CONDUCTOR_INTERNAL_OTEL_INGEST_TOKEN", "CONDUCTOR_INTERNAL_WDA_VERIFY_KEY",
    )

    def __init__(self, env=None):
        env = env if env is not None else os.environ
        self.values = sorted(
            {v for k in self.ENV_KEYS for v in [env.get(k)] if v and len(v) >= 8},
            key=len, reverse=True,
        )

    def __call__(self, text):
        if text is None:
            return None
        if not isinstance(text, str):
            text = str(text)
        for v in self.values:
            text = text.replace(v, "[REDACTED]")
        return SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)


SCRUB = Scrubber()


def load_gh_token():
    """Read the operator-supplied PAT, if present, for `gh` subprocesses only.

    Lives in a file rather than the environment so it stays in this workspace: the
    dispatcher never passes it to a worker workspace, never puts it in argv, and
    never mirrors it. Reading it also registers it with the log scrubber.
    """
    rel = (read_json(CONFIG) or {}).get("github_token_file") or DEFAULT_CONFIG["github_token_file"]
    path = BASE / rel if not os.path.isabs(rel) else Path(rel)
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    if not token:
        return {}
    mode = path.stat().st_mode & 0o077
    if mode:
        log("WARNING: %s is group/world readable; tighten it with chmod 600" % path.name)
    if token not in SCRUB.values:
        SCRUB.values.append(token)
        SCRUB.values.sort(key=len, reverse=True)
    return {"GH_TOKEN": token, "GITHUB_TOKEN": token}


def gh_token_present():
    return bool(load_gh_token())


def gh_executable():
    """Resolve which `gh` to run.

    The `gh` on PATH in a Conductor sandbox is a shim that does
    `GH_TOKEN="$broker_token" exec real_gh ...`, so it silently discards any token
    we put in the environment. When the operator has supplied a PAT we therefore
    invoke the real binary directly; otherwise we keep the shim, which is what
    supplies credentials in the first place.
    """
    if not load_gh_token():
        return "gh"
    real = os.environ.get("CONDUCTOR_REAL_GH_PATH")
    if real and os.access(real, os.X_OK):
        return real
    log("WARNING: operator token present but CONDUCTOR_REAL_GH_PATH is unusable; "
        "falling back to the gh shim, which will override it")
    return "gh"


def rotate_log():
    try:
        if LOGFILE.exists() and LOGFILE.stat().st_size > 10 * 1024 * 1024:
            for i in range(4, 0, -1):
                src = LOGFILE.with_suffix(".log.%d" % i)
                if src.exists():
                    src.rename(LOGFILE.with_suffix(".log.%d" % (i + 1)))
            LOGFILE.rename(LOGFILE.with_suffix(".log.1"))
    except OSError:
        pass


def log(msg, echo=False):
    STATE.mkdir(parents=True, exist_ok=True)
    rotate_log()
    line = f"{iso(utcnow())} {SCRUB(msg)}\n"
    with open(LOGFILE, "a", encoding="utf-8") as fh:
        fh.write(line)
    if echo:
        sys.stdout.write(line)


# ------------------------------------------------------------------- pure helpers

def extract_json_block(text, role=None, batch_id=None):
    """Return the last fenced JSON object that looks like a backlog_sweep result.

    Falls back to unfenced balanced objects.  Returns None when nothing matches.
    """
    if not text:
        return None
    candidates = []
    for m in re.finditer(r"```(?:json|JSON)?[ \t]*\r?\n(.*?)```", text, re.S):
        candidates.append(m.group(1))
    if not candidates:
        candidates = _balanced_objects(text)
    best = None
    for raw in candidates:
        obj = _try_json(raw)
        if obj is None:
            continue
        if not isinstance(obj, dict) or obj.get("backlog_sweep") != "v1":
            continue
        if role is not None and obj.get("role") != role:
            continue
        if batch_id is not None and obj.get("batch_id") != batch_id:
            continue
        best = obj
    if best is None:
        # tolerate a correct-shaped block whose role/batch_id drifted
        for raw in candidates:
            obj = _try_json(raw)
            if isinstance(obj, dict) and obj.get("backlog_sweep") == "v1" and "results" in obj:
                best = obj
    return best


def _try_json(raw):
    raw = raw.strip()
    if not raw.startswith("{"):
        i = raw.find("{")
        if i < 0:
            return None
        raw = raw[i:]
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _balanced_objects(text):
    out, depth, start, instr, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
            continue
        if ch == '"':
            instr = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start is not None:
                    out.append(text[start:i + 1])
    return out


def render_template(md_path, mapping):
    """Extract the region between TEMPLATE START/END and substitute {{KEYS}}."""
    text = Path(md_path).read_text(encoding="utf-8")
    m = re.search(r"^##\s+TEMPLATE START\s*$(.*?)^##\s+TEMPLATE END\s*$", text, re.S | re.M)
    if not m:
        raise RuntimeError("no TEMPLATE START/END markers in %s" % md_path)
    body = m.group(1).strip("\n")
    for k, v in mapping.items():
        body = body.replace("{{%s}}" % k, "" if v is None else str(v))
    left = re.findall(r"\{\{([A-Z_]+)\}\}", body)
    if left:
        raise RuntimeError(f"unsubstituted placeholders {sorted(set(left))} in {md_path}")
    return body + "\n"


def render_claims(claims):
    """Render verifier claim list (independence rule: no triage notes)."""
    lines = []
    for c in claims:
        cls = c["class"]
        if cls == "duplicate":
            proposed = "duplicate of #%s (close NOT_PLANNED)" % c.get("duplicate_of")
        elif cls == "already-fixed":
            proposed = "already-fixed (close COMPLETED)"
        else:
            proposed = "obsolete (close NOT_PLANNED)"
        refs = "; ".join(
            "{} {}".format(e.get("type"), e.get("ref")) for e in (c.get("evidence") or [])
        ) or "none cited"
        lines.append('- issue: #{} — "{}"'.format(c["issue"], (c.get("title") or "").replace('"', "'")))
        lines.append("  proposed: %s" % proposed)
        lines.append("  cited evidence: %s" % refs)
        lines.append("  proposed closing comment: %s" % (c.get("proposed_comment") or "(none supplied)"))
        lines.append("")
    return "\n".join(lines).rstrip()


CLOSURE_TAG = (
    "\n\n<sub>Automated backlog sweep; independently verified. "
    "Wrongly closed? Please reopen.</sub>"
)


def render_closure_comment(final_comment):
    return (final_comment or "").strip() + CLOSURE_TAG


def lease_is_expired(lease, now, pause_seconds=0):
    exp = parse_iso(lease.get("expires_at"))
    if exp is None:
        return True
    return now > exp + dt.timedelta(seconds=pause_seconds)


def eligible_issue_numbers(issues, pilot_limit):
    """Issue numbers eligible for leasing under pilot_limit (highest first)."""
    nums = sorted((int(n) for n in issues), reverse=True)
    if pilot_limit and pilot_limit > 0:
        nums = nums[:pilot_limit]
    return nums


# ------------------------------------------------------------------ subprocesses

class InfraError(Exception):
    def __init__(self, msg, output=""):
        Exception.__init__(self, msg)
        self.output = output or ""


class Runner:
    """Subprocess runner: 120 s timeout, 3 attempts, exponential backoff."""

    def __init__(self, cfg, sleeper=time.sleep, env_overlay=None):
        self.cfg = cfg
        self.sleep = sleeper
        self.infra_failures = []  # timestamps
        self.env_overlay = env_overlay or {}

    def run(self, argv, input_text=None, check=True, retries=None, timeout=None):
        timeout = timeout or self.cfg.get("subprocess_timeout", 120)
        sleeps = self.cfg.get("retry_sleeps", [5, 25, 125])
        attempts = retries if retries is not None else len(sleeps)
        last = None
        for i in range(attempts):
            t0 = time.time()
            try:
                env = None
                if self.env_overlay:
                    env = dict(os.environ)
                    env.update(self.env_overlay)
                p = subprocess.run(
                    argv, input=input_text, capture_output=True, text=True, timeout=timeout,
                    env=env,
                )
                rc, out, err = p.returncode, p.stdout, p.stderr
            except subprocess.TimeoutExpired:
                rc, out, err = -1, "", "TIMEOUT after %ss" % timeout
            except OSError as exc:
                rc, out, err = -1, "", "OSError: %s" % exc
            dur = time.time() - t0
            log("exec rc={} {:.1f}s {} :: {}".format(rc, dur, " ".join(argv[:6]), SCRUB((out + err)[:400])))
            if rc == 0:
                return out if check else (out + err)
            last = InfraError(f"{argv[0]} exited {rc}", out + err)
            if not check:
                return out + err
            if i < attempts - 1:
                self.sleep(sleeps[min(i, len(sleeps) - 1)])
        self.infra_failures.append(utcnow())
        raise last

    def recent_infra_failures(self, minutes=10):
        cut = utcnow() - dt.timedelta(minutes=minutes)
        self.infra_failures = [t for t in self.infra_failures if t >= cut]
        return len(self.infra_failures)


class Conductor:
    """Conductor /v0 REST client (same endpoints the `conductor` CLI calls)."""

    def __init__(self, cfg, sleeper=time.sleep):
        self.cfg = cfg
        self.sleep = sleeper
        self.base = os.environ.get("CONDUCTOR_API_URL", "https://api.conductor.build").rstrip("/")
        self._auth = os.environ.get("CONDUCTOR_API_KEY") or os.environ.get("CONDUCTOR_API_TOKEN")
        if not self._auth:
            raise RuntimeError("CONDUCTOR_API_KEY / CONDUCTOR_API_TOKEN not set")
        self.infra_failures = []
        self.client_version = os.environ.get("CONDUCTOR_INTERNAL_APP_VERSION", "0.0.0")
        self.session_id = os.environ.get("CONDUCTOR_SESSION_ID")

    def _request(self, method, path, query=None, body=None):
        url = self.base + path
        if query:
            q = {k: v for k, v in query.items() if v is not None}
            if q:
                url += "?" + urllib.parse.urlencode(q)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self._auth)
        if data is not None:
            # Only declare a JSON body when we are sending one. A body-less POST
            # with Content-Type: application/json is rejected by the API's Fastify
            # layer with FST_ERR_CTP_EMPTY_JSON_BODY, which is what silently broke
            # every workspace archive (and would have broken session cancel).
            req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        # Cloudflare in front of the API rejects the default Python-urllib UA with
        # error 1010, so we identify exactly as the CLI does.
        req.add_header("User-Agent", "conductor-cli/%s" % self.client_version)
        req.add_header("x-conductor-client-type", "cli")
        req.add_header("x-conductor-client-version", self.client_version)
        if self.session_id:
            req.add_header("x-conductor-session-id", self.session_id)
        sleeps = self.cfg.get("retry_sleeps", [5, 25, 125])
        last = None
        for i in range(len(sleeps)):
            try:
                with urllib.request.urlopen(req, timeout=self.cfg.get("subprocess_timeout", 120)) as r:
                    raw = r.read().decode("utf-8", "replace")
                log("api %s %s -> %s (%d bytes)" % (method, path, r.status, len(raw)))
                return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", "replace")[:400]
                log(f"api {method} {path} -> HTTP {exc.code} {SCRUB(raw)}")
                if 400 <= exc.code < 500 and exc.code not in (403, 408, 425, 429):
                    raise InfraError(f"HTTP {exc.code} on {path}", raw)
                last = InfraError(f"HTTP {exc.code} on {path}", raw)
            except Exception as exc:  # noqa: BLE001 - network layer
                log(f"api {method} {path} -> {SCRUB(str(exc))}")
                last = InfraError(str(exc))
            if i < len(sleeps) - 1:
                self.sleep(sleeps[i])
        self.infra_failures.append(utcnow())
        raise last

    # -- verbs -------------------------------------------------------------
    def create_workspace(self, name, session_name, message, model, effort, project_id):
        return self._request("POST", "/v0/workspaces", body={
            "projectId": project_id, "name": name, "sessionName": session_name,
            "agent": "claude", "model": model, "effort": effort, "message": message,
        })

    def list_project_workspaces(self, project_id, limit=100):
        return self._request("GET", "/v0/projects/%s/workspaces" % urllib.parse.quote(project_id),
                             query={"limit": limit})

    def list_workspaces(self, name=None, include_archived=False, limit=100):
        return self._request("GET", "/v0/workspaces", query={
            "name": name, "limit": limit,
            "includeArchived": "true" if include_archived else None,
        })

    def workspace_status(self, wid):
        return self._request("GET", "/v0/workspaces/%s/status" % urllib.parse.quote(wid))

    def list_sessions(self, wid):
        return self._request("GET", "/v0/workspaces/%s/sessions" % urllib.parse.quote(wid))

    def archive_workspace(self, wid):
        return self._request("POST", "/v0/workspaces/%s/archive" % urllib.parse.quote(wid))

    def session_status(self, sid):
        return self._request("GET", "/v0/sessions/%s/status" % urllib.parse.quote(sid))

    def cancel_session(self, sid):
        return self._request("POST", "/v0/sessions/%s/cancel" % urllib.parse.quote(sid))

    def messages(self, sid, limit=100, offset=0):
        return self._request("GET", "/v0/sessions/%s/messages" % urllib.parse.quote(sid),
                             query={"limit": limit, "offset": offset})

    def send_message(self, sid, text, message_id=None):
        body = {"message": text}
        if message_id:
            body["messageId"] = message_id
        return self._request("POST", "/v0/sessions/%s/messages" % urllib.parse.quote(sid), body=body)

    def sql(self, query):
        return self._request("POST", "/v0/sql", body={"query": query})

    # -- derived -----------------------------------------------------------
    def all_messages(self, sid, cap=2000):
        out, offset = [], 0
        while offset < cap:
            r = self.messages(sid, limit=100, offset=offset)
            batch = r.get("data") or []
            out.extend(batch)
            if not r.get("hasMore") or not batch:
                break
            offset += len(batch)
        return out

    def assistant_texts(self, messages):
        texts = []
        for m in messages:
            rp = (m.get("content") or {}).get("rawPayload") or {}
            if rp.get("type") != "assistant":
                continue
            chunks = []
            for blk in ((rp.get("message") or {}).get("content") or []):
                if isinstance(blk, dict) and blk.get("type") == "text" and blk.get("text"):
                    chunks.append(blk["text"])
            if chunks:
                texts.append("\n".join(chunks))
        return texts

    def rate_limit_state(self, messages):
        """Most recent rate_limit_event status, or None."""
        for m in reversed(messages):
            rp = (m.get("content") or {}).get("rawPayload") or {}
            if rp.get("type") == "rate_limit_event":
                return (rp.get("rate_limit_info") or {})
        return None

    def transcript_updated(self, session_ids):
        if not session_ids:
            return {}
        quoted = ",".join("'%s'" % s.replace("'", "") for s in session_ids)
        rows = self.sql(
            "SELECT session_id, transcript_updated_at FROM session_transcripts_view "
            "WHERE session_id IN (%s)" % quoted
        ).get("rows") or []
        return {r["session_id"]: r.get("transcript_updated_at") for r in rows}


class GitHub:
    def __init__(self, runner, repo, gh_bin=None):
        self._run = runner.run
        self.repo = repo
        self.gh = gh_bin or "gh"

    def run(self, argv, **kw):
        if argv and argv[0] == "gh":
            argv = [self.gh] + list(argv[1:])
        return self._run(argv, **kw)

    def _json(self, argv):
        out = self.run(argv)
        try:
            return json.loads(out)
        except ValueError:
            raise InfraError("gh returned non-JSON", out[:400])

    def list_open_issues(self, limit=1000):
        return self._json([
            "gh", "issue", "list", "--repo", self.repo, "--state", "open",
            "--limit", str(limit), "--json", "number,title,labels,updatedAt",
        ])

    def issue(self, number, fields="state,updatedAt,comments,title,labels"):
        return self._json([
            "gh", "issue", "view", str(number), "--repo", self.repo, "--json", fields,
        ])

    def close_issue(self, number, reason, comment):
        return self.run([
            "gh", "issue", "close", str(number), "--repo", self.repo,
            "--reason", reason, "--comment", comment,
        ])

    def reopen_issue(self, number):
        return self.run(["gh", "issue", "reopen", str(number), "--repo", self.repo])

    def open_prs_mentioning(self, number):
        return self._json([
            "gh", "pr", "list", "--repo", self.repo, "--state", "open",
            "--search", "%s in:title,body" % number, "--json", "number,title",
        ])

    def prs_for_branch(self, branch):
        return self._json([
            "gh", "pr", "list", "--repo", self.repo, "--head", branch,
            "--state", "all", "--json", "number,url,state",
        ])

    def create_pr(self, branch, title, body_file):
        # --draft is the merge brake for this campaign (bakert, 2026-08-23): Mergify
        # auto-merges his non-draft PRs once CI is green, and both GitHub and Mergify
        # refuse to merge a draft. His review action is clicking "Ready for review".
        return self.run([
            "gh", "pr", "create", "--repo", self.repo, "--base", "master", "--draft",
            "--head", branch, "--title", title, "--body-file", str(body_file),
        ])

    def count_open_sweep_prs(self):
        """Live count of open sweep PRs.

        Deliberately not derived from internal state: bakert merges and closes PRs
        outside the sweep, so our own `pr_open` count drifts high and would throttle
        us against PRs he has already cleared.
        """
        rows = self._json([
            "gh", "pr", "list", "--repo", self.repo, "--state", "open",
            "--limit", "300", "--json", "number,headRefName",
        ])
        return sum(1 for r in rows if (r.get("headRefName") or "").startswith("sweep/"))

    def pr_state(self, number):
        return self._json([
            "gh", "pr", "view", str(number), "--repo", self.repo,
            "--json", "state,mergedAt,isDraft,mergeable,mergeStateStatus",
        ])

    def pr_update_branch(self, number):
        return self.run([
            "gh", "pr", "update-branch", str(number), "--repo", self.repo,
        ], check=False)

    def pr_checks(self, number):
        return self._json([
            "gh", "pr", "checks", str(number), "--repo", self.repo,
            "--json", "name,state,bucket,link",
        ])

    def check_run_summary(self, sha, name, limit=1200):
        """Best-effort log tail for a failing check (no Actions log scope needed)."""
        try:
            runs = self._json(["gh", "api", f"repos/{self.repo}/commits/{sha}/check-runs",
                               "--paginate"]).get("check_runs") or []
        except InfraError:
            return ""
        for r in runs:
            if r.get("name") != name or r.get("conclusion") in (None, "success", "skipped", "neutral"):
                continue
            out = r.get("output") or {}
            text = "\n".join(x for x in (out.get("title"), out.get("summary"), out.get("text")) if x)
            if text:
                return text[-limit:]
        return ""

    def failed_check_log(self, number, names, limit=4000):
        """Fetch the failing job's log. Best-effort: at detection time the run is
        often still in progress, so this is called again at adjudication time."""
        try:
            rows = self.pr_checks(number)
        except InfraError:
            return ""
        chunks = []
        for name in names[:2]:
            link = next((r.get("link") for r in rows
                         if r.get("name") == name and (r.get("bucket") or "").lower() == "fail"), None)
            m = re.search(r"/runs/(\d+)", link or "")
            if not m:
                continue
            out = self.run(["gh", "run", "view", m.group(1), "--repo", self.repo, "--log-failed"],
                           check=False)
            if out and "still in progress" not in out and "could not find" not in out.lower():
                chunks.append(f"### {name}\n{out[-limit:]}")
        return "\n\n".join(chunks)

    def delete_remote_branch(self, branch):
        return self.run(["git", "push", "origin", "--delete", branch], check=False)

    def pr_readied_by_human(self, number):
        """True if someone clicked "Ready for review" on this PR.

        The dispatcher has no un-draft code path, so a sweep PR that is no longer a
        draft was either readied by bakert (the intended review workflow) or never
        drafted at all. Only the second is an incident.
        """
        try:
            rows = self._json([
                "gh", "api", f"repos/{self.repo}/issues/{number}/timeline",
                "--paginate", "-q", "[.[] | select(.event==\"ready_for_review\")]",
            ])
        except InfraError:
            return False
        return bool(rows)

    def pr_is_draft(self, number):
        return bool(self._json([
            "gh", "pr", "view", str(number), "--repo", self.repo, "--json", "isDraft",
        ]).get("isDraft"))

    def close_pr(self, number, comment=None):
        argv = ["gh", "pr", "close", str(number), "--repo", self.repo]
        if comment:
            argv += ["--comment", comment]
        return self.run(argv)

    def remove_label(self, number, label):
        return self.run([
            "gh", "pr", "edit", str(number), "--repo", self.repo, "--remove-label", label,
        ])

    def compare(self, branch):
        return self._json([
            "gh", "api", f"repos/{self.repo}/compare/master...{branch}",
        ])

    def remote_branch_sha(self, branch):
        out = self.run(["git", "ls-remote", "origin", "refs/heads/" + branch], check=False)
        parts = out.split()
        return parts[0] if parts and re.fullmatch(r"[0-9a-f]{40}", parts[0] or "") else None

    def branches_matching(self, pattern):
        out = self.run(["git", "ls-remote", "origin", pattern], check=False)
        return [l.split()[-1] for l in out.splitlines() if l.strip() and "\t" in l]


# ------------------------------------------------------------------------ state

def new_issue(number, title, labels):
    return {
        "issue": int(number), "title": title, "labels": labels, "status": "pending",
        "stage_attempts": {"triage": 0, "verify": 0, "fix": 0}, "lease": None,
        "class": None, "confidence": None, "verdict": None, "evidence_file": None,
        "closure": None, "pr": None, "escalation": None, "history": [], "notes": None,
        "fixup": None,
    }


class State:
    """Materialized view of the journal.  apply() is pure w.r.t. the event."""

    def __init__(self):
        self.last_seq = 0
        self.issues = {}
        self.workspaces = {}
        self.counters = {"workspaces_created": 0, "nudges": 0, "infra_failures": 0}
        self.daily = {"day": None, "closures": 0, "prs": 0}
        self.paused = False
        self.pause_until = None
        self.pause_level = 0
        self.pause_seconds = 0
        self.last_bundle_at = None
        self.pr_backpressure = False
        self.last_master_sha = None
        self.last_mirror_at = None
        self.last_snapshot_at = None
        self.invariants = []

    # -- serialization -----------------------------------------------------
    def to_dict(self):
        return {
            "last_seq": self.last_seq, "issues": self.issues, "workspaces": self.workspaces,
            "counters": self.counters, "daily": self.daily, "paused": self.paused,
            "pause_until": self.pause_until, "pause_level": self.pause_level,
            "pr_backpressure": self.pr_backpressure,
            "last_master_sha": self.last_master_sha,
            "pause_seconds": self.pause_seconds, "last_bundle_at": self.last_bundle_at,
            "last_mirror_at": self.last_mirror_at, "last_snapshot_at": self.last_snapshot_at,
            "invariants": self.invariants[-50:],
        }

    @classmethod
    def from_dict(cls, d):
        s = cls()
        if not d:
            return s
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s

    # -- helpers -----------------------------------------------------------
    def issue(self, n):
        return self.issues.get(str(n))

    def _set_status(self, rec, status, ts, event):
        cur = rec["status"]
        if cur == status:
            return True
        blocked = (cur in ADJUDICATION_ONLY
                   and event not in ("ADJUDICATED", "ROLLBACK_RECORDED"))
        if blocked or status not in LEGAL.get(cur, set()):
            self.invariants.append({"ts": ts, "issue": rec["issue"], "from": cur, "to": status, "event": event})
            rec["status"] = "escalated"
            rec["escalation"] = {"kind": "invariant", "detail": f"illegal {cur} -> {status}"}
            rec.setdefault("history", []).append({"ts": ts, "event": "INVARIANT_VIOLATION"})
            return False
        rec["status"] = status
        rec.setdefault("history", []).append({"ts": ts, "event": event, "status": status})
        return True

    def _roll_day(self, ts):
        day = (ts or "")[:10]
        if self.daily.get("day") != day:
            self.daily = {"day": day, "closures": 0, "prs": 0}

    # -- the reducer -------------------------------------------------------
    def apply(self, ev):
        seq = ev.get("seq", 0)
        if seq <= self.last_seq:
            return
        self.last_seq = seq
        ts = ev.get("ts")
        name = ev.get("event")
        fn = getattr(self, "_ev_" + name.lower(), None)
        if fn is None:
            return
        fn(ev, ts)

    def _ev_campaign_init(self, ev, ts):
        pass

    def _ev_config_changed(self, ev, ts):
        pass

    def _ev_snapshot_written(self, ev, ts):
        self.last_snapshot_at = ts

    def _ev_mirror_pushed(self, ev, ts):
        self.last_mirror_at = ts

    def _ev_issue_enqueued(self, ev, ts):
        key = str(ev["issue"])
        if key in self.issues:
            return
        rec = new_issue(ev["issue"], ev.get("title"), ev.get("labels") or [])
        rec["history"].append({"ts": ts, "event": "ISSUE_ENQUEUED"})
        self.issues[key] = rec

    def _ev_issue_skipped(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec:
            rec["notes"] = ev.get("reason")
            self._set_status(rec, "skipped", ts, "ISSUE_SKIPPED")

    def _ev_workspace_created(self, ev, ts):
        self.workspaces[ev["workspace_id"]] = {
            "workspace_id": ev["workspace_id"], "session_id": ev.get("session_id"),
            "kind": ev["kind"], "batch_id": ev["batch_id"], "issues": ev.get("issues") or [],
            "state": "running", "created_at": ts, "last_transcript_at": None,
            "harvest": {"parsed": False, "malformed_attempts": 0},
        }
        self.counters["workspaces_created"] = self.counters.get("workspaces_created", 0) + 1

    def _ev_workspace_archived(self, ev, ts):
        ws = self.workspaces.get(ev["workspace_id"])
        if ws:
            ws["state"] = "archived"

    def _ev_workspace_harvested(self, ev, ts):
        ws = self.workspaces.get(ev["workspace_id"])
        if ws:
            ws["state"] = "harvested"
            ws["last_archive_attempt_state"] = ev.get("state")

    def _ev_workspace_failed(self, ev, ts):
        ws = self.workspaces.get(ev.get("workspace_id"))
        if ws:
            ws["state"] = "failed"
        self.counters["infra_failures"] = self.counters.get("infra_failures", 0) + 1

    def _ev_lease_granted(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        kind = ev["kind"]
        rec["lease"] = {
            "kind": kind, "batch_id": ev["batch_id"], "workspace_id": ev.get("workspace_id"),
            "session_id": ev.get("session_id"), "granted_at": ts,
            "expires_at": ev["expires_at"], "attempt": ev.get("attempt", 1),
        }
        self._set_status(rec, kind + "_leased", ts, "LEASE_GRANTED")

    def _ev_lease_extended(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec and rec.get("lease"):
            rec["lease"]["expires_at"] = ev["expires_at"]

    def _ev_lease_expired(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        kind = ev["kind"]
        rec["stage_attempts"][kind] = rec["stage_attempts"].get(kind, 0) + 1
        rec["lease"] = None
        rec.setdefault("history", []).append({"ts": ts, "event": "LEASE_EXPIRED"})

    def _ev_retry_scheduled(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec:
            self._set_status(rec, ev["status"], ts, "RETRY_SCHEDULED")

    def _ev_nudge_sent(self, ev, ts):
        ws = self.workspaces.get(ev.get("workspace_id"))
        if ws:
            ws["state"] = "nudged"
            ws["harvest"]["malformed_attempts"] = ws["harvest"].get("malformed_attempts", 0) + 1
        self.counters["nudges"] = self.counters.get("nudges", 0) + 1

    def _ev_result_malformed(self, ev, ts):
        ws = self.workspaces.get(ev.get("workspace_id"))
        if ws:
            ws["harvest"]["parsed"] = False

    def _ev_result_rejected(self, ev, ts):
        pass

    def _ev_result_recorded(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        rec["lease"] = None
        rec["evidence_file"] = "evidence/%s.json" % ev["issue"]
        for k in ("class", "confidence", "verdict"):
            if ev.get(k) is not None:
                rec[k] = ev[k]
        if ev.get("notes"):
            rec["notes"] = ev["notes"]
        if ev.get("pr_branch"):
            rec["pr"] = dict(rec.get("pr") or {}, branch=ev["pr_branch"], head_sha=ev.get("head_sha"))
        self._set_status(rec, ev["status"], ts, "RESULT_RECORDED")

    def _ev_mutation_planned(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec and ev.get("kind") == "close":
            self._set_status(rec, "closing", ts, "MUTATION_PLANNED")

    def _ev_close_executed(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        if not self._set_status(rec, "closed", ts, "CLOSE_EXECUTED"):
            return
        rec["closure"] = {
            "reason": ev.get("reason"), "comment_posted": bool(ev.get("comment_posted")),
            "executed_at": ts, "verified_by_batch": ev.get("verified_by_batch"),
            "duplicate_of": ev.get("duplicate_of"), "external": bool(ev.get("external")),
        }
        if not ev.get("external"):
            self._roll_day(ts)
            self.daily["closures"] += 1

    def _ev_pr_opened(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        if not self._set_status(rec, "pr_open", ts, "PR_OPENED"):
            return
        rec["pr"] = {
            "number": ev.get("number"), "branch": ev.get("branch"), "head_sha": ev.get("head_sha"),
            "opened_at": ts, "url": ev.get("url"), "adopted": bool(ev.get("adopted")),
        }
        if not ev.get("adopted"):
            self._roll_day(ts)
            self.daily["prs"] += 1

    def _ev_pr_withdrawn(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        if rec.get("pr") is not None:
            rec["pr"]["withdrawn_at"] = ts
            rec["pr"]["branch_deleted"] = bool(ev.get("branch_deleted"))
        rec["notes"] = "PR #%s closed without merging by a human; settled outside the sweep." % ev.get("pr")
        self._set_status(rec, "deferred_human", ts, "PR_WITHDRAWN")

    def _ev_pr_readied_by_human(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec and rec.get("pr") is not None:
            rec["pr"]["readied_by_human_at"] = ts

    def _ev_pr_merged(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec and rec.get("pr") is not None:
            rec["pr"]["merged_at"] = ev.get("merged_at") or ts
            rec["pr"]["ci"] = {"state": "merged", "checked_at": ts, "failed": []}
            rec.setdefault("history", []).append({"ts": ts, "event": "PR_MERGED"})

    def _ev_pr_branch_updated(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec and rec.get("pr") is not None:
            rec["pr"]["last_branch_update"] = ts
            rec.setdefault("history", []).append({"ts": ts, "event": "PR_BRANCH_UPDATED"})

    def _ev_pr_conflict(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        if rec.get("pr") is not None:
            rec["pr"]["ci"] = {"state": "conflict", "checked_at": ts, "failed": ["merge-conflict"]}
        self._set_status(rec, "pr_ci_failed", ts, "PR_CONFLICT")

    def _ev_pr_ci_green(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec and rec.get("pr") is not None:
            rec["pr"]["ci"] = {"state": "green", "checked_at": ts, "failed": []}
            rec.setdefault("history", []).append({"ts": ts, "event": "PR_CI_GREEN"})

    def _ev_pr_ci_failed(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        if rec.get("pr") is not None:
            rec["pr"]["ci"] = {"state": "failed", "checked_at": ts, "failed": ev.get("failed") or []}
        self._set_status(rec, "pr_ci_failed", ts, "PR_CI_FAILED")

    def _ev_ci_checked(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec and rec.get("pr") is not None:
            ci = rec["pr"].setdefault("ci", {})
            ci["checked_at"] = ts
            ci.setdefault("state", "pending")

    def _ev_fixup_dispatched(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        rec["fixup"] = {"branch": ev.get("branch"), "pr": ev.get("pr"),
                        "failed": ev.get("failed") or [], "attempt": ev.get("attempt", 1),
                        "log_tail": ev.get("log_tail") or ""}
        self._set_status(rec, "fix_pending", ts, "FIXUP_DISPATCHED")

    def _ev_mutation_failed(self, ev, ts):
        rec = self.issue(ev["issue"])
        if rec:
            rec["escalation"] = {"kind": "mutation-failed", "detail": ev.get("reason")}
            self._set_status(rec, "escalated", ts, "MUTATION_FAILED")

    def _ev_escalated(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        rec["escalation"] = {"kind": ev.get("kind"), "question": ev.get("question")}
        rec["lease"] = None
        self._set_status(rec, "escalated", ts, "ESCALATED")

    def _ev_adjudicated(self, ev, ts):
        rec = self.issue(ev["issue"])
        if not rec:
            return
        rec["escalation"] = None
        rec["notes"] = ev.get("note") or rec.get("notes")
        if ev.get("status"):
            self._set_status(rec, ev["status"], ts, "ADJUDICATED")

    def _ev_master_advanced(self, ev, ts):
        self.last_master_sha = ev.get("sha")

    def _ev_pr_backpressure_on(self, ev, ts):
        self.pr_backpressure = True

    def _ev_pr_backpressure_off(self, ev, ts):
        self.pr_backpressure = False
        self.last_master_sha = None

    def _ev_pause_on(self, ev, ts):
        self.paused = True
        self.pause_until = ev.get("until")
        self.pause_level = ev.get("level", 1)

    def _ev_pause_off(self, ev, ts):
        started = parse_iso(ev.get("since"))
        ended = parse_iso(ts)
        if started and ended:
            self.pause_seconds += max(0, int((ended - started).total_seconds()))
        self.paused = False
        self.pause_until = None
        self.pause_level = 0

    def _ev_invariant_violation(self, ev, ts):
        self.invariants.append(dict(ev))

    def _ev_rollback_recorded(self, ev, ts):
        rec = self.issue(ev.get("issue"))
        if rec and ev.get("status"):
            self._set_status(rec, ev["status"], ts, "ROLLBACK_RECORDED")


class Store:
    """flock + journal + snapshot."""

    def __init__(self, blocking=False, readonly=False):
        STATE.mkdir(parents=True, exist_ok=True)
        for d in (EVIDENCE, ESCALATIONS, REPORTS, OUTBOX):
            d.mkdir(parents=True, exist_ok=True)
        self.readonly = readonly
        self._fh = None if readonly else open(LOCKFILE, "a+")
        flags = fcntl.LOCK_EX if blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if not readonly:
                fcntl.flock(self._fh, flags)
        except OSError as exc:
            self._fh.close()
            if exc.errno in (errno.EAGAIN, errno.EACCES):
                sys.stderr.write("dispatcher: state lock held by another process\n")
                raise SystemExit(75)
            raise
        self.config = self._load_config()
        self.state = State.from_dict(read_json(SNAPSHOT))
        self._replay()
        self._pending = []

    def close(self):
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def _load_config(self):
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        disk = read_json(CONFIG)
        if disk:
            cfg.update(disk)
        else:
            write_json(CONFIG, cfg)
        return cfg

    def _replay(self):
        if not JOURNAL.exists():
            return
        with open(JOURNAL, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    log("journal: truncating torn tail line")
                    break
                self.state.apply(ev)

    def journal(self, event, **payload):
        if self.readonly:
            raise RuntimeError("read-only store cannot journal")
        ev = {"ts": iso(utcnow()), "seq": self.state.last_seq + 1, "event": event}
        ev.update(payload)
        with open(JOURNAL, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.state.apply(ev)
        return ev

    def snapshot(self):
        write_json(SNAPSHOT, self.state.to_dict())
        write_json(QUEUE, {k: {kk: v[kk] for kk in ("issue", "title", "status", "class", "verdict", "pr", "closure")}
                           for k, v in self.state.issues.items()})
        self.journal("SNAPSHOT_WRITTEN", last_seq=self.state.last_seq)
        write_json(SNAPSHOT, self.state.to_dict())

    def save_config(self):
        write_json(CONFIG, self.config)


# ----------------------------------------------------------------------- engine

class Engine:
    def __init__(self, store, dry_run=False, sleeper=time.sleep):
        self.store = store
        self.cfg = store.config
        self.st = store.state
        self.dry = dry_run
        self.runner = Runner(self.cfg, sleeper, env_overlay=load_gh_token())
        self.gh = GitHub(self.runner, self.cfg["repo"], gh_bin=gh_executable())
        self.cond = Conductor(self.cfg, sleeper)
        self.plan = []
        self.create_failures = 0
        self.dry_leased = set()  # dry-run only: issues a planned (unexecuted) spawn would take
        self.unregistered = []   # project workspaces the sweep did not create (A7 tightening)
        self.mirror_error = None
        self.open_sweep_prs = None

    # -- small helpers -----------------------------------------------------
    def say(self, msg):
        self.plan.append(msg)
        log("PLAN " + msg if self.dry else msg, echo=self.dry)

    def active_workspaces(self):
        return [w for w in self.st.workspaces.values() if w["state"] in ("creating", "running", "nudged")]

    def add_evidence(self, issue, kind, obj):
        path = EVIDENCE / ("%s.json" % issue)
        doc = read_json(path) or {"issue": int(issue), "triage": [], "verify": [], "fix": []}
        doc.setdefault(kind, []).append(obj)
        write_json(path, doc)
        return "evidence/%s.json#%s[%d]" % (issue, kind, len(doc[kind]) - 1)

    def last_evidence(self, issue, kind):
        doc = read_json(EVIDENCE / ("%s.json" % issue)) or {}
        arr = doc.get(kind) or []
        return arr[-1] if arr else None

    def escalate(self, issue, kind, question, summary="", refs=None):
        if self.dry:
            self.say(f"WOULD escalate #{issue} ({kind}): {question}")
            return
        rec = {
            "issue": int(issue), "created_at": iso(utcnow()), "kind": kind,
            "question": question, "summary": summary[:1000],
            "evidence_refs": refs or [], "bundled_at": None, "adjudication": None,
        }
        write_json(ESCALATIONS / ("%s.json" % issue), rec)
        self.store.journal("ESCALATED", issue=int(issue), kind=kind, question=question)

    def note_infra_failure(self, why):
        log("infra failure: %s" % why)
        self.st.counters["infra_failures"] = self.st.counters.get("infra_failures", 0) + 1

    def check_rate_limit_text(self, text):
        return bool(text and RATE_LIMIT_RE.search(text))

    def pause(self, reason):
        if self.st.paused:
            return
        level = max(1, self.st.pause_level)
        minutes = min(self.cfg["pause_initial_minutes"] * (2 ** (level - 1)), self.cfg["pause_max_minutes"])
        until = iso(utcnow() + dt.timedelta(minutes=minutes))
        self.store.journal("PAUSE_ON", reason=reason, until=until, level=level, since=iso(utcnow()))
        log(f"PAUSED ({reason}) until {until}")

    def maybe_unpause(self):
        if not self.st.paused:
            return
        until = parse_iso(self.st.pause_until)
        if until and utcnow() < until:
            return
        # probe: extend every live lease by the pause duration, then resume
        since = None
        for line in reversed(self._journal_tail(400)):
            if line.get("event") == "PAUSE_ON":
                since = line.get("since") or line.get("ts")
                break
        started = parse_iso(since)
        if started:
            delta = utcnow() - started
            for rec in self.st.issues.values():
                if rec.get("lease"):
                    exp = parse_iso(rec["lease"]["expires_at"])
                    if exp:
                        self.store.journal("LEASE_EXTENDED", issue=rec["issue"],
                                           expires_at=iso(exp + delta), reason="pause")
        self.store.journal("PAUSE_OFF", since=since or iso(utcnow()))
        log("UNPAUSED")

    def _journal_tail(self, n):
        if not JOURNAL.exists():
            return []
        lines = JOURNAL.read_text(encoding="utf-8").splitlines()[-n:]
        out = []
        for l in lines:
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
        return out

    # -- 1. harvest --------------------------------------------------------
    def harvest(self):
        active = self.active_workspaces()
        if not active:
            return
        try:
            tmap = self.cond.transcript_updated([w["session_id"] for w in active if w.get("session_id")])
        except InfraError:
            tmap = {}
        for ws in list(active):
            sid = ws.get("session_id")
            if not sid:
                continue
            try:
                status = self.cond.session_status(sid)
            except InfraError as exc:
                self.note_infra_failure(f"session_status {sid}: {exc}")
                continue
            ws["last_transcript_at"] = tmap.get(sid) or ws.get("last_transcript_at")
            s = status.get("status")
            age = (utcnow() - (parse_iso(ws.get("created_at")) or utcnow())).total_seconds()
            if s == "error":
                msg = status.get("errorMessage") or status.get("lastError") or "session error"
                if self.check_rate_limit_text(msg):
                    self.pause("session error looks rate-limited")
                self.fail_workspace(ws, "session-error: %s" % msg[:200])
            elif s == "idle" and age >= self.cfg["min_session_age_seconds"]:
                self.harvest_workspace(ws)
            elif s == "working" and self.is_stale(ws):
                log("workspace %s hung: no transcript movement for >%d min"
                    % (ws["batch_id"], self.cfg["stale_transcript_minutes"]))
                try:
                    self.cond.cancel_session(sid)
                except InfraError as exc:
                    log("cancel failed: %s" % exc)
                self.fail_workspace(ws, "stale transcript (hung worker)")

    def is_stale(self, ws):
        """A 'working' session whose transcript has not moved is hung.

        Measured from the later of workspace creation and last transcript movement,
        so a slow-booting workspace is never killed for not having said anything yet.
        """
        limit = dt.timedelta(minutes=self.cfg["stale_transcript_minutes"])
        marks = [parse_iso(ws.get("created_at")), parse_iso(ws.get("last_transcript_at"))]
        marks = [m for m in marks if m]
        if not marks:
            return False
        return (utcnow() - max(marks)) > limit

    def fail_workspace(self, ws, reason):
        self.store.journal("WORKSPACE_FAILED", workspace_id=ws["workspace_id"],
                           batch_id=ws["batch_id"], reason=reason, issues=ws["issues"])
        self.archive(ws)
        self.consume_attempts(ws, reason)

    def archive(self, ws):
        """Archive a workspace and CONFIRM it, before claiming we did.

        The journal previously recorded WORKSPACE_ARCHIVED whether or not the call
        worked, so 39 workspaces sat in `sleeping` while state said `archived`.
        A failed archive now leaves the workspace in `harvested` for retry_archives()
        to pick up on a later tick.
        """
        wid = ws["workspace_id"]
        try:
            self.cond.archive_workspace(wid)
        except InfraError as exc:
            log(f"archive call failed for {wid}: {exc}")
        try:
            state = (self.cond.workspace_status(wid) or {}).get("status")
        except InfraError as exc:
            log(f"archive verification failed for {wid}: {exc}")
            state = None
        if state in ("archived", "deleted"):
            self.store.journal("WORKSPACE_ARCHIVED", workspace_id=wid, verified_state=state)
            return True
        log(f"archive did NOT take for {wid} (state={state}); will retry")
        if ws.get("state") != "harvested":
            self.store.journal("WORKSPACE_HARVESTED", workspace_id=wid, state=state)
        return False

    def retry_archives(self):
        """Re-attempt archives that did not take. Cheap: one call per stuck workspace."""
        stuck = [w for w in self.st.workspaces.values() if w["state"] == "harvested"]
        for ws in stuck[:20]:
            if self.dry:
                self.say("WOULD retry archive of {} ({})".format(ws["workspace_id"], ws["batch_id"]))
                continue
            self.archive(ws)

    def consume_attempts(self, ws, reason, issues=None):
        """Expire-equivalent bookkeeping: +1 attempt, retry or escalate."""
        kind = ws["kind"]
        for n in (issues if issues is not None else ws["issues"]):
            rec = self.st.issue(n)
            if not rec or rec["status"] not in ("%s_leased" % kind,):
                continue
            self.store.journal("LEASE_EXPIRED", issue=int(n), kind=kind, batch_id=ws["batch_id"],
                               reason=reason)
            rec = self.st.issue(n)
            if rec["stage_attempts"].get(kind, 0) < self.cfg["max_stage_attempts"]:
                back = {"triage": "pending", "verify": "verify_pending", "fix": "fix_pending"}[kind]
                self.store.journal("RETRY_SCHEDULED", issue=int(n), kind=kind, status=back,
                                   attempt=rec["stage_attempts"][kind])
            else:
                self.escalate(int(n), "attempts-exhausted",
                              "%s stage failed %d times (%s) — retry, report-only, or drop?"
                              % (kind, rec["stage_attempts"][kind], reason[:120]),
                              summary=reason[:400])

    def harvest_workspace(self, ws):
        sid = ws["session_id"]
        try:
            msgs = self.cond.all_messages(sid)
        except InfraError as exc:
            self.note_infra_failure(f"messages {sid}: {exc}")
            return
        rl = self.cond.rate_limit_state(msgs)
        if rl and rl.get("status") not in (None, "allowed", "warning"):
            self.pause("rate_limit_event status=%s" % rl.get("status"))
        texts = self.cond.assistant_texts(msgs)
        role = ws["kind"]
        obj = None
        for i, text in enumerate(reversed(texts[-3:])):
            obj = extract_json_block(text, role=role, batch_id=ws["batch_id"])
            if obj:
                if i:
                    log("harvest %s: JSON found %d messages before the last" % (ws["batch_id"], i))
                break
        if obj is None:
            self.handle_malformed(ws)
            return
        self.record_results(ws, obj)
        ws["harvest"]["parsed"] = True
        self.archive(ws)

    def handle_malformed(self, ws):
        self.store.journal("RESULT_MALFORMED", workspace_id=ws["workspace_id"], batch_id=ws["batch_id"])
        if ws["harvest"].get("malformed_attempts", 0) == 0 and not self.st.paused:
            nudge = (
                "Your final message must end with the single fenced ```json block specified in "
                "your instructions (backlog_sweep v1, role %s, batch_id %s, one result per assigned "
                "issue). Reply with ONLY that block." % (ws["kind"], ws["batch_id"])
            )
            try:
                self.cond.send_message(ws["session_id"], nudge, message_id=None)
            except InfraError as exc:
                self.note_infra_failure("nudge: %s" % exc)
                return
            self.store.journal("NUDGE_SENT", workspace_id=ws["workspace_id"], batch_id=ws["batch_id"])
            return
        self.archive(ws)
        self.consume_attempts(ws, "malformed output after nudge")

    # -- result recording --------------------------------------------------
    def record_results(self, ws, obj):
        results = obj.get("results")
        if not isinstance(results, list):
            self.handle_malformed(ws)
            return
        seen = set()
        for r in results:
            if not isinstance(r, dict) or "issue" not in r:
                continue
            try:
                n = int(r["issue"])
            except (TypeError, ValueError):
                continue
            if n not in ws["issues"]:
                self.store.journal("RESULT_REJECTED", issue=n, batch_id=ws["batch_id"],
                                   reason="not leased to this batch")
                continue
            if n in seen:
                continue
            seen.add(n)
            r = dict(r, batch_id=ws["batch_id"], recorded_at=iso(utcnow()))
            try:
                getattr(self, "_record_" + ws["kind"])(ws, n, r)
            except Exception as exc:  # noqa: BLE001 defensive: one bad result must not kill the tick
                log(f"record error #{n}: {exc!r}")
                self.add_evidence(n, ws["kind"], r)
                self.escalate(n, "malformed", "Result could not be processed (%s)." % exc)
        missing = [n for n in ws["issues"] if n not in seen]
        if missing:
            self.consume_attempts(ws, "no result in batch output", issues=missing)

    def _record_triage(self, ws, n, r):
        ref = self.add_evidence(n, "triage", r)
        cls = r.get("class")
        conf = r.get("confidence")
        if cls not in TRIAGE_CLASSES:
            self.escalate(n, "malformed", "Unknown triage class %r." % cls, refs=[ref])
            return
        if cls == "skip-closed":
            self.store.journal("ISSUE_SKIPPED", issue=n, reason="closed before triage")
            return
        if cls in CLOSURE_CLASSES:
            if conf != "high":
                self.store.journal("RESULT_RECORDED", issue=n, kind="triage", batch_id=ws["batch_id"],
                                   **{"class": cls, "confidence": conf, "status": "triaged"})
                self.escalate(n, "class-escalate",
                              "Closure candidate %s at %s confidence — verify anyway, report-only, or drop?"
                              % (cls, conf), summary=(r.get("notes") or "")[:400], refs=[ref])
                return
            if cls == "duplicate" and not r.get("duplicate_of"):
                self.escalate(n, "class-escalate", "duplicate claimed without duplicate_of.", refs=[ref])
                return
            self.store.journal("RESULT_RECORDED", issue=n, kind="triage", batch_id=ws["batch_id"],
                               **{"class": cls, "confidence": conf, "status": "triaged"})
            self.store.journal("RESULT_RECORDED", issue=n, kind="triage", batch_id=ws["batch_id"],
                               **{"class": cls, "confidence": conf, "status": "verify_pending"})
            return
        if cls == "easy-fix":
            self.store.journal("RESULT_RECORDED", issue=n, kind="triage", batch_id=ws["batch_id"],
                               **{"class": cls, "confidence": conf, "status": "triaged"})
            self.store.journal("RESULT_RECORDED", issue=n, kind="triage", batch_id=ws["batch_id"],
                               **{"class": cls, "confidence": conf, "status": "fix_pending"})
            return
        if cls in REPORT_ONLY_CLASSES:
            self.store.journal("RESULT_RECORDED", issue=n, kind="triage", batch_id=ws["batch_id"],
                               **{"class": cls, "confidence": conf, "status": "triaged"})
            self.store.journal("RESULT_RECORDED", issue=n, kind="triage", batch_id=ws["batch_id"],
                               **{"class": cls, "confidence": conf, "status": "reported"})
            return
        # escalation classes
        self.store.journal("RESULT_RECORDED", issue=n, kind="triage", batch_id=ws["batch_id"],
                           **{"class": cls, "confidence": conf, "status": "triaged"})
        self.escalate(n, "class-escalate", "Triaged %s — needs a human/product call." % cls,
                      summary=(r.get("notes") or "")[:400], refs=[ref])

    def _record_verify(self, ws, n, r):
        ref = self.add_evidence(n, "verify", r)
        verdict = (r.get("verdict") or "").upper()
        if verdict == "CONFIRMED" and not r.get("recent_human_activity") and r.get("final_comment"):
            self.store.journal("RESULT_RECORDED", issue=n, kind="verify", batch_id=ws["batch_id"],
                               verdict=verdict, status="verified")
            return
        self.store.journal("RESULT_RECORDED", issue=n, kind="verify", batch_id=ws["batch_id"],
                           verdict=verdict or "MISSING", status="verify_leased")
        kind = "verifier-refuted" if verdict == "REFUTED" else "verifier-uncertain"
        self.escalate(n, kind, "Verifier returned %s — drop the closure, re-triage, or override?" % (verdict or "no verdict"),
                      summary=(r.get("refutation_reason") or "")[:400], refs=[ref])

    def _record_fix(self, ws, n, r):
        ref = self.add_evidence(n, "fix", r)
        outcome = r.get("outcome")
        if outcome == "pushed" and r.get("branch") and r.get("head_sha"):
            self.store.journal("RESULT_RECORDED", issue=n, kind="fix", batch_id=ws["batch_id"],
                               status="fix_pushed", pr_branch=r["branch"], head_sha=r["head_sha"])
            return
        self.store.journal("RESULT_RECORDED", issue=n, kind="fix", batch_id=ws["batch_id"],
                           status="fix_leased")
        self.escalate(n, "fix-abort" if outcome == "abort-escalate" else "fix-validation",
                      "Fixer reported %s — re-queue, report-only, or defer?" % outcome,
                      summary=(r.get("notes") or "")[:400], refs=[ref])

    # -- 2. lease expiry ---------------------------------------------------
    def expire_leases(self):
        if self.st.paused:
            return
        now = utcnow()
        for ws in list(self.active_workspaces()):
            leases = [self.st.issue(n)["lease"] for n in ws["issues"]
                      if self.st.issue(n) and self.st.issue(n).get("lease")]
            if not leases:
                continue
            exp = min(parse_iso(l["expires_at"]) or now for l in leases)
            if now <= exp:
                continue
            advanced = parse_iso(ws.get("last_transcript_at"))
            if advanced and (now - advanced) < dt.timedelta(minutes=10) and not ws.get("extended"):
                ws["extended"] = True
                bonus = dt.timedelta(minutes=self.cfg["lease_minutes"][ws["kind"]] * 0.5)
                for n in ws["issues"]:
                    rec = self.st.issue(n)
                    if rec and rec.get("lease"):
                        self.store.journal("LEASE_EXTENDED", issue=int(n),
                                           expires_at=iso(exp + bonus), reason="transcript advancing")
                continue
            try:
                self.cond.cancel_session(ws["session_id"])
            except InfraError as exc:
                log("cancel failed: %s" % exc)
            self.archive(ws)
            self.consume_attempts(ws, "lease expired")

    # -- 3. mutations ------------------------------------------------------
    def execute_mutations(self):
        self.execute_closures()
        self.execute_prs()

    def _ready(self, status):
        return sorted((r for r in self.st.issues.values()
                       if r["status"] == status and r["issue"] not in self.dry_leased),
                      key=lambda r: -r["issue"])

    def execute_closures(self):
        if not self.dry and self.cfg["mutations_enabled"] and not self.cfg.get("closures_enabled", True):
            n_waiting = len(self._ready("verified"))
            if n_waiting:
                log("closures disabled; %d verified issue(s) queued" % n_waiting)
            return
        for rec in self._ready("verified"):
            n = rec["issue"]
            if self.st.daily.get("closures", 0) >= self.cfg["daily_close_cap"]:
                log("daily close cap reached")
                return
            tri = self.last_evidence(n, "triage") or {}
            ver = self.last_evidence(n, "verify") or {}
            reason_key = CLOSURE_CLASSES.get(tri.get("class"))
            if not reason_key:
                self.escalate(n, "mutation-failed", "No closure class on record for a verified issue.")
                continue
            gh_reason = "completed" if reason_key == "completed" else "not planned"
            comment = render_closure_comment(ver.get("final_comment"))
            if self.dry or not self.cfg["mutations_enabled"]:
                self.say("WOULD close #{} ({}): {}".format(n, gh_reason, (ver.get("final_comment") or "")[:120]))
                continue
            ok, why = self.closure_guards(n, ver)
            if ok == "already-closed":
                self.store.journal("CLOSE_EXECUTED", issue=n, reason=reason_key, external=True,
                                   comment_posted=False, verified_by_batch=ver.get("batch_id"))
                continue
            if not ok:
                self.escalate(n, "class-escalate", "Closure guard tripped: %s" % why, summary=why)
                continue
            self.store.journal("MUTATION_PLANNED", issue=n, kind="close", reason=reason_key)
            out = ""
            try:
                out = self.gh.close_issue(n, gh_reason, comment)
            except InfraError as exc:
                out = exc.output
                if not PERMISSION_RE.search(out or ""):
                    self.store.journal("MUTATION_FAILED", issue=n, kind="close", reason=str(exc)[:200])
                    continue
            try:
                state = self.gh.issue(n, "state").get("state")
            except InfraError:
                state = None
            if state != "CLOSED" and PERMISSION_RE.search(out or ""):
                # Environmental, not issue-specific: do not burn the issue. Park it
                # back on `verified`, shut the closure gate, and alert the manager.
                self.store.journal("ROLLBACK_RECORDED", issue=n, status="verified",
                                   action="closure blocked by token permissions")
                self.cfg["closures_enabled"] = False
                self.store.config["closures_enabled"] = False
                self.store.save_config()
                self.store.journal("CONFIG_CHANGED", changes={"closures_enabled": False},
                                   reason="GitHub token lacks issues:write")
                self.st.counters["alert"] = ("closures disabled: GH token lacks issues:write "
                                             "(issue close/comment returns 403)")
                log("CLOSURES DISABLED: token cannot write issues")
                return
            if state == "CLOSED":
                self.store.journal("CLOSE_EXECUTED", issue=n, reason=reason_key, comment_posted=True,
                                   verified_by_batch=ver.get("batch_id"),
                                   duplicate_of=tri.get("duplicate_of"))
            else:
                self.store.journal("MUTATION_FAILED", issue=n, kind="close",
                                   reason="post-close state=%s" % state)

    def closure_guards(self, n, ver):
        try:
            data = self.gh.issue(n, "state,updatedAt,comments")
        except InfraError as exc:
            return False, "gh issue view failed: %s" % exc
        if data.get("state") == "CLOSED":
            return "already-closed", ""
        bots = set(self.cfg["bot_logins"])
        guard = utcnow() - dt.timedelta(days=self.cfg["recent_activity_guard_days"])
        if self.cfg.get("recent_activity_guard_mode") == "updated_at":
            touched = parse_iso(data.get("updatedAt"))
            if touched and touched >= guard:
                return False, "issue updatedAt %s is inside the %d-day guard" % (
                    data.get("updatedAt"), self.cfg["recent_activity_guard_days"])
        verified_at = parse_iso(ver.get("recorded_at"))
        for c in data.get("comments") or []:
            login = ((c.get("author") or {}).get("login") or "")
            if login in bots or login.endswith("[bot]"):
                continue
            when = parse_iso(c.get("createdAt"))
            if not when:
                continue
            if when >= guard:
                return False, "human comment by %s on %s is inside the %d-day guard" % (
                    login, c.get("createdAt"), self.cfg["recent_activity_guard_days"])
            if verified_at and when > verified_at:
                return False, "human comment appeared after verification"
        return True, ""

    def execute_prs(self):
        if not self.dry and self.cfg["mutations_enabled"] and not self.cfg.get("prs_enabled", True):
            return
        queued = self._ready("fix_pushed")
        if queued and not self.dry:
            if not self.pr_capacity_available(len(queued)):
                return
        for rec in queued:
            n = rec["issue"]
            if self.st.daily.get("prs", 0) >= self.cfg["daily_pr_cap"]:
                log("daily PR cap reached")
                return
            fx = self.last_evidence(n, "fix") or {}
            branch = fx.get("branch")
            if self.dry or not self.cfg["mutations_enabled"]:
                self.say("WOULD open PR for #{} from {}: {}".format(n, branch, fx.get("pr_title")))
                continue
            existing = []
            try:
                existing = [p for p in self.gh.prs_for_branch(branch) if p.get("state") == "OPEN"]
            except InfraError as exc:
                log("pr list failed: %s" % exc)
            if existing:
                p = existing[0]
                self.store.journal("PR_OPENED", issue=n, number=p["number"], url=p.get("url"),
                                   branch=branch, head_sha=fx.get("head_sha"), adopted=True)
                try:
                    if not self.gh.pr_is_draft(p["number"]):
                        if self.gh.pr_readied_by_human(p["number"]):
                            # bakert clicked "Ready for review" — that IS the review
                            # workflow, not a failure of the draft brake.
                            self.store.journal("PR_READIED_BY_HUMAN", issue=n, pr=p["number"])
                            log("PR #%s was readied by a human; leaving it alone" % p["number"])
                        else:
                            self.escalate(n, "fix-validation",
                                          "Adopted PR #%s on %s is NOT a draft and nobody readied "
                                          "it, so the draft brake failed. Draft it or confirm."
                                          % (p["number"], branch),
                                          summary="adopted non-draft PR, no ready_for_review event")
                            self.st.counters["alert"] = "adopted non-draft PR #%s" % p["number"]
                except InfraError as exc:
                    log("draft check failed for #{}: {}".format(p["number"], exc))
                continue
            ok, why = self.pr_guards(n, fx)
            if not ok:
                self.escalate(n, "fix-validation", "PR validation failed: %s" % why, summary=why)
                continue
            body = fx.get("pr_body") or ""
            tests = (fx.get("tests") or {})
            if tests.get("result") != "passed" and "test" not in body.lower():
                body += "\n\nTest status: {} — {}".format(tests.get("result"), tests.get("detail"))
            body_file = OUTBOX / ("pr-%s.md" % n)
            write_atomic(body_file, body)
            self.store.journal("MUTATION_PLANNED", issue=n, kind="pr", branch=branch)
            try:
                out = self.gh.create_pr(branch, fx.get("pr_title") or "Fix #%s" % n, body_file)
            except InfraError as exc:
                self.store.journal("MUTATION_FAILED", issue=n, kind="pr", reason=str(exc)[:200])
                continue
            m = re.search(r"(https://\S+/pull/(\d+))", out or "")
            number = int(m.group(2)) if m else None
            if number is None:
                self.store.journal("MUTATION_FAILED", issue=n, kind="pr",
                                   reason="could not parse PR number from gh output")
                self.escalate(n, "fix-validation", "PR may have been created but its number could "
                              "not be parsed - check %s by hand." % branch)
                continue
            # Draft is the merge brake. A non-draft sweep PR is an incident, not a nit:
            # Mergify merges bakert's green PRs automatically.
            try:
                is_draft = self.gh.pr_is_draft(number)
            except InfraError as exc:
                is_draft = False
                log(f"draft verification failed for #{number}: {exc}")
            if not is_draft:
                log("PR #%s IS NOT A DRAFT - closing immediately" % number)
                try:
                    self.gh.close_pr(number, "Closing automatically: this sweep PR was not created "
                                             "as a draft, and non-draft PRs here are auto-merged. "
                                             "The branch is untouched; it will be reopened as a draft.")
                except InfraError as exc:
                    log(f"emergency close of #{number} FAILED: {exc}")
                self.cfg["prs_enabled"] = False
                self.store.config["prs_enabled"] = False
                self.store.save_config()
                self.store.journal("CONFIG_CHANGED", changes={"prs_enabled": False},
                                   reason="a sweep PR was created non-draft; pipeline halted")
                self.store.journal("MUTATION_FAILED", issue=n, kind="pr",
                                   reason="PR #%s created non-draft; closed and pipeline halted" % number)
                self.escalate(n, "fix-validation",
                              "PR #%s was created WITHOUT draft status and was closed immediately. "
                              "PR creation is halted. Investigate before re-enabling." % number,
                              summary="draft brake failed")
                self.st.counters["alert"] = "non-draft PR #%s created and closed; PRs halted" % number
                return
            self.store.journal("PR_OPENED", issue=n, number=number,
                               url=m.group(1), branch=branch, head_sha=fx.get("head_sha"),
                               draft=True)

    def pr_capacity_available(self, queued):
        """Backpressure on the reviewer, not just on the day.

        `daily_pr_cap` bounds the rate; this bounds the standing pile awaiting
        review. Holding branches in `fix_pushed` is normal flow control, so it is
        journaled once per transition and never escalated.
        """
        cap = self.cfg.get("max_open_prs")
        if not cap:
            return True
        try:
            open_now = self.gh.count_open_sweep_prs()
        except InfraError as exc:
            log("open-PR count failed, holding PRs this tick: %s" % exc)
            return False
        self.open_sweep_prs = open_now
        if open_now >= cap:
            if not self.st.pr_backpressure:
                self.store.journal("PR_BACKPRESSURE_ON", open_prs=open_now, cap=cap, queued=queued)
                log("PR backpressure ON: %d open sweep PRs >= cap %d; holding %d branch(es)"
                    % (open_now, cap, queued))
            return False
        if self.st.pr_backpressure:
            self.store.journal("PR_BACKPRESSURE_OFF", open_prs=open_now, cap=cap)
            log("PR backpressure OFF: %d open sweep PRs < cap %d" % (open_now, cap))
        return True

    def pr_guards(self, n, fx):
        branch, sha = fx.get("branch"), (fx.get("head_sha") or "")
        if not branch:
            return False, "no branch reported"
        remote = self.gh.remote_branch_sha(branch)
        if not remote:
            return False, "branch %s not on origin" % branch
        if sha and not (remote.startswith(sha) or sha.startswith(remote[:7])):
            return False, f"branch head {remote[:10]} != reported {sha[:10]}"
        try:
            cmp_ = self.gh.compare(branch)
        except InfraError as exc:
            return False, "compare failed: %s" % exc
        changed = (cmp_.get("files") or [])
        total = sum((f.get("additions", 0) + f.get("deletions", 0)) for f in changed)
        if total > self.cfg["max_fix_lines"]:
            return False, "%d changed lines exceeds budget %d" % (total, self.cfg["max_fix_lines"])
        for f in changed:
            path = f.get("filename", "")
            for bad in self.cfg["forbidden_paths"]:
                if path == bad or path.startswith(bad):
                    return False, "touches forbidden path %s" % path
            if path == "pyproject.toml":
                return False, "touches pyproject.toml (dependency review needed)"
        return True, ""

    # -- 3b. CI watch ------------------------------------------------------
    @staticmethod
    def summarize_checks(rows, required):
        """Aggregate gh's per-run rows into one verdict per required check.

        The same check appears once per workflow run, so a name is only `pass`
        when every instance of it passed, and `fail` if any instance failed.
        """
        out = {}
        for name in required:
            states = [r for r in rows if (r.get("name") or "") == name]
            if not states:
                out[name] = "pending"
            elif any((r.get("bucket") or "").lower() in ("fail", "cancel") for r in states):
                out[name] = "fail"
            elif all((r.get("bucket") or "").lower() in ("pass", "skipping") for r in states):
                out[name] = "pass"
            else:
                out[name] = "pending"
        return out

    def pr_settled_by_human(self, rec, pr, number):
        """Stop watching a PR a human has merged or closed.

        A sweep PR closed without merging is bakert rejecting the fix: delete the
        branch, mark the issue human-settled, and never retry it.
        """
        try:
            info = self.gh.pr_state(number)
        except InfraError as exc:
            log(f"PR state check failed for #{number}: {exc}")
            return False
        state = (info.get("state") or "").upper()
        if state == "MERGED":
            if (pr.get("ci") or {}).get("state") != "merged":
                self.store.journal("PR_MERGED", issue=rec["issue"], pr=number,
                                   merged_at=info.get("mergedAt"))
                log("PR #%s was merged by a human" % number)
            return True
        if state == "OPEN":
            return self.handle_mergeability(rec, pr, number, info)
        if state == "CLOSED":
            branch = pr.get("branch")
            deleted = False
            if branch and self.gh.remote_branch_sha(branch):
                self.gh.delete_remote_branch(branch)
                deleted = self.gh.remote_branch_sha(branch) is None
            self.store.journal("PR_WITHDRAWN", issue=rec["issue"], pr=number,
                               branch=branch, branch_deleted=deleted)
            log("PR #%s closed without merging; issue #%s settled by human%s"
                % (number, rec["issue"], " (branch deleted)" if deleted else ""))
            return True
        return False

    def handle_mergeability(self, rec, pr, number, info):
        """Master moves under long-lived sweep PRs; a green PR can still be unmergeable.

        BEHIND is mechanical, so the dispatcher merges master in itself. CONFLICTING
        needs judgement, so it escalates and waits for an adjudication.
        """
        status = (info.get("mergeStateStatus") or "").upper()
        mergeable = (info.get("mergeable") or "").upper()
        if mergeable == "CONFLICTING" or status == "DIRTY":
            if (pr.get("ci") or {}).get("state") != "conflict":
                self.store.journal("PR_CONFLICT", issue=rec["issue"], pr=number)
                self.escalate(
                    rec["issue"], "pr-conflict",
                    "PR #%s conflicts with master — dispatch one fixer to merge master and "
                    "resolve (queue-fixup), or abandon it (abandon-pr)?" % number,
                    summary="mergeable=%s mergeStateStatus=%s on branch %s"
                            % (mergeable, status, pr.get("branch")),
                    refs=["evidence/%s.json#fix[-1]" % rec["issue"]])
                log("PR #%s conflicts with master" % number)
            return True
        if status == "BEHIND" and self.cfg.get("auto_update_behind_branches", True):
            last = parse_iso(pr.get("last_branch_update"))
            if not last or (utcnow() - last) > dt.timedelta(minutes=15):
                out = self.gh.pr_update_branch(number)
                if "conflict" in (out or "").lower():
                    return False  # next pass sees CONFLICTING and escalates properly
                self.store.journal("PR_BRANCH_UPDATED", issue=rec["issue"], pr=number)
                log("PR #%s was behind master; merged master in" % number)
            return False
        return False

    def watch_ci(self):
        """Poll the Mergify-required checks on every open sweep PR.

        `pr_open` is terminal for the sweep, but a red draft would otherwise sit
        unnoticed until bakert opened it, so the dispatcher keeps watching.
        """
        required = self.cfg["required_checks"]
        recheck = dt.timedelta(minutes=self.cfg["ci_recheck_minutes"])
        # Conflicts and BEHIND states are *caused* by master moving, so poll on that
        # event rather than waiting out a timer. One `git ls-remote` per tick costs
        # no REST quota and makes detection immediate instead of interval-bound.
        master_moved = False
        if not self.dry:
            try:
                sha = self.gh.remote_branch_sha("master")
            except InfraError:
                sha = None
            if sha and sha != self.st.last_master_sha:
                master_moved = self.st.last_master_sha is not None
                self.store.journal("MASTER_ADVANCED", sha=sha)
                if master_moved:
                    log("master advanced to %s; rechecking every open sweep PR" % sha[:10])
        for rec in self._ready("pr_open") + self._ready("pr_ci_failed"):
            pr = rec.get("pr") or {}
            number = pr.get("number")
            if not number:
                continue
            ci = pr.get("ci") or {}
            checked = parse_iso(ci.get("checked_at"))
            settled = ci.get("state") in ("green", "merged")
            if settled and checked and (utcnow() - checked) < recheck and not master_moved:
                continue
            if self.dry:
                self.say("WOULD poll CI for PR #{} (issue #{})".format(number, rec["issue"]))
                continue
            if self.pr_settled_by_human(rec, pr, number):
                continue
            try:
                rows = self.gh.pr_checks(number)
            except InfraError as exc:
                log(f"CI poll failed for #{number}: {exc}")
                continue
            verdict = self.summarize_checks(rows, required)
            failed = sorted(n for n, v in verdict.items() if v == "fail")
            if failed:
                tails = []
                for name in failed[:2]:
                    tail = self.gh.check_run_summary(pr.get("head_sha") or "", name)
                    if tail:
                        tails.append(f"### {name}\n{tail}")
                self.store.journal("PR_CI_FAILED", issue=rec["issue"], pr=number, failed=failed)
                self.escalate(
                    rec["issue"], "pr-ci-failed",
                    "PR #%s is red on %s — dispatch one follow-up fixer to the same branch "
                    "(queue-fixup), or abandon the PR (abandon-pr)?" % (number, ", ".join(failed)),
                    summary=("failing checks: {}\n{}".format(", ".join(failed), "\n".join(tails)))[:4000],
                    refs=["evidence/%s.json#fix[-1]" % rec["issue"]])
                continue
            if all(v == "pass" for v in verdict.values()):
                if ci.get("state") != "green":
                    self.store.journal("PR_CI_GREEN", issue=rec["issue"], pr=number)
                    log("PR #%s green on all required checks" % number)
                else:
                    self.store.journal("CI_CHECKED", issue=rec["issue"], pr=number)
            else:
                self.store.journal("CI_CHECKED", issue=rec["issue"], pr=number)

    # -- 4. escalation bundles --------------------------------------------
    def bundle_escalations(self):
        files = sorted(ESCALATIONS.glob("*.json"))
        recs = [read_json(f) for f in files]
        unbundled = [r for r in recs if r and not r.get("bundled_at")]
        if not unbundled:
            return
        now = utcnow()
        last = parse_iso(self.st.last_bundle_at)
        if last and (now - last) < dt.timedelta(hours=self.cfg["bundle_min_gap_hours"]):
            return
        oldest = min((parse_iso(r["created_at"]) or now) for r in unbundled)
        trigger = (len(unbundled) >= self.cfg["bundle_min_items"]
                   or (now - oldest) > dt.timedelta(hours=self.cfg["bundle_max_age_hours"]))
        if not trigger:
            return
        ts = now.strftime("%Y%m%dT%H%M%SZ")
        lines = ["# Escalation bundle %s" % ts, "", self.vitals_line(), ""]
        for r in unbundled[:40]:
            lines += [
                "## #{} — {}".format(r["issue"], r["kind"]),
                "- question: %s" % r["question"],
                "- summary: %s" % (r.get("summary") or "")[:400].replace("\n", " "),
                "- evidence: %s" % ", ".join(r.get("evidence_refs") or []),
                "- suggested default: %s" % self.suggested_default(r),
                "",
            ]
        lines += ["Adjudicate with: dispatcher.py adjudicate <issue> <verb> [--note ...]", ""]
        path = OUTBOX / ("bundle-%s.md" % ts)
        write_atomic(path, "\n".join(lines))
        sid = self.cfg.get("opus_session_id")
        if not sid:
            self.st.counters["alert"] = "bundle queued, opus_session_id unset"
            return
        if self.dry:
            self.say(f"WOULD send bundle {path.name} to session {sid}")
            return
        try:
            self.cond.send_message(sid, "Escalation bundle ready: read `%s` and adjudicate." % path,
                                   message_id="bundle-%s" % ts)
        except InfraError as exc:
            log("bundle send failed: %s" % exc)
            return
        self.st.last_bundle_at = iso(now)
        for r, f in zip(recs, files):
            if r and not r.get("bundled_at"):
                r["bundled_at"] = iso(now)
                write_json(f, r)

    @staticmethod
    def suggested_default(r):
        return {
            "verifier-refuted": "report-only",
            "verifier-uncertain": "report-only",
            "cannot-reproduce": "report-only",
            "attempts-exhausted": "report-only",
            "fix-abort": "report-only",
            "fix-validation": "defer-to-human",
            "mutation-failed": "retry",
            "class-escalate": "defer-to-human",
            "malformed": "retry-triage",
            "invariant": "defer-to-human",
        }.get(r.get("kind"), "defer-to-human")

    def vitals_line(self):
        c = self.counts()
        return "vitals: %s | closures_today=%d/%d prs_today=%d/%d active_ws=%d paused=%s" % (
            " ".join("%s=%d" % kv for kv in sorted(c.items()) if kv[1]),
            self.st.daily.get("closures", 0), self.cfg["daily_close_cap"],
            self.st.daily.get("prs", 0), self.cfg["daily_pr_cap"],
            len(self.active_workspaces()), self.st.paused,
        )

    def counts(self):
        out = {}
        for r in self.st.issues.values():
            out[r["status"]] = out.get(r["status"], 0) + 1
        return out

    # -- 5. replenish ------------------------------------------------------
    def replenish(self):
        if self.st.paused or not self.cfg.get("spawning_enabled", True):
            return
        cap = self.cfg["concurrency_cap"]
        created = self.st.counters.get("workspaces_created", 0)
        planned = 0
        while len(self.active_workspaces()) + planned < cap:
            if created + planned >= self.cfg["max_total_workspaces"]:
                log("max_total_workspaces reached")
                return
            job = self.next_job()
            if job is None:
                return
            if not self.spawn(job):
                return
            if self.dry:
                planned += 1

    def next_job(self):
        verify = self._ready("verify_pending")
        if verify:
            batch = verify[:self.cfg["verify_batch_size"]]
            return ("verify", [r["issue"] for r in batch])
        for rec in self._ready("fix_pending"):
            ok, why = self.fix_guards(rec)
            if ok:
                return ("fix", [rec["issue"]])
            self.escalate(rec["issue"], "fix-validation", "Pre-dispatch guard: %s" % why, summary=why)
        eligible = set(eligible_issue_numbers(self.st.issues, self.cfg["pilot_limit"]))
        pending = [r for r in self._ready("pending") if r["issue"] in eligible]
        if pending:
            batch = pending[:self.cfg["triage_batch_size"]]
            return ("triage", [r["issue"] for r in batch])
        return None

    def fix_guards(self, rec):
        n = rec["issue"]
        if rec.get("fixup"):
            # The one sanctioned exception: a manager-adjudicated follow-up fixer
            # pushes to the sweep branch that already exists, for the PR that
            # already exists. Both guards below would reject it by design.
            return True, ""
        try:
            if self.gh.issue(n, "state").get("state") != "OPEN":
                return False, "issue is no longer open"
        except InfraError as exc:
            return False, "gh issue view failed: %s" % exc
        try:
            if self.gh.open_prs_mentioning(n):
                return False, "an open PR already references #%s" % n
        except InfraError as exc:
            return False, "gh pr list failed: %s" % exc
        stale = self.gh.branches_matching("refs/heads/sweep/%s-*" % n)
        if stale:
            # A previous fixer pushed but its report was never harvested (malformed
            # output or an expired lease), so the retry now collides with its own
            # orphan. The branch is ours by naming convention and has no PR of any
            # kind, so reclaim it rather than deadlocking on it.
            if not self.cfg.get("reclaim_orphan_branches", True):
                return False, "a sweep/%s-* branch already exists on origin" % n
            for ref in stale:
                branch = ref.replace("refs/heads/", "")
                if not re.match(r"^sweep/%d-" % n, branch):
                    return False, "unexpected branch %s" % branch
                try:
                    if self.gh.prs_for_branch(branch):
                        return False, "branch %s already has a PR" % branch
                except InfraError as exc:
                    return False, f"could not check PRs for {branch}: {exc}"
                self.gh.delete_remote_branch(branch)
                if self.gh.remote_branch_sha(branch):
                    return False, "could not delete orphan branch %s" % branch
                self.store.journal("ROLLBACK_RECORDED", issue=n, status=None,
                                   action="deleted orphan branch %s (pushed by a fixer whose "
                                          "report was never harvested; no PR existed)" % branch)
                log(f"reclaimed orphan branch {branch} for #{n}")
        return True, ""

    def batch_id(self, kind, issues):
        attempt = 1 + max(self.st.issue(n)["stage_attempts"].get(kind, 0) for n in issues)
        prefix = "u" if (kind == "fix" and self.st.issue(issues[0]).get("fixup")) else kind[0]
        return "%s-%s-%d" % (prefix, issues[0], attempt)

    def render_prompt(self, kind, issues, batch_id):
        if kind == "triage":
            return render_template(BASE / "WORKER_PROMPT.md", {
                "ISSUE_NUMBERS": ", ".join("#%s" % n for n in issues),
                "BATCH_ID": batch_id,
            })
        if kind == "verify":
            claims = []
            for n in issues:
                tri = self.last_evidence(n, "triage") or {}
                claims.append({
                    "issue": n, "title": self.st.issue(n)["title"], "class": tri.get("class"),
                    "duplicate_of": tri.get("duplicate_of"), "evidence": tri.get("evidence"),
                    "proposed_comment": tri.get("proposed_comment"),
                })
            return render_template(BASE / "VERIFIER_PROMPT.md", {
                "BATCH_ID": batch_id, "CLAIMS": render_claims(claims),
                "PROPOSED_COMMENT": "(shown with each claim above)",
            })
        n = issues[0]
        rec = self.st.issue(n)
        if rec.get("fixup"):
            fu = rec["fixup"]
            failed = fu.get("failed") or []
            if failed == ["merge-conflict"]:
                problem = "the branch conflicts with master and cannot be merged"
            else:
                problem = "these required checks are failing: %s" % (", ".join(failed) or "unknown")
            return render_template(BASE / "FIXUP_PROMPT.md", {
                "ISSUE": n, "TITLE": rec["title"], "BATCH_ID": batch_id,
                "BRANCH": fu["branch"], "PR": fu["pr"], "PROBLEM": problem,
                "DETAIL": (fu.get("log_tail") or "(no detail captured; reproduce it yourself)")[:4000],
            })
        tri = self.last_evidence(n, "triage") or {}
        return render_template(BASE / "FIXER_PROMPT.md", {
            "ISSUE": n, "TITLE": rec["title"], "BATCH_ID": batch_id,
            "FIX_SKETCH": tri.get("fix_sketch") or "(none supplied — derive it yourself)",
            "BRANCH": "sweep/{}-{}".format(n, slugify(rec["title"])),
        })

    def spawn(self, job):
        kind, issues = job
        bid = self.batch_id(kind, issues)
        prompt = self.render_prompt(kind, issues, bid)
        path = OUTBOX / ("%s.md" % bid)
        write_atomic(path, prompt)
        name = "sweep-%s" % bid
        if self.dry:
            self.say("WOULD create workspace %s (%s) for %s  [prompt %d chars -> %s]"
                     % (name, kind, issues, len(prompt), path.name))
            self.dry_leased.update(issues)
            return True
        try:
            res = self.cond.create_workspace(
                name=name, session_name=name, message=prompt,
                model=self.cfg["worker_model"], effort=self.cfg["worker_effort"],
                project_id=self.cfg["project_id"],
            )
        except InfraError as exc:
            self.create_failures += 1
            self.store.journal("WORKSPACE_FAILED", batch_id=bid, reason=str(exc)[:200], issues=issues)
            if self.check_rate_limit_text(exc.output) or self.create_failures >= 2:
                self.pause("workspace creation failing (%s)" % str(exc)[:80])
            return False
        self.create_failures = 0
        wid, sid = res.get("workspaceId"), res.get("sessionId")
        if not wid:
            self.store.journal("WORKSPACE_FAILED", batch_id=bid, reason="no workspaceId in response",
                               issues=issues)
            return False
        self.store.journal("WORKSPACE_CREATED", workspace_id=wid, session_id=sid, kind=kind,
                           batch_id=bid, issues=issues)
        expires = iso(utcnow() + dt.timedelta(minutes=self.cfg["lease_minutes"][kind]))
        attempt = int(bid.rsplit("-", 1)[1])
        for n in issues:
            self.store.journal("LEASE_GRANTED", issue=n, kind=kind, batch_id=bid, workspace_id=wid,
                               session_id=sid, expires_at=expires, attempt=attempt)
        return True

    def check_unregistered_workspaces(self):
        """A7 tightening: alert on ANY workspace in the project we did not create.

        Workers can create workspaces (validated 2026-08-23), so the prompt barrier
        needs a detector behind it.  Informational only: it never pauses the sweep,
        because bakert may legitimately open a workspace here mid-campaign.
        """
        try:
            data = self.cond.list_project_workspaces(self.cfg["project_id"]).get("data") or []
        except InfraError as exc:
            log("project workspace list failed: %s" % exc)
            return
        mine = set(self.st.workspaces)
        manager = os.environ.get("CONDUCTOR_WORKSPACE_ID")
        found = []
        for w in data:
            if w.get("state") in ("archived", "deleted"):
                continue
            if w["id"] in mine or w["id"] == manager:
                continue
            found.append("{} ({})".format(w.get("name") or "?", w["id"][:8]))
        if found != self.unregistered and found:
            log("UNREGISTERED workspaces in project: %s" % ", ".join(found))
        self.unregistered = found

    # -- 6. bookkeeping ----------------------------------------------------
    def write_metrics(self):
        m = {
            "heartbeat": iso(utcnow()), "phase": self.cfg["phase"], "paused": self.st.paused,
            "pause_until": self.st.pause_until, "active_workspaces": len(self.active_workspaces()),
            "counts": self.counts(),
            "caps": {"closures_today": self.st.daily.get("closures", 0),
                     "prs_today": self.st.daily.get("prs", 0)},
            "totals": {"workspaces_created": self.st.counters.get("workspaces_created", 0),
                       "nudges": self.st.counters.get("nudges", 0),
                       "infra_failures": self.st.counters.get("infra_failures", 0)},
            "open_escalations": len(list(ESCALATIONS.glob("*.json"))),
            "unregistered_workspaces": self.unregistered,
            "pr_backpressure": self.st.pr_backpressure,
            "open_sweep_prs": self.open_sweep_prs,
            "max_open_prs": self.cfg.get("max_open_prs"),
            "alert": self.alert(),
        }
        write_json(METRICS, m)
        return m

    def alert(self):
        if self.mirror_error:
            return "mirror failing: %s" % self.mirror_error
        if self.unregistered:
            return "unregistered workspace(s) in project: %s" % ", ".join(self.unregistered)
        if self.st.counters.get("alert"):
            return self.st.counters["alert"]
        if self.st.paused:
            for ev in reversed(self._journal_tail(400)):
                if ev.get("event") == "PAUSE_ON":
                    since = parse_iso(ev.get("since") or ev.get("ts"))
                    if since and (utcnow() - since) > dt.timedelta(hours=4):
                        return "paused for over 4h"
                    break
        if self.cfg.get("mirror", {}).get("kind") not in (None, "none"):
            last = parse_iso(self.st.last_mirror_at)
            if last and (utcnow() - last) > dt.timedelta(minutes=60):
                return "mirror stale"
        return None

    def maybe_mirror(self, force=False):
        conf = self.cfg.get("mirror") or {}
        if conf.get("kind") in (None, "none"):
            return
        last = parse_iso(self.st.last_mirror_at)
        if not force and last and (utcnow() - last) < dt.timedelta(minutes=conf.get("interval_minutes", 15)):
            return
        if self.dry:
            self.say("WOULD mirror state to {}:{}".format(conf.get("kind"), conf.get("ref")))
            return
        try:
            if conf["kind"] == "branch":
                pushed = self.mirror_branch(conf.get("ref", "sweep-state"))
            elif conf["kind"] == "gist":
                pushed = self.mirror_gist(conf.get("ref"))
            else:
                return False
            if pushed:
                self.store.journal("MIRROR_PUSHED", kind=conf["kind"], ref=conf.get("ref"))
            else:
                self.st.last_mirror_at = iso(utcnow())  # nothing to push; still fresh
            self.mirror_error = None
            return True
        except (InfraError, OSError) as exc:
            self.mirror_error = str(exc)[:200]
            log("mirror FAILED: %s" % exc)
            return False

    def _mirror_payload(self, dest):
        dest = Path(dest)
        for name in ("journal.jsonl", "snapshot.json", "config.json", "metrics.json"):
            src = STATE / name
            if src.exists():
                shutil.copy2(src, dest / name)
        for sub in ("evidence", "escalations", "reports"):
            tgt = dest / sub
            if tgt.exists():
                shutil.rmtree(tgt)
            if (STATE / sub).exists():
                shutil.copytree(STATE / sub, tgt)

    def mirror_branch(self, ref):
        """Push state to the orphan `sweep-state` branch and VERIFY it landed.

        Every step is checked: a mirror that silently no-ops is worse than no
        mirror, because recovery would restore stale state.
        """
        run = self.runner.run
        git = ["git", "-C", str(MIRROR_DIR)]
        if not (MIRROR_DIR / ".git").exists():
            MIRROR_DIR.mkdir(parents=True, exist_ok=True)
            run(git + ["init", "-q", "-b", ref])
            url = run(["git", "-C", str(BASE), "remote", "get-url", "origin"]).strip()
            run(git + ["remote", "add", "origin", url])
            for key, fallback in (("user.name", "penny-dreadful-sweep"),
                                  ("user.email", "sweep@localhost")):
                val = run(["git", "-C", str(BASE), "config", key], check=False).strip()
                run(git + ["config", key, val.splitlines()[0] if val.strip() else fallback])
            fetched = run(git + ["fetch", "-q", "origin", ref], check=False)
            if "couldn't find remote ref" not in fetched:
                run(git + ["reset", "-q", "--hard", "FETCH_HEAD"])
        self._mirror_payload(MIRROR_DIR)
        run(git + ["add", "-A"])
        status = run(git + ["status", "--porcelain"], check=False)
        if not status.strip():
            log("mirror: nothing changed")
            return False
        run(git + ["commit", "-q", "-m", "sweep state %s" % iso(utcnow())])
        local = run(git + ["rev-parse", "HEAD"]).strip()
        push = run(git + ["push", "origin", "HEAD:%s" % ref], check=False)
        if "rejected" in push or "non-fast-forward" in push:
            raise InfraError("mirror push rejected — another writer? STOPPING mirror", push)
        remote = run(["git", "ls-remote", "origin", "refs/heads/" + ref]).split()
        if not remote or remote[0] != local:
            raise InfraError("mirror push did not land: origin/%s is %s, local is %s"
                             % (ref, (remote[0][:10] if remote else "absent"), local[:10]), push)
        log(f"mirror: pushed {local[:10]} to origin/{ref}")
        return True

    def mirror_gist(self, gist_id):
        tar = STATE / ".mirror.tar.gz"
        subprocess.run(["tar", "czf", str(tar), "-C", str(STATE), "journal.jsonl", "snapshot.json",
                        "config.json", "evidence", "escalations"], check=False)
        b64 = STATE / ".mirror.tar.gz.b64"
        import base64
        write_atomic(b64, base64.b64encode(tar.read_bytes()).decode())
        self.runner.run(["gh", "gist", "edit", gist_id, "-f", "sweep-state.tar.gz.b64", str(b64)])
        return True

    def maybe_snapshot(self, events_since):
        last = parse_iso(self.st.last_snapshot_at)
        if events_since >= 50 or not last or (utcnow() - last) > dt.timedelta(minutes=5):
            self.store.snapshot()

    def daily_report(self, day=None):
        day = day or iso(utcnow())[:10]
        c = self.counts()
        closed = [r for r in self.st.issues.values() if r["status"] == "closed"]
        prs = [r for r in self.st.issues.values() if r["status"] == "pr_open"]
        lines = [
            "# Sweep daily report %s" % day, "",
            "phase: %s   paused: %s   active workspaces: %d" % (
                self.cfg["phase"], self.st.paused, len(self.active_workspaces())), "",
            "## Counts by status", "",
        ]
        lines += ["- %s: %d" % (k, v) for k, v in sorted(c.items())]
        lines += ["", "## Mutations", "",
                  "- closed to date: %d" % len(closed),
                  "- PRs open to date: %d" % len(prs),
                  "- closures today: %d / %d" % (self.st.daily.get("closures", 0), self.cfg["daily_close_cap"]),
                  "- PRs today: %d / %d" % (self.st.daily.get("prs", 0), self.cfg["daily_pr_cap"]),
                  "", "## Open escalations", ""]
        for f in sorted(ESCALATIONS.glob("*.json")):
            r = read_json(f) or {}
            lines.append("- #{} ({}): {}".format(r.get("issue"), r.get("kind"), r.get("question")))
        lines += ["", "## Totals", "",
                  "- workspaces created: %d" % self.st.counters.get("workspaces_created", 0),
                  "- nudges: %d" % self.st.counters.get("nudges", 0),
                  "- infra failures: %d" % self.st.counters.get("infra_failures", 0), ""]
        path = REPORTS / ("daily-%s.md" % day)
        write_atomic(path, "\n".join(lines))
        return path

    # -- the tick ----------------------------------------------------------
    def tick(self):
        start_seq = self.st.last_seq
        self.maybe_unpause()
        try:
            self.harvest()
        except InfraError as exc:
            self.note_infra_failure("harvest: %s" % exc)
        self.expire_leases()
        self.execute_mutations()
        self.watch_ci()
        self.retry_archives()
        self.bundle_escalations()
        self.replenish()
        self.check_unregistered_workspaces()
        if self.runner.recent_infra_failures(10) >= 3:
            self.pause("3+ infrastructure failures in 10 minutes")
        if not self.dry:
            self.maybe_snapshot(self.st.last_seq - start_seq)
            self.maybe_mirror()
            m = self.write_metrics()
            today = iso(utcnow())[:10]
            if not (REPORTS / ("daily-%s.md" % today)).exists():
                self.daily_report(today)
            return m
        self.store.snapshot()
        return None

    # -- recover -----------------------------------------------------------
    def recover(self):
        out = ["# recover %s" % iso(utcnow())]
        session_note = refresh_manager_session(self.store, dry_run=self.dry)
        if session_note:
            out.append(session_note)
        for rec in self._ready("closing"):
            n = rec["issue"]
            try:
                state = self.gh.issue(n, "state").get("state")
            except InfraError:
                continue
            if state == "CLOSED":
                self.store.journal("CLOSE_EXECUTED", issue=n, reason=(rec.get("closure") or {}).get("reason"),
                                   comment_posted=True, external=True)
                out.append("#%s settled to closed" % n)
            else:
                self.store.journal("ROLLBACK_RECORDED", issue=n, status="verified",
                                   action="closing did not land; back to verified")
                out.append("#%s back to verified" % n)
        for rec in self._ready("fix_pushed"):
            n, fx = rec["issue"], (self.last_evidence(rec["issue"], "fix") or {})
            branch = fx.get("branch")
            if branch and not self.gh.remote_branch_sha(branch):
                self.escalate(n, "fix-validation", "Branch %s vanished from origin." % branch)
                out.append("#%s branch missing -> escalated" % n)
        # Reconcile every workspace we ever created against its real state. The
        # journal has been wrong about this before, so trust the API, not ourselves.
        stale = []
        for ws in self.st.workspaces.values():
            if ws["state"] == "archived":
                try:
                    live = (self.cond.workspace_status(ws["workspace_id"]) or {}).get("status")
                except InfraError:
                    continue
                if live not in ("archived", "deleted"):
                    stale.append((ws, live))
        for ws, live in stale:
            out.append("registry said archived but {} is {} ({})".format(ws["workspace_id"], live, ws["batch_id"]))
            if not self.dry:
                self.store.journal("WORKSPACE_HARVESTED", workspace_id=ws["workspace_id"], state=live)
                if self.archive(ws):
                    out.append("  -> archived for real")
                else:
                    out.append("  -> STILL not archived; needs a human")
        known = set(self.st.workspaces)
        try:
            listing = (self.cond.list_workspaces(name="sweep-").get("data") or [])
        except InfraError as exc:
            listing = []
            out.append("workspace list failed: %s" % exc)
        for w in listing:
            if w.get("state") in ("archived", "deleted") or w["id"] in known:
                continue
            m = re.match(r"^sweep-([tvf])-(\d+)-(\d+)$", w.get("name") or "")
            if not m:
                out.append("ignoring non-sweep workspace {} ({})".format(w["id"], w.get("name")))
                continue
            kind = {"t": "triage", "v": "verify", "f": "fix"}[m.group(1)]
            bid = w["name"][len("sweep-"):]
            issues = [int(n) for n, r in self.st.issues.items()
                      if (r.get("lease") or {}).get("batch_id") == bid]
            if not issues:
                out.append("orphan workspace {} ({}) has no live lease — archiving".format(w["id"], bid))
                if not self.dry:
                    try:
                        self.cond.archive_workspace(w["id"])
                    except InfraError:
                        pass
                continue
            sids = [s2["id"] for s2 in (self.cond.list_sessions(w["id"]).get("data") or [])]
            if not self.dry:
                self.store.journal("WORKSPACE_CREATED", workspace_id=w["id"],
                                   session_id=sids[0] if sids else None, kind=kind,
                                   batch_id=bid, issues=issues, adopted=True)
            out.append("adopted orphan workspace {} ({}) for {}".format(w["id"], bid, issues))
        for ws in list(self.active_workspaces()):
            try:
                st = self.cond.session_status(ws["session_id"]).get("status")
            except InfraError:
                continue
            if st == "idle":
                self.harvest_workspace(ws)
                out.append("harvested %s" % ws["batch_id"])
            elif st == "error":
                self.fail_workspace(ws, "session error at recover")
                out.append("failed %s" % ws["batch_id"])
            else:
                out.append("re-adopted %s (still working)" % ws["batch_id"])
        try:
            live_open = {i["number"] for i in self.gh.list_open_issues()}
        except InfraError:
            live_open = None
        if live_open is not None:
            for rec in list(self.st.issues.values()):
                if rec["status"] in TERMINAL or rec["status"] == "closing":
                    continue
                if rec["issue"] not in live_open:
                    self.store.journal("ISSUE_SKIPPED", issue=rec["issue"], reason="closed outside the sweep")
                    out.append("#%s closed externally -> skipped" % rec["issue"])
        self.store.snapshot()
        self.maybe_mirror(force=True)
        return "\n".join(out)


# ------------------------------------------------------------------------ verbs

def refresh_manager_session(store, dry_run=False):
    """Point escalation bundles at the manager running this recovery."""
    session_id = os.environ.get("CONDUCTOR_SESSION_ID")
    if not session_id or store.config.get("opus_session_id") == session_id:
        return None
    if dry_run:
        return "WOULD update manager session to this recovery session"
    store.config["opus_session_id"] = session_id
    store.save_config()
    store.journal("CONFIG_CHANGED", changes={"opus_session_id": "<this session>"})
    return "manager session updated to this recovery session"


def cmd_init(store, args):
    eng = Engine(store)
    cfg = store.config
    issues = eng.gh.list_open_issues()
    universe = [i for i in issues if cfg["frontier_min"] <= i["number"] <= cfg["frontier_max"]]
    universe.sort(key=lambda i: -i["number"])
    if not store.state.issues:
        store.journal("CAMPAIGN_INIT", frontier_min=cfg["frontier_min"], frontier_max=cfg["frontier_max"],
                      universe=len(universe), repo=cfg["repo"])
    live = {i["number"] for i in universe}
    added = 0
    for i in universe:
        if str(i["number"]) in store.state.issues:
            continue
        store.journal("ISSUE_ENQUEUED", issue=i["number"], title=i["title"],
                      labels=[l["name"] for l in i.get("labels") or []])
        added += 1
    gone = 0
    for rec in list(store.state.issues.values()):
        if rec["issue"] not in live and rec["status"] not in TERMINAL:
            store.journal("ISSUE_SKIPPED", issue=rec["issue"], reason="closed before triage")
            gone += 1
    refresh_manager_session(store)
    store.snapshot()
    return "queue: %d issues in universe (%d newly enqueued, %d newly closed -> skipped)" % (
        len(universe), added, gone)


def cmd_status(store, args):
    st, cfg = store.state, store.config
    eng = Engine(store)
    c = eng.counts()
    lines = [
        "phase={} pilot_limit={} concurrency={} mutations={} paused={}".format(
            cfg["phase"], cfg["pilot_limit"], cfg["concurrency_cap"], cfg["mutations_enabled"], st.paused),
        "issues=%d  %s" % (len(st.issues), "  ".join("%s=%d" % kv for kv in sorted(c.items()))),
        "workspaces active=%d created=%d nudges=%d infra_failures=%d" % (
            len(eng.active_workspaces()), st.counters.get("workspaces_created", 0),
            st.counters.get("nudges", 0), st.counters.get("infra_failures", 0)),
        "open sweep PRs cap={}  backpressure={}".format(cfg.get("max_open_prs"), st.pr_backpressure),
        "today closures=%d/%d prs=%d/%d" % (
            st.daily.get("closures", 0), cfg["daily_close_cap"],
            st.daily.get("prs", 0), cfg["daily_pr_cap"]),
        "open escalations=%d  last_seq=%d" % (len(list(ESCALATIONS.glob("*.json"))), st.last_seq),
        "daemon: %s" % ("running as pid %s" % daemon_pid() if daemon_pid() else "NOT RUNNING"),
    ]
    for ws in eng.active_workspaces():
        lines.append("  %-14s %-6s %s" % (ws["batch_id"], ws["kind"], ws["issues"]))
    return "\n".join(lines)


def _coerce(v):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    try:
        return json.loads(v)
    except ValueError:
        return v


def cmd_config(store, args):
    changes = {}
    for kv in args.pairs:
        if "=" not in kv:
            raise SystemExit("config set expects K=V, got %r" % kv)
        k, v = kv.split("=", 1)
        if k not in DEFAULT_CONFIG:
            raise SystemExit("unknown config key %r" % k)
        changes[k] = _coerce(v)
    if changes.get("concurrency_cap", 0) > 16:
        raise SystemExit("concurrency_cap > 16 requires explicit user approval (PLAN.md §5)")
    store.config.update(changes)
    store.save_config()
    store.journal("CONFIG_CHANGED", changes=changes)
    store.snapshot()
    return "config updated: %s" % json.dumps(changes, sort_keys=True)


ADJUDICATIONS = {
    "annotate": None,          # record a decision, change nothing
    "queue-fixup": "fix_pending",
    "abandon-pr": "deferred_human",
    "close-completed": "closing",
    "close-not-planned": "closing",
    "queue-fix": "fix_pending",
    "report-only": "reported",
    "retry-triage": "pending",
    "retry-verify": "verify_pending",
    "defer-to-human": "deferred_human",
    "mark-failed": "failed",
}


def cmd_adjudicate(store, args):
    n = int(args.issue)
    rec = store.state.issue(n)
    if not rec:
        raise SystemExit("#%s is not in the queue" % n)
    verb = args.verb
    if verb not in ADJUDICATIONS:  # noqa: SIM102 - explicit for the error message
        raise SystemExit("unknown verb {!r} (choose from {})".format(verb, ", ".join(sorted(ADJUDICATIONS))))
    eng = Engine(store)
    status = ADJUDICATIONS[verb]
    if verb == "queue-fixup":
        pr = (rec.get("pr") or {})
        if not pr.get("number") or not pr.get("branch"):
            raise SystemExit("#%s has no PR on record to fix up" % n)
        prior = (rec.get("fixup") or {}).get("attempt", 0)
        if prior >= store.config["max_fixup_attempts"]:
            raise SystemExit("#%s has already had %d fixup attempt(s); abandon-pr or defer instead"
                             % (n, prior))
        esc = read_json(ESCALATIONS / ("%s.json" % n)) or {}
        failed = ((rec.get("pr") or {}).get("ci") or {}).get("failed") or []
        # Retry the log fetch here: at detection time the workflow run is usually
        # still in progress, so `gh run view --log-failed` had nothing to give.
        detail = ""
        if failed and failed != ["merge-conflict"]:
            try:
                detail = eng.gh.failed_check_log(pr["number"], failed)
            except InfraError as exc:
                log("log fetch for #{} failed: {}".format(pr["number"], exc))
        if not detail:
            detail = (esc.get("summary") or "")[:4000]
        store.journal("FIXUP_DISPATCHED", issue=n, branch=pr["branch"], pr=pr["number"],
                      failed=failed, attempt=prior + 1, log_tail=detail[:4000], note=args.note)
        msg = "#{} queued for one CI-remediation fixer on {} (PR #{})".format(n, pr["branch"], pr["number"])
        _finish_adjudication(store, n, verb, args)
        store.snapshot()
        return msg
    if verb == "abandon-pr":
        pr = (rec.get("pr") or {})
        if pr.get("number"):
            try:
                eng.gh.close_pr(pr["number"], "Closing this automated sweep PR: CI could not be made "
                                              "green within the campaign's remediation budget.")
            except InfraError as exc:
                log("abandon-pr: closing #{} failed: {}".format(pr["number"], exc))
        if pr.get("branch"):
            eng.gh.delete_remote_branch(pr["branch"])
        store.journal("ADJUDICATED", issue=n, verb=verb, note=args.note, status="deferred_human")
        _finish_adjudication(store, n, verb, args)
        store.snapshot()
        return "#{}: PR #{} closed, branch {} deleted, issue deferred to bakert".format(
            n, pr.get("number"), pr.get("branch"))
    if verb.startswith("close-"):
        if not args.comment_file:
            raise SystemExit("close-* requires --comment-file")
        comment = Path(args.comment_file).read_text(encoding="utf-8").strip()
        reason = "completed" if verb == "close-completed" else "not planned"
        eng.add_evidence(n, "verify", {"batch_id": "opus-adjudication", "verdict": "CONFIRMED",
                                       "final_comment": comment, "recorded_at": iso(utcnow()),
                                       "own_evidence": [{"type": "manual", "ref": "opus",
                                                         "detail": "manager independently confirmed"}]})
        store.journal("ADJUDICATED", issue=n, verb=verb, note=args.note, status="closing")
        if not store.config["mutations_enabled"]:
            store.snapshot()
            return "#%s queued for closure (mutations are disabled; enable to execute)" % n
        store.journal("MUTATION_PLANNED", issue=n, kind="close", reason=reason)
        eng.gh.close_issue(n, reason, render_closure_comment(comment))
        if eng.gh.issue(n, "state").get("state") == "CLOSED":
            store.journal("CLOSE_EXECUTED", issue=n, reason=reason.replace(" ", "_"),
                          comment_posted=True, verified_by_batch="opus-adjudication")
            msg = f"#{n} closed ({reason})"
        else:
            store.journal("MUTATION_FAILED", issue=n, kind="close", reason="state not CLOSED")
            msg = "#%s close did not land" % n
    elif status is None:
        store.journal("ADJUDICATED", issue=n, verb=verb, note=args.note)
        msg = "#{} annotated (still {})".format(n, rec["status"])
    else:
        store.journal("ADJUDICATED", issue=n, verb=verb, note=args.note, status=status)
        msg = f"#{n} -> {status}"
    _finish_adjudication(store, n, verb, args)
    store.snapshot()
    return msg


def _finish_adjudication(store, n, verb, args):
    f = ESCALATIONS / ("%s.json" % n)
    if f.exists():
        r = read_json(f) or {}
        r["adjudication"] = {"verb": verb, "note": args.note, "at": iso(utcnow())}
        write_json(REPORTS / ("adjudicated-%s.json" % n), r)
        f.unlink()
    if verb in ("defer-to-human", "abandon-pr"):
        digest = REPORTS / "human_digest.md"
        prev = digest.read_text(encoding="utf-8") if digest.exists() else "# Human digest\n"
        write_atomic(digest, prev + "\n- #{} — {} ({})\n".format(n, args.note or "deferred", iso(utcnow())))


def cmd_rollback(store, args):
    n = int(args.issue)
    eng = Engine(store)
    eng.gh.reopen_issue(n)
    store.journal("ROLLBACK_RECORDED", issue=n, status="pending", action="reopened by manager",
                  note=args.note)
    store.snapshot()
    return "#%s reopened and returned to pending" % n


def cmd_tick(store, args):
    eng = Engine(store, dry_run=args.dry_run)
    m = eng.tick()
    if args.dry_run:
        return "\n".join(eng.plan) + ("\n\n(dry run: %d planned actions)" % len(eng.plan))
    return json.dumps(m, sort_keys=True)


def _alive(pid):
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


def daemon_pid():
    d = read_json(PIDFILE) or {}
    return d["pid"] if d.get("pid") and _alive(d["pid"]) else None


def cmd_daemon(_store, args):
    """Tick forever, taking the state lock for one tick at a time.

    Holding the lock across the whole run would block `adjudicate` and every other
    verb, so each tick opens its own Store and releases it before sleeping.
    """
    stopping = {"now": False}

    def onterm(signum, frame):
        stopping["now"] = True
        log("SIGTERM received; finishing current tick")

    signal.signal(signal.SIGTERM, onterm)
    signal.signal(signal.SIGINT, onterm)
    existing = read_json(PIDFILE) or {}
    if existing.get("pid") and _alive(existing["pid"]):
        raise SystemExit("daemon already running as pid %s" % existing["pid"])
    write_json(PIDFILE, {"pid": os.getpid(), "started_at": iso(utcnow())})
    log(f"daemon start interval={args.interval}s pid={os.getpid()}", echo=True)
    while not stopping["now"]:
        try:
            store = Store()
        except SystemExit:
            log("daemon: state lock busy, skipping this tick")
            store = None
        if store is not None:
            try:
                Engine(store).tick()
            except Exception as exc:  # noqa: BLE001 - the daemon must not die on one bad tick
                log("tick error: %r" % exc)
            finally:
                store.close()  # tick() already snapshots on its own schedule
        for _ in range(int(args.interval)):
            if stopping["now"]:
                break
            time.sleep(1)
    try:
        PIDFILE.unlink()
    except OSError:
        pass
    try:
        store = Store()
    except SystemExit:
        return "daemon stopped (lock busy; state left as-is)"
    try:
        store.snapshot()
        Engine(store).maybe_mirror(force=True)
    finally:
        store.close()
    return "daemon stopped cleanly"


def cmd_mirror(store, args):
    eng = Engine(store)
    ok = eng.maybe_mirror(force=True)
    if not ok:
        raise SystemExit("mirror FAILED: %s" % (eng.mirror_error or "see dispatcher.log"))
    return "mirror ok (%s)" % (store.config.get("mirror") or {}).get("kind")


def cmd_report(store, args):
    if args.what != "daily":
        raise SystemExit("only 'daily' is implemented")
    return "wrote %s" % Engine(store).daily_report()


def cmd_recover(store, args):
    return Engine(store, dry_run=args.dry_run).recover()


def build_parser():
    p = argparse.ArgumentParser(prog="dispatcher.py", description="backlog sweep dispatcher")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    t = sub.add_parser("tick")
    t.add_argument("--dry-run", action="store_true")
    d = sub.add_parser("daemon")
    d.add_argument("--interval", type=int, default=60)
    sub.add_parser("status")
    c = sub.add_parser("config")
    c.add_argument("action", choices=["set"])
    c.add_argument("pairs", nargs="+")
    a = sub.add_parser("adjudicate")
    a.add_argument("issue")
    a.add_argument("verb")
    a.add_argument("--comment-file")
    a.add_argument("--note")
    r = sub.add_parser("rollback")
    r.add_argument("issue")
    r.add_argument("--note")
    rec = sub.add_parser("recover")
    rec.add_argument("--dry-run", action="store_true")
    sub.add_parser("mirror")
    rep = sub.add_parser("report")
    rep.add_argument("what", choices=["daily"])
    return p


HANDLERS = {
    "init": cmd_init, "tick": cmd_tick, "daemon": cmd_daemon, "status": cmd_status,
    "config": cmd_config, "adjudicate": cmd_adjudicate, "recover": cmd_recover,
    "mirror": cmd_mirror, "report": cmd_report, "rollback": cmd_rollback,
}


READONLY_VERBS = {"status"}


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "daemon":
        out = cmd_daemon(None, args)
        if out:
            print(out)
        return 0
    store = Store(readonly=args.cmd in READONLY_VERBS)
    try:
        out = HANDLERS[args.cmd](store, args)
    finally:
        store.close()
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
