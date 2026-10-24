# Product engineering gates

AXOVAR is an evidence-constrained financial decision research system. The goal is to determine whether that research can support a reliable, defensible institutional workflow. Funding is not an engineering milestone. Credible technical results, user need and a lawful commercial structure come first.

## Product hypothesis

**Proposed customer:** A digital-asset market risk team, execution infrastructure operator or internal research group that must explain why a proposed action was allowed, denied or held for insufficient evidence.

**Proposed product boundary:** Read-only evidence assessment and replayable decision assurance that sits beside an existing trading and risk stack. The earliest product must not accept or route live orders. Human owners retain control of strategy, capital, risk settings and downstream execution.

**Core value to validate:** Existing tooling often reports a numerical risk indicator without preserving the evidence, source dependencies, input cutoffs and policy semantics needed to investigate an adverse decision later. AXOVAR should make those dependencies and the reasons for abstention independently reproducible. This is a hypothesis, not a validated customer claim.

## Engineering acceptance gates

| Gate | Deliverable | Exit evidence |
| --- | --- | --- |
| A. Evidence contract | Versioned observations, clock domains, source identity and provenance claims | Strict schema, negative tests, deterministic replay and migration plan |
| B. Policy assurance | Exact numeric reference, configurable versioned policy, visible failed and unevaluated checks | Golden vectors, independent arithmetic oracle, boundary and mutation tests |
| C. Audit continuity | Immutable local append-only log, signed receipts under a documented key threat model | Crash recovery, deletion/tamper tests, key rotation procedure and independent verification |
| D. Integration isolation | Read-only adapters for external market sources and existing risk systems | Fixture replay, API contract tests, backpressure policy and no-trade guarantee |
| E. Operations | Health, metrics, bounded resource use, structured logs and reproducible builds | Failure injection, load and tail-latency measurements under stated hardware |
| F. Security | Authentication, least privilege, tenant boundaries, dependency review and vulnerability handling | Threat model, negative authorization tests, external security review |
| G. Controlled pilot | One approved workflow with an accountable design partner | Written pilot scope, lawful data use, usage observations and incident handling |
| H. Commercial proof | Evidence of repeat use and willingness to pay | Recorded interviews, pilot retention and commercial decisions. No invented traction |

Current G0 establishes a local synthetic research path. The first G1 audit tranche addresses part of B and the reproducibility portion of C. It does **not** satisfy the remaining gates.

## Non-negotiable boundaries

- Do not connect a read-write exchange API, brokerage account or key-custody system during the evidence-only pilot.
- Do not treat fixture-declared health or independence as authenticated market reality.
- Do not claim precise cross-platform financial arithmetic without controlled reference-vector evidence.
- Keep model-generated descriptions out of deterministic decision authorization. The existing optional local language-model feature is read-only and non-authoritative.
- Separate customer data rights, security, geographic export controls and financial regulations before external ingestion.
- Decide the open-source or source-available licensing strategy and ownership structure deliberately, before accepting outside code or requesting grants with licensing requirements.

## Evaluation design

Every product claim requires a reproducible experiment with an identified baseline. The initial benchmarks should include false approvals, inappropriate abstentions, missed source dependencies, stale data handling, sequence disorder, policy replay accuracy, mean and tail latency, and total time to investigate a decision. Report workload, hardware, compiler, dataset generation, sample count and failure cases.

A candidate feature is ready for a design-partner demonstration when a reviewer can run it independently, understand its failure modes and inspect a stable contract without access to private infrastructure.

## Investor diligence artifacts

A future financing process will need a concise problem statement, competitive landscape, customer evidence, intellectual-property position, architecture and data rights, security plan, reproducible benchmark record, roadmap by milestones, cost assumptions and defined use of proceeds.

Prepare these from documented evidence. Do not equate commit count, repository stars, generated dashboard screenshots or unsupervised model output with adoption or enterprise readiness.

## Current sequencing

1. Make the audit contract independently reproducible and fix policy-source selection ambiguity.
2. Build an exact arithmetic oracle and adversarial test generator.
3. Introduce versioned ingestion and clock-domain semantics.
4. Specify an append-only local evidence format and crash recovery.
5. Measure performance and failure behavior before deciding on distributed or cloud deployment.
6. Seek targeted engineering review and only then discuss bounded read-only design-partner pilots.

The implementation roadmap remains in [ROADMAP.md](ROADMAP.md). The active audit specification is [DECISION_AUDIT.md](DECISION_AUDIT.md).
