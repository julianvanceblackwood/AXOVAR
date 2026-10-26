"""Finite exhaustive exploration of a declared three-event synthetic policy model.

This is bounded enumeration + differential checking, not proof of an unbounded
C++ program. Each modeled trace is also evaluated by the compiled C++ engine.
"""
from __future__ import annotations

from itertools import product
import json
import subprocess
import tempfile
from pathlib import Path

from verification.decision_reference import reference, verify
from server.audit import build_receipt

HEADER = "id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\n"


def generate_traces():
    """Enumerate source dependency, timing, sequence, health and price choices."""
    a1 = "A1,100,100,ALPHA,UP_A,1,10000000,OK"
    for b_up, b_health, b_price, b_time in product(
        ("UP_A", "UP_B"), ("OK", "DEGRADED"),
        (10000000, 10150000, 14000000), (200, 3000)
    ):
        b1 = f"B1,{b_time},{b_time},BRAVO,{b_up},1,{b_price},{b_health}"
        yield [a1, b1]
        for a_up, a_health, a_seq, a_price in product(
            ("UP_A", "UP_C"), ("OK", "DEGRADED"), (2, 3),
            (10000000, 14000000)
        ):
            receive = b_time + 100
            a2 = f"A2,{receive},{receive},ALPHA,{a_up},{a_seq},{a_price},{a_health}"
            yield [a1, b1, a2]


def explore(binary: Path) -> dict:
    binary = binary.resolve()
    traces = 0
    checked = 0
    allowed = 0
    denied = 0
    abstained = 0
    with tempfile.TemporaryDirectory(prefix="axovar-model-") as dirname:
        fixture = Path(dirname) / "bounded.csv"
        for rows in generate_traces():
            traces += 1
            raw = (HEADER + "\n".join(rows) + "\n").encode("ascii")
            fixture.write_bytes(raw)
            for prefix in range(len(rows) + 1):
                expected = reference(raw, prefix)
                state = json.loads(subprocess.check_output(
                    [str(binary), "--scenario", str(fixture), str(prefix)],
                    timeout=5, text=True))
                envelope = build_receipt(state, raw)
                verdict = verify(envelope, raw)
                if not verdict["valid"]:
                    raise AssertionError(f"trace={traces} prefix={prefix} {verdict['errors']}")
                status = state["decision"]["result"]
                if status != expected["decision"]:
                    raise AssertionError(f"unexpected decision: trace={traces} prefix={prefix}")
                if status == "ALLOW_SIMULATION":
                    allowed += 1
                    if (expected["source_count"] < 2 or
                        any(v != "PASS" for v in expected["checks"].values())):
                        raise AssertionError("unsafe allow state")
                elif status == "DENY_SIMULATION":
                    denied += 1
                elif status == "INSUFFICIENT_EVIDENCE":
                    abstained += 1
                else:
                    raise AssertionError("unknown policy outcome")
                selections = [x for x in expected["source_selection"] if x["selected"]]
                if len({x["upstream"] for x in selections}) != len(selections):
                    raise AssertionError("upstream counted twice")
                for x in expected["source_selection"]:
                    if (x["dependency_changed"] or x["gaps"] > 0) and x["eligible"]:
                        raise AssertionError("quarantined source became eligible")
                checked += 1
    return {"bounded_traces": traces, "checked_prefixes": checked,
            "allow": allowed, "deny": denied, "abstain": abstained,
            "formal_proof": False, "external_data": False}
