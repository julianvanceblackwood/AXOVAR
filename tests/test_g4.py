"""G4 exact-reference differential tests and bounded policy-state exploration."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BINARY = Path(sys.argv[1]).resolve()
ROOT = Path(sys.argv[2]).resolve()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(ROOT))

from server.audit import build_receipt
from verification.decision_reference import reference, verify

HEADER = "id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\n"


def evaluate_rows(rows, step=None):
    raw = (HEADER + "\n".join(rows) + "\n").encode("ascii")
    with tempfile.TemporaryDirectory() as folder:
        file = Path(folder) / "input.csv"
        file.write_bytes(raw)
        completed = subprocess.run(
            [str(BINARY), "--scenario", str(file), str(len(rows) if step is None else step)],
            text=True, capture_output=True, timeout=5, check=True)
        state = json.loads(completed.stdout)
    return raw, state, build_receipt(state, raw)


class IndependentOracleTests(unittest.TestCase):
    def test_bundled_scenarios_all_prefixes(self):
        for name in ("NORMAL-001", "DEGRADED-001"):
            raw = (ROOT / "scenarios" / (name + ".csv")).read_bytes()
            events = len(raw.decode().splitlines()) - 1
            for step in range(events + 1):
                with self.subTest(name=name, step=step):
                    rows = raw.decode().splitlines()[1:]
                    source, _, receipt = evaluate_rows(rows, step)
                    report = verify(receipt, source)
                    self.assertTrue(report["valid"], report["errors"])

    def test_dependency_change_never_restores_eligibility(self):
        rows = [
            "A1,100,100,ALPHA,U1,1,10000000,OK",
            "B1,110,110,BRAVO,U2,1,10000100,OK",
            "A2,120,120,ALPHA,U3,2,10000200,OK",
            "A3,130,130,ALPHA,U3,3,10000300,OK",
        ]
        for step, expected in ((2, "ALLOW_SIMULATION"), (3, "INSUFFICIENT_EVIDENCE"),
                               (4, "INSUFFICIENT_EVIDENCE")):
            with self.subTest(step=step):
                raw, state, receipt = evaluate_rows(rows, step)
                self.assertEqual(state["decision"]["result"], expected)
                a = next(x for x in state["venues"] if x["name"] == "ALPHA")
                if step > 2:
                    self.assertTrue(a["dependency_changed"])
                    self.assertFalse(a["eligible"])
                    self.assertFalse(a["reference_selected"])
                self.assertTrue(verify(receipt, raw)["valid"])

    def test_rounding_edges_and_exact_boundary_invariants(self):
        for price in (10_000_000, 10_150_000, 11_666_666, 12_000_000):
            for offset in (0, 100, 149_999, 150_000, 150_001):
                rows = [
                    f"A1,100,100,ALPHA,U1,1,{price},OK",
                    f"B1,101,101,BRAVO,U2,1,{price + offset},OK",
                ]
                with self.subTest(price=price, offset=offset):
                    raw, state, receipt = evaluate_rows(rows)
                    check = verify(receipt, raw)
                    self.assertTrue(check["valid"], check["errors"])
                    statuses = {x["id"]: x["status"] for x in state["checks"]}
                    if state["decision"]["result"] == "ALLOW_SIMULATION":
                        self.assertTrue(all(x == "PASS" for x in statuses.values()))
                    if state["decision"]["result"] == "INSUFFICIENT_EVIDENCE":
                        self.assertNotEqual(statuses["INDEPENDENT_SOURCES"], "PASS")

    def test_seeded_bounded_source_health_and_gap_matrix(self):
        # Reproducible sampling of fixture states, not formal proof of unbounded inputs.
        for seed in range(64):
            rng = random.Random(seed)
            lines = []
            for index, name in enumerate(("ALPHA", "BRAVO", "CHARLIE")):
                upstream = rng.choice(("UP_A", "UP_B", "UP_C"))
                health = rng.choice(("OK", "OK", "DEGRADED"))
                sequence = rng.choice((1, 1, 2))
                price = rng.randint(9_000_000, 12_000_000)
                receive = 100 + index * rng.randint(1, 40)
                lines.append(f"E{index},{receive},{receive},{name},{upstream},{sequence},{price},{health}")
            for step in range(4):
                with self.subTest(seed=seed, step=step):
                    raw, state, receipt = evaluate_rows(lines, step)
                    outcome = verify(receipt, raw)
                    self.assertTrue(outcome["valid"], outcome["errors"])
                    ref = reference(raw, step)
                    self.assertEqual(state["decision"]["result"], ref["decision"])

    def test_rehashed_forgery_still_rejected_by_independent_reference(self):
        rows = ["A1,100,100,ALPHA,U1,1,10000000,OK",
                "B1,101,101,BRAVO,U2,1,10000100,OK"]
        raw, _, envelope = evaluate_rows(rows)
        self.assertTrue(verify(envelope, raw)["valid"])
        envelope["receipt"]["policy"]["result"] = "DENY_SIMULATION"
        self.assertFalse(verify(envelope, raw)["valid"])
        canonical = json.dumps(envelope["receipt"], sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii")
        envelope["sha256"] = hashlib.sha256(canonical).hexdigest()
        report = verify(envelope, raw)
        self.assertFalse(report["valid"])
        self.assertIn("decision or evidence linkage mismatch", report["errors"])

    def test_rehashed_source_selection_forgery_is_rejected(self):
        raw, _, envelope = evaluate_rows(
            ["A1,100,100,ALPHA,U1,1,10000000,OK",
             "B1,101,101,BRAVO,U2,1,10000100,OK"])
        envelope["receipt"]["source_selection"][0]["selected"] = False
        encoded = json.dumps(envelope["receipt"], sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")
        envelope["sha256"] = hashlib.sha256(encoded).hexdigest()
        self.assertIn("source eligibility or provenance mismatch", verify(envelope, raw)["errors"])

    def test_fixture_mismatch_is_detected(self):
        raw, _, receipt = evaluate_rows(
            ["A1,100,100,ALPHA,U1,1,10000000,OK",
             "B1,101,101,BRAVO,U2,1,10000100,OK"])
        self.assertFalse(verify(receipt, raw + b"\n")["valid"])

    def test_cli_accepts_valid_and_rejects_tampering(self):
        raw, _, envelope = evaluate_rows(
            ["A1,100,100,ALPHA,U1,1,10000000,OK",
             "B1,101,101,BRAVO,U2,1,10000100,OK"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture, doc = root / "scenario.csv", root / "receipt.json"
            fixture.write_bytes(raw)
            doc.write_text(json.dumps(envelope), encoding="utf-8")
            cmd = [sys.executable, "-m", "verification.decision_reference",
                   "--receipt", str(doc), "--fixture", str(fixture)]
            good = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertTrue(json.loads(good.stdout)["valid"])
            fixture.write_bytes(raw + b"\n")
            bad = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertFalse(json.loads(bad.stdout)["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
