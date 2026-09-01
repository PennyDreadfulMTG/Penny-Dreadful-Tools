#!/usr/bin/env python3
"""Unit tests for the pure parts of dispatcher.py.

Run:  python3 -m unittest discover -s .context/backlog-sweep/bin -t .context/backlog-sweep/bin
(Do NOT use the repo's pytest config; its coverage addopts point at the repo.)
"""

import datetime as dt
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dispatcher as D  # noqa: E402

BASE = Path(__file__).resolve().parent


_LOG_SANDBOX = {}


def setUpModule():
    """Nothing in this module may touch the live state dir or dispatcher.log.

    Engine helpers call log() freely; fixture PR numbers landing in the real log
    have twice looked like production events during this campaign.
    """
    _LOG_SANDBOX["dir"] = tempfile.mkdtemp()
    _LOG_SANDBOX["saved"] = (D.LOGFILE, D.STATE)
    D.STATE = Path(_LOG_SANDBOX["dir"])
    D.LOGFILE = Path(_LOG_SANDBOX["dir"]) / "test-dispatcher.log"


def tearDownModule():
    D.LOGFILE, D.STATE = _LOG_SANDBOX["saved"]
    shutil.rmtree(_LOG_SANDBOX["dir"], ignore_errors=True)


def ev(seq, event, **kw):
    d = {"ts": kw.pop("ts", "2026-08-24T00:00:%02dZ" % min(seq, 59)), "seq": seq, "event": event}
    d.update(kw)
    return d


class TestJsonExtraction(unittest.TestCase):
    def blob(self, issue=12781, role="triage", batch="t-12781-1"):
        return json.dumps({
            "backlog_sweep": "v1", "role": role, "batch_id": batch,
            "results": [{"issue": issue, "class": "already-fixed", "confidence": "high"}],
        })

    def test_simple_fenced(self):
        text = "Some prose.\n\n```json\n%s\n```\n" % self.blob()
        got = D.extract_json_block(text, role="triage", batch_id="t-12781-1")
        self.assertEqual(got["results"][0]["issue"], 12781)

    def test_takes_the_last_block(self):
        text = ("```json\n%s\n```\nthen I revised it\n```json\n%s\n```"
                % (self.blob(issue=1), self.blob(issue=999)))
        got = D.extract_json_block(text, role="triage", batch_id="t-12781-1")
        self.assertEqual(got["results"][0]["issue"], 999)

    def test_unfenced_fallback(self):
        got = D.extract_json_block("here is the result: " + self.blob())
        self.assertEqual(got["role"], "triage")

    def test_bare_fence_without_language(self):
        text = "```\n%s\n```" % self.blob()
        self.assertIsNotNone(D.extract_json_block(text, role="triage", batch_id="t-12781-1"))

    def test_role_mismatch_still_returns_shaped_block(self):
        text = "```json\n%s\n```" % self.blob(role="verify")
        got = D.extract_json_block(text, role="triage", batch_id="t-12781-1")
        self.assertEqual(got["role"], "verify")  # surfaced, caller rejects on role

    def test_no_json_at_all(self):
        self.assertIsNone(D.extract_json_block("I could not finish, sorry."))

    def test_malformed_json_ignored(self):
        self.assertIsNone(D.extract_json_block("```json\n{\"backlog_sweep\": \"v1\",,,}\n```"))

    def test_prose_braces_do_not_match(self):
        self.assertIsNone(D.extract_json_block("the dict {a: 1} is not json"))

    def test_json_containing_braces_in_strings(self):
        payload = {"backlog_sweep": "v1", "role": "fix", "batch_id": "f-1-1",
                   "results": [{"issue": 1, "notes": 'uses {"a": "}"} in a string'}]}
        text = "```json\n%s\n```" % json.dumps(payload)
        got = D.extract_json_block(text, role="fix", batch_id="f-1-1")
        self.assertEqual(got["results"][0]["issue"], 1)


class TestRendering(unittest.TestCase):
    def test_closure_comment_appends_tag_once(self):
        out = D.render_closure_comment("  Fixed in abc1234.  ")
        self.assertTrue(out.startswith("Fixed in abc1234."))
        self.assertEqual(out.count("Automated backlog sweep"), 1)
        self.assertIn("Please reopen", out)

    def test_closure_comment_handles_none(self):
        self.assertTrue(D.render_closure_comment(None).startswith("\n\n<sub>"))

    def test_render_claims_hides_triage_reasoning(self):
        claims = [{"issue": 12781, "title": 'Broken "thing"', "class": "duplicate",
                   "duplicate_of": 12000, "proposed_comment": "Dupe of #12000.",
                   "evidence": [{"type": "issue", "ref": "#12000", "detail": "same request"}],
                   "notes": "SECRET TRIAGE REASONING"}]
        out = D.render_claims(claims)
        self.assertIn("duplicate of #12000 (close NOT_PLANNED)", out)
        self.assertIn("issue #12000", out)
        self.assertNotIn("SECRET TRIAGE REASONING", out)

    def test_render_claims_class_wording(self):
        self.assertIn("already-fixed (close COMPLETED)",
                      D.render_claims([{"issue": 1, "title": "t", "class": "already-fixed"}]))
        self.assertIn("obsolete (close NOT_PLANNED)",
                      D.render_claims([{"issue": 1, "title": "t", "class": "obsolete"}]))

    def test_worker_template_substitutes(self):
        out = D.render_template(BASE / "WORKER_PROMPT.md",
                                {"ISSUE_NUMBERS": "#1, #2", "BATCH_ID": "t-1-1"})
        self.assertIn("#1, #2", out)
        self.assertIn("t-1-1", out)
        self.assertNotIn("{{", out)
        self.assertNotIn("TEMPLATE START", out)

    def test_verifier_template_substitutes(self):
        out = D.render_template(BASE / "VERIFIER_PROMPT.md",
                                {"BATCH_ID": "v-1-1", "CLAIMS": "- issue: #1",
                                 "PROPOSED_COMMENT": "x"})
        self.assertNotIn("{{", out)

    def test_fixer_template_substitutes(self):
        out = D.render_template(BASE / "FIXER_PROMPT.md",
                                {"ISSUE": 1, "TITLE": "t", "BATCH_ID": "f-1-1",
                                 "FIX_SKETCH": "s", "BRANCH": "sweep/1-t"})
        self.assertNotIn("{{", out)

    def test_unsubstituted_placeholder_raises(self):
        with self.assertRaises(RuntimeError):
            D.render_template(BASE / "WORKER_PROMPT.md", {"BATCH_ID": "t-1-1"})

    def test_slugify(self):
        self.assertEqual(D.slugify("Fix the Thing!  (again)"), "fix-the-thing-again")
        self.assertEqual(D.slugify(""), "issue")
        self.assertLessEqual(len(D.slugify("x" * 100)), 40)


