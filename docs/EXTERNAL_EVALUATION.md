# External Evaluation Brief

**Status:** Generation Zero research demonstrator. Synthetic data and simulation only.

## The decision problem

When market observations are delayed, contradictory, stale or not independent, a financial system can calculate a plausible price while lacking sufficient evidence to justify an action. AXOVAR examines whether evidence checks and financial policy can remain separate and inspectable.

## What can be evaluated today

- A C++20 engine parses controlled market fixtures and derives a research-only state.
- Synthetic normal and degraded scenarios exercise source-health, staleness, sequence-gap and declared upstream-independence checks.
- A simulated purchase is evaluated against explicit divergence and concentration rules.
- A local dashboard exposes state, evidence references and simulated decision outcomes.
- Automated engine and API checks are documented in the main README.

Start with [the recorded demonstration](../README.md#recorded-demonstration), [local verification instructions](../README.md#run-locally) and [architecture](ARCHITECTURE.md). The local research API is bound to loopback; do not expose it publicly.

### Minimal independent check

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
./build/axovar_core --scenario scenarios/NORMAL-001.csv 9
./build/axovar_core --scenario scenarios/DEGRADED-001.csv 9
```

Compare the recorded inputs, the eligible observations, the derived decision and its stated reasons. Record the environment, revision and any mismatch. An expected demonstration is not a guarantee that every environment reproduces it.

## Questions worth testing

1. Can duplicate upstream dependency be mistaken for independent confirmation?
2. Does delayed or missing information change what the engine is allowed to conclude?
3. Are receipt-time constraints respected when event timestamps disagree?
4. Which outputs can be reproduced from preserved fixture inputs?
5. Where does the toy exposure calculation diverge from production accounting requirements?

## Boundaries

There is no real exchange connectivity, real-order execution, authenticated market data, calibrated forecasting, production ledger precision or production suitability claim. The optional local language model does not authorize financial decisions.

## Useful external input

Reproducible bug reports, adversarial synthetic fixtures, alternative source-independence models, numeric-assurance reviews and controlled evaluation proposals are welcome. Please identify the commit or revision, the tested scenario, expected behavior, observed behavior and supporting evidence.

Technical discussion: use repository issues for non-sensitive findings. For private or commercial discussions, use the contact route on the [research profile](https://github.com/julianvanceblackwood). Public repository access does not, by itself, establish an open-source license or commercial reuse rights. No customer, deployment, sponsor or institutional partnership is implied by this document.
