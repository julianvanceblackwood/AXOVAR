# AXOVAR

**Adversarial Financial Intelligence & Verifiable Systems Infrastructure**  
**Vance Blackwood | Generation Zero | Research implementation**

> What happens to a financial decision when the observations on which it depends become unreliable?

AXOVAR Generation Zero is an **executable, deterministic research vertical slice**. It demonstrates a controlled market-data integrity failure and a fail-closed simulated financial decision. It is not an exchange, trading bot, production risk management system, or financial recommendation engine.

## What works now

- C++20 engine with strict typed numeric parsing and validated synthetic market observations.
- Multi-venue price reconstruction ordered by **receipt time** (not future event time).
- Sequence gap detection, upstream-change signals, degraded/untrusted source exclusion and staleness checks.
- One observation per **independent eligible upstream** used for the reference price. Independence is an explicit fixture assumption.
- Cross-venue divergence measured in basis points; configurable policy is **not** yet implemented (values are compiled constants).
- Synthetic portfolio assessment of a proposed **0.1 BTC** purchase, with a 75% post-trade BTC concentration ceiling.
- Deterministic decision gate with `ALLOW_SIMULATION`, `DENY_SIMULATION`, or `INSUFFICIENT_EVIDENCE` states.
- Decision receipts linking the latest venue evidence IDs to the policy output.
- Python standard-library, **loopback-only** HTTP API and interactive dashboard driven by the actual C++ executable.
- Original fixture bytes and SHA-256 fingerprints exposed in the evidence panel (a hash **does not prove external truth or authenticity**).
- Two deterministic scenarios and automated C++ executable and API integration tests.

## Run on macOS / Linux

**Prerequisites:** CMake 3.20+, a C++20 compiler, Python 3.10+.

```bash
./run.sh
```

Open **http://127.0.0.1:8765**. The script configures the C++ project, builds the core, runs tests and launches the API and dashboard. No package installation, accounts, credentials, trading APIs or internet connection required.

Manual commands:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
python3 -m server.app
```

Run the core independently:

```bash
./build/axovar_core --scenario scenarios/NORMAL-001.csv 9
./build/axovar_core --scenario scenarios/DEGRADED-001.csv 9
```

The final argument selects the number of received events known to the analysis at that replay step.

## Scenarios

| Scenario | Design | Expected final decision |
| --- | --- | --- |
| `NORMAL-001` | Three independent, healthy sources, small price disagreement | `ALLOW_SIMULATION` |
| `DEGRADED-001` | Two degraded venues change to the same upstream; sequence gap, 8% divergence, delayed third venue | `INSUFFICIENT_EVIDENCE` |

Both results concern a **research-only simulated action**. No order submission or real account integration exists.

### Decision semantics

1. Require at least **two** eligible, fresh, gap-free, independent upstreams.
2. If eligible sources are insufficient, return `INSUFFICIENT_EVIDENCE`.
3. Otherwise, deny when observed cross-venue disagreement exceeds **150 basis points**.
4. Otherwise, deny when post-trade BTC exposure exceeds **75%**.
5. Only then allow the synthetic operation.

For clarity, the reference-price estimator is simply the arithmetic mean of one fresh healthy venue price per unique upstream. This is a **baseline**, not a robust market price oracle. If a compromised source misreports itself as healthy and is assumed independent, the current policy can fail. This is an explicit research limitation.

## API

- `GET /api/health`
- `GET /api/scenarios`
- `GET /api/state`
- `GET /api/raw`
- `POST /api/replay/scenario` with `{"scenario":"NORMAL-001"}`
- `POST /api/replay/step`
- `POST /api/replay/reset`
- `POST /api/replay/end`

The server listens only on `127.0.0.1`. **Do not expose to the internet.** There is no multi-user authentication or production-grade rate limiting. State is process-local and shared among browser clients.

## Architecture

```text
CSV scenario fixtures (original bytes)
            |
            v
     C++20 core
     | parsing / validation
     | event receipt ordering
     | venue state + source dependencies
     | basic risk and evidence gates
     v
     JSON decision and evidence receipt
            |
            v
  Python loopback HTTP adapter
            |
            v
  JS/CSS offline-ready research dashboard
```

This initial release intentionally uses **vanilla JavaScript** rather than React to remain runnable with no external package installation. A React/TypeScript migration can be evaluated after core APIs stabilize. The infrastructure is a modular *seed*, not yet the complete modular monolith from the research directive.

## Verification

Execute `ctest --test-dir build --output-on-failure`. See [architecture and limitations](docs/ARCHITECTURE.md) and [development roadmap](docs/ROADMAP.md).

## Non-claims

The initial slice does **not** implement: calibrated uncertainty sets, on-chain settlement, real-time exchange adapters, persistent raw evidence database, historical backtesting, real blockchain risk, machine-learning analytics, FPGA acceleration, cryptographic source authentication, actual upstream-independence discovery, formally verified financial decisions, multi-user operations, or production regulatory compliance.

Financial arithmetic currently uses integer cents for input events and `long double` for a **toy valuation**; it is not a production ledger-grade precision policy. Raw SHA-256 verification occurs in the Python API and is separate from C++ decision semantics. Alerts do not independently prove source compromise.

No live financial transactions are supported.

## External engineering references

- [CPMI-IOSCO Principles for Financial Market Infrastructures](https://www.bis.org/committees/cpmi/pfmi/overview)
- [CPMI-IOSCO Cyber resilience toolkit (consultative, September 2026)](https://www.bis.org/publications/cpmi-iosco-cyber-resilience-toolkit-practical-considerations-fmis)
- [MAS Guidelines on AI Risk Management for FIs (issued October 2026)](https://www.mas.gov.sg/regulation/guidelines/guidelines-on-artificial-intelligence-risk-management-for-financial-institutions)

These are research references, not claims of compliance or endorsement.

## Portfolio relationship

- **KORDAXIS:** evidence-native reasoning and decision provenance (conceptual alignment).
- **ELENCHION:** evidence-bounded execution intelligence and observability limits (research alignment).
- **TEICHION:** hardware-owned event sequencing and canonical seal records (future interface research).

No existing repository was modified or copied. Integration requires separate technical review and verification.