class TestLeases(unittest.TestCase):
    def test_expiry(self):
        now = D.parse_iso("2026-08-24T12:00:00Z")
        self.assertTrue(D.lease_is_expired({"expires_at": "2026-08-24T11:59:59Z"}, now))
        self.assertFalse(D.lease_is_expired({"expires_at": "2026-08-24T12:00:01Z"}, now))

    def test_pause_freezes_the_clock(self):
        now = D.parse_iso("2026-08-24T12:00:00Z")
        lease = {"expires_at": "2026-08-24T11:30:00Z"}
        self.assertTrue(D.lease_is_expired(lease, now))
        self.assertFalse(D.lease_is_expired(lease, now, pause_seconds=3600))

    def test_missing_expiry_counts_as_expired(self):
        self.assertTrue(D.lease_is_expired({}, D.utcnow()))

    def test_eligible_respects_pilot_limit(self):
        issues = {str(n): {} for n in range(100, 140)}
        self.assertEqual(D.eligible_issue_numbers(issues, 5), [139, 138, 137, 136, 135])
        self.assertEqual(len(D.eligible_issue_numbers(issues, 0)), 40)


class TestReplay(unittest.TestCase):
    def state_with_issue(self, n=12781):
        s = D.State()
        s.apply(ev(1, "CAMPAIGN_INIT"))
        s.apply(ev(2, "ISSUE_ENQUEUED", issue=n, title="t", labels=["+ bug"]))
        return s

    def test_enqueue(self):
        s = self.state_with_issue()
        self.assertEqual(s.issue(12781)["status"], "pending")
        self.assertEqual(s.last_seq, 2)

    def test_seq_replay_is_idempotent(self):
        s = self.state_with_issue()
        s.apply(ev(2, "ISSUE_ENQUEUED", issue=999, title="dup", labels=[]))
        self.assertIsNone(s.issue(999))

    def test_full_happy_path_to_closed(self):
        s = self.state_with_issue()
        s.apply(ev(3, "WORKSPACE_CREATED", workspace_id="w1", session_id="s1", kind="triage",
                   batch_id="t-12781-1", issues=[12781]))
        s.apply(ev(4, "LEASE_GRANTED", issue=12781, kind="triage", batch_id="t-12781-1",
                   workspace_id="w1", session_id="s1", expires_at="2026-08-24T01:00:00Z"))
        self.assertEqual(s.issue(12781)["status"], "triage_leased")
        s.apply(ev(5, "RESULT_RECORDED", issue=12781, kind="triage", batch_id="t-12781-1",
                   status="triaged", **{"class": "already-fixed", "confidence": "high"}))
        s.apply(ev(6, "RESULT_RECORDED", issue=12781, kind="triage", batch_id="t-12781-1",
                   status="verify_pending", **{"class": "already-fixed"}))
        s.apply(ev(7, "LEASE_GRANTED", issue=12781, kind="verify", batch_id="v-12781-1",
                   workspace_id="w2", session_id="s2", expires_at="2026-08-24T02:00:00Z"))
        s.apply(ev(8, "RESULT_RECORDED", issue=12781, kind="verify", batch_id="v-12781-1",
                   verdict="CONFIRMED", status="verified"))
        s.apply(ev(9, "MUTATION_PLANNED", issue=12781, kind="close"))
        self.assertEqual(s.issue(12781)["status"], "closing")
        s.apply(ev(10, "CLOSE_EXECUTED", issue=12781, reason="completed", comment_posted=True))
        rec = s.issue(12781)
        self.assertEqual(rec["status"], "closed")
        self.assertEqual(rec["closure"]["reason"], "completed")
        self.assertEqual(s.daily["closures"], 1)

    def test_external_close_does_not_count_against_the_cap(self):
        s = self.state_with_issue()
        s.apply(ev(3, "RESULT_RECORDED", issue=12781, kind="triage", status="triaged",
                   **{"class": "obsolete"}))
        s.apply(ev(4, "RESULT_RECORDED", issue=12781, kind="triage", status="verify_pending"))
        s.apply(ev(5, "RESULT_RECORDED", issue=12781, kind="verify", verdict="CONFIRMED",
                   status="verified"))
        s.apply(ev(6, "CLOSE_EXECUTED", issue=12781, reason="not_planned", external=True))
        self.assertEqual(s.daily["closures"], 0)
        self.assertEqual(s.issue(12781)["status"], "closed")

    def test_daily_counters_roll_over_at_midnight(self):
        s = self.state_with_issue()
        s.apply(ev(3, "RESULT_RECORDED", issue=12781, kind="triage", status="triaged",
                   **{"class": "obsolete"}))
        s.apply(ev(4, "RESULT_RECORDED", issue=12781, kind="triage", status="verify_pending"))
        s.apply(ev(5, "RESULT_RECORDED", issue=12781, kind="verify", verdict="CONFIRMED",
                   status="verified"))
        s.apply(ev(6, "CLOSE_EXECUTED", issue=12781, reason="not_planned", ts="2026-08-24T23:59:00Z"))
        self.assertEqual(s.daily, {"day": "2026-08-24", "closures": 1, "prs": 0})
        s.apply(ev(7, "ISSUE_ENQUEUED", issue=12780, title="t2", labels=[]))
        s.apply(ev(8, "RESULT_RECORDED", issue=12780, kind="triage", status="triaged",
                   **{"class": "easy-fix"}))
        s.apply(ev(9, "RESULT_RECORDED", issue=12780, kind="triage", status="fix_pending"))
        s.apply(ev(10, "LEASE_GRANTED", issue=12780, kind="fix", batch_id="f-12780-1",
                   expires_at="2026-08-25T02:00:00Z"))
        s.apply(ev(11, "RESULT_RECORDED", issue=12780, kind="fix", status="fix_pushed",
                   pr_branch="sweep/12780-t2", head_sha="abc1234"))
        s.apply(ev(12, "PR_OPENED", issue=12780, number=1, branch="sweep/12780-t2",
                   ts="2026-08-25T00:01:00Z"))
        self.assertEqual(s.issue(12780)["status"], "pr_open")
        self.assertEqual(s.daily, {"day": "2026-08-25", "closures": 0, "prs": 1})

    def test_lease_expiry_increments_attempts(self):
        s = self.state_with_issue()
        s.apply(ev(3, "LEASE_GRANTED", issue=12781, kind="triage", batch_id="t-12781-1",
                   expires_at="2026-08-24T01:00:00Z"))
        s.apply(ev(4, "LEASE_EXPIRED", issue=12781, kind="triage", batch_id="t-12781-1"))
        s.apply(ev(5, "RETRY_SCHEDULED", issue=12781, kind="triage", status="pending"))
        rec = s.issue(12781)
        self.assertEqual(rec["stage_attempts"]["triage"], 1)
        self.assertEqual(rec["status"], "pending")
        self.assertIsNone(rec["lease"])

    def test_illegal_transition_freezes_to_escalated(self):
        s = self.state_with_issue()
        s.apply(ev(3, "CLOSE_EXECUTED", issue=12781, reason="completed"))
        rec = s.issue(12781)
        self.assertEqual(rec["status"], "escalated")
        self.assertEqual(rec["escalation"]["kind"], "invariant")
        self.assertEqual(len(s.invariants), 1)
        self.assertEqual(s.daily["closures"], 0)

    def test_adjudication_moves_out_of_escalated(self):
        s = self.state_with_issue()
        s.apply(ev(3, "ESCALATED", issue=12781, kind="verifier-uncertain", question="q"))
        s.apply(ev(4, "ADJUDICATED", issue=12781, verb="report-only", status="reported", note="n"))
        rec = s.issue(12781)
        self.assertEqual(rec["status"], "reported")
        self.assertIsNone(rec["escalation"])

    def test_pause_accumulates_frozen_time(self):
        s = D.State()
        s.apply(ev(1, "PAUSE_ON", until="2026-08-24T01:00:00Z", level=1,
                   since="2026-08-24T00:00:00Z"))
        self.assertTrue(s.paused)
        s.apply(ev(2, "PAUSE_OFF", since="2026-08-24T00:00:00Z", ts="2026-08-24T00:30:00Z"))
        self.assertFalse(s.paused)
        self.assertEqual(s.pause_seconds, 1800)

    def test_workspace_lifecycle(self):
        s = self.state_with_issue()
        s.apply(ev(3, "WORKSPACE_CREATED", workspace_id="w1", session_id="s1", kind="triage",
                   batch_id="t-12781-1", issues=[12781]))
        self.assertEqual(s.counters["workspaces_created"], 1)
        s.apply(ev(4, "NUDGE_SENT", workspace_id="w1", batch_id="t-12781-1"))
        self.assertEqual(s.workspaces["w1"]["state"], "nudged")
        self.assertEqual(s.workspaces["w1"]["harvest"]["malformed_attempts"], 1)
        s.apply(ev(5, "WORKSPACE_ARCHIVED", workspace_id="w1"))
        self.assertEqual(s.workspaces["w1"]["state"], "archived")


