# Start with AXOVAR

AXOVAR is an independent financial systems research project. It asks a practical question: **what should a decision system do when the market evidence behind a proposed action is incomplete, delayed or dependent on the same source?**

It is not a trading platform, investment strategy or connected financial account. The current software runs locally against deliberately synthetic fixtures.

## What you can test

| Research area | Working example | What it does not establish |
| --- | --- | --- |
| Market evidence | C++20 replay of healthy and degraded venue observations, including declared upstream dependencies | Authenticity of external data feeds or production market integrity |
| Decision trace | Explicit policy results and a reproducible local SHA-256 audit receipt | Cryptographically signed attestations or permission to place trades |
| Portfolio risk | Ordered synthetic USD journal, FIFO lots, accounting reconciliation, stress shocks and constructed one-period VaR / Expected Shortfall | Calibrated market forecasts, customer portfolio reporting or liquidity risk |

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

In the dashboard, inspect **Evidence Lab** to see source selection, check status and the replay audit hash. Open **Portfolio Risk** for the separately constructed portfolio book, FIFO accounting and hypothetical shock results. The two workspaces do not share live state or a real trading account.

## A useful technical challenge

Try to make the engine arrive at an unjustified conclusion using **synthetic input only**. In particular:

- Can two venues that declare the same upstream be mistaken for independent sources?
- Can delayed input or a sequence gap influence a decision before it was observed?
- Does a failed or unevaluated risk check ever appear as a pass?
- Does the portfolio's cash, FIFO cost and marked equity still reconcile after partial sales or fees?
- Can a controlled change in the fixture be detected by its published digest?

When reporting a finding, include the commit SHA, operating system, compiler version, fixture, steps, expected outcome and observed outcome. The [source-dependency review issue](../issues/3) is a concrete starting point. For other reproducible issues, use [GitHub Issues](../issues). Do not publish credentials or confidential customer data.

## Boundaries and collaboration

This is a public research repository. It has **no declared open-source license at present**; access to the source does not automatically grant permission to copy, modify, redistribute or commercially reuse it.

Technical feedback, independent reproduction and focused research conversations are welcome. For private inquiries, use [email](mailto:julianvanceblackwood@gmail.com).

[Main README](../README.md) · [Market decision audit](DECISION_AUDIT.md) · [Portfolio calculations](PORTFOLIO_RISK.md) · [External evaluation](EXTERNAL_EVALUATION.md)
