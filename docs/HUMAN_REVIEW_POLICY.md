# Human Review Policy

## Status

This document defines planned human-review policy. It does not implement review assignment, UI, or adjudication workflows.

## When Human Review Is Required

Human review is required when:

- A deployment gate depends on ambiguous correctness, safety, policy, or user-impact evidence.
- Model-judge confidence is low, uncalibrated, disputed, or safety-relevant.
- Review involves high-risk content, tool side effects, agent autonomy, or sensitive tenant data.
- Evaluator disagreement exceeds documented thresholds.
- Owner-approved policy marks a dataset, metric, gate, or workflow as human-review mandatory.

## Blind And Non-Blind Comparison

Blind comparison should be used when reviewer bias could affect variant selection. Non-blind review may be used for diagnostics, security review, or adjudication when context is necessary. Review mode must be recorded with the review.

## Rubric Versioning

Rubrics must be versioned. Review records must bind to the rubric version, instructions, scale, allowed decisions, evidence requirements, and reviewer-facing context used at review time.

## Reviewer Assignment

Reviewer assignment must consider required expertise, tenant access, workload, conflicts of interest, and independence where blind review is required. Assignment and reassignment must be audited.

## Conflict Of Interest

Reviewers should not be sole approvers for changes they authored when the decision can block or permit deployment. Conflicts must be disclosed or mitigated through additional review or adjudication.

## Adjudication

Adjudication resolves disagreement or high-impact decisions. The adjudicator must have explicit authorization and must record final decision, evidence, rationale, affected metrics or gates, and relationship to prior reviews.

## Review Disagreement And Agreement Metrics

EvalForge must preserve individual reviews before adjudication. Human-review agreement and inter-rater agreement must be reported where enough reviews exist. Disagreement should trigger additional review, rubric refinement, evaluator calibration, or gate failure depending on policy.

## Reviewer Comments And Evidence

Reviewer comments must cite evidence where possible, including run, test case, trace, span, artifact, citation, or metric observation references. Comments may contain sensitive data and must follow tenant access and retention policy.

## Audit History

Review assignment, submission, edit-by-correction, adjudication, reviewer removal, rubric changes, and deployment-blocking decisions must be audited.

## Protection Against Model-Judge Anchoring

Human reviewers should not be shown model-judge output in blind review unless the review design explicitly requires it. When model-judge output is shown, reports must disclose that reviewers had access to it.

## Sensitive Content

Review workflows must protect sensitive prompts, completions, retrieved context, tool outputs, and reviewer comments. Reviewers must have tenant and workspace authorization for the evidence they inspect.

## Deployment-Blocking Decisions

Human decisions that block or permit deployment must be bound to rubric version, reviewer or adjudicator identity, evidence, timestamp, and gate definition. Overrides require explicit authorization and audit history.

Related documents: [Evaluation Taxonomy](EVALUATION_TAXONOMY.md), [Metric Definitions](METRIC_DEFINITIONS.md), and [Security Baseline](SECURITY_BASELINE.md).