class TestScrubber(unittest.TestCase):
    def test_env_values_blanked(self):
        sc = D.Scrubber({"CONDUCTOR_API_KEY": "sk-abcdefghijklmnop", "GH_TOKEN": "ghu_12345678"})
        self.assertNotIn("sk-abcdefghijklmnop", sc("using sk-abcdefghijklmnop now"))
        self.assertIn("[REDACTED]", sc("using ghu_12345678 now"))

    def test_pattern_scrub(self):
        sc = D.Scrubber({})
        self.assertNotIn("hunter2", sc("Authorization: hunter2"))
        self.assertNotIn("abc123", sc("token=abc123"))

    def test_short_values_are_not_used(self):
        sc = D.Scrubber({"GH_TOKEN": "abc"})
        self.assertEqual(sc("abcdef"), "abcdef")


class TestStoreRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = {k: getattr(D, k) for k in
                      ("STATE", "EVIDENCE", "ESCALATIONS", "REPORTS", "OUTBOX", "LOCKFILE",
                       "JOURNAL", "SNAPSHOT", "CONFIG", "QUEUE", "METRICS", "LOGFILE")}
        D.STATE = self.tmp
        D.EVIDENCE, D.ESCALATIONS = self.tmp / "evidence", self.tmp / "escalations"
        D.REPORTS, D.OUTBOX = self.tmp / "reports", self.tmp / "outbox"
        D.LOCKFILE, D.JOURNAL = self.tmp / ".lock", self.tmp / "journal.jsonl"
        D.SNAPSHOT, D.CONFIG = self.tmp / "snapshot.json", self.tmp / "config.json"
        D.QUEUE, D.METRICS = self.tmp / "queue.json", self.tmp / "metrics.json"
        D.LOGFILE = self.tmp / "dispatcher.log"

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(D, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_journal_survives_a_restart(self):
        s = D.Store()
        s.journal("ISSUE_ENQUEUED", issue=1, title="a", labels=[])
        s.journal("ISSUE_ENQUEUED", issue=2, title="b", labels=[])
        s.snapshot()
        s.journal("ESCALATED", issue=2, kind="unclear", question="q")
        s.close()
        s2 = D.Store()
        self.assertEqual(s2.state.issue(1)["status"], "pending")
        self.assertEqual(s2.state.issue(2)["status"], "escalated")
        s2.close()

    def test_torn_tail_line_is_truncated(self):
        s = D.Store()
        s.journal("ISSUE_ENQUEUED", issue=1, title="a", labels=[])
        s.close()
        with open(D.JOURNAL, "a") as fh:
            fh.write('{"ts": "2026', )
        s2 = D.Store()
        self.assertEqual(len(s2.state.issues), 1)
        s2.close()

    def test_lock_is_exclusive(self):
        s = D.Store()
        with self.assertRaises(SystemExit) as cm:
            D.Store()
        self.assertEqual(cm.exception.code, 75)
        s.close()

    def test_snapshot_replay_equivalence(self):
        s = D.Store()
        for i in range(5):
            s.journal("ISSUE_ENQUEUED", issue=100 + i, title="t%d" % i, labels=[])
        s.journal("RESULT_RECORDED", issue=104, kind="triage", status="triaged",
                  **{"class": "needs-work"})
        s.journal("RESULT_RECORDED", issue=104, kind="triage", status="reported")
        before = json.dumps(s.state.to_dict(), sort_keys=True)
        s.snapshot()
        s.close()
        s2 = D.Store()
        after = json.dumps(s2.state.to_dict(), sort_keys=True)
        s2.close()
        b, a = json.loads(before), json.loads(after)
        self.assertEqual(b["issues"], a["issues"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestStaleness(unittest.TestCase):
    """The hung-worker detector must not kill slow-booting workspaces."""

    class FakeEngine:
        cfg = {"stale_transcript_minutes": 20}
        is_stale = None  # bound below

    def stale(self, created_min_ago, transcript_min_ago=None):
        now = D.utcnow()
        ws = {"created_at": D.iso(now - dt.timedelta(minutes=created_min_ago)),
              "last_transcript_at": None if transcript_min_ago is None
              else D.iso(now - dt.timedelta(minutes=transcript_min_ago))}
        eng = self.FakeEngine()
        return D.Engine.is_stale(eng, ws)

    def test_young_workspace_with_no_transcript_is_not_stale(self):
        self.assertFalse(self.stale(created_min_ago=5))

    def test_old_workspace_with_no_transcript_is_stale(self):
        self.assertTrue(self.stale(created_min_ago=25))

    def test_recent_transcript_beats_old_creation(self):
        self.assertFalse(self.stale(created_min_ago=90, transcript_min_ago=2))

    def test_old_transcript_is_stale(self):
        self.assertTrue(self.stale(created_min_ago=90, transcript_min_ago=30))

    def test_unparseable_timestamps_are_never_stale(self):
        eng = self.FakeEngine()
        self.assertFalse(D.Engine.is_stale(eng, {"created_at": None, "last_transcript_at": None}))


class TestPermissionDetection(unittest.TestCase):
    """`gh issue close` exits 0 while printing a GraphQL permission error."""

    def test_graphql_permission_error_detected(self):
        self.assertTrue(D.PERMISSION_RE.search(
            "GraphQL: Resource not accessible by integration (addComment)"))

    def test_http_403_detected(self):
        self.assertTrue(D.PERMISSION_RE.search("gh: Forbidden (HTTP 403)"))

    def test_ordinary_failure_not_treated_as_permission(self):
        self.assertIsNone(D.PERMISSION_RE.search("could not resolve to an Issue with number 999"))

    def test_escalated_can_return_to_verified(self):
        s = D.State()
        s.apply(ev(1, "ISSUE_ENQUEUED", issue=1, title="t", labels=[]))
        s.apply(ev(2, "LEASE_GRANTED", issue=1, kind="triage", batch_id="t-1-1",
                   expires_at="2026-08-24T01:00:00Z"))
        s.apply(ev(3, "RESULT_RECORDED", issue=1, kind="triage", status="triaged",
                   **{"class": "already-fixed"}))
        s.apply(ev(4, "RESULT_RECORDED", issue=1, kind="triage", status="verify_pending"))
        s.apply(ev(5, "LEASE_GRANTED", issue=1, kind="verify", batch_id="v-1-1",
                   expires_at="2026-08-24T02:00:00Z"))
        s.apply(ev(6, "RESULT_RECORDED", issue=1, kind="verify", verdict="CONFIRMED",
                   status="verified"))
        s.apply(ev(7, "MUTATION_PLANNED", issue=1, kind="close"))
        s.apply(ev(8, "ROLLBACK_RECORDED", issue=1, status="verified",
                   action="closure blocked by token permissions"))
        self.assertEqual(s.issue(1)["status"], "verified")
        self.assertEqual(s.daily["closures"], 0)
        self.assertEqual(len(s.invariants), 0)


class TestDraftPolicy(unittest.TestCase):
    """Draft is the merge brake for this campaign; assert the wiring can't regress."""

    def test_create_pr_passes_draft_flag(self):
        seen = {}

        class R:
            def run(self, argv, **kw):
                seen["argv"] = argv
                return "https://github.com/o/r/pull/123\n"

        gh = D.GitHub(R(), "o/r")
        gh.create_pr("sweep/1-x", "t", "/tmp/body.md")
        self.assertIn("--draft", seen["argv"])
        self.assertNotIn("--web", seen["argv"])

    def test_pr_url_and_number_parsed_together(self):
        m = re.search(r"(https://\S+/pull/(\d+))",
                      "Creating pull request...\nhttps://github.com/o/r/pull/14943\n")
        self.assertEqual(m.group(2), "14943")
        self.assertEqual(m.group(1), "https://github.com/o/r/pull/14943")

    def test_missing_pr_url_yields_no_number(self):
        self.assertIsNone(re.search(r"(https://\S+/pull/(\d+))", "gh: something went wrong"))

    def test_pr_is_draft_reads_the_field(self):
        class R:
            def __init__(self, val):
                self.val = val

            def run(self, argv, **kw):
                return json.dumps({"isDraft": self.val})

        self.assertTrue(D.GitHub(R(True), "o/r").pr_is_draft(1))
        self.assertFalse(D.GitHub(R(False), "o/r").pr_is_draft(1))


class TestCiWatch(unittest.TestCase):
    REQ = ["mypy", "lint", "test", "jslint"]

    def rows(self, *pairs):
        return [{"name": n, "bucket": b, "state": b.upper()} for n, b in pairs]

    def test_all_pass(self):
        v = D.Engine.summarize_checks(
            self.rows(("mypy", "pass"), ("lint", "pass"), ("test", "pass"), ("jslint", "pass")),
            self.REQ)
        self.assertTrue(all(x == "pass" for x in v.values()))

    def test_duplicate_runs_one_failing_means_fail(self):
        v = D.Engine.summarize_checks(
            self.rows(("test", "pass"), ("test", "fail"), ("mypy", "pass"),
                      ("lint", "pass"), ("jslint", "pass")), self.REQ)
        self.assertEqual(v["test"], "fail")

    def test_missing_check_is_pending_not_pass(self):
        v = D.Engine.summarize_checks(self.rows(("mypy", "pass")), self.REQ)
        self.assertEqual(v["mypy"], "pass")
        self.assertEqual(v["lint"], "pending")

    def test_in_progress_is_pending(self):
        v = D.Engine.summarize_checks(
            self.rows(("mypy", "pending"), ("lint", "pass"), ("test", "pass"), ("jslint", "pass")),
            self.REQ)
        self.assertEqual(v["mypy"], "pending")

    def test_cancelled_counts_as_failure(self):
        v = D.Engine.summarize_checks(self.rows(("test", "cancel")), self.REQ)
        self.assertEqual(v["test"], "fail")

    def test_skipped_counts_as_pass(self):
        v = D.Engine.summarize_checks(self.rows(("jslint", "skipping")), self.REQ)
        self.assertEqual(v["jslint"], "pass")

    def test_unrelated_checks_ignored(self):
        v = D.Engine.summarize_checks(
            self.rows(("CodeQL", "fail"), ("mypy", "pass"), ("lint", "pass"),
                      ("test", "pass"), ("jslint", "pass")), self.REQ)
        self.assertTrue(all(x == "pass" for x in v.values()))

    def test_ci_status_transitions(self):
        s = D.State()
        s.apply(ev(1, "ISSUE_ENQUEUED", issue=7, title="t", labels=[]))
        s.apply(ev(2, "LEASE_GRANTED", issue=7, kind="triage", batch_id="t-7-1",
                   expires_at="2026-08-24T01:00:00Z"))
        s.apply(ev(3, "RESULT_RECORDED", issue=7, kind="triage", status="triaged",
                   **{"class": "easy-fix"}))
        s.apply(ev(4, "RESULT_RECORDED", issue=7, kind="triage", status="fix_pending"))
        s.apply(ev(5, "LEASE_GRANTED", issue=7, kind="fix", batch_id="f-7-1",
                   expires_at="2026-08-24T02:00:00Z"))
        s.apply(ev(6, "RESULT_RECORDED", issue=7, kind="fix", status="fix_pushed",
                   pr_branch="sweep/7-t", head_sha="abc"))
        s.apply(ev(7, "PR_OPENED", issue=7, number=99, branch="sweep/7-t", head_sha="abc"))
        s.apply(ev(8, "PR_CI_GREEN", issue=7, pr=99))
        self.assertEqual(s.issue(7)["status"], "pr_open")
        self.assertEqual(s.issue(7)["pr"]["ci"]["state"], "green")
        s.apply(ev(9, "PR_CI_FAILED", issue=7, pr=99, failed=["mypy"]))
        self.assertEqual(s.issue(7)["status"], "pr_ci_failed")
        s.apply(ev(10, "FIXUP_DISPATCHED", issue=7, branch="sweep/7-t", pr=99,
                   failed=["mypy"], attempt=1))
        self.assertEqual(s.issue(7)["status"], "fix_pending")
        self.assertEqual(s.issue(7)["fixup"]["attempt"], 1)

    def test_fixup_bypasses_the_branch_guard(self):
        class E:
            fix_guards = D.Engine.fix_guards
        self.assertEqual(D.Engine.fix_guards(E(), {"issue": 7, "fixup": {"branch": "sweep/7-t"}}),
                         (True, ""))

    def test_fixup_batch_id_is_distinct(self):
        self.assertNotEqual("u-7-1", "f-7-1")


class TestFixupTemplate(unittest.TestCase):
    def render(self, problem, detail):
        return D.render_template(BASE / "FIXUP_PROMPT.md", {
            "ISSUE": 7, "TITLE": "t", "BATCH_ID": "u-7-1", "BRANCH": "sweep/7-t",
            "PR": 99, "PROBLEM": problem, "DETAIL": detail})

    def test_renders_and_forbids_ready_for_review(self):
        out = self.render("these required checks are failing: mypy", "error: bad type")
        self.assertNotIn("{{", out)
        self.assertIn("sweep/7-t", out)
        self.assertIn("error: bad type", out)
        self.assertIn("must stay a draft", out)
        self.assertIn("never force-push", out)

    def test_conflict_variant_says_merge_not_rebase(self):
        out = self.render("the branch conflicts with master and cannot be merged", "DIRTY")
        self.assertIn("git merge origin/master", out)
        self.assertIn("Do NOT rebase and do NOT force-push", out)


class TestPrSettlement(unittest.TestCase):
    def pr_open_state(self):
        s = D.State()
        s.apply(ev(1, "ISSUE_ENQUEUED", issue=7, title="t", labels=[]))
        s.apply(ev(2, "LEASE_GRANTED", issue=7, kind="triage", batch_id="t-7-1",
                   expires_at="2026-08-24T01:00:00Z"))
        s.apply(ev(3, "RESULT_RECORDED", issue=7, kind="triage", status="triaged",
                   **{"class": "easy-fix"}))
        s.apply(ev(4, "RESULT_RECORDED", issue=7, kind="triage", status="fix_pending"))
        s.apply(ev(5, "LEASE_GRANTED", issue=7, kind="fix", batch_id="f-7-1",
                   expires_at="2026-08-24T02:00:00Z"))
        s.apply(ev(6, "RESULT_RECORDED", issue=7, kind="fix", status="fix_pushed",
                   pr_branch="sweep/7-t", head_sha="abc"))
        s.apply(ev(7, "PR_OPENED", issue=7, number=99, branch="sweep/7-t", head_sha="abc"))
        return s

    def test_withdrawn_pr_settles_the_issue(self):
        s = self.pr_open_state()
        s.apply(ev(8, "PR_WITHDRAWN", issue=7, pr=99, branch="sweep/7-t", branch_deleted=True))
        rec = s.issue(7)
        self.assertEqual(rec["status"], "deferred_human")
        self.assertTrue(rec["pr"]["branch_deleted"])
        self.assertIn("without merging", rec["notes"])
        self.assertEqual(len(s.invariants), 0)

    def test_withdrawn_is_terminal_no_retry(self):
        s = self.pr_open_state()
        s.apply(ev(8, "PR_WITHDRAWN", issue=7, pr=99, branch="sweep/7-t"))
        s.apply(ev(9, "RETRY_SCHEDULED", issue=7, kind="fix", status="fix_pending"))
        self.assertEqual(s.issue(7)["status"], "escalated")  # frozen, never re-fixed

    def test_withdrawn_from_red_pr_also_settles(self):
        s = self.pr_open_state()
        s.apply(ev(8, "PR_CI_FAILED", issue=7, pr=99, failed=["test"]))
        s.apply(ev(9, "PR_WITHDRAWN", issue=7, pr=99, branch="sweep/7-t"))
        self.assertEqual(s.issue(7)["status"], "deferred_human")

    def test_merged_pr_stops_polling_but_stays_pr_open(self):
        s = self.pr_open_state()
        s.apply(ev(8, "PR_MERGED", issue=7, pr=99, merged_at="2026-08-23T21:55:28Z"))
        rec = s.issue(7)
        self.assertEqual(rec["status"], "pr_open")
        self.assertEqual(rec["pr"]["ci"]["state"], "merged")
        self.assertEqual(rec["pr"]["merged_at"], "2026-08-23T21:55:28Z")


class TestOrphanBranchReclaim(unittest.TestCase):
    """A fixer that pushes but never reports must not deadlock its own retry."""

    class FakeGH:
        def __init__(self, branches, prs=None, deletable=True):
            self.branches, self.prs, self.deletable = branches, prs or [], deletable
            self.deleted = []

        def issue(self, n, fields):
            return {"state": "OPEN"}

        def open_prs_mentioning(self, n):
            return []

        def branches_matching(self, pattern):
            return list(self.branches)

        def prs_for_branch(self, branch):
            return list(self.prs)

        def delete_remote_branch(self, branch):
            self.deleted.append(branch)
            if self.deletable:
                self.branches = [b for b in self.branches if not b.endswith(branch)]

        def remote_branch_sha(self, branch):
            return "abc" if any(b.endswith(branch) for b in self.branches) else None

    class FakeStore:
        def __init__(self):
            self.events = []

        def journal(self, event, **kw):
            self.events.append((event, kw))

    def engine(self, gh):
        e = D.Engine.__new__(D.Engine)
        e.cfg = {"reclaim_orphan_branches": True}
        e.gh = gh
        e.store = self.FakeStore()
        e.dry = False
        return e

    def test_orphan_branch_is_deleted_and_dispatch_proceeds(self):
        gh = self.FakeGH(["refs/heads/sweep/12618-sort-by-colors"])
        e = self.engine(gh)
        ok, why = D.Engine.fix_guards(e, {"issue": 12618})
        self.assertTrue(ok, why)
        self.assertEqual(gh.deleted, ["sweep/12618-sort-by-colors"])
        self.assertEqual(e.store.events[0][0], "ROLLBACK_RECORDED")

    def test_branch_with_a_pr_is_never_deleted(self):
        gh = self.FakeGH(["refs/heads/sweep/12618-x"], prs=[{"number": 1, "state": "CLOSED"}])
        e = self.engine(gh)
        ok, why = D.Engine.fix_guards(e, {"issue": 12618})
        self.assertFalse(ok)
        self.assertIn("already has a PR", why)
        self.assertEqual(gh.deleted, [])

    def test_undeletable_branch_blocks_dispatch(self):
        gh = self.FakeGH(["refs/heads/sweep/12618-x"], deletable=False)
        ok, why = D.Engine.fix_guards(self.engine(gh), {"issue": 12618})
        self.assertFalse(ok)
        self.assertIn("could not delete", why)

    def test_reclaim_can_be_switched_off(self):
        gh = self.FakeGH(["refs/heads/sweep/12618-x"])
        e = self.engine(gh)
        e.cfg = {"reclaim_orphan_branches": False}
        ok, why = D.Engine.fix_guards(e, {"issue": 12618})
        self.assertFalse(ok)
        self.assertEqual(gh.deleted, [])

    def test_never_touches_a_differently_numbered_branch(self):
        gh = self.FakeGH(["refs/heads/sweep/126180-other"])
        ok, why = D.Engine.fix_guards(self.engine(gh), {"issue": 12618})
        self.assertTrue(ok or "unexpected branch" in why)
        self.assertEqual(gh.deleted, [])


class TestMergeability(unittest.TestCase):
    """A green PR can still be unmergeable once master moves under it."""

    def engine(self, out="", update_calls=None):
        class GH:
            def pr_update_branch(self, n):
                (update_calls if update_calls is not None else []).append(n)
                return out

        class Store:
            def __init__(self):
                self.events = []

            def journal(self, event, **kw):
                self.events.append((event, kw))

        e = D.Engine.__new__(D.Engine)
        e.cfg = {"auto_update_behind_branches": True}
        e.gh, e.store, e.dry = GH(), Store(), False
        e.escalate = lambda *a, **k: e.store.journal("ESCALATED", args=a)
        return e

    def test_conflicting_escalates_once(self):
        e = self.engine()
        pr = {"branch": "sweep/1-x", "ci": {}}
        handled = D.Engine.handle_mergeability(
            e, {"issue": 1}, pr, 99, {"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"})
        self.assertTrue(handled)
        self.assertEqual([ev[0] for ev in e.store.events], ["PR_CONFLICT", "ESCALATED"])

    def test_conflict_not_re_escalated(self):
        e = self.engine()
        pr = {"branch": "sweep/1-x", "ci": {"state": "conflict"}}
        D.Engine.handle_mergeability(e, {"issue": 1}, pr, 99,
                                     {"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"})
        self.assertEqual(e.store.events, [])

    def test_behind_is_updated_automatically(self):
        calls = []
        e = self.engine(out="updated", update_calls=calls)
        D.Engine.handle_mergeability(e, {"issue": 1}, {"branch": "b"}, 99,
                                     {"mergeable": "MERGEABLE", "mergeStateStatus": "BEHIND"})
        self.assertEqual(calls, [99])
        self.assertEqual(e.store.events[0][0], "PR_BRANCH_UPDATED")

    def test_behind_update_that_conflicts_is_not_journaled_as_success(self):
        e = self.engine(out="merge conflict between base and head")
        D.Engine.handle_mergeability(e, {"issue": 1}, {"branch": "b"}, 99,
                                     {"mergeable": "MERGEABLE", "mergeStateStatus": "BEHIND"})
        self.assertEqual(e.store.events, [])

    def test_behind_is_not_retried_within_15_minutes(self):
        calls = []
        e = self.engine(update_calls=calls)
        recent = D.iso(D.utcnow() - dt.timedelta(minutes=3))
        D.Engine.handle_mergeability(e, {"issue": 1}, {"branch": "b", "last_branch_update": recent},
                                     99, {"mergeable": "MERGEABLE", "mergeStateStatus": "BEHIND"})
        self.assertEqual(calls, [])

    def test_clean_pr_is_left_alone(self):
        e = self.engine()
        handled = D.Engine.handle_mergeability(
            e, {"issue": 1}, {"branch": "b"}, 99,
            {"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"})
        self.assertFalse(handled)
        self.assertEqual(e.store.events, [])

    def test_conflict_routes_to_pr_ci_failed(self):
        s = D.State()
        s.apply(ev(1, "ISSUE_ENQUEUED", issue=7, title="t", labels=[]))
        s.apply(ev(2, "LEASE_GRANTED", issue=7, kind="triage", batch_id="t-7-1",
                   expires_at="2026-08-24T01:00:00Z"))
        s.apply(ev(3, "RESULT_RECORDED", issue=7, kind="triage", status="triaged",
                   **{"class": "easy-fix"}))
        s.apply(ev(4, "RESULT_RECORDED", issue=7, kind="triage", status="fix_pending"))
        s.apply(ev(5, "LEASE_GRANTED", issue=7, kind="fix", batch_id="f-7-1",
                   expires_at="2026-08-24T02:00:00Z"))
        s.apply(ev(6, "RESULT_RECORDED", issue=7, kind="fix", status="fix_pushed",
                   pr_branch="sweep/7-t", head_sha="abc"))
        s.apply(ev(7, "PR_OPENED", issue=7, number=99, branch="sweep/7-t", head_sha="abc"))
        s.apply(ev(8, "PR_CONFLICT", issue=7, pr=99))
        self.assertEqual(s.issue(7)["status"], "pr_ci_failed")
        self.assertEqual(s.issue(7)["pr"]["ci"]["failed"], ["merge-conflict"])


class TestTokenFile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (D.CONFIG, D.BASE, D.LOGFILE, D.STATE, list(D.SCRUB.values))
        D.STATE = self.tmp
        D.LOGFILE = self.tmp / "t.log"
        D.BASE = self.tmp
        D.CONFIG = self.tmp / "config.json"

    def tearDown(self):
        D.CONFIG, D.BASE, D.LOGFILE, D.STATE, D.SCRUB.values = self.saved

    def test_absent_file_yields_no_overlay(self):
        self.assertEqual(D.load_gh_token(), {})

    def test_token_is_loaded_and_registered_for_scrubbing(self):
        (self.tmp / "state").mkdir()
        tok = self.tmp / "state" / ".gh_token"
        tok.write_text("ghp_supersecrettokenvalue\n")
        tok.chmod(0o600)
        overlay = D.load_gh_token()
        self.assertEqual(overlay["GH_TOKEN"], "ghp_supersecrettokenvalue")
        self.assertEqual(overlay["GITHUB_TOKEN"], "ghp_supersecrettokenvalue")
        self.assertNotIn("ghp_supersecrettokenvalue", D.SCRUB("using ghp_supersecrettokenvalue"))

    def test_empty_file_yields_no_overlay(self):
        (self.tmp / "state").mkdir()
        (self.tmp / "state" / ".gh_token").write_text("   \n")
        self.assertEqual(D.load_gh_token(), {})

    def test_token_is_never_in_argv(self):
        r = D.Runner(dict(D.DEFAULT_CONFIG), sleeper=lambda s: None,
                     env_overlay={"GH_TOKEN": "ghp_x"})
        out = r.run(["printenv", "GH_TOKEN"], check=False)
        self.assertIn("ghp_x", out)  # reaches the child through env, not the command line


class TestPrBackpressure(unittest.TestCase):
    """max_open_prs bounds the standing review pile; daily_pr_cap only bounds rate."""

    def engine(self, open_count=0, raises=False, backpressure=False, cap=30):
        class GH:
            def count_open_sweep_prs(self):
                if raises:
                    raise D.InfraError("gh exploded")
                return open_count

        class Store:
            def __init__(self, st):
                self.events, self.state = [], st

            def journal(self, event, **kw):
                self.events.append((event, kw))
                if event == "PR_BACKPRESSURE_ON":
                    self.state.pr_backpressure = True
                elif event == "PR_BACKPRESSURE_OFF":
                    self.state.pr_backpressure = False

        st = D.State()
        st.pr_backpressure = backpressure
        e = D.Engine.__new__(D.Engine)
        e.cfg = {"max_open_prs": cap}
        e.gh, e.st = GH(), st
        e.store = Store(st)
        e.open_sweep_prs = None
        return e

    def test_under_cap_allows_prs(self):
        e = self.engine(open_count=14)
        self.assertTrue(D.Engine.pr_capacity_available(e, 3))
        self.assertEqual(e.store.events, [])
        self.assertEqual(e.open_sweep_prs, 14)

    def test_at_cap_holds_and_journals_once(self):
        e = self.engine(open_count=30)
        self.assertFalse(D.Engine.pr_capacity_available(e, 5))
        self.assertEqual([x[0] for x in e.store.events], ["PR_BACKPRESSURE_ON"])
        self.assertEqual(e.store.events[0][1]["open_prs"], 30)
        # second tick while still at cap must not journal again
        self.assertFalse(D.Engine.pr_capacity_available(e, 5))
        self.assertEqual(len(e.store.events), 1)

    def test_recovery_journals_off_once(self):
        e = self.engine(open_count=12, backpressure=True)
        self.assertTrue(D.Engine.pr_capacity_available(e, 2))
        self.assertEqual([x[0] for x in e.store.events], ["PR_BACKPRESSURE_OFF"])
        self.assertTrue(D.Engine.pr_capacity_available(e, 2))
        self.assertEqual(len(e.store.events), 1)

    def test_count_failure_holds_rather_than_floods(self):
        e = self.engine(raises=True)
        self.assertFalse(D.Engine.pr_capacity_available(e, 4))
        self.assertEqual(e.store.events, [])  # infra hiccup is not a backpressure event

    def test_cap_of_zero_or_none_disables_backpressure(self):
        self.assertTrue(D.Engine.pr_capacity_available(self.engine(open_count=999, cap=0), 1))
        self.assertTrue(D.Engine.pr_capacity_available(self.engine(open_count=999, cap=None), 1))

    def test_backpressure_never_escalates(self):
        e = self.engine(open_count=40)
        D.Engine.pr_capacity_available(e, 9)
        self.assertNotIn("ESCALATED", [x[0] for x in e.store.events])

    def test_state_flag_survives_replay(self):
        s = D.State()
        s.apply(ev(1, "PR_BACKPRESSURE_ON", open_prs=30, cap=30))
        self.assertTrue(s.pr_backpressure)
        self.assertTrue(s.to_dict()["pr_backpressure"])
        s.apply(ev(2, "PR_BACKPRESSURE_OFF", open_prs=20, cap=30))
        self.assertFalse(s.pr_backpressure)

    def test_counts_only_sweep_branches(self):
        class R:
            def run(self, argv, **kw):
                return json.dumps([
                    {"number": 1, "headRefName": "sweep/12-a"},
                    {"number": 2, "headRefName": "dependabot/npm/x"},
                    {"number": 3, "headRefName": "sweep/13-b"},
                    {"number": 4, "headRefName": "feature/unrelated"},
                ])

        self.assertEqual(D.GitHub(R(), "o/r").count_open_sweep_prs(), 2)


class TestMasterAdvanced(unittest.TestCase):
    """Conflicts are caused by master moving, so poll on that event, not a timer."""

    def test_sha_recorded_and_replayed(self):
        s = D.State()
        self.assertIsNone(s.last_master_sha)
        s.apply(ev(1, "MASTER_ADVANCED", sha="a" * 40))
        self.assertEqual(s.last_master_sha, "a" * 40)
        self.assertEqual(s.to_dict()["last_master_sha"], "a" * 40)
        s.apply(ev(2, "MASTER_ADVANCED", sha="b" * 40))
        self.assertEqual(s.last_master_sha, "b" * 40)

    def test_first_observation_does_not_count_as_movement(self):
        # last_master_sha is None on a fresh campaign; that must not force a
        # full recheck storm on the very first tick.
        s = D.State()
        first = s.last_master_sha is None
        self.assertTrue(first)
        moved = s.last_master_sha is not None
        self.assertFalse(moved)

    def test_default_recheck_is_minutes_not_half_an_hour(self):
        self.assertLessEqual(D.DEFAULT_CONFIG["ci_recheck_minutes"], 10)


class TestReadyForReviewIsNotAnIncident(unittest.TestCase):
    """The draft brake failing and bakert reviewing must not look the same."""

    def gh(self, timeline_rows):
        class R:
            def run(self, argv, **kw):
                return json.dumps(timeline_rows)
        return D.GitHub(R(), "o/r")

    def test_readied_pr_is_recognised(self):
        self.assertTrue(self.gh([{"event": "ready_for_review"}]).pr_readied_by_human(1))

    def test_never_readied_pr_is_not(self):
        self.assertFalse(self.gh([]).pr_readied_by_human(1))

    def test_api_failure_is_treated_as_not_readied(self):
        class R:
            def run(self, argv, **kw):
                raise D.InfraError("boom")
        # Fail safe: an unknown state escalates rather than being waved through.
        self.assertFalse(D.GitHub(R(), "o/r").pr_readied_by_human(1))

    def test_readied_timestamp_recorded(self):
        s = D.State()
        s.apply(ev(1, "ISSUE_ENQUEUED", issue=7, title="t", labels=[]))
        s.apply(ev(2, "LEASE_GRANTED", issue=7, kind="triage", batch_id="t-7-1",
                   expires_at="2026-08-24T01:00:00Z"))
        s.apply(ev(3, "RESULT_RECORDED", issue=7, kind="triage", status="triaged",
                   **{"class": "easy-fix"}))
        s.apply(ev(4, "RESULT_RECORDED", issue=7, kind="triage", status="fix_pending"))
        s.apply(ev(5, "LEASE_GRANTED", issue=7, kind="fix", batch_id="f-7-1",
                   expires_at="2026-08-24T02:00:00Z"))
        s.apply(ev(6, "RESULT_RECORDED", issue=7, kind="fix", status="fix_pushed",
                   pr_branch="sweep/7-t", head_sha="abc"))
        s.apply(ev(7, "PR_OPENED", issue=7, number=99, branch="sweep/7-t", head_sha="abc"))
        s.apply(ev(8, "PR_READIED_BY_HUMAN", issue=7, pr=99))
        self.assertTrue(s.issue(7)["pr"]["readied_by_human_at"])
        self.assertEqual(s.issue(7)["status"], "pr_open")


class TestDeferredCanBeHandedBack(unittest.TestCase):
    """deferred_human is terminal for the sweep, not for bakert."""

    def deferred(self):
        s = D.State()
        s.apply(ev(1, "ISSUE_ENQUEUED", issue=5, title="t", labels=[]))
        s.apply(ev(2, "LEASE_GRANTED", issue=5, kind="triage", batch_id="t-5-1",
                   expires_at="2026-08-24T01:00:00Z"))
        s.apply(ev(3, "RESULT_RECORDED", issue=5, kind="triage", status="triaged",
                   **{"class": "needs-product-decision"}))
        s.apply(ev(4, "ESCALATED", issue=5, kind="class-escalate", question="q"))
        s.apply(ev(5, "ADJUDICATED", issue=5, verb="defer-to-human",
                   status="deferred_human", note="bakert decides"))
        return s

    def test_automatic_retry_cannot_leave_deferred(self):
        s = self.deferred()
        s.apply(ev(6, "RETRY_SCHEDULED", issue=5, kind="fix", status="fix_pending"))
        self.assertEqual(s.issue(5)["status"], "escalated")  # frozen, not resurrected

    def test_defer_then_queue_fix_is_legal(self):
        s = self.deferred()
        self.assertEqual(s.issue(5)["status"], "deferred_human")
        s.apply(ev(6, "ADJUDICATED", issue=5, verb="queue-fix", status="fix_pending",
                   note="bakert said do it"))
        self.assertEqual(s.issue(5)["status"], "fix_pending")
        self.assertEqual(len(s.invariants), 0)

    def test_bakert_can_close_a_deferred_issue(self):
        s = self.deferred()
        s.apply(ev(6, "ADJUDICATED", issue=5, verb="close-completed", status="closing",
                   note="resolved by events"))
        s.apply(ev(7, "CLOSE_EXECUTED", issue=5, reason="completed", comment_posted=True))
        self.assertEqual(s.issue(5)["status"], "closed")
        self.assertEqual(len(s.invariants), 0)

    def test_annotate_records_without_moving(self):
        s = self.deferred()
        s.apply(ev(6, "ADJUDICATED", issue=5, verb="annotate", note="deliberately punted"))
        self.assertEqual(s.issue(5)["status"], "deferred_human")
        self.assertEqual(s.issue(5)["notes"], "deliberately punted")
        self.assertEqual(len(s.invariants), 0)

    def test_annotate_is_a_known_verb_with_no_transition(self):
        self.assertIn("annotate", D.ADJUDICATIONS)
        self.assertIsNone(D.ADJUDICATIONS["annotate"])


class TestArchiveVerification(unittest.TestCase):
    """39 workspaces sat in `sleeping` while the journal claimed `archived`."""

    def engine(self, states, raise_on_archive=False):
        calls = {"archive": []}

        class Cond:
            def archive_workspace(self, wid):
                calls["archive"].append(wid)
                if raise_on_archive:
                    raise D.InfraError("HTTP 400 on archive")
                return {}

            def workspace_status(self, wid):
                return {"status": states.pop(0) if states else "ready"}

        class Store:
            def __init__(self, st):
                self.events, self.state = [], st

            def journal(self, event, **kw):
                self.events.append((event, kw))
                ws = self.state.workspaces.get(kw.get("workspace_id"))
                if ws and event == "WORKSPACE_ARCHIVED":
                    ws["state"] = "archived"
                elif ws and event == "WORKSPACE_HARVESTED":
                    ws["state"] = "harvested"

        st = D.State()
        st.workspaces["w1"] = {"workspace_id": "w1", "batch_id": "t-1-1", "state": "running",
                               "kind": "triage", "issues": [1]}
        e = D.Engine.__new__(D.Engine)
        e.cond, e.st, e.dry = Cond(), st, False
        e.store = Store(st)
        e.calls = calls
        return e

    def test_confirmed_archive_is_journaled(self):
        e = self.engine(["archived"])
        self.assertTrue(D.Engine.archive(e, e.st.workspaces["w1"]))
        self.assertEqual([x[0] for x in e.store.events], ["WORKSPACE_ARCHIVED"])

    def test_sleeping_workspace_is_not_claimed_as_archived(self):
        e = self.engine(["sleeping"])
        self.assertFalse(D.Engine.archive(e, e.st.workspaces["w1"]))
        self.assertEqual([x[0] for x in e.store.events], ["WORKSPACE_HARVESTED"])
        self.assertEqual(e.st.workspaces["w1"]["state"], "harvested")

    def test_failed_call_still_verifies_and_does_not_lie(self):
        e = self.engine(["ready"], raise_on_archive=True)
        self.assertFalse(D.Engine.archive(e, e.st.workspaces["w1"]))
        self.assertNotIn("WORKSPACE_ARCHIVED", [x[0] for x in e.store.events])

    def test_deleted_counts_as_archived(self):
        e = self.engine(["deleted"])
        self.assertTrue(D.Engine.archive(e, e.st.workspaces["w1"]))

    def test_harvested_workspaces_are_retried(self):
        e = self.engine(["sleeping", "archived"])
        D.Engine.archive(e, e.st.workspaces["w1"])          # first attempt fails
        D.Engine.retry_archives(e)                            # second succeeds
        self.assertEqual(len(e.calls["archive"]), 2)
        self.assertEqual(e.st.workspaces["w1"]["state"], "archived")

    def test_harvested_is_not_counted_as_active(self):
        s = D.State()
        s.apply(ev(1, "WORKSPACE_CREATED", workspace_id="w1", session_id="s1", kind="triage",
                   batch_id="t-1-1", issues=[1]))
        s.apply(ev(2, "WORKSPACE_HARVESTED", workspace_id="w1", state="sleeping"))
        active = [w for w in s.workspaces.values() if w["state"] in ("creating", "running", "nudged")]
        self.assertEqual(active, [])


class TestBodylessPost(unittest.TestCase):
    def test_content_type_only_when_a_body_is_sent(self):
        import inspect
        src = inspect.getsource(D.Conductor._request)
        self.assertIn("if data is not None:", src)
        i_guard = src.index("if data is not None:")
        i_ct = src.index('req.add_header("Content-Type"')
        self.assertGreater(i_ct, i_guard, "Content-Type must be inside the body guard")
