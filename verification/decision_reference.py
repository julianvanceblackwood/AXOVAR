"""Independent bounded G4 oracle for the synthetic AXOVAR G1 policy receipt.

This implementation does not import the production replay core or receipt builder.
It uses exact Fraction arithmetic for decision boundaries. This is a reference
checker for a fixed fixture and policy, not a formal proof or data attestation.
"""
from __future__ import annotations

from fractions import Fraction
from hashlib import sha256
import json
import re

HEADER = "id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health"
MAX_RECORDS = 256
INT = re.compile(r"-?(0|[1-9][0-9]*)\Z")
CHECK_IDS = ("INDEPENDENT_SOURCES", "VENUE_DIVERGENCE", "CONCENTRATION")


class VerificationError(ValueError):
    pass


def _integer(value: str) -> int:
    if not INT.fullmatch(value):
        raise VerificationError("noncanonical integer")
    parsed = int(value)
    if parsed < -(2**63) or parsed > 2**63-1:
        raise VerificationError("integer outside 64-bit range")
    return parsed


def reference(fixture: bytes, step: int) -> dict:
    """Compute a separate reference from only the received fixture prefix."""
    if type(step) is not int or step < 0:
        raise VerificationError("invalid replay step")
    try:
        lines = fixture.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise VerificationError("invalid fixture encoding") from exc
    if not lines or lines[0] != HEADER or len(lines) > MAX_RECORDS + 1:
        raise VerificationError("invalid fixture format or size")
    events = []
    identifiers = set()
    for line in lines[1:]:
        if not line:
            continue
        cells = line.split(",")
        if len(cells) != 8:
            raise VerificationError("incorrect event columns")
        event_id, et, rt, venue, upstream, sequence, cents, health = cells
        event_ms, receive_ms, seq, price = map(_integer, (et, rt, sequence, cents))
        if (not event_id or not venue or not upstream or
            event_ms < 0 or receive_ms < 0 or seq <= 0 or price <= 0 or
            health not in ("OK", "DEGRADED", "UNTRUSTED") or event_id in identifiers):
            raise VerificationError("invalid event")
        identifiers.add(event_id)
        events.append({"id": event_id, "event_ms": event_ms,
                       "receive_ms": receive_ms, "venue": venue,
                       "upstream": upstream, "sequence": seq,
                       "price_cents": price, "health": health})
    events.sort(key=lambda e: e["receive_ms"])
    count = min(len(events), step)
    knowledge_ms = events[count-1]["receive_ms"] if count else 0
    venues = {}
    for event in events[:count]:
        name = event["venue"]
        previous = venues.get(name)
        if previous is not None and event["sequence"] <= previous["sequence"]:
            continue
        changed = (previous is not None and
                   (previous["dependency_changed"]
                    or previous["upstream"] != event["upstream"]))
        gaps = (previous["gaps"] if previous else 0)
        if previous is not None and event["sequence"] > previous["sequence"] + 1:
            gaps += 1
        venues[name] = {**event, "gaps": gaps, "dependency_changed": changed}

    selected = {}
    for venue in venues.values():
        valid = (venue["health"] == "OK" and venue["gaps"] == 0 and
                 not venue["dependency_changed"] and
                 knowledge_ms - venue["receive_ms"] <= 2500)
        venue["eligible"] = valid
        if not valid:
            continue
        current = selected.get(venue["upstream"])
        if (current is None or venue["receive_ms"] > current["receive_ms"] or
                (venue["receive_ms"] == current["receive_ms"]
                 and venue["venue"] < current["venue"])):
            selected[venue["upstream"]] = venue

    source_count = len(selected)
    source_prices = [x["price_cents"] for x in selected.values()]
    consensus_cents = Fraction(sum(source_prices), source_count) if source_count else Fraction(0)
    all_prices = [x["price_cents"] for x in venues.values()]
    divergence = (Fraction(10_000 * (max(all_prices)-min(all_prices)), min(all_prices))
                  if len(all_prices) >= 2 else Fraction(0))
    # The existing G1 model is a synthetic BTC policy: 0.6 BTC after a
    # candidate purchase, 0.5 BTC prior position, and USD 35,000 cash.
    exposure = (Fraction(6 * consensus_cents, 5 * consensus_cents + 35_000_000)
                if source_count else Fraction(0))
    if source_count < 2:
        decision = "INSUFFICIENT_EVIDENCE"
    elif divergence > 150 or exposure > Fraction(3, 4):
        decision = "DENY_SIMULATION"
    else:
        decision = "ALLOW_SIMULATION"
    checks = {
        "INDEPENDENT_SOURCES": "PASS" if source_count >= 2 else "FAIL",
        "VENUE_DIVERGENCE": ("NOT_EVALUATED" if len(venues) < 2
                             else "FAIL" if divergence > 150 else "PASS"),
        "CONCENTRATION": ("NOT_EVALUATED" if source_count < 2
                           else "FAIL" if exposure > Fraction(3,4) else "PASS"),
    }
    selection = [{
        "venue": name, "upstream": v["upstream"], "evidence_id": v["id"],
        "eligible": v["eligible"], "selected": selected.get(v["upstream"]) is v,
        "health": "STALE" if knowledge_ms - v["receive_ms"] > 2500 else v["health"],
        "gaps": v["gaps"], "dependency_changed": v["dependency_changed"],
        "event_ms": v["event_ms"], "receive_ms": v["receive_ms"],
    } for name, v in sorted(venues.items())]
    return {
        "source_selection": selection, "decision": decision, "checks": checks,
        "source_count": source_count, "reference_price": consensus_cents / 100,
        "divergence_bps": divergence, "exposure_pct": exposure * 100,
        "evidence_ids": [v["id"] for _, v in sorted(venues.items())],
        "knowledge_ms": knowledge_ms, "step": count, "total": len(events),
        "fixture_sha256": sha256(fixture).hexdigest(),
    }


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def verify(envelope: dict, fixture: bytes) -> dict:
    """Verify hash, claims and exact boundary decisions against fixture bytes.

    A rewritten fixture and matching receipt can still pass. The verifier has
    no independent access to an exchange, clock, source identity or signatures.
    """
    errors = []
    if type(envelope) is not dict:
        return {"valid": False, "errors": ["invalid envelope"]}
    payload = envelope.get("receipt")
    if type(payload) is not dict:
        return {"valid": False, "errors": ["invalid receipt"]}
    if (envelope.get("hash_algorithm") != "SHA-256" or
        envelope.get("signed") is not False):
        errors.append("invalid digest or signing metadata")
    try:
        calculated = sha256(_canonical(payload)).hexdigest()
    except (TypeError, ValueError, OverflowError):
        return {"valid": False, "errors": ["noncanonical receipt"]}
    if envelope.get("sha256") != calculated:
        errors.append("receipt digest does not match canonical content")
    if payload.get("schema") != "AXV-AUDIT-002" or payload.get("synthetic") is not True:
        errors.append("invalid contract or simulation flag")
    if payload.get("instrument") != "BTC/USD":
        errors.append("unsupported instrument")
    if payload.get("fixture_sha256") != sha256(fixture).hexdigest():
        errors.append("fixture digest mismatch")
    try:
        expected = reference(fixture, payload.get("replay_step"))
        if payload.get("event_count") != expected["total"]:
            errors.append("event count mismatch")
        if payload.get("knowledge_ms") != expected["knowledge_ms"]:
            errors.append("knowledge boundary mismatch")
        if payload.get("replay_step") != expected["step"]:
            errors.append("replay step mismatch")
        if payload.get("source_selection") != expected["source_selection"]:
            errors.append("source eligibility or provenance mismatch")
        policy = payload["policy"]
        if type(policy) is not dict or policy.get("id") != "AXV-POLICY-001":
            errors.append("unsupported policy")
        elif (policy.get("result") != expected["decision"] or
              policy.get("evidence_ids") != expected["evidence_ids"]):
            errors.append("decision or evidence linkage mismatch")
        observed_checks = {item["id"]: item["status"]
                           for item in policy["checks"]}
        if observed_checks != expected["checks"] or len(policy["checks"]) != len(CHECK_IDS):
            errors.append("policy check mismatch")
        check_rows = {item["id"]: item for item in policy["checks"]}
        if check_rows.get("INDEPENDENT_SOURCES") != {
            "id": "INDEPENDENT_SOURCES", "status": expected["checks"]["INDEPENDENT_SOURCES"],
            "observed": expected["source_count"], "minimum": 2,
        }:
            errors.append("source threshold fields mismatch")
        divergence_row = check_rows.get("VENUE_DIVERGENCE", {})
        if (divergence_row.get("maximum_bps") != 150 or
            set(divergence_row) != {"id", "status", "observed_bps", "maximum_bps"} or
            type(divergence_row.get("observed_bps")) not in (int, float) or
            abs(Fraction(divergence_row["observed_bps"]) - expected["divergence_bps"]) > Fraction(1, 20000)):
            errors.append("divergence check fields mismatch")
        exposure_row = check_rows.get("CONCENTRATION", {})
        if (exposure_row.get("maximum_pct") != 75 or
            set(exposure_row) != {"id", "status", "observed_pct", "maximum_pct"} or
            type(exposure_row.get("observed_pct")) not in (int, float) or
            abs(Fraction(exposure_row["observed_pct"]) - expected["exposure_pct"]) > Fraction(1, 20000)):
            errors.append("concentration check fields mismatch")
        reason = ("At least two fresh, gap-free, independent healthy upstreams are required."
                  if expected["source_count"] < 2 else
                  "Cross-venue disagreement exceeds the 150 bps market-integrity limit."
                  if expected["divergence_bps"] > 150 else
                  "Proposed BTC exposure exceeds the 75% portfolio concentration limit."
                  if expected["exposure_pct"] > 75 else
                  "Independent source and configured financial policy checks passed.")
        if policy.get("reason") != reason or policy.get("id") != "AXV-POLICY-001":
            errors.append("policy explanation mismatch")
        if (policy.get("required_independent_sources") != 2 or
            policy.get("max_disagreement_bps") != 150 or
            policy.get("max_post_trade_exposure_pct") != 75):
            errors.append("policy threshold metadata mismatch")
        metrics = payload["metrics"]
        if metrics.get("independent_healthy_sources") != expected["source_count"]:
            errors.append("source count mismatch")
        for name, target in (("reference_price", "reference_price"),
                             ("venue_disagreement_bps", "divergence_bps"),
                             ("post_trade_btc_exposure_pct", "exposure_pct")):
            actual = metrics[name]
            if type(actual) not in (int, float) or abs(Fraction(actual) - expected[target]) > Fraction(1, 20000):
                errors.append("metric mismatch: " + name)
    except (VerificationError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        errors.append("invalid or incomplete policy contract: " + type(exc).__name__)
    return {"valid": not errors, "errors": errors}

def main() -> int:
    """Validate a downloaded audit response without importing the AXOVAR server."""
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Verify an AXOVAR synthetic decision receipt")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    try:
        envelope = json.loads(args.receipt.read_text(encoding="utf-8"))
        result = verify(envelope, args.fixture.read_bytes())
    except (OSError, ValueError, UnicodeError) as exc:
        result = {"valid": False, "errors": ["unable to load evidence: " + type(exc).__name__]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
