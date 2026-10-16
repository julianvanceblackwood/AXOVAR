# AXOVAR Intelligence

## Research question

Can a local research assistant explain financial state, contradictory evidence and the reason for a deterministic policy decision without gaining authority over that decision?

## Scope in the first implementation

`server/intelligence.py` constructs an allowlisted, bounded evidence snapshot from existing C++ JSON output. It contains derived metrics, current venue states, source assumptions, alerts and event identifiers. The model receives no filesystem access, browser access, shell, tools, secrets or transaction endpoints.

The dashboard calls `GET /api/intelligence/status` and `POST /api/intelligence/ask`. The latter accepts a question up to 1000 characters and a boolean `use_model`. The session is sampled under a lock before model processing. Model invocation cannot change replay state. Responses include `mode`, `model`, `scenario`, `step`, `evidence_ids` and limitations.

When a model is not available, a deterministic evidence interpreter answers a limited set of scenario questions. It is not described as generative AI. A language model may provide natural-language technical explanations, but its text is not verified and must not alter authoritative decisions.

## Optional model

The integration uses the local Ollama `POST /api/chat` API with streaming disabled. Default open-weight model: `gemma3:4b`. The model is supplied by its original provider, not trained by AXOVAR. It must be downloaded separately. The default endpoint is fixed to `http://127.0.0.1:11434` and is not configurable through a user prompt.

`ollama pull gemma3:4b`

Start the local Ollama service, then run AXOVAR. Ollama and Gemma license terms apply to model use and distribution. No weights are committed to the repository.

## Threat boundaries

- The assistant consumes only curated state, not raw fixture files or arbitrary web pages.
- Scenario state is synthetic. Source independence and health are source assertions, not authenticated truths.
- A model response can be mistaken or manipulated by prompt injection, even if it contains correct event identifiers.
- The application labels local-model answers separately from deterministic explanations.
- Model generation is bounded by output-token and HTTP response limits, with a 30-second upstream timeout.
- Failure to reach the model returns an evidence-only explanation and does not modify the deterministic policy engine.
- API is loopback-only without multi-user authentication. Do not publish the server on an untrusted network.
- Questions are not persisted by AXOVAR; Ollama itself is a separate local service with its own runtime and settings.
- No independent claim-level verification of model prose exists. This is a stated research limitation.

## Future research

Independent claim checking, structured source citations, retrieval over versioned research artifacts, calibrated uncertainty estimates, explicit sensor health and adversarial evaluation are future research. None are implied by the current chat interface.

## Verification

`ctest --test-dir build --output-on-failure`

`intelligence_tests` covers deterministic answers, state consistency, input constraints, cross-origin rejection, optional-model stubs and fallback behavior. Tests do not download model weights and do not claim to validate the actual model's language quality.
