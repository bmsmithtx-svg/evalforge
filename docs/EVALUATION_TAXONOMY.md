# Evaluation Taxonomy

## Status

This document defines planned evaluator categories and interpretation rules. It does not implement evaluators.

## Primary Evaluation Families

### 1. Deterministic Evaluation

Deterministic evaluators produce the same output for the same inputs, configuration, and evaluator version. They include exact-match evaluators, normalized-match evaluators, structured-output and schema validation, reference-based scoring where rules are fixed, rule-based safety and policy checks, retrieval and ranking metrics, citation structure checks, tool-selection and argument checks, and latency, token, and cost measurements.

### 2. Model-Based Evaluation

Model-based evaluators use an LLM or other model as a judge. They include LLM-as-judge evaluation, semantic scoring, groundedness checks, citation entailment checks, pairwise comparison, and rubric-based review assistance. Judge model identity, prompt, rubric, calibration set, configuration, and thresholds must be versioned. Model judges are fallible and must not be treated as an unquestionable source of truth.

### 3. Human Evaluation

Human evaluation captures reviewer judgments under versioned rubrics. It includes blind review, non-blind review, pairwise review, rubric-based review, comments, evidence selection, disagreement tracking, adjudication, human-review agreement, inter-rater agreement, and deployment-blocking decisions.

## Evaluator Lifecycle

Evaluators are categorized by family, metric outputs, supported input evidence, deterministic or nondeterministic behavior, calibration requirements, and risk level. Each evaluator must have a stable evaluator identity and immutable evaluator version when used for recorded results.

Configuration must capture thresholds, normalization rules, judge prompts, model parameters, rubric versions, reference data, retrieval settings, safety policies, and aggregation rules where applicable. Invocation must record inputs, evaluator version, execution timestamp, errors, and output. Interpretation must disclose limitations and avoid collapsing raw evidence, scores, aggregate metrics, and gate decisions into a single unsupported claim.

## Required Evaluator Categories

| Category | Family | Contract |
| --- | --- | --- |
| Exact-match and normalized-match evaluators | Deterministic evaluation | Compare output against reference strings with documented normalization. Useful for constrained answers; limited for semantically equivalent free text. |
| Structured-output and schema validation | Deterministic evaluation | Validate JSON or other structured outputs against schemas and constraints. Useful for tool and API compatibility; does not prove semantic correctness. |
| Reference-based scoring | Deterministic evaluation or model-based evaluation | Compare generated output with expected references using explicit scoring rules or a versioned judge. Limited by reference quality and coverage. |
| Rule-based safety and policy checks | Deterministic evaluation | Apply versioned rules to detect prohibited content or policy failures. Limited by rule coverage and adversarial phrasing. |
| Retrieval and ranking metrics | Deterministic evaluation | Measure retrieved-document quality using labeled relevance or expected sources. Limited by relevance labels and corpus drift. |
| Citation and grounding checks | Deterministic evaluation or model-based evaluation | Assess citation presence, validity, entailment, completeness, groundedness, and faithfulness. Limited by source quality and entailment uncertainty. |
| Tool-selection and argument checks | Deterministic evaluation | Validate selected tool and arguments against expected tool definitions, schemas, and reference behavior. Limited when multiple valid tool plans exist. |
| Agent-trajectory checks | Deterministic evaluation, model-based evaluation, or human evaluation | Assess step order, state transitions, tool use, recovery, and final outcome. Limited by incomplete observability and multiple acceptable paths. |
| Latency, token, and cost measurements | Deterministic evaluation | Record timing, token usage, and pricing-version-based costs. Limited by provider reporting accuracy and pricing changes. |
| LLM-as-judge evaluation | Model-based evaluation | Use a versioned judge model, prompt, rubric, calibration, and configuration. Must disclose nondeterminism, bias, and susceptibility to manipulation. |
| Pairwise and rubric-based review | Model-based evaluation or human evaluation | Compare alternatives or score against rubrics. Requires versioned rubrics and clear evidence requirements. |
| Human review and adjudication | Human evaluation | Capture reviewer decisions and resolve disagreement through authorized adjudication. Limited by reviewer expertise, fatigue, and bias. |
| Composite scores | Derived evaluation | Combine multiple metric observations using documented weighting and thresholds. Must preserve component scores and avoid hiding safety-critical failures. |

## Limitations And Prohibitions

- Model-judge output must not determine authorization, tenant access, or deployment-gate override authority.
- A model judge must not be treated as an unquestionable source of truth.
- Composite scores must not hide severe safety, security, or tenant-isolation failures.
- Evaluator comparisons must use versioned evaluator definitions and disclose evaluator drift.
- Human review is required where policy, safety, ambiguity, or deployment impact exceeds model-judge confidence.

Related documents: [Metric Definitions](METRIC_DEFINITIONS.md), [Human Review Policy](HUMAN_REVIEW_POLICY.md), and ADR [0003](adr/0003-evaluator-contracts-and-model-judge-isolation.md).
