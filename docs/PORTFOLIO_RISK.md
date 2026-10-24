# Portfolio replay and risk experiment

Contract: `AXV-RISK-001`  
Fixture: `scenarios/PORTFOLIO-001.json`  
Endpoint: `GET /api/risk/portfolio`

This is the first implemented G2 research slice. It models a long-only, USD-denominated portfolio with a deterministic synthetic journal, FIFO cost lots, marked positions and hypothetical asset-price shocks. It does not consume the G1 market replay. These two fixtures are intentionally isolated to prevent users from mistaking research data for authenticated market prices.

## Accounting contract

The JSON fixture has an explicit schema, currency, strictly increasing event sequences, unique event IDs, positive price and quantity fields and a finite number of records. Floats, duplicate keys, unsupported assets, short sales and overdrafts are rejected.

Supported event kinds are `CASH_IN`, `CASH_OUT`, `FEE`, `BUY`, and `SELL`. A quantity of 100000000 integer units equals one instrument unit, regardless of symbol. USD values are always integer cents. Every valuation uses decimal arithmetic with **ROUND_HALF_EVEN** to the nearest cent. The contract is not a general asset-precision or currency accounting standard.

A buy debits the sum of rounded execution notional and its commission. Its entire cost becomes an acquisition lot. A sale credits proceeds less commission and removes matching acquisition cost from the oldest lots first.

### Financial identities

For a trade of `q` integer quantity units and `p` cents per whole unit:

```text
notional_cents = round_half_even(q * p / 100000000)
buy_cash_delta = -(notional_cents + fee_cents)
sell_cash_delta = notional_cents - fee_cents
realized_sale_pnl = sell_cash_delta - fifo_released_cost
```

For each remaining position:

```market_value_cents = round_half_even(q * mark_price_cents / 100000000)
unrealized_pnl_cents = market_value_cents - remaining_fifo_cost_cents

equity_cents = cash_cents + sum(market_value_cents)
net_contributions_cents = cash_in - cash_out
net_pnl_cents = equity_cents - net_contributions_cents

reconciliation_delta_cents =
    net_pnl_cents - (realized_pnl_cents + unrealized_pnl_cents
                     - nontrade_fees_cents)
```

The engine refuses to produce a report unless this final reconciliation equals zero. Fees attached to trades are included in acquisition cost or deducted from sale proceeds; separate `FEE` events are a distinct overhead charge.

## Stress experiments

A stress assigns each marked asset a whole-number shock in basis points. A value of `-3000` means -30 percent and `1000` means +10 percent. Every shock vector must cover every marked asset, with shocks constrained to -100% through +200%.

The shocked mark is evaluated in one rational expression before rounding the resulting **position value** to cents. This avoids introducing an additional rounding stage at the unit price.

```text
stressed_position_value_cents =
    round_half_even(q * mark_price_cents * (10000 + shock_bps)
                    / (100000000 * 10000))

stressed_equity_cents = cash_cents + sum(stressed_position_value_cents)
pnl_impact_cents = stressed_equity_cents - base_equity_cents
scenario_loss_cents = max(0, -pnl_impact_cents)
```

These are price-shock experiments only. The scenario labelled `LIQUIDITY_SHOCK_PROXY` is a **price decline proxy**, not a liquidity, order-book depth, slippage or liquidation model.

## Synthetic empirical VaR and expected shortfall

The fixture has 60 **constructed** one-period shock vectors. They are not real historical observations, an independently sampled return distribution or a prediction of a future tail event.

The calculation applies the same revaluation formula to every constructed shock and sets

```text
loss_i = max(0, -pnl_i)
tail_count = ceil(N * (1 - confidence))
VaR = tail_count-th largest observed loss
ES = round_half_even(mean of the tail_count largest observed losses)
```

At a 95% confidence level with 60 synthetic observations, three observations form the stress tail. Both VaR and ES are non-negative. Small sample size, arbitrary shock selection, loss truncation, liquidity effects, changing correlations and tail uncertainty make this unsuitable for forecasting or regulatory capital use.

## Fixture and reproducibility

The starting book contains a $200,000 USD deposit, synthetic BTC and ETH purchases, a partial ETH sale, a fee and a cash withdrawal. The independent unit tests verify expected cash, FIFO basis, realized and unrealized gains, total equity and accounting identity in cents. A second calculation using the standard-library Decimal type independently reconstructs the shock tail from the published positions.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
python3 -m server.app --binary build/axovar_core
```

Open the **Portfolio Risk** tab at `http://127.0.0.1:8765`. The read-only endpoint `/api/risk/portfolio` returns `synthetic:true`, the accounting result, marked holdings, stress rows and risk summary, fixture byte digest and report digest. The report digest is the SHA-256 over the stable, sorted-key JSON representation of the report before the digest field is added. It is **not signed** and does not authenticate the fixture producer.

## Model and operational limits

- The portfolio has one USD cash account, no shorting, no borrowing, and a fixed 1e-8 quantity scale.
- Marks are fixture assertions; prices are not validated against any exchange or risk data vendor.
- VaR and ES use constructed finite vectors, not observed price histories or calibrated loss distributions.
- There is no collateral, margin, funding, settlement latency, market liquidity or counterparty model.
- The portfolio fixture is independent of the G1 synthetic BTC risk gate. Different balances or prices between tabs are deliberate; neither is a live account.
- Evidence hashes detect changes to local bytes, not deliberate replacement by a compromised host.
- Performance, account separation, exchange licensing, legal compliance and audit retention require separate work.

The next G2 engineering gates are a versioned portfolio event ingestion boundary, asset-level risk factor attribution, margin and collateral *simulation*, a genuine liquidity model with explicit data sources, and systemic dependency experiments. The existing G1 source-reconstruction and risk-policy components do not yet share an integrated production-safe state model with the portfolio module.
