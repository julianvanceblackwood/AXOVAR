"""G5 benchmark contract tests. Never gate on noisy shared-runner latency."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BENCH = Path(sys.argv[1]).resolve()
CORE = Path(sys.argv[2]).resolve()
ROOT = Path(sys.argv[3]).resolve()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(ROOT))

from benchmarks.run import generated_fixture, run


class PerformanceContractTests(unittest.TestCase):
    def test_measurements_have_consistent_distribution_and_provenance(self):
        report = run(BENCH, ROOT, samples=10, warmups=2)
        self.assertEqual(report["schema"], "AXV-PERF-001")
        self.assertTrue(report["not_an_slo"])
        self.assertFalse(report["validated_market_data"])
        self.assertEqual(len(report["results"]), 6)
        self.assertEqual({v["case"] for v in report["results"]},
                         {"normal", "degraded", "dense_256"})
        self.assertEqual({v["benchmark"] for v in report["results"]},
                         {"ingest", "replay"})
        self.assertEqual(report["binary_sha256"],
                         hashlib.sha256(BENCH.read_bytes()).hexdigest())
        for result in report["results"]:
            self.assertEqual(result["samples"], 10)
            self.assertTrue(result["synthetic"])
            self.assertEqual(result["unit"], "ns")
            self.assertTrue(result["checksum"])
            values = [result[k] for k in
                      ("min_ns", "p50_ns", "p95_ns", "p99_ns", "max_ns")]
            self.assertEqual(values, sorted(values))
            self.assertGreaterEqual(result["mean_ns"], 0)
            if result["case"] == "dense_256":
                self.assertEqual(result["event_count"], 256)

    def test_dense_fixture_independent_result_matches_compiled_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder) / "DENSE.csv"
            fixture.write_bytes(generated_fixture())
            result = json.loads(subprocess.check_output(
                [str(CORE), "--scenario", str(fixture), "256"], text=True, timeout=5))
            self.assertEqual(result["total"], 256)
            self.assertEqual(result["step"], 256)
            self.assertTrue(result["synthetic"])
            self.assertEqual(result["metrics"]["independent_healthy_sources"], 8)
            self.assertEqual(result["decision"]["result"], "ALLOW_SIMULATION")

    def test_bounded_concurrent_api_load_preserves_read_only_contract(self):
        from benchmarks.service_load import exercise
        report = exercise(CORE, ROOT, concurrency=3, requests_per_route=5)
        self.assertEqual(report["schema"], "AXV-LOAD-001")
        self.assertEqual(report["total_requests"], 20)
        self.assertEqual(report["successful"], 20)
        self.assertEqual(report["failed"], 0)
        for result in report["endpoints"]:
            self.assertEqual(result["samples"], 5)
            self.assertTrue(result["same_response_bytes"])
            self.assertLessEqual(result["p50_ms"], result["p95_ms"])
            self.assertLessEqual(result["p95_ms"], result["p99_ms"])

    def test_broken_engine_isolates_failures_from_independent_risk_route(self):
        from http.server import ThreadingHTTPServer
        from threading import Thread
        from urllib.error import HTTPError
        from urllib.request import urlopen
        from server.app import Session, create_handler
        missing = ROOT / "build" / "engine-does-not-exist"
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), create_handler(ROOT, missing, Session()))
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for endpoint in ("/api/state", "/api/audit/receipt"):
                with self.subTest(endpoint=endpoint):
                    with self.assertRaises(HTTPError) as failure:
                        urlopen(base + endpoint, timeout=5)
                    self.assertEqual(failure.exception.code, 500)
            with urlopen(base + "/api/risk/portfolio", timeout=5) as response:
                portfolio = json.loads(response.read())
            self.assertEqual(portfolio["accounting"]["reconciliation_delta_cents"], 0)
            self.assertTrue(portfolio["synthetic"])
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()

    def test_invalid_mode_and_sample_bounds_fail(self):
        scenario = ROOT / "scenarios" / "NORMAL-001.csv"
        for mode, warmups, samples in (
            ("unrecognized", "2", "10"), ("replay", "0", "10"),
            ("replay", "2", "4"), ("ingest", "2", "10001")
        ):
            with self.subTest(mode=mode, warmups=warmups, samples=samples):
                proc = subprocess.run(
                    [str(BENCH), mode, str(scenario), "9", warmups, samples],
                    capture_output=True, text=True, timeout=5)
                self.assertNotEqual(proc.returncode, 0)

    def test_cli_generates_machine_readable_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "results.json"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "benchmarks" / "run.py"),
                 "--binary", str(BENCH), "--root", str(ROOT), "--samples", "5",
                 "--warmups", "1", "--output", str(output)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout), json.loads(output.read_text()))
            self.assertTrue(json.loads(output.read_text())["method"]["in_process"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
