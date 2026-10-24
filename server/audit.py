"""Deterministic receipt for a synthetic decision snapshot.

This is an integrity checksum, not a signature or an assertion of market truth.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "AXV-AUDIT-001"


def canonical_bytes(value: dict[str, Any]) -> bytes:
    """Encode the documented audit fields independently of dict insertion order."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def build_receipt(state: dict[str, Any], fixture: bytes) -> dict[str, Any]:
    decision = state["decision"]
    metrics = state["metrics"]
    source_selection = [
        {
            "venue": v["name"],
            "upstream": v["upstream"],
            "evidence_id": v["evidence"],
            "eligible": v["eligible"],
            "selected": v["reference_selected"],
            "health": v["health"],
            "gaps": v["gaps"],
            "event_ms": v["event_ms"],
            "receive_ms": v["receive_ms"],
        }
        for v in state["venues"]
    ]
    payload = {
        "schema": SCHEMA,
        "scenario": state["scenario"],
        "fixture_sha256": hashlib.sha256(fixture).hexdigest(),
        "replay_step": state["step"],
        "event_count": state["total"],
        "knowledge_ms": state["knowledge_ms"],
        "synthetic": True,
        "instrument": state["instrument"],
        "source_selection": source_selection,
        "policy": {
            "id": decision["policy"],
            "result": decision["result"],
            "reason": decision["reason"],
            "checks": state["checks"],
            "evidence_ids": decision["evidence_ids"],
        },
        "metrics": {
            "independent_healthy_sources": metrics["independent_healthy_sources"],
            "reference_price": metrics["reference_price"],
            "venue_disagreement_bps": metrics["venue_disagreement_bps"],
            "post_trade_btc_exposure_pct": metrics["post_trade_btc_exposure_pct"],
        },
    }
    digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    return {
        "receipt": payload,
        "sha256": digest,
        "hash_algorithm": "SHA-256",
        "signed": False,
        "limits": [
            "Synthetic fixtures and source health assertions are not authenticated market data",
            "The digest detects byte changes within this canonical payload; it does not prove provenance",
            "Cross-platform floating-point equivalence is not established",
            "No trade authorization or execution is represented",
        ],
    }
