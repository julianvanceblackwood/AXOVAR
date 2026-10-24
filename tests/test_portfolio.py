"""G2 portfolio accounting, scenario risk and loopback integration tests."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import threading
import unittest
from decimal import Decimal, ROUND_HALF_EVEN
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
from server.portfolio import RiskError, evaluate, load_fixture

FIXTURE = ROOT / "scenarios" / "PORTFOLIO-001.json"


def baseline():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class PortfolioTests(unittest.TestCase):
    def test_golden_accounting_and_fifo(self):
        result = load_fixture(FIXTURE)
        account = result["accounting"]
        self.assertEqual(result["event_count"], 6)
        self.assertEqual(account["cash_cents"], 13_763_250)
        self.assertEqual(account["net_contributions_cents"], 19_500_000)
        self.assertEqual(account["equity_cents"], 19_793_250)
        self.assertEqual(account["realized_pnl_cents"], 19_300)
        self.assertEqual(account["unrealized_pnl_cents"], 274_100)
        self.assertEqual(account["nontrade_fees_cents"], 150)
        self.assertEqual(account["net_pnl_cents"], 293_250)
        self.assertEqual(account["reconciliation_delta_cents"], 0)
        positions = {p["asset"]: p for p in result["holdings"]}
        self.assertEqual(positions["BTC"]["quantity_units"], 50_000_000)
        self.assertEqual(positions["BTC"]["open_cost_cents"], 5_005_000)
        self.assertEqual(positions["ETH"]["quantity_units"], 300_000_000)
        self.assertEqual(positions["ETH"]["open_cost_cents"], 750_900)

    def test_fixed_stress_results(self):
        result = load_fixture(FIXTURE)
        stresses = {row["id"]: row for row in result["stresses"]}
        self.assertEqual(stresses["RISK_OFF"]["pnl_cents"], -1_926_000)
        self.assertEqual(stresses["FULL_ASSET_LOSS"]["pnl_cents"], -6_030_000)
        self.assertEqual(stresses["FULL_ASSET_LOSS"]["equity_cents"], 13_763_250)
        self.assertGreater(stresses["UPSIDE"]["pnl_cents"], 0)

    def test_synthetic_empirical_tail_against_independent_decimal_oracle(self):
        fixture = baseline()
        report = evaluate(fixture)
        equity = Decimal(report["accounting"]["equity_cents"])
        cash = Decimal(report["accounting"]["cash_cents"])
        values = []
        for sample in fixture["history"]:
            stressed = cash
            for holding in report["holdings"]:
                shock = sample["returns_bps"][holding["asset"]]
                exact = (Decimal(holding["quantity_units"])
                         * Decimal(holding["mark_price_cents"])
                         * Decimal(10_000 + shock)
                         / Decimal(100_000_000 * 10_000))
                stressed += exact.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
            values.append(max(Decimal(0), equity - stressed))
        count = (len(values) * (10_000 - fixture["confidence_bps"]) + 9999) // 10_000
        tail = sorted(values, reverse=True)[:count]
        expected_es = (sum(tail) / Decimal(count)).quantize(Decimal("1"),
                                                            rounding=ROUND_HALF_EVEN)
        self.assertEqual(report["historical_risk"]["tail_observations"], 3)
        self.assertEqual(report["historical_risk"]["var_cents"], int(tail[-1]))
        self.assertEqual(report["historical_risk"]["expected_shortfall_cents"],
                         int(expected_es))

    def test_integrity_receipt_stable_and_sensitive(self):
        same = load_fixture(FIXTURE)
        self.assertEqual(same, load_fixture(FIXTURE))
        self.assertFalse(same["signed"])
        self.assertEqual(same["fixture_sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        changed = baseline()
        changed["marks_cents"]["ETH"] += 100
        again = evaluate(changed)
        self.assertNotEqual(same["receipt_sha256"], again["receipt_sha256"])

    def test_reject_non_increasing_sequences_and_duplicate_ids(self):
        for mutate in ("repeat_sequence", "repeat_id"):
            with self.subTest(mutate=mutate):
                payload = baseline()
                if mutate == "repeat_sequence":
                    payload["events"][1]["sequence"] = 1
                else:
                    payload["events"][1]["id"] = "C001"
                with self.assertRaises(RiskError):
                    evaluate(payload)

    def test_reject_oversell_overdraw_and_zero_notional(self):
        for change in ("oversell", "overdraw", "zero_notional"):
            with self.subTest(change=change):
                payload = baseline()
                if change == "oversell":
                    payload["events"][3]["quantity_units"] = 900_000_000
                elif change == "overdraw":
                    payload["events"][-1]["amount_cents"] = 999_999_999
                else:
                    payload["events"][1]["quantity_units"] = 1
                    payload["events"][1]["price_cents"] = 1
                with self.assertRaises(RiskError):
                    evaluate(payload)

    def test_partial_fifo_and_rounding_invariant(self):
        payload = baseline()
        payload["events"] = [
            {"id": "C1", "sequence": 1, "kind": "CASH_IN", "amount_cents": 10_000},
            {"id": "B1", "sequence": 2, "kind": "BUY", "asset": "ETH",
             "quantity_units": 300_000_000, "price_cents": 101, "fee_cents": 2},
            {"id": "S1", "sequence": 3, "kind": "SELL", "asset": "ETH",
             "quantity_units": 100_000_000, "price_cents": 102, "fee_cents": 1},
            {"id": "S2", "sequence": 4, "kind": "SELL", "asset": "ETH",
             "quantity_units": 200_000_000, "price_cents": 103, "fee_cents": 0},
        ]
        report = evaluate(payload)
        self.assertEqual(report["holdings"], [])
        self.assertEqual(report["accounting"]["realized_pnl_cents"], 2)
        self.assertEqual(report["accounting"]["net_pnl_cents"], 2)
        self.assertEqual(report["accounting"]["reconciliation_delta_cents"], 0)

    def test_malformed_payloads_fail_closed(self):
        for mutate in ("float", "bool", "missing_return", "outside_stress",
                       "insufficient_samples", "bad_schema", "missing_mark"):
            with self.subTest(mutate=mutate):
                payload = baseline()
                if mutate == "float":
                    payload["marks_cents"]["BTC"] = 2.5
                elif mutate == "bool":
                    payload["confidence_bps"] = True
                elif mutate == "missing_return":
                    del payload["history"][0]["returns_bps"]["ETH"]
                elif mutate == "outside_stress":
                    payload["stresses"][0]["shocks_bps"]["BTC"] = -10001
                elif mutate == "insufficient_samples":
                    payload["history"] = payload["history"][:19]
                elif mutate == "bad_schema":
                    payload["schema"] = "unknown"
                elif mutate == "missing_mark":
                    del payload["marks_cents"]["BTC"]
                with self.assertRaises(RiskError):
                    evaluate(payload)

    def test_duplicate_keys_in_fixture_rejected(self):
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "duplicate.json"
            file.write_text('{"schema":"AXV-RISK-001","schema":"AXV-RISK-001"}')
            with self.assertRaises(RiskError):
                load_fixture(file)


class RiskAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                         create_handler(ROOT, BINARY, Session()))
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)
        cls.httpd.server_close()

    def test_report_is_read_only_and_reproducible(self):
        with urlopen(self.url + "/api/risk/portfolio", timeout=5) as response:
            a = json.loads(response.read())
        with urlopen(self.url + "/api/risk/portfolio", timeout=5) as response:
            b = json.loads(response.read())
        self.assertEqual(a, b)
        self.assertEqual(a["schema"], "AXV-RISK-001")
        self.assertTrue(a["synthetic"])
        self.assertFalse(a["signed"])
        self.assertEqual(a["accounting"]["reconciliation_delta_cents"], 0)
        request = Request(self.url + "/api/risk/portfolio", data=b"{}",
                          headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(HTTPError) as failure:
            urlopen(request, timeout=5)
        self.assertEqual(failure.exception.code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
