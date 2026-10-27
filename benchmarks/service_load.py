"""Read-only loopback load experiment with correctness checks at each response.

A controlled, fixed-scenario local test; not a public load test or SLO.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROUTES = (
    "/api/state",
    "/api/audit/receipt",
    "/api/risk/portfolio",
    "/api/settlement",
)


def percentile(values: list[int], pct: int) -> int:
    return sorted(values)[max(1, math.ceil(len(values) * pct / 100)) - 1]


def exercise(binary: Path, root: Path, concurrency: int = 4,
             requests_per_route: int = 15) -> dict:
    if not (1 <= concurrency <= 16 and 5 <= requests_per_route <= 100):
        raise ValueError("load experiment parameters outside controlled bounds")
    from server.app import Session, create_handler
    server = ThreadingHTTPServer(("127.0.0.1", 0),
                                 create_handler(root, binary, Session()))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    fingerprints = {}
    failed = []
    latency = {route: [] for route in ROUTES}

    def fetch(route: str):
        start = time.perf_counter_ns()
        with urlopen(address + route, timeout=10) as response:
            if response.status != 200:
                raise AssertionError("unexpected HTTP response")
            body = response.read()
        end = time.perf_counter_ns()
        obj = json.loads(body)
        if route == "/api/state" and obj.get("step") != 0:
            raise AssertionError("unexpected replay mutation")
        elif route == "/api/audit/receipt" and obj.get("signed") is not False:
            raise AssertionError("audit signing status changed")
        elif route == "/api/risk/portfolio" and obj.get("accounting", {}).get("reconciliation_delta_cents") != 0:
            raise AssertionError("portfolio accounting changed")
        elif route == "/api/settlement" and obj.get("read_only") is not True:
            raise AssertionError("settlement status changed")
        return route, end - start, body

    try:
        # All requests are GET; benchmark never invokes a state-changing route.
        start = time.perf_counter_ns()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            tasks = [pool.submit(fetch, route) for _ in range(requests_per_route)
                     for route in ROUTES]
            for task in as_completed(tasks):
                try:
                    route, elapsed, data = task.result()
                    if route in fingerprints and fingerprints[route] != data:
                        raise AssertionError("read-only response differs under load")
                    fingerprints[route] = data
                    latency[route].append(elapsed)
                except Exception as exc:
                    failed.append(type(exc).__name__ + ": " + str(exc)[:100])
        end = time.perf_counter_ns()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    attempted = len(ROUTES) * requests_per_route
    seconds = (end - start) / 1_000_000_000
    report = {
        "schema": "AXV-LOAD-001", "synthetic": True, "read_only": True,
        "platform": platform.platform(), "concurrency": concurrency,
        "total_requests": attempted, "successful": sum(len(x) for x in latency.values()),
        "failed": len(failed), "elapsed_ms": (end - start) // 1_000_000,
        "throughput_requests_per_second": round(attempted / seconds, 2) if seconds else 0,
        "endpoints": [
            {"route": route, "samples": len(latency[route]),
             "p50_ms": round(percentile(latency[route], 50) / 1_000_000, 3) if latency[route] else None,
             "p95_ms": round(percentile(latency[route], 95) / 1_000_000, 3) if latency[route] else None,
             "p99_ms": round(percentile(latency[route], 99) / 1_000_000, 3) if latency[route] else None,
             "same_response_bytes": route in fingerprints and bool(latency[route])}
            for route in ROUTES
        ],
        "failure_samples": failed[:8],
        "limitations": [
            "Shared runner scheduling, OS and network loopback only",
            "Synthetic fixed session; no client authentication or external integration",
            "Throughput includes Python HTTP, C++ subprocess launch and JSON encoding",
            "No statistically calibrated SLO or guaranteed capacity",
        ],
    }
    if failed:
        raise AssertionError(json.dumps(report, sort_keys=True))
    if any(len(latency[route]) != requests_per_route for route in ROUTES):
        raise AssertionError("missing read-only responses")
    return report


def main():
    cli = argparse.ArgumentParser(description="AXOVAR G5 bounded read-only load test")
    cli.add_argument("--binary", type=Path, required=True)
    cli.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--concurrency", type=int, default=4)
    cli.add_argument("--requests-per-route", type=int, default=15)
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    result = exercise(args.binary.resolve(), args.root.resolve(),
                      args.concurrency, args.requests_per_route)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
