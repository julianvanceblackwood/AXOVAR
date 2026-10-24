"""Executable G1 audit and source-selection regressions."""
from __future__ import annotations

import hashlib
import json
import random
from decimal import Decimal
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

BINARY = Path(sys.argv[1]).resolve()
ROOT = Path(sys.argv[2]).resolve()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(ROOT))

from server.app import Session, create_handler
from server.audit import canonical_bytes, SCHEMA


def evaluate(rows: str, step: int = 99) -> dict:
    with tempfile.TemporaryDirectory() as folder:
        fixture = Path(folder) / "policy.csv"
        fixture.write_text(
            "id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\n"
            + rows,
            encoding="utf-8",
        )
        output = subprocess.check_output(
            [str(BINARY), "--scenario", str(fixture), str(step)],
            text=True,
            timeout=5,
        )
        return json.loads(output)


class PolicyTests(unittest.TestCase):
    def test_source_choice_follows_receipt_time_not_venue_sort(self):
        state = evaluate(
            "A1,100,100,ALPHA,U1,1,10000000,OK\n"
            "Z1,101,300,ZULU,U1,1,12000000,OK\n"
            "B1,102,400,BRAVO,U2,1,10500000,OK\n"
        )
        selected = [v for v in state["venues"] if v["reference_selected"]]
        self.assertEqual({v["name"] for v in selected}, {"ZULU", "BRAVO"})
        self.assertEqual(state["metrics"]["independent_healthy_sources"], 2)
        self.assertAlmostEqual(state["metrics"]["reference_price"], 112500.0)
        self.assertTrue(any("SHARED_UPSTREAM" in a for a in state["alerts"]))
        self.assertEqual(state["decision"]["result"], "DENY_SIMULATION")
        self.assertEqual([check["id"] for check in state["checks"]],
                         ["INDEPENDENT_SOURCES", "VENUE_DIVERGENCE", "CONCENTRATION"])

    def test_same_receipt_time_has_stable_tie_break(self):
        state = evaluate(
            "Z1,10,10,ZULU,U1,1,12000000,OK\n"
            "A1,11,10,ALPHA,U1,1,10000000,OK\n"
            "B1,12,20,BRAVO,U2,1,10000000,OK\n"
        )
        self.assertEqual(
            [v["name"] for v in state["venues"] if v["reference_selected"]],
            ["ALPHA", "BRAVO"],
        )
        self.assertAlmostEqual(state["metrics"]["reference_price"], 100000.0)

    def test_checks_do_not_claim_exposure_test_without_sufficient_evidence(self):
        state = evaluate("A1,10,10,ALPHA,U1,1,10000000,OK\n")
        self.assertEqual(state["decision"]["result"], "INSUFFICIENT_EVIDENCE")
        checks = {item["id"]: item for item in state["checks"]}
        self.assertEqual(checks["INDEPENDENT_SOURCES"]["status"], "FAIL")
        self.assertEqual(checks["VENUE_DIVERGENCE"]["status"], "NOT_EVALUATED")
        self.assertEqual(checks["CONCENTRATION"]["status"], "NOT_EVALUATED")

    def test_seeded_upstream_reference_against_decimal_oracle(self):
        for seed in range(32):
            rng = random.Random(seed)
            rows = []
            chosen = {}
            for i in range(6):
                venue = f"V{i}"
                upstream = rng.choice(("U0", "U1", "U2"))
                cents = rng.randint(8000000, 12000000)
                received = 100 + i * 10
                rows.append(f"E{i},{received},{received},{venue},{upstream},1,{cents},OK")
                chosen[upstream] = (venue, cents)
            state = evaluate("\\n".join(rows) + "\\n")
            selected = {v["name"] for v in state["venues"] if v["reference_selected"]}
            self.assertEqual(selected, {v for v, cents in chosen.values()})
            self.assertEqual(state["metrics"]["independent_healthy_sources"], len(chosen))
            expected = (sum(Decimal(cents) for _, cents in chosen.values())
                        / Decimal(100) / Decimal(len(chosen)))
            self.assertAlmostEqual(state["metrics"]["reference_price"], float(expected),
                                   places=3, msg=f"seed={seed}")

    def test_sequence_boundary_does_not_overflow(self):
        state = evaluate(
            "A1,10,10,ALPHA,U1,9223372036854775807,10000000,OK\n"
            "A2,11,11,ALPHA,U1,9223372036854775807,10002000,OK\n"
            "B1,11,12,BRAVO,U2,1,10002000,OK\n"
        )
        self.assertTrue(any("REPEATED_OR_REORDERED_SEQUENCE" in a
                            for a in state["alerts"]))
        self.assertEqual(state["metrics"]["independent_healthy_sources"], 2)
        self.assertEqual(
            next(v for v in state["venues"] if v["name"] == "ALPHA")["evidence"], "A1")


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = ThreadingHTTPServer(
            ("127.0.0.1", 0), create_handler(ROOT, BINARY, Session())
        )
        cls.origin = f"http://127.0.0.1:{cls.service.server_port}"
        cls.thread = threading.Thread(target=cls.service.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.service.shutdown()
        cls.thread.join(timeout=5)
        cls.service.server_close()

    def fetch(self, path):
        with urlopen(self.origin + path, timeout=5) as response:
            return json.loads(response.read())

    def submit(self, path, data=None):
        request = Request(
            self.origin + path,
            data=json.dumps(data or {}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def setUp(self):
        self.submit("/api/replay/scenario", {"scenario": "NORMAL-001"})

    def test_receipt_hash_can_be_verified_independently(self):
        self.submit("/api/replay/end")
        response = self.fetch("/api/audit/receipt")
        receipt = response["receipt"]
        self.assertEqual(receipt["schema"], SCHEMA)
        self.assertTrue(receipt["synthetic"])
        self.assertFalse(response["signed"])
        self.assertEqual(
            hashlib.sha256(canonical_bytes(receipt)).hexdigest(), response["sha256"])
        fixture = (ROOT / "scenarios/NORMAL-001.csv").read_bytes()
        self.assertEqual(receipt["fixture_sha256"], hashlib.sha256(fixture).hexdigest())
        self.assertEqual(receipt["replay_step"], 9)
        self.assertEqual(receipt["policy"]["result"], "ALLOW_SIMULATION")

    def test_replay_change_changes_receipt_and_reset_restores_it(self):
        initial = self.fetch("/api/audit/receipt")
        repeated = self.fetch("/api/audit/receipt")
        self.assertEqual(initial, repeated)
        self.submit("/api/replay/step")
        advanced = self.fetch("/api/audit/receipt")
        self.assertNotEqual(initial["sha256"], advanced["sha256"])
        self.submit("/api/replay/reset")
        self.assertEqual(initial, self.fetch("/api/audit/receipt"))

    def test_degraded_case_abstains_with_policy_trace(self):
        self.submit("/api/replay/scenario", {"scenario": "DEGRADED-001"})
        self.submit("/api/replay/end")
        receipt = self.fetch("/api/audit/receipt")["receipt"]
        self.assertEqual(receipt["policy"]["result"], "INSUFFICIENT_EVIDENCE")
        checks = {x["id"]: x["status"] for x in receipt["policy"]["checks"]}
        self.assertEqual(checks["INDEPENDENT_SOURCES"], "FAIL")
        self.assertEqual(checks["CONCENTRATION"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
