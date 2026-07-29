# ADR 0003: Evaluator Contracts And Model Judge Isolation

## Status

Accepted.

## Context

EvalForge will support deterministic evaluation, model-based evaluation, and human evaluation. Model judges can help assess semantic, grounding, citation, and rubric-based behavior, but they are vulnerable to nondeterminism, prompt injection, manipulation, bias, and correlated failure.

## Decision

All evaluator implementations must conform to common evaluator contracts. Deterministic evaluators must be isolated from model judges. Model judges must have versioned judge models, prompts, rubrics, parameters, thresholds, and calibration evidence. Judge output must not be treated as authorization policy, deployment-gate override authority, or unquestionable truth.

Human review and adjudication must remain available for high-risk, ambiguous, disputed, or deployment-blocking decisions.

## Rationale

Consistent evaluator contracts allow metrics, comparisons, and gates to use evaluation evidence without depending on evaluator internals. Model-judge isolation prevents unreliable model output from controlling security or deployment authority.

## Alternatives Considered

- Treat model judges as the primary source of truth. Rejected because judge outputs can be wrong, biased, or manipulated.
- Implement separate evaluator interfaces for every metric family. Rejected because it would fragment aggregation and comparison behavior.
- Use human review only. Rejected because it would not scale for repeated experiment workflows.

## Consequences

Model-based evaluation requires calibration, disclosure, and review policy. Deterministic and human evaluation remain first-class evidence sources.

## Security Implications

Untrusted model output must not decide authorization, tenant access, or override gates. Judge prompts and outputs must be protected as tenant-scoped evidence.

## Modularity Implications

Evaluator contracts belong in provider-neutral domain or package layers. Model-provider adapters must not determine authorization requirements or gate authority.

## Revisit Conditions

Revisit if evaluator families require additional common contract fields, if model-judge reliability changes materially, or if owner-approved policy changes human-review requirements.
