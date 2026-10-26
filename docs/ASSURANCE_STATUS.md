# Assurance status and outstanding acceptance criteria

VANCE BLACKWOOD CAPITAL / RESEARCH SYSTEMS

This record separates repeatable repository evidence from operational or commercial claims. A completed automated test is not an independently certified production control. AXOVAR is synthetic, local and read-only by design.

## Verified in-repository capabilities

| Boundary | Current evidence | Limit |
| --- | --- | --- |
| Market replay | Compiled C++ event processor, receipt-time ordering and source integrity checks | Source identity and observations are fixture assertions |
| Decision assurance | Independent exact-rational oracle, fail-closed source-identity changes, explicit check states | Fixed synthetic policy, not an unbounded formal proof |
| Bounded model exploration | All 408 declared traces and 1,608 replay prefixes checked against the core | Three-event, two-venue model only |
| Compiler parity | Linux CI compiles GCC and Clang independently and compares replay JSON bytes for every prefix of both bundled CSVs | No universal architecture, OS, compiler-flag or long-double portability claim |
| Evidence journal | Optional local hash-linked, self-contained fixture and audit records; verify-before-append and fsync | No signing, independent anchor, remote backup or hostile-host protection |
| API boundary | Loopback binding, strict local Host validation, cross-origin POST checks and size limits | No user authentication; localhost processes can still access the service |
| Portfolio experiment | Synthetic integer-cent FIFO book, stress analysis and finite-shock tail statistics | No production accounting, authenticated prices or calibrated VaR |
| Settlement experiment | Synthetic chain and counterparty reconstruction with reversible confirmation states | No node validation, custody, real finality or settlement |
| Regression process | CTest under GCC and Clang, browser syntax validation and compiler parity job | CI does not replace independent security review or end-to-end customer testing |

## Controls requiring external dependencies

| Gate | Acceptance evidence still needed | Why not claimed complete |
| --- | --- | --- |
| Data provenance | Licensed feeds, documented timestamps, provider authentication and independent data cross-checks | No access to real authorized provider agreements or production events |
| Cryptographic attestation | Threat model, identity binding, protected signing keys, key rotation and independent verifier | A file checksum is not a digital signature |
| Durable evidence custody | External immutable/retained storage, backup, retention policy and restoration tests | Local journal can be rewritten by an administrator controlling the host |
| Formal full-system proof | Independent state-machine specification, model-checking toolchain and covered implementation mapping | Bounded simulation is not exhaustive proof of C++ behavior |
| Multi-platform reproducibility | Exact-byte comparison across target processors, operating systems and compilers | Current parity is Linux GCC versus Clang only |
| Portfolio model validity | Real licensed data, independent statistical validation, horizon convention and liquidity/collateral modeling | Current shocks are constructed |
| Real settlement finality | Chain-specific consensus verification and custody integration under a security review | Current chain data is fictional |
| Institutional security | Authenticated multi-user design, isolation, secrets management, pen test and incident exercises | Loopback research service is deliberately not production hardened |
| Customer validation | Named design partner, lawful pilot, measured usage and repeated demand | No independent customer usage demonstrated |
| Investor readiness | Incorporation and IP ownership checks, forecast, budget, competition analysis and actual commercial evidence | Code execution alone is not funding evidence |

## Rules for future capability claims

1. Do not call a simulated outcome an investment result or authorize funds based on it.
2. Cite a reproducible fixture, exact commit, test command and independent reference for numerical claims.
3. Include missing inputs, known biases, trust assumptions and applicable time horizons.
4. Distinguish `PASS`, `FAIL`, `NOT_EVALUATED` and evidence-unavailable.
5. Reopen an assurance gate when its implementation, data source or threat model changes.

Current local verification:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

This document is not a substitute for actual independent assurance, legal advice or regulatory certification.
