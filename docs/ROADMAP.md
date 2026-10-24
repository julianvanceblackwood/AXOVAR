# Research and development gates

## G0 — executable vertical slice

C++ engine, synthetic fixtures, independent upstream baseline, risk gate, replay, loopback dashboard, executable tests. This is the only implemented gate.

## G1 — quantitative and temporal reliability

**First implemented slice: deterministic source selection and decision audit.** The core selects one latest eligible receipt per declared upstream with a deterministic tie rule, exposes the policy gate statuses, and publishes a read-only canonical audit payload with a SHA-256 checksum. Automated tests cover same-fixture reproduction and boundary cases. See [decision audit contract](DECISION_AUDIT.md).

**Still required for G1 completion:**

Canonical binary or versioned event formats, robust numeric precision, configurable policies, asynchronous source health, explicit clock domains, gap recovery, deterministic raw persistence, mathematical reference tests, multi-source estimator experiments and strong baseline comparisons.

## G2 — quantitative risk and systemic dependencies

Add real risk statistics with known units and horizons, portfolio event sourcing, stress testing, liquidity constraints, margin and collateral simulation, contagion network experiments.

## G3 — defensive execution and settlement

Add provenance-aware local execution traces, on-chain read-only adapters, simulated settlement finality, counterparty assumptions and cross-domain incident reconstruction. Include a separate threat model for each adapter.

## G4 — formally checkable decisions

Specify decision machine invariants, model check a bounded subset, independently verify decision receipts, compare exact reproducibility across platforms, and evaluate conservative abstention trade-offs.

## G5 — performance and hardware evaluation

Benchmark event pipeline tail latency, state updates and replay; identify actual bottlenecks; isolate and verify FPGA-compatible interfaces. Do not claim acceleration before measurement.

## G6 — scientific evaluation

Blind synthetic scenarios, comparison against credible baselines, false assurance measurements, ablations, calibrated uncertainty under explicit assumptions, reproducible engineering report and external review.
