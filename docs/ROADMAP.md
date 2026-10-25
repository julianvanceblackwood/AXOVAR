# Research and development gates

## G0 — executable vertical slice

C++ engine, synthetic fixtures, independent upstream baseline, risk gate, replay, loopback dashboard, executable tests. This was the original full vertical slice; parts of G1 and G2 are now implemented separately.

## G1 — quantitative and temporal reliability

**First implemented slice: deterministic source selection and decision audit.** The core selects one latest eligible receipt per declared upstream with a deterministic tie rule, exposes the policy gate statuses, and publishes a read-only canonical audit payload with a SHA-256 checksum. Automated tests cover same-fixture reproduction and boundary cases. See [decision audit contract](DECISION_AUDIT.md).

**Still required for G1 completion:**

Canonical binary or versioned event formats, robust numeric precision, configurable policies, asynchronous source health, explicit clock domains, gap recovery, deterministic raw persistence, mathematical reference tests, multi-source estimator experiments and strong baseline comparisons.

## G2 — quantitative risk and systemic dependencies

**Implemented first research slice:** deterministic replay of a synthetic USD portfolio ledger with FIFO acquisition lots, integer-cent accounting, long-only positions and independent reconciliation. The module exposes price-shock P&L, constructed one-period return samples and descriptive 95% empirical VaR and Expected Shortfall. Its API is read-only and separate from the G0/G1 market replay. See [risk methodology and arithmetic](PORTFOLIO_RISK.md) and [portfolio acceptance tests](../tests/test_portfolio.py).

**Unfinished G2 gates:** authenticated position and price ingestion, cross-module event sourcing, calibrated statistical risk with real data licenses, duration/horizon semantics, volatility and correlation estimation, liquidity constraints, margin and collateral simulation, portfolio factor attribution and contagion network experiments.

The new shock samples are deliberately fabricated for regression testing and must not be described as live data, historical realized returns or investment results.

## G3 — defensive execution and settlement

**Implemented first research slice:** versioned synthetic settlement intents with simulated execution references, read-only canonical block reconstruction, bounded fork replacement, reversible confirmation-depth policy, independent counterparty hold states and an incident timeline. Each fixture event participates in a deterministic hash-linked evidence trace. The local API provides a reproducible report without wallet keys, RPC calls, broadcast transactions or execution authority. See [settlement contract and threat boundaries](SETTLEMENT_RESEARCH.md).

**Unfinished G3 gates:** actual read-only chain adapters, externally authenticated chain state, real consensus/finality semantics by network, licensed counterparty data, cross-domain settlement and portfolio reconciliation, durable evidence storage and incident recovery under independent verification. The local policy threshold does not establish economic or legal finality.

## G4 — formally checkable decisions

Specify decision machine invariants, model check a bounded subset, independently verify decision receipts, compare exact reproducibility across platforms, and evaluate conservative abstention trade-offs.

## G5 — performance and hardware evaluation

Benchmark event pipeline tail latency, state updates and replay; identify actual bottlenecks; isolate and verify FPGA-compatible interfaces. Do not claim acceleration before measurement.

## G6 — scientific evaluation

Blind synthetic scenarios, comparison against credible baselines, false assurance measurements, ablations, calibrated uncertainty under explicit assumptions, reproducible engineering report and external review.
