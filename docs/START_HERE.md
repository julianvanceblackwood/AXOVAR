# AXOVAR

VANCE BLACKWOOD CAPITAL / RESEARCH SYSTEMS

AXOVAR studies how financial policy decisions can be reconstructed when source data is incomplete, delayed or internally dependent.

It is not a trading platform, investment strategy or connected financial account. The current software runs locally against deliberately synthetic fixtures.

## What you can test

| Research area | Working example | What it does not establish |
| --- | --- | --- |
| Market evidence | C++20 replay of healthy and degraded venue observations, including declared upstream dependencies | Authenticity of external data feeds or production market integrity |
| Decision trace | Policy results, versioned audit receipt and independent G4 exact-rational verification | Cryptographically signed attestations, formal production proof or permission to trade |
| Portfolio risk | Ordered synthetic USD journal, FIFO lots, accounting reconciliation, stress shocks and constructed one-period VaR / Expected Shortfall | Calibrated market forecasts, customer portfolio reporting or liquidity risk |
| Settlement reconstruction | Local synthetic blockchain reorgs, counterparty holds, reversible confirmation policy and trace hashes | Valid blockchain consensus, real settlement, signed proof or payment authority |

## Try it locally

Requirements: CMake 3.20+, a C++20 compiler, Python 3.10+, macOS or Linux.

```bash
git clone https://github.com/julianvanceblackwood/AXOVAR.git
cd AXOVAR
./run.sh
```

The script builds the C++ engine, runs the automated tests and starts a loopback-only dashboard at **http://127.0.0.1:8765**. It does not require market credentials or a hosted account. The optional local language-model integration is not required.

If you prefer to inspect reproducibility without the dashboard:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
./build/axovar_core --scenario scenarios/NORMAL-001.csv 9
./build/axovar_core --scenario scenarios/DEGRADED-001.csv 9
```

The **normal** fixture ends in `ALLOW_SIMULATION`; the **degraded** fixture ends in `INSUFFICIENT_EVIDENCE`. These are synthetic policy results, not trade signals.

In the dashboard, inspect **Evidence Lab** to see source selection, check status and the replay audit hash. Open **Portfolio Risk** for the separately constructed portfolio book, FIFO accounting and hypothetical shock results. Open **Settlement Research** to step through a fabricated confirmation reversal and counterparty interruption. These workspaces do not share live state or a real trading account.

## Check evidence independently

A normal replay receipt can be downloaded from `/api/audit/receipt` and checked against its synthetic fixture using `python3 -m verification.decision_reference`. A local opt-in hash-linked evidence journal is available through `python3 -m verification.evidence_journal`. See [G4 verification](G4_VERIFICATION.md) for both commands and [assurance status](ASSURANCE_STATUS.md) for their trust limits.

The CI also enumerates 408 bounded policy traces and compares GCC/Clang replay output bytes on Linux. None of these steps authenticates real-world prices or creates a signed legal record.

## Measure the system

G5 adds real synthetic performance experiments with separate C++ and HTTP timing boundaries. After building, run `python3 benchmarks/run.py --binary build/axovar_bench --samples 200 --warmups 20` and `python3 benchmarks/service_load.py --binary build/axovar_core`. Neither measures real trading latency or market execution. See [G5 performance](G5_PERFORMANCE.md) for reproducibility, accuracy checks and benchmark limitations.

## Reproduction checklist

Use the bundled fixtures or new synthetic cases to test these conditions:

- Can two venues that declare the same upstream be mistaken for independent sources?
- Can delayed input or a sequence gap influence a decision before it was observed?
- Does a failed or unevaluated risk check ever appear as a pass?
- Does the portfolio's cash, FIFO cost and marked equity still reconcile after partial sales or fees?
- Can a controlled change in the fixture be detected by its published digest?
- Can a formerly confirmed simulated transaction become orphaned, and does the review gate immediately return to HOLD?

When reporting a finding, include the commit SHA, operating system, compiler version, fixture, steps, expected outcome and observed outcome. The [source-dependency review issue](https://github.com/julianvanceblackwood/AXOVAR/issues/3) is a concrete starting point. For other reproducible issues, use [GitHub Issues](https://github.com/julianvanceblackwood/AXOVAR/issues). Do not publish credentials or confidential customer data.

## Scope and contact

This is a public research repository. It has **no declared open-source license at present**; access to the source does not automatically grant permission to copy, modify, redistribute or commercially reuse it.

Report reproducible defects through [GitHub Issues](https://github.com/julianvanceblackwood/AXOVAR/issues). For private technical inquiries, use [email](mailto:julianvanceblackwood@gmail.com).

[Main README](../README.md) | [Decision audit](DECISION_AUDIT.md) | [Independent verification](G4_VERIFICATION.md) | [Portfolio risk](PORTFOLIO_RISK.md) | [Settlement](SETTLEMENT_RESEARCH.md) | [G5 performance](G5_PERFORMANCE.md) | [External evaluation](EXTERNAL_EVALUATION.md)
