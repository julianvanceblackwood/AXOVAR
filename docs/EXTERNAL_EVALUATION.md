# Independent technical evaluation

**Status:** locally reproducible synthetic research, with implemented G0 replay, an initial G1 decision audit and an initial G2 portfolio-risk laboratory. No real trading or production certification is claimed.

## What AXOVAR examines

When market observations are delayed, stale, contradictory or share an upstream dependency, a plausible reference price does not necessarily justify a financial decision. AXOVAR separates source eligibility, stated risk policy and the ability to reproduce the resulting synthetic decision.

A separate portfolio module examines whether synthetic ledger events produce consistent cash, FIFO cost and marked equity, and how constructed return shocks affect that book.

## Available for independent reproduction

| Boundary | Inspect | Reproducible questions |
| --- | --- | --- |
| G0 market replay | `core/main.cpp`, `scenarios/NORMAL-001.csv`, `scenarios/DEGRADED-001.csv` | Do healthy and degraded evidence conditions produce defensible different outcomes? |
| G1 decision audit | `docs/DECISION_AUDIT.md`, `server/audit.py`, `tests/test_audit.py` | Are upstream representatives deterministic? Do unevaluated checks remain explicit? Can the receipt be recomputed? |
| G2 portfolio accounting and shocks | `docs/PORTFOLIO_RISK.md`, `server/portfolio.py`, `tests/test_portfolio.py` | Does the FIFO cost basis reconcile? Does an independent arithmetic oracle agree with synthetic stress and tail results? |

There is a [short first-run guide](START_HERE.md) and a [recorded dashboard replay](../README.md#recorded-demonstration).

## Reproduction

```bash
git clone https://github.com/julianvanceblackwood/AXOVAR.git
cd AXOVAR
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
./build/axovar_core --scenario scenarios/NORMAL-001.csv 9
./build/axovar_core --scenario scenarios/DEGRADED-001.csv 9
```

The tests include a local API harness; no internet account or exchange key is required. The web dashboard is loopback-bound. The audit and portfolio API outputs are deterministic under the tested environment, but their hashes are not signatures or trusted attestations.

## What would make a review valuable?

1. A minimal fixture showing an incorrect result or an unexamined assumption.
2. A comparison with an independent mathematical implementation and the exact precision used.
3. An analysis of source dependence, receipt-time ordering or false confidence.
4. A criticism of the synthetic return generator and its VaR / Expected Shortfall interpretation.
5. A negative test for input validation, authorization boundaries or unexpected changes across versions.

Please identify the commit SHA, environment, test input, intended invariant and observed behavior. [Source-dependency research question](https://github.com/julianvanceblackwood/AXOVAR/issues/3) is one existing starting point. For other nonsensitive findings, use [Issues](https://github.com/julianvanceblackwood/AXOVAR/issues).

## Assurance boundaries

The current implementation has no live market feeds, order routing, custody, client portfolio data, liquidity execution model, margin engine, audited security controls, authenticated upstream source identities or calibrated predictive risk forecasts. G0/G1 market replay and G2 portfolio research have independent synthetic inputs, not a shared live financial account.

The optional local language model is an explanatory tool, not an input to deterministic authorization. Portfolio VaR and Expected Shortfall use *constructed* finite shock samples and are not investment results or regulatory measures.

## Collaboration and rights

Constructive technical review and bounded research proposals are welcome. Private correspondence: [julianvanceblackwood@gmail.com](mailto:julianvanceblackwood@gmail.com).

This public repository does not currently declare an open-source license. Public readability alone is not permission for redistribution, modification or commercial use. No existing customers, sponsors, financing, certifications, institutional affiliation or external production deployment are claimed.

[Project README](../README.md) · [Getting started](START_HERE.md) · [Product evidence gates](PRODUCT_GATES.md)
