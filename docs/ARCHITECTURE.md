# Generation Zero architecture and trust boundaries

## Boundary inventory

1. **Scenario fixture → C++ decoder:** Strict eight-column unquoted CSV subset, positive integer prices in USD cents, nonnegative timestamps, positive sequence identifiers, enum source-health states, unique event identifiers. The fixture generator is a simulation authority, not an external market truth source.
2. **C++ replay state:** Events sorted by receipt time. A replay at step N only observes N received records. Latest per-venue state and source-dependency annotations are derived from those records.
3. **Source health semantics:** `OK`, `DEGRADED`, `UNTRUSTED` originate in synthetic fixtures. Runtime checks additionally mark sources stale after 2500 ms of receipt-time inactivity or ineligible after a sequence gap. Recovery after a gap is not automated.
4. **Upstream independence:** The upstream ID is asserted by the fixture; the engine deduplicates healthy sources with identical upstream IDs, but cannot infer a hidden upstream relationship.
5. **Financial arithmetic:** Price inputs are fixed integer USD cents. Derived metrics and concentration policy use `long double`. No production decimal accounting, currency conversions or ledger is provided.
6. **Risk/evidence gate:** At least two fresh, gap-free, independently labeled upstreams; at most 150 bps cross-venue disagreement; at most 75% proposed post-action BTC exposure.
7. **Core → HTTP API:** The server launches a fixed binary, with whitelisted scenario filenames and numeric step argument. No shell invocation. It binds to localhost only.
8. **API → dashboard:** The browser receives JSON state and displays synthetic labels. API mutation routes are limited to replay operations. CSP and same-origin mutation checks reduce basic browser-based risks, but are not a replacement for authentication.

## Distinguish what is verified

- Original fixture SHA-256 is calculated by Python over the file bytes; it demonstrates byte identity, not independent market authenticity.
- The decision receipt is a deterministic JSON explanation of the current calculation; it is **not signed** and does not provide an independently verified formal proof.
- Hidden scenario truth is not evaluated in this vertical slice.
- The reference price is a simple demonstrator, not a trustworthy price oracle.
- Replaying identical inputs produces byte-identical C++ JSON on the tested execution environment. Cross-platform floating-point reproducibility is not yet established.
- Historical event time is recorded but not retroactively used to improve an earlier decision.

## Generation One audit extension

The core selects one eligible venue per declared upstream according to the latest received record, breaking receipt-time ties by venue name. This removes dependence of the representative price on venue-name traversal order. Venues expose both eligibility and whether they were used in the reference mean.

The synthetic decision includes three structured checks for source count, cross-venue disagreement and portfolio concentration. Checks that lack required evidence are marked `NOT_EVALUATED` rather than passed. The read-only Python API creates a canonical SHA-256 receipt over the current versioned state and fixture hash. No key or signing claim is implied.

See [decision audit contract](DECISION_AUDIT.md) for the precise data fields and limitations. This is an intermediate step in G1 and does not supersede the Generation Zero baseline.

## Principal open risk

Two distinct true market states can sometimes be observationally indistinguishable. This initial implementation represents insufficient evidence through an abstention state but does not compute rigorous admissible uncertainty sets. Its source-health labels are simulated, and it can be misled by mislabeled compromised inputs. Formalizing and measuring that failure boundary is the next scientific task.
