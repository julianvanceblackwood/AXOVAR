"""Reconstruct synthetic settlement evidence without networking, keys or order authority."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "AXV-SETTLEMENT-001"
GENESIS = "0" * 64
_HEX = re.compile(r"^[a-f0-9]{64}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_-]{0,39}$")
MAX_FILE_BYTES = 150_000
MAX_EVENTS = 128
MAX_INTENTS = 20


class SettlementError(ValueError):
    pass


def _object(value: Any, keys: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise SettlementError(f"invalid {label} fields")
    return value


def _integer(value: Any, label: str, lo: int = 0, hi: int = 1_000_000_000_000) -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise SettlementError(f"invalid {label}")
    return value


def _code(value: Any, label: str) -> str:
    if type(value) is not str or not _CODE.fullmatch(value):
        raise SettlementError(f"invalid {label}")
    return value


def _hash(value: Any, label: str) -> str:
    if type(value) is not str or not _HEX.fullmatch(value):
        raise SettlementError(f"invalid {label}")
    return value


def _unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise SettlementError("duplicate JSON key")
        result[key] = value
    return result


def _reject_float(value):
    raise SettlementError("floating-point numbers are not permitted")


def _block(raw: Any, parent: str, height: int, known_txids: set[str],
           chain_txs: set[str], seen_blocks: set[str]) -> dict:
    _object(raw, {"hash", "parent", "height", "txids"}, "block")
    digest = _hash(raw["hash"], "block hash")
    previous = _hash(raw["parent"], "parent hash")
    if digest == GENESIS or digest in seen_blocks:
        raise SettlementError("repeated or reserved block hash")
    if previous != parent or _integer(raw["height"], "height", 1) != height:
        raise SettlementError("broken parent link or block height")
    txids = raw["txids"]
    if type(txids) is not list or len(txids) > MAX_INTENTS:
        raise SettlementError("invalid block transaction list")
    local = set()
    for txid in txids:
        txid = _hash(txid, "transaction ID")
        if txid not in known_txids:
            raise SettlementError("unknown transaction")
        if txid in local or txid in chain_txs:
            raise SettlementError("duplicate canonical transaction inclusion")
        local.add(txid)
    chain_txs.update(local)
    seen_blocks.add(digest)
    return {"hash": digest, "parent": previous, "height": height, "txids": list(txids)}


def _states(intents: dict, chain: list[dict], orphaned: set[str],
            counterparties: dict, confirmations_required: int) -> list[dict]:
    index = {}
    for block in chain:
        for txid in block["txids"]:
            index[txid] = block
    tip_height = chain[-1]["height"] if chain else 0
    result = []
    for intent in intents.values():
        block = index.get(intent["txid"])
        depth = tip_height - block["height"] + 1 if block else 0
        if block:
            chain_state = ("POLICY_CONFIRMED" if depth >= confirmations_required
                           else "PENDING_CONFIRMATIONS")
        elif intent["txid"] in orphaned:
            chain_state = "REORGED_OUT"
        else:
            chain_state = "NOT_OBSERVED"
        counterparty = counterparties[intent["counterparty"]]
        gate = ("REVIEW_ELIGIBLE" if chain_state == "POLICY_CONFIRMED"
                and counterparty == "CLEAR" else "HOLD")
        result.append({
            "intent_id": intent["intent_id"],
            "txid": intent["txid"],
            "asset": intent["asset"],
            "amount_cents": intent["amount_cents"],
            "counterparty": intent["counterparty"],
            "counterparty_state": counterparty,
            "chain_state": chain_state,
            "confirmations": depth,
            "included_block": block["hash"] if block else None,
            "review_gate": gate,
        })
    return result


def evaluate(document: dict, raw_bytes: bytes = b"") -> dict:
    _object(document, {"schema", "network", "policy", "events"}, "fixture")
    if document["schema"] != SCHEMA or document["network"] != "AXV-SIMNET":
        raise SettlementError("unsupported synthetic network")
    policy = _object(document["policy"],
                     {"confirmations_required", "max_reorg_depth"}, "policy")
    required = _integer(policy["confirmations_required"], "confirmation policy", 2, 12)
    max_reorg = _integer(policy["max_reorg_depth"], "reorg limit", 1, 12)
    events = document["events"]
    if type(events) is not list or not 1 <= len(events) <= MAX_EVENTS:
        raise SettlementError("event count outside supported range")

    intents = {}
    txids = set()
    counterparties = {}
    chain = []
    orphaned = set()
    seen_blocks = set()
    seen_event_ids = set()
    timeline = []
    incidents = []
    last_seq, last_received = 0, -1

    for event in events:
        if type(event) is not dict:
            raise SettlementError("invalid event")
        kind = event.get("kind")
        base_fields = {"id", "seq", "received_ms", "kind"}
        identifier = _code(event.get("id"), "event identifier")
        sequence = _integer(event.get("seq"), "event sequence", 1, MAX_EVENTS * 10)
        received = _integer(event.get("received_ms"), "receipt time")
        if identifier in seen_event_ids or sequence <= last_seq or received < last_received:
            raise SettlementError("duplicate, reordered or noncausal events")
        seen_event_ids.add(identifier)
        last_seq, last_received = sequence, received
        before = _states(intents, chain, orphaned, counterparties, required)

        if kind == "INTENT":
            _object(event, base_fields | {"intent_id", "txid", "counterparty",
                                           "asset", "amount_cents"}, "intent")
            intent_id = _code(event["intent_id"], "intent identifier")
            txid = _hash(event["txid"], "transaction ID")
            cp = _code(event["counterparty"], "counterparty")
            asset = _code(event["asset"], "asset")
            if asset not in ("BTC", "ETH") or intent_id in intents or txid in txids:
                raise SettlementError("duplicate intent or unsupported asset")
            if len(intents) >= MAX_INTENTS:
                raise SettlementError("too many intents")
            amount = _integer(event["amount_cents"], "simulated USD amount", 1)
            intents[intent_id] = {"intent_id": intent_id, "txid": txid,
                                   "counterparty": cp, "asset": asset, "amount_cents": amount}
            counterparties.setdefault(cp, "CLEAR")
            txids.add(txid)
        elif kind == "BLOCK":
            _object(event, base_fields | {"block"}, "block event")
            tip = chain[-1]["hash"] if chain else GENESIS
            candidate = _block(event["block"], tip, len(chain) + 1, txids,
                               {tx for b in chain for tx in b["txids"]}, seen_blocks)
            chain.append(candidate)
        elif kind == "REORG":
            _object(event, base_fields | {"ancestor", "replacement"}, "reorg event")
            ancestor = _hash(event["ancestor"], "ancestor")
            known = [GENESIS] + [b["hash"] for b in chain]
            if ancestor not in known:
                raise SettlementError("reorg ancestor not canonical")
            ancestor_index = known.index(ancestor)
            old_suffix = chain[ancestor_index:]
            replacement = event["replacement"]
            if (not old_suffix or len(old_suffix) > max_reorg
                    or type(replacement) is not list
                    or not 1 <= len(replacement) <= max_reorg):
                raise SettlementError("invalid reorganization depth or replacement")
            preserved = chain[:ancestor_index]
            base_txids = {tx for b in preserved for tx in b["txids"]}
            pending_blocks = []
            pending_hashes = set(seen_blocks)
            parent = ancestor
            for i, raw_block in enumerate(replacement):
                candidate = _block(raw_block, parent, ancestor_index + i + 1, txids,
                                   base_txids, pending_hashes)
                pending_blocks.append(candidate)
                parent = candidate["hash"]
            # Commit only after validating the entire replacement sequence.
            old_txids = {tx for b in old_suffix for tx in b["txids"]}
            new_txids = {tx for b in pending_blocks for tx in b["txids"]}
            orphaned.update(old_txids - new_txids)
            orphaned.difference_update(new_txids)
            chain = preserved + pending_blocks
            seen_blocks = pending_hashes
            incidents.append({
                "event_id": identifier, "kind": "CANONICAL_REORG",
                "removed_blocks": [b["hash"] for b in old_suffix],
                "replacement_blocks": [b["hash"] for b in pending_blocks],
                "orphaned_txids": sorted(old_txids - new_txids),
            })
        elif kind == "COUNTERPARTY":
            _object(event, base_fields | {"counterparty", "state"}, "counterparty event")
            cp = _code(event["counterparty"], "counterparty")
            if cp not in counterparties or event["state"] not in ("CLEAR", "HALT"):
                raise SettlementError("unknown counterparty or state")
            counterparties[cp] = event["state"]
            if event["state"] == "HALT":
                incidents.append({"event_id": identifier, "kind": "COUNTERPARTY_HALT",
                                  "counterparty": cp})
        else:
            raise SettlementError("unsupported event type")

        after = _states(intents, chain, orphaned, counterparties, required)
        earlier = {s["intent_id"]: s for s in before}
        for current in after:
            previous = earlier.get(current["intent_id"])
            if (previous and previous["chain_state"] == "POLICY_CONFIRMED"
                    and current["chain_state"] != "POLICY_CONFIRMED"):
                incidents.append({
                    "event_id": identifier, "kind": "CONFIRMATION_REVOKED",
                    "intent_id": current["intent_id"],
                    "before": previous["chain_state"],
                    "after": current["chain_state"],
                })
        timeline.append({
            "event_id": identifier, "seq": sequence, "kind": kind,
            "received_ms": received,
            "tip": chain[-1]["hash"] if chain else GENESIS,
            "height": len(chain), "states": after,
        })

    final = timeline[-1]
    report = {
        "schema": SCHEMA, "network": "AXV-SIMNET", "synthetic": True,
        "read_only": True, "signed": False,
        "policy": {"confirmations_required": required, "max_reorg_depth": max_reorg,
                   "finality_semantics": "reversible depth heuristic only"},
        "fixture_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "event_count": len(timeline), "active_chain": chain,
        "intents": final["states"], "timeline": timeline, "incidents": incidents,
        "trust_limits": [
            "Synthetic block identifiers are fixture claims and are not verified consensus",
            "Policy confirmation is reversible and does not establish economic finality",
            "Counterparty states are asserted, not independently authenticated",
            "Review eligibility is not permission to trade, transfer or settle funds",
        ],
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    report["receipt_sha256"] = hashlib.sha256(encoded).hexdigest()
    return report


def load_fixture(path: Path) -> dict:
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise SettlementError("fixture exceeds supported size")
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs,
                          parse_float=_reject_float, parse_constant=_reject_float)
    except (ValueError, UnicodeError) as exc:
        raise SettlementError("malformed settlement fixture") from exc
    return evaluate(data, raw)
