# Decision audit contract

AXOVAR Generation One introduces a narrow, reproducible research record. This is not a financial authorization system.

## Source selection

Input events are replayed in receipt-time order. Latest valid venue state is retained for each venue. A venue is eligible when its fixture health is OK, its receipt is fresh under the 2500 ms threshold and no sequence gap has been observed for that venue.

Multiple eligible venues may declare the same upstream identity. They are not independent evidence. The reference price uses exactly one representative per declared upstream:

1. Select the eligible venue whose retained receipt has the latest `receive_ms`.
2. For equal receipt times, select the lexicographically smaller venue name.
3. Sort upstream identifiers when forming the arithmetic reference mean.

Each venue includes `eligible` and `reference_selected` boolean fields. Eligibility does not imply selection. Declared upstream IDs are fixture claims. They do not prove actual physical or economic independence.

Cross-venue divergence deliberately includes all retained venue prices, including flagged inputs, to produce a conservative integrity warning. This is an adversarial stress test, not a calibrated price estimate. The current policy abstains if it cannot establish sufficient independent sources.

## Structured policy checks

The top-level `checks` array contains these identifiers in a fixed order.

| ID | Meaning | Statuses |
| --- | --- | --- |
| `INDEPENDENT_SOURCES` | At least two eligible declared upstream representatives | `PASS`, `FAIL` |
| `VENUE_DIVERGENCE` | Maximum cross-venue price disagreement of 150 bps | `PASS`, `FAIL`, `NOT_EVALUATED` |
| `CONCENTRATION` | Synthetic post-action BTC exposure at or below 75 percent | `PASS`, `FAIL`, `NOT_EVALUATED` |

Divergence cannot be evaluated with fewer than two retained venues. Concentration is not evaluated when there are fewer than two eligible independent sources. A `NOT_EVALUATED` check must never be presented as a pass.

The existing decision precedence is retained. Insufficient evidence takes priority over a failed risk threshold. When evidence is sufficient, the divergence threshold is checked before the synthetic concentration threshold.

## Read-only receipt endpoint

```text
GET http://127.0.0.1:8765/api/audit/receipt
```

The endpoint returns a `receipt` object and its SHA-256 hash. The canonical content contains:

- schema identifier `AXV-AUDIT-002`
- exact SHA-256 hash of the synthetic fixture file bytes
- scenario name, replay step, event count and knowledge-time boundary
- per-venue source eligibility, dependency-change quarantine, reference selection and receipt identifier
- policy identifier, outcome, explanatory reason, configured limits and all check results
- decision evidence IDs and selected derived metrics

The digest is calculated over the UTF-8 bytes produced by:

```python
json.dumps(receipt, sort_keys=True, separators=(",", ":"),
           ensure_ascii=True, allow_nan=False).encode("ascii")
```

An independent verifier should hash the canonical payload, compare the published SHA-256, then separately hash the original CSV fixture bytes and compare `fixture_sha256`. Receipt equality across identical replays and changes between different steps are covered by executable tests.

**G4 compatibility note:** the receipt schema was upgraded from AXV-AUDIT-001. Version 2 adds a per-venue dependency-change flag and explicit policy thresholds. Existing consumers must check the schema before using the receipt. A standalone checker independently replays the fixture and validates both policy logic and digest, described in [G4 verification](G4_VERIFICATION.md).

The receipt is **not signed**. The hash does not prove collection authenticity, tamper resistance against a hostile host, market truth, trading permission or regulatory compliance. The present representation includes derived decimal values, and bit-for-bit equivalence between different processor architectures or C++ implementations has not been established.

## Local verification

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

The `audit_tests` suite covers the stable upstream representative, tie handling, policy check status, maximum signed sequence number, reproducible hash and replay transitions.

## Next assurance gates

- Independent reference implementation of price, exposure and integrity arithmetic with controlled precision
- Explicit event-time versus receipt-time uncertainty and rules for gap recovery
- Versioned fixture format and provenance contract
- Property-based and adversarial synthetic scenario testing
- A persistent append-only evidence log with a defined trust and retention model
- Independently verifiable signing only after key custody and threat model have been specified
- Reproducible performance measurements with hardware, compiler and workload metadata

These are future work, not capabilities provided by the current receipt endpoint.
