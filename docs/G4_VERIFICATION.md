# Independent decision verification

AXOVAR G4 research slice  
Receipt contract: `AXV-AUDIT-002`  
Scope: synthetic market fixtures and policy `AXV-POLICY-001`

The decision verifier reconstructs source eligibility and policy outcomes from the original CSV fixture, rather than accepting the market engine's answers as ground truth. It is implemented in `verification/decision_reference.py` and does not import the C++ replay engine or the Python receipt producer.

This is **bounded differential verification**, not a formal proof of arbitrary execution, authenticated market observations or safety in real trading.

## Policy state and invariants

The reference uses exact rational numbers to decide threshold comparisons, and accepts the C++ engine's derived decimal output only within its documented four-place display precision.

1. A decision with fewer than two eligible declared upstream sources must be `INSUFFICIENT_EVIDENCE`.
2. A source with a sequence gap is ineligible. It does not recover automatically.
3. A venue reporting a different declared upstream after a previous observation is disqualified for the remainder of the replay. Later fixture `OK` labels alone cannot restore its source identity.
4. Only one eligible observation represents each declared upstream. Choose the latest received observation, then the lexicographically smaller venue for a tied timestamp.
5. The engine may not use an event received after the requested replay step.
6. The divergence comparison is against the retained venue price range at 150 basis points. It is a synthetic integrity policy, not an executable market price.
7. The concentration comparison uses the G1 demonstration book: 0.5 BTC held, 0.1 BTC proposed buy, and USD 35,000 cash. The 75 percent threshold is evaluated against the independent rational reference.
8. An `ALLOW_SIMULATION` outcome requires all policy gates to pass. A missing source requirement takes precedence over financial-risk denials.
9. The receipt must contain the correct evidence references, per-source eligibility and selection flags, check results and configured policy thresholds.
10. A receipt digest and fixture digest must match the exact canonical bytes independently reconstructed by the checker.

### Decision precedence

| Evidence condition | Policy outcome |
| --- | --- |
| Fewer than two eligible declared upstreams | `INSUFFICIENT_EVIDENCE` |
| Evidence sufficient, cross-venue divergence above 150 bps | `DENY_SIMULATION` |
| Evidence sufficient, divergence acceptable, concentration above 75% | `DENY_SIMULATION` |
| Evidence sufficient and both financial limits satisfied | `ALLOW_SIMULATION` |

The verifier also checks that concentration is marked `NOT_EVALUATED` when evidence is insufficient and divergence is marked `NOT_EVALUATED` when fewer than two venues have been observed.

## Versioned audit receipt

G4 changes the original G1 audit schema from `AXV-AUDIT-001` to `AXV-AUDIT-002`. The new canonical receipt preserves the declared `dependency_changed` flag for each source and the three explicit policy thresholds in the policy record.

The digest is unchanged conceptually: SHA-256 over `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")`. The schema version increment matters because **v1 and v2 receipt digests and field contracts are not interchangeable**. Existing consumers should reject an unfamiliar schema rather than silently accept new fields.

The checker rejects receipts with an inconsistent hash, a mismatched original fixture, a forged decision, altered source selections, contradicted numeric outcomes or incorrect policy metadata, even when an attacker has recomputed the hash of the modified payload.

It **cannot** establish whether the fixture itself is economically truthful. An adversary controlling the fixture, application and corresponding receipt can rewrite all three. There are no signatures, authenticated timestamping, durable append-only storage, custody boundaries or independent market data providers.

## Local verification

Run the standard regression suite first:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

With `./run.sh` running locally, capture a receipt and compare it with the matching on-disk fixture:

```bash
curl --fail --silent http://127.0.0.1:8765/api/audit/receipt > receipt.json
python3 -m verification.decision_reference \
  --receipt receipt.json \
  --fixture scenarios/NORMAL-001.csv
```

First select the normal scenario in the local dashboard. The command prints `{"errors":[],"valid":true}` when the receipt matches the supplied fixture and supported policy. A failed check exits with a nonzero status and prints the applicable mismatch reason.

### Automated evidence

`tests/test_g4.py` compares replay prefixes for the normal and degraded fixtures; performs a reproducible bounded matrix of source health, dependency and price states; checks exact price divergence and concentration threshold edges; verifies persistent source drift quarantine; and introduces deliberately forged or inconsistent receipts.

CI compiles the C++ core under both GCC and Clang, runs this suite alongside earlier CTest groups and checks the dashboard JavaScript syntax. Passing these tests establishes only the stated finite test coverage.

## Remaining G4 work

- A machine-checkable formal state-machine specification and model checking over a clearly declared finite state space
- Stronger event schema, ordering and gap-recovery semantics
- Cross-compiler exact-byte receipt comparisons with controlled floating-point representation
- Independent signing, key-custody and durable evidence retention under a documented threat model
- Broader mutation testing, property-based generation and conservatism/false-abstention measurements
- Independent technical review and adversarial evaluation

This release completes **the first verifiable-policy research slice**, not the full G4 gate.
