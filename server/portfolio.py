"""Deterministic synthetic portfolio replay and one-period risk experiments.

All financial amounts are integer USD cents. Quantity is measured in 1e-8
units; rounding is explicit and no floating-point arithmetic is used.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path

SCHEMA = "AXV-RISK-001"
SCALE = 100_000_000
MAX_INT = 10**15
MAX_EVENTS = 500
MAX_RETURNS = 2000
ASSET_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


class RiskError(ValueError):
    pass


def _integer(value, field, minimum=0, maximum=MAX_INT):
    if type(value) is not int or not minimum <= value <= maximum:
        raise RiskError(f"invalid {field}")
    return value


def _object(value, keys, context):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise RiskError(f"invalid {context} fields")
    return value


def _asset(value):
    if not isinstance(value, str) or not ASSET_RE.fullmatch(value):
        raise RiskError("invalid asset identifier")
    return value


def _identifier(value, context):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,39}", value):
        raise RiskError(f"invalid {context}")
    return value


def _round_cents(numerator, denominator=SCALE):
    # The maximum validated operand product exceeds Decimal's default precision.
    with localcontext() as context:
        context.prec = 60
        return int((Decimal(numerator) / Decimal(denominator)).to_integral_value(
            rounding=ROUND_HALF_EVEN))


def _money(quantity_units, price_cents):
    return _round_cents(quantity_units * price_cents)


def _shocked_value(quantity_units, price_cents, shock_bps):
    return _round_cents(quantity_units * price_cents * (10_000 + shock_bps),
                        SCALE * 10_000)


def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise RiskError("duplicate JSON key")
        out[key] = value
    return out


def _not_float(_):
    raise RiskError("JSON floating-point values are forbidden; use integer units")


def load_fixture(path: Path):
    raw = path.read_bytes()
    if not raw or len(raw) > 256_000:
        raise RiskError("portfolio fixture size limit exceeded")
    try:
        document = json.loads(raw, object_pairs_hook=_pairs_no_duplicates,
                              parse_float=_not_float, parse_constant=_not_float)
    except (ValueError, UnicodeError) as exc:
        raise RiskError("invalid portfolio fixture JSON") from exc
    return evaluate(document, raw)


def evaluate(document, raw=b""):
    _object(document, ("schema", "base_currency", "events", "marks_cents",
                       "stresses", "history", "confidence_bps"), "portfolio")
    if document["schema"] != SCHEMA or document["base_currency"] != "USD":
        raise RiskError("unsupported portfolio contract")
    events = document["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise RiskError("invalid event count")
    marks = document["marks_cents"]
    if not isinstance(marks, dict) or not 1 <= len(marks) <= 12:
        raise RiskError("invalid mark set")
    for asset, price in marks.items():
        _asset(asset)
        _integer(price, "mark price", 1, 10**12)

    cash = 0
    net_contributions = 0
    realized = 0
    overhead_fees = 0
    lots = {asset: [] for asset in marks}
    seen = set()
    previous = 0
    for event in events:
        if not isinstance(event, dict):
            raise RiskError("invalid event")
        kind = event.get("kind")
        if kind in ("CASH_IN", "CASH_OUT", "FEE"):
            _object(event, ("id", "sequence", "kind", "amount_cents"), "cash event")
            amount = _integer(event["amount_cents"], "cash amount", 1)
        elif kind in ("BUY", "SELL"):
            _object(event, ("id", "sequence", "kind", "asset", "quantity_units",
                            "price_cents", "fee_cents"), "trade event")
            asset = _asset(event["asset"])
            if asset not in marks:
                raise RiskError("trade asset missing from marks")
            qty = _integer(event["quantity_units"], "quantity", 1, 10**12)
            price = _integer(event["price_cents"], "trade price", 1, 10**12)
            fee = _integer(event["fee_cents"], "trade fee")
            amount = _money(qty, price)
            if amount <= 0:
                raise RiskError("trade notional rounds to zero cents")
        else:
            raise RiskError("unsupported event kind")
        event_id = _identifier(event["id"], "event ID")
        sequence = _integer(event["sequence"], "sequence", 1)
        if event_id in seen or sequence <= previous:
            raise RiskError("duplicate event or non-increasing event sequence")
        seen.add(event_id)
        previous = sequence

        if kind == "CASH_IN":
            cash += amount
            net_contributions += amount
        elif kind == "CASH_OUT":
            if amount > cash:
                raise RiskError("cash withdrawal exceeds available balance")
            cash -= amount
            net_contributions -= amount
        elif kind == "FEE":
            if amount > cash:
                raise RiskError("fee exceeds available balance")
            cash -= amount
            overhead_fees += amount
        elif kind == "BUY":
            expense = amount + fee
            if expense > cash:
                raise RiskError("purchase exceeds available cash")
            cash -= expense
            lots[asset].append([qty, expense])
        elif kind == "SELL":
            available = sum(position[0] for position in lots[asset])
            if qty > available:
                raise RiskError("sale exceeds available units; shorting disabled")
            if fee > amount:
                raise RiskError("sale fee exceeds gross proceeds")
            remaining = qty
            basis = 0
            while remaining:
                lot_qty, lot_cost = lots[asset][0]
                removed = min(remaining, lot_qty)
                cost = lot_cost if removed == lot_qty else _round_cents(
                    lot_cost * removed, lot_qty)
                basis += cost
                if removed == lot_qty:
                    lots[asset].pop(0)
                else:
                    lots[asset][0] = [lot_qty - removed, lot_cost - cost]
                remaining -= removed
            cash += amount - fee
            realized += amount - fee - basis

        if abs(cash) > MAX_INT or abs(net_contributions) > MAX_INT:
            raise RiskError("portfolio value exceeds safety bound")

    positions = []
    total_market_value = 0
    total_basis = 0
    quantity_by_asset = {}
    for asset in sorted(marks):
        qty = sum(item[0] for item in lots[asset])
        basis = sum(item[1] for item in lots[asset])
        value = _money(qty, marks[asset])
        if qty:
            positions.append({
                "asset": asset, "quantity_units": qty,
                "mark_price_cents": marks[asset],
                "market_value_cents": value, "open_cost_cents": basis,
                "unrealized_pnl_cents": value - basis,
            })
        quantity_by_asset[asset] = qty
        total_market_value += value
        total_basis += basis
    equity = cash + total_market_value
    if equity <= 0 or equity > MAX_INT:
        raise RiskError("portfolio equity outside supported range")
    for position in positions:
        position["exposure_bps"] = _round_cents(
            position["market_value_cents"] * 10_000, equity)

    unrealized = total_market_value - total_basis
    net_pnl = equity - net_contributions
    reconciliation = net_pnl - (realized + unrealized - overhead_fees)
    if reconciliation != 0:
        raise RiskError("accounting reconciliation failed")

    def shock_result(shocks):
        if not isinstance(shocks, dict) or set(shocks) != set(marks):
            raise RiskError("shock vector must cover every marked asset")
        stressed = 0
        for asset in sorted(marks):
            basis_points = _integer(shocks[asset], "return bps", -10_000, 20_000)
            stressed += _shocked_value(quantity_by_asset[asset],
                                       marks[asset], basis_points)
        stressed_equity = cash + stressed
        if stressed_equity < 0 or stressed_equity > MAX_INT:
            raise RiskError("stressed equity outside supported range")
        pnl = stressed_equity - equity
        return {
            "equity_cents": stressed_equity, "pnl_cents": pnl,
            "loss_cents": max(0, -pnl),
        }

    stresses = document["stresses"]
    if not isinstance(stresses, list) or not 1 <= len(stresses) <= 32:
        raise RiskError("invalid stress case count")
    scenario_rows = []
    stress_ids = set()
    for scenario in stresses:
        _object(scenario, ("id", "shocks_bps"), "stress case")
        name = _identifier(scenario["id"], "stress ID")
        if name in stress_ids:
            raise RiskError("duplicate stress ID")
        stress_ids.add(name)
        scenario_rows.append({"id": name, "shocks_bps": scenario["shocks_bps"],
                              **shock_result(scenario["shocks_bps"])})

    history = document["history"]
    if not isinstance(history, list) or not 20 <= len(history) <= MAX_RETURNS:
        raise RiskError("historical simulation requires 20 to 2000 observations")
    confidence = _integer(document["confidence_bps"], "confidence", 5_000, 9_900)
    observed = []
    names = set()
    for sample in history:
        _object(sample, ("id", "returns_bps"), "historical sample")
        name = _identifier(sample["id"], "history ID")
        if name in names:
            raise RiskError("duplicate history ID")
        names.add(name)
        observed.append(shock_result(sample["returns_bps"])["loss_cents"])
    tail_count = (len(history) * (10_000 - confidence) + 9_999) // 10_000
    worst = sorted(observed, reverse=True)[:tail_count]
    var_cents = worst[-1]
    expected_shortfall = _round_cents(sum(worst), tail_count)
    if var_cents > expected_shortfall:
        raise RiskError("tail risk ordering failed")

    result = {
        "schema": SCHEMA, "synthetic": True,
        "currency": "USD", "quantity_scale": SCALE,
        "event_count": len(events),
        "accounting": {
            "cash_cents": cash, "net_contributions_cents": net_contributions,
            "realized_pnl_cents": realized, "nontrade_fees_cents": overhead_fees,
            "unrealized_pnl_cents": unrealized, "equity_cents": equity,
            "net_pnl_cents": net_pnl, "reconciliation_delta_cents": reconciliation,
        },
        "holdings": positions,
        "stresses": scenario_rows,
        "historical_risk": {
            "method": "nearest-rank loss quantile on constructed one-period shocks",
            "confidence_bps": confidence, "observation_count": len(history),
            "tail_observations": tail_count,
            "var_cents": var_cents,
            "expected_shortfall_cents": expected_shortfall,
            "return_horizon": "one synthetic interval",
            "note": "Illustrative scenario distribution; no predictive calibration or liquidity model",
        },
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "signed": False,
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode("ascii")
    result["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return result
