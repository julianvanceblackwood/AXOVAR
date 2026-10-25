# Synthetic settlement and incident reconstruction

G3 contract: `AXV-SETTLEMENT-001`  
Fixture: `scenarios/SETTLEMENT-001.json`  
Endpoint: `GET /api/settlement`  
Scope: deterministic, read-only research without blockchain RPC, transactions, signatures or funds.

## Research question

What can a financial system defensibly conclude when a transaction initially appears to have enough confirmations, but the canonical chain later changes or a dependent counterparty becomes unavailable?

The research engine accepts ten constructed events: two synthetic intents, canonical block observations, a counterparty halt and recovery, two reorganization events, and a second halt. Its endpoint returns the resulting event-by-event decision history, independent counterparty state, active chain, incidents and hash-linked local evidence trace.

This **does not implement a blockchain node or validate consensus**. Every block hash and transaction ID in the fixture is an opaque, locally asserted test identifier. The word "confirmation" here means the modeled depth of an inclusion in an asserted canonical chain.

## Causal reconstruction

The synthetic event types are:

| Event | Effect |
| --- | --- |
| `INTENT` | Introduces a hypothetical transaction ID, simulated execution reference, asset, USD notional and counterparty |
| `BLOCK` | Appends an asserted block extending the current canonical tip |
| `REORG` | Atomically removes a canonical suffix and replaces it with a height- and parent-consistent fork |
| `COUNTERPARTY` | Updates the fixture-asserted `CLEAR` or `HALT` status |

Events require unique identifiers, strictly increasing sequence numbers and nondecreasing integer receipt timestamps. A block must reference the current canonical tip, have the next height and include only previously declared, nonduplicated transaction IDs. A reorganization must select a canonical ancestor, remove a nonempty bounded suffix and supply a valid replacement chain. Reused block identifiers are forbidden even when the old block was orphaned. The full replacement is validated before the active chain is changed.

At every step the engine reconstructs the status of each intent from the current canonical chain. It does not retroactively grant knowledge of later blocks to earlier steps.

## Reversible confirmation policy

For transaction `t` included at canonical height `h_t` and current tip height `H`:

```text
confirmations(t) = H - h_t + 1
```

The default fixture policy requires three confirmations:

| Chain status | Meaning |
| --- | --- |
| `NOT_OBSERVED` | Intent recorded, no canonical or orphaned inclusion observed |
| `PENDING_CONFIRMATIONS` | Canonical inclusion with fewer than three confirmations |
| `POLICY_CONFIRMED` | Canonical inclusion meets the local depth threshold |
| `REORGED_OUT` | Prior inclusion was removed from the canonical chain |

A transaction that reached `POLICY_CONFIRMED` may later be `REORGED_OUT`. The engine records the transition as a `CONFIRMATION_REVOKED` incident. This models a bounded confirmation policy, **not deterministic finality, consensus validity, settlement discharge or legal title**. The correct threshold in a real network depends on the chain, threat model, value and counterparty policy.

The independent counterparty state can be `CLEAR` or `HALT`. The local review gate is `REVIEW_ELIGIBLE` only when both:

- `chain_state == POLICY_CONFIRMED`
- `counterparty_state == CLEAR`

In every other state the gate is `HOLD`. **REVIEW_ELIGIBLE is not authorization to trade, broadcast, bridge, transfer, release collateral or settle.** No API endpoint accepts such an instruction.

## Reproducible scenario

The included fixture demonstrates:

1. A synthetic BTC intent reaches three confirmations.
2. Its counterparty changes to `HALT`, forcing `HOLD`.
3. A shallow chain reorganization occurs while leaving its inclusion intact.
4. The counterparty returns to `CLEAR`.
5. A deeper reorganization removes the previously confirmed transaction, creating `CONFIRMATION_REVOKED`.
6. A separate ETH intent reaches the depth threshold, then its counterparty is halted.

This separates chain inclusion, policy depth, counterparty dependency and manual review into different states rather than collapsing them into one "settled" boolean.

## Trace and receipt verification

Every event is encoded as sorted-key, ASCII JSON with compact separators. Its evidence hash links the prior event's digest and the current event encoding:

```python
event_bytes = json.dumps(event, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
evidence_hash = sha256(bytes.fromhex(previous_hash) + event_bytes).hexdigest()
```

The first `previous_hash` is 64 zero characters. The returned `event_trace` includes an event ID, sequence, type, previous digest and evidence digest; the final event digest is published as `trace_head`. The full report excludes `receipt_sha256` when being hashed, then adds the result:

```python
encoded = json.dumps(report, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("ascii")
receipt_sha256 = sha256(encoded).hexdigest()
```

A verifier should separately recompute the original fixture SHA-256, each linked event digest and the complete report digest. These hashes provide **local repeatability and accidental-change detection only**. An attacker who controls the fixture and report can rewrite both and recompute the hashes. No independent time anchor, signature, custody control or append-only durable storage exists.

## Security and trust model

| Boundary | What is asserted | What is not established |
| --- | --- | --- |
| Input fixture | Local, strict, bounded synthetic JSON | Real blockchain consensus |
| Block/transaction IDs | 64-character lowercase hexadecimal test strings | Valid network transaction structure |
| Chain selection | Explicit canonical tip changes in a replay | Proof of work, proof of stake or honest majority |
| Counterparty notice | Fixture-defined clear or halt state | Signed institutional attestations |
| Execution reference | Identifier tying a simulated intent to its record | Exchange order, broker fill or custody transfer |
| API | Local HTTP GET, no mutation or RPC | Authenticated multi-tenant API |
| Receipt | Deterministic digest and causal event lineage | Nonrepudiation, legal finality or independent verification |

The endpoint processes a bundled fixture only. It does not accept external URLs, chain RPC destinations, wallet secrets, private keys, broadcast transactions or state mutation. This avoids SSRF, endpoint credential leakage and unintended financial action in the current experimental boundary. Future read-only adapters would require a separate threat model addressing hostile JSON-RPC responses, fork choice, rate limits, provider dependency, network authenticity, clock domains and data licensing.

## Local validation

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
./run.sh
```

Open **Settlement Research** on `http://127.0.0.1:8765`, then select the replay event. The screen shows canonical height, local depth threshold, review state, incident list and evidence hashes. The G3 settlement fixture is independent from G0 market replay and G2 portfolio risk; balances and transaction identifiers do not cross these research boundaries.

The `settlement_tests` suite checks policy confirmation reversal, reorg reinclusion, counterparty hold, canonical parent and height validation, duplicate block/transaction rejection, strict fixture decoding, reproducible digests and the read-only API.

## Remaining G3 acceptance gates

- A versioned read-only adapter with explicit clock, chain and provider assumptions
- Authenticated data provenance and checks against independently operated nodes
- Real consensus and finality models for named networks, including probabilistic failure analysis
- Cross-domain settlement reconciliation linked to a licensed external data source
- Operational incident handling, durable evidence storage and retention policies
- Quantified counterparty exposure and collateral obligations
- A security assessment before any integration with client environments

Nothing in this research module proves a network's actual finality, settlement instruction validity or investor-grade operational reliability.
