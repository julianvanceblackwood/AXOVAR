"""G3 synthetic settlement replay, adversarial validation and API contract tests."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BINARY = Path(sys.argv[1]).resolve()
ROOT = Path(sys.argv[2]).resolve()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(ROOT))

from server.app import Session, create_handler
from server.settlement import GENESIS, SCHEMA, SettlementError, evaluate, load_fixture

FIXTURE = ROOT / "scenarios" / "SETTLEMENT-001.json"


def base():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def snapshot(report, index, intent):
    row = report["timeline"][index]["states"]
    return next(item for item in row if item["intent_id"] == intent)


class SettlementTests(unittest.TestCase):
    def test_policy_confirmation_is_reversible(self):
        report = load_fixture(FIXTURE)
        self.assertTrue(report["synthetic"])
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["event_count"], 10)
        self.assertEqual(snapshot(report, 4, "I_BTC")["chain_state"], "POLICY_CONFIRMED")
        self.assertEqual(snapshot(report, 4, "I_BTC")["confirmations"], 3)
        self.assertEqual(snapshot(report, 4, "I_BTC")["review_gate"], "REVIEW_ELIGIBLE")
        self.assertEqual(snapshot(report, 5, "I_BTC")["review_gate"], "HOLD")
        self.assertEqual(snapshot(report, 7, "I_BTC")["review_gate"], "REVIEW_ELIGIBLE")
        self.assertEqual(snapshot(report, 8, "I_BTC")["chain_state"], "REORGED_OUT")
        self.assertEqual(snapshot(report, 8, "I_BTC")["confirmations"], 0)
        self.assertEqual(snapshot(report, 8, "I_BTC")["review_gate"], "HOLD")
        self.assertIn("CONFIRMATION_REVOKED", [x["kind"] for x in report["incidents"]])

    def test_reorg_reinclusion_and_counterparty_hold(self):
        report = load_fixture(FIXTURE)
        self.assertEqual(snapshot(report, 4, "I_ETH")["chain_state"], "PENDING_CONFIRMATIONS")
        self.assertEqual(snapshot(report, 6, "I_ETH")["chain_state"], "PENDING_CONFIRMATIONS")
        self.assertEqual(snapshot(report, 8, "I_ETH")["chain_state"], "POLICY_CONFIRMED")
        self.assertEqual(snapshot(report, 9, "I_ETH")["review_gate"], "HOLD")
        self.assertEqual(snapshot(report, 9, "I_ETH")["counterparty_state"], "HALT")
        self.assertEqual(report["active_chain"][-1]["hash"], "2" * 64)
        self.assertEqual(report["active_chain"][-1]["height"], 3)
        self.assertFalse(report["signed"])
        self.assertTrue(report["read_only"])

    def test_hash_reproducible_and_sensitive(self):
        report = load_fixture(FIXTURE)
        self.assertEqual(report, load_fixture(FIXTURE))
        self.assertEqual(report["fixture_sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        receipt = dict(report)
        reported_digest = receipt.pop("receipt_sha256")
        canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii")
        self.assertEqual(reported_digest, hashlib.sha256(canonical).hexdigest())
        altered = base()
        altered["events"][-1]["received_ms"] += 1
        self.assertNotEqual(reported_digest, evaluate(altered)["receipt_sha256"])

    def test_linked_execution_evidence_trace(self):
        report = load_fixture(FIXTURE)
        events = base()["events"]
        previous = GENESIS
        for event, trace in zip(events, report["event_trace"]):
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=True, allow_nan=False).encode("ascii")
            expected = hashlib.sha256(bytes.fromhex(previous) + canonical).hexdigest()
            self.assertEqual(trace["previous_hash"], previous)
            self.assertEqual(trace["evidence_hash"], expected)
            self.assertEqual(trace["source"], "synthetic_fixture")
            previous = expected
        self.assertEqual(report["trace_head"], previous)
        self.assertEqual(snapshot(report, 4, "I_BTC")["execution_ref"], "EXEC_BTC_A")
        self.assertEqual(snapshot(report, 8, "I_ETH")["execution_ref"], "EXEC_ETH_B")

    def test_reject_invalid_ancestor_links_and_duplicate_inclusions(self):
        for label in ("unknown_ancestor", "wrong_height", "broken_parent", "double_inclusion",
                      "noncanonical_reorg", "reused_block_hash", "oversized_reorg"):
            with self.subTest(label=label):
                fixture = base()
                if label == "unknown_ancestor":
                    fixture["events"][8]["ancestor"] = "7" * 64
                elif label == "wrong_height":
                    fixture["events"][3]["block"]["height"] = 7
                elif label == "broken_parent":
                    fixture["events"][4]["block"]["parent"] = GENESIS
                elif label == "double_inclusion":
                    fixture["events"][3]["block"]["txids"].append("9" * 64)
                elif label == "noncanonical_reorg":
                    fixture["events"][8]["ancestor"] = "b" * 64
                elif label == "reused_block_hash":
                    fixture["events"][6]["replacement"][0]["hash"] = "b" * 64
                else:
                    fixture["policy"]["max_reorg_depth"] = 1
                with self.assertRaises(SettlementError):
                    evaluate(fixture)

    def test_fail_closed_inputs(self):
        for label in ("reordered", "clock_backwards", "duplicate_intent", "unknown_tx",
                      "unknown_counterparty", "float", "bool", "unknown_network"):
            with self.subTest(label=label):
                fixture = base()
                if label == "reordered":
                    fixture["events"][2]["seq"] = 2
                elif label == "clock_backwards":
                    fixture["events"][3]["received_ms"] = 0
                elif label == "duplicate_intent":
                    fixture["events"][1]["intent_id"] = "I_BTC"
                elif label == "unknown_tx":
                    fixture["events"][2]["block"]["txids"] = ["7" * 64]
                elif label == "unknown_counterparty":
                    fixture["events"][5]["counterparty"] = "UNREGISTERED"
                elif label == "float":
                    fixture["events"][0]["amount_cents"] = 3.2
                elif label == "bool":
                    fixture["policy"]["confirmations_required"] = True
                else:
                    fixture["network"] = "BITCOIN"
                with self.assertRaises(SettlementError):
                    evaluate(fixture)

    def test_prohibit_duplicate_json_keys(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "duplicate.json"
            path.write_text('{"schema":"AXV-SETTLEMENT-001","schema":"AXV-SETTLEMENT-001"}')
            with self.assertRaises(SettlementError):
                load_fixture(path)


class SettlementAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                         create_handler(ROOT, BINARY, Session()))
        cls.address = f"http://127.0.0.1:{cls.server.server_port}"
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.worker.join(timeout=5)
        cls.server.server_close()

    def test_read_only_loopback_endpoint(self):
        with urlopen(self.address + "/api/settlement", timeout=5) as response:
            result = json.loads(response.read())
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(result, load_fixture(FIXTURE))
        request = Request(self.address + "/api/settlement",
                          data=b"{}", headers={"Content-Type": "application/json"},
                          method="POST")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(request, timeout=5)
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
