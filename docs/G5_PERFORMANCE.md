# G5 — Measured performance and operational reliability

VANCE BLACKWOOD CAPITAL / RESEARCH SYSTEMS

Contract: `AXV-PERF-001` for core timings, `AXV-LOAD-001` for loopback HTTP observations.

**Current stage: implemented research measurement infrastructure, not an institutional production SLO.**

## Objective

G5 answers a more demanding question than "is the algorithm fast?" It asks how the existing financial decision implementation behaves under well-described workloads, where its latency comes from, and whether the result remains correct when requests are repeated or concurrent.

G5 does not infer a future customer load profile from invented inputs. Tests use synthetic, deterministic fixtures and standard-library tools; no proprietary exchange adapter, FPGA, trading account, latency accelerator or machine-learning engine is introduced.

## Two non-interchangeable measurements

### In-process C++ engine

`axovar_bench` is a separate binary that includes the same `axovar::load` and `axovar::json` implementation as the production-style local research executable.

- `ingest` measures file reading, input validation, event allocation and stable ordering.
- `replay` measures reconstruction of a selected event prefix, policy checks, and JSON serialization, from events already loaded into memory.
- Warmup runs are discarded. A fixed number of measured runs follows.
- Every run must match the baseline output fingerprint; inconsistent work fails the measurement.
- Durations are collected using C++ `std::chrono::steady_clock` as integer nanoseconds.
- p50, p95 and p99 use the **nearest-rank definition**: value at sorted position `ceil(N * percentile / 100)`, starting at 1.
- The measured runs are serial. These numbers **exclude process startup, Python HTTP overhead and network latency**.

Sample workloads are the nine-event normal and degraded market fixtures, and a generated 256-event maximum-contract case with eight distinct declared upstreams. The 256-event fixture is constructed deterministically inside the runner. The measurement report includes its SHA-256 digest rather than suggesting it is a market dataset.

The harness currently includes the monolithic C++ core behind `AXOVAR_NO_MAIN`; a future core/library split should eliminate this inclusion without changing measured semantics.

### Read-only loopback service

`benchmarks/service_load.py` starts a local, isolated `ThreadingHTTPServer` using the actual Python handler and compiled C++ core. It requests four routes under bounded concurrency:

- `GET /api/state`
- `GET /api/audit/receipt`
- `GET /api/risk/portfolio`
- `GET /api/settlement`

Every response is required to be HTTP 200 with valid JSON and route-specific correctness checks. Repeated responses for the same fixture must be byte-identical throughout the experiment; missing or corrupted responses fail the experiment. Requests never mutate the replay state.

Wall-clock request latency includes local HTTP and, where applicable, Python JSON handling and the child C++ process. The report records p50/p95/p99 per route, attempted requests, successes, failures, the fixed experiment duration and achieved request rate. An error **does not become a fast successful sample**: failures invalidate the test.

This is not a public concurrency benchmark, representative trading capacity estimate, multi-tenant security test or latency guarantee.

## Running G5

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure

python3 benchmarks/run.py \
  --binary build/axovar_bench \
  --warmups 20 \
  --samples 200 \
  --output reports/core-performance.json

python3 benchmarks/service_load.py \
  --binary build/axovar_core \
  --concurrency 4 \
  --requests-per-route 15 \
  --output reports/service-load.json
```

Both generated reports are machine-readable JSON. They record workload, relevant fixture hash, executable hash or runtime platform details and precisely what was measured. The GitHub Actions `g5-measurement` job also generates synthetic reports, stored as short-lived workflow artifacts.

**Do not compare absolute CI latency numbers from different GitHub-hosted runners as proof of optimization.** A credible before/after evaluation would pin processor model, CPU affinity, power policy, thermal conditions, OS/compiler/build options, sample count, concurrency, and resource isolation; then report confidence intervals or variability across independent repetitions.

## Reliability and software quality controls

The CI pipeline keeps the existing GCC, Clang and exact-byte compiler parity checks. G5 adds a separate **Clang UndefinedBehaviorSanitizer** compilation and CTest run. The suite exercises the existing core, API, audit, portfolio, settlement, verifier and the benchmark contract, rather than silently bypassing correctness tests for speed.

UndefinedBehaviorSanitizer detects only the configured family of runtime undefined behaviors under paths it executes. Passing UBSan is not a memory safety or formal proof. AddressSanitizer, fuzzing coverage, operational load thresholds, resource limits and privileged service isolation remain separate gates.

The `g5_performance_contract_tests` suite rejects corrupted benchmark parameters, impossible percentile ordering, mismatched fixture quantities and differing read-only responses under bounded concurrency. It deliberately does **not** assert a machine-independent maximum number of microseconds on a shared CI runner.

## Methodology and reference principles

- Google's SRE materials favor examining tail percentiles and clearly scoped service indicators, not relying on means alone: https://sre.google/sre-book/service-level-objectives/
- The Google Benchmark user guide documents warmup, repetitions, measurement variation and machine context; AXOVAR uses its own dependency-free bounded harness but adopts those reporting principles: https://google.github.io/benchmark/user_guide.html
- NIST SSDF emphasizes integrating security and verification throughout software development: https://csrc.nist.gov/pubs/sp/800/218/final

These are external methodological references, **not a certification, endorsement or institutional affiliation**.

## Investor/enterprise acceptance gates not yet satisfied

1. A workload derived from signed pilot requirements and legitimate user traffic.
2. Per-operation trace spans and system profiling that localize the actual dominant cost, not just whole-function measurements.
3. Measured SLO/error budgets under fixed deployment hardware, load levels, duration and cold-start conditions.
4. Multi-user authentication, secure data handling, service isolation, abuse rate limits and independent security review.
5. Real licensed data, authenticated market provenance, independent settlement/network verification and a valid risk model.
6. Evidence-backed reliability across restarts, disk errors, process crashes, recovery and sustained workload.
7. An actual hardware architecture review and, only if warranted, an independently measured FPGA or accelerator prototype.

**Current scope:** G5 measured research and bounded reliability validation. No FPGA acceleration, customer capacity, live trading performance, production availability or financial investment return is claimed.
