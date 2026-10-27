"""Run repeatable synthetic performance profiles without asserting universal speed.

The in-process C++ binary measures fixture ingest and replay/JSON rendering.
This script adds input hashes, machine details, executable hash and failure checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

HEADER = "id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\n"
SCHEMA = "AXV-PERF-001"
MODES = ("ingest", "replay")


def generated_fixture() -> bytes:
    rows = []
    for i in range(256):
        idx = i % 8
        sequence = i // 8 + 1
        price = 10_000_000 + (i % 13) * 120
        rows.append(f"E{i:03d},{i*10},{i*10},VENUE{idx},UP{idx},{sequence},{price},OK")
    return (HEADER + "\n".join(rows) + "\n").encode("ascii")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(binary: Path, root: Path, samples: int, warmups: int) -> dict:
    if not 5 <= samples <= 10_000 or not 1 <= warmups <= 500:
        raise ValueError("warmups/samples outside the supported contract")
    binary = binary.resolve()
    fixture_map = {
        "normal": root / "scenarios" / "NORMAL-001.csv",
        "degraded": root / "scenarios" / "DEGRADED-001.csv",
    }
    with tempfile.TemporaryDirectory(prefix="axovar-g5-") as folder:
        dense = Path(folder) / "DENSE-256.csv"
        dense.write_bytes(generated_fixture())
        fixture_map["dense_256"] = dense
        measurements = []
        for label, path in fixture_map.items():
            raw = path.read_bytes()
            expected_count = len([x for x in raw.splitlines()[1:] if x])
            for mode in MODES:
                cmd = [str(binary), mode, str(path), str(expected_count),
                       str(warmups), str(samples)]
                output = subprocess.check_output(cmd, text=True, timeout=90)
                row = json.loads(output)
                if row["schema"] != SCHEMA or row["benchmark"] != mode:
                    raise AssertionError("unexpected benchmark schema")
                if row["event_count"] != expected_count or not row["synthetic"]:
                    raise AssertionError("wrong workload or data provenance")
                if row["warmups"] != warmups or row["samples"] != samples:
                    raise AssertionError("sample contract mismatch")
                if not (0 <= row["min_ns"] <= row["p50_ns"] <= row["p95_ns"] <=
                        row["p99_ns"] <= row["max_ns"]):
                    raise AssertionError("latency percentile ordering broken")
                measurements.append({"case": label, "fixture_sha256": digest(raw), **row})
    return {
        "schema": SCHEMA,
        "measurement_type": "synthetic_local_microbenchmark",
        "not_an_slo": True, "validated_market_data": False,
        "machine": {
            "platform": platform.platform(), "architecture": platform.machine(),
            "python": platform.python_version(), "cpu_logical": os.cpu_count(),
            "note": "Clock, CPU scheduling and thermal conditions are not controlled",
        },
        "binary_sha256": digest(binary.read_bytes()),
        "method": {
            "in_process": True, "includes_process_startup": False,
            "ingest": "read CSV, validate identifiers, stable sort",
            "replay": "reconstruct prefix, evaluate checks and serialize JSON",
            "latency_unit": "nanoseconds, steady_clock wall time",
            "percentile": "nearest-rank over measured repetitions",
            "samples_per_case": samples, "warmups_per_case": warmups,
            "concurrency": 1, "fixture_type": "fully synthetic",
        },
        "results": measurements,
    }


def main():
    parser = argparse.ArgumentParser(description="AXOVAR G5 reproducible benchmark")
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.binary, args.root.resolve(), args.samples, args.warmups)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
