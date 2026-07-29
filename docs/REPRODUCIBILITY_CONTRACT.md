# Reproducibility Contract

## Status

This document defines what EvalForge must capture in later milestones to reproduce, explain, or compare experiments. It does not implement run execution.

## Required Capture For Experiments

Each experiment run must capture:

- Dataset and test-case version, including immutable dataset snapshot identity and content hash.
- Prompt version and rendered prompt inputs where permitted by data governance.
- Model provider and model identifier.
- Model parameters such as temperature, maximum output length, tool mode, response format, and seed when supported.
- Retrieval configuration, including source identity, index version, embedding configuration, filters, ranking, chunking, and top-k behavior.
- Tool definitions and schemas, including tool side-effect classification and version.
- Workflow version, agent policy, step rules, retry rules, and termination criteria.
- Evaluator versions and configurations, including deterministic rules, judge prompts, judge model versions, rubric versions, thresholds, and calibration evidence.
- Pricing version with provider, unit, currency, effective interval, and assumptions.
- Random seeds when supported by the target, provider, evaluator, or sampling system.
- Environment and application version for the evaluated target.
- Source commit for EvalForge-controlled code and evaluated application code where available.
- Execution timestamps for experiment, run, attempt, trace, span, evaluator, and review events.
- Repetition index for repeated runs.
- Trace and artifact references with stable IDs and hashes.
- External dependency limitations such as provider behavior, corpus drift, unavailable seeds, and hidden provider changes.

## Snapshot And Hashing Requirements

- Finalized dataset snapshots must freeze test-case membership and version references.
- Content used for execution must have stable hashes where technically practical.
- Artifact hashes must cover stored bytes or canonicalized content, with the hashing method recorded.
- Completed run snapshots must bind artifact versions, configuration versions, timestamps, traces, evaluator outputs, pricing assumptions, and source references.
- Hash mismatches must invalidate exact reproducibility claims and trigger diagnostic reporting.

## Immutable Completed Runs

Once a run reaches a completed terminal state:

- Evaluation-significant inputs, outputs, traces, artifacts, metric observations, and cost observations must not be mutated.
- Corrections must be represented as new runs, new evaluations, superseding records, or audited correction events.
- Deletion must follow tenant-scoped governance while preserving required audit evidence under policy.

## Reruns And Comparisons

- A rerun creates a new run identity and records its relationship to the prior run.
- Comparisons must identify baseline and candidate runs, variants, dataset snapshot, metric definitions, evaluator versions, and aggregation rules.
- Repeated runs must preserve repetition indexes so variance can be analyzed.
- If exact reproduction is impossible, EvalForge must disclose which dependency or provider behavior prevents it.

## External Nondeterminism

Provider-hosted models, embedding systems, retrieval indexes, target applications, network behavior, and model judges may be nondeterministic even when parameters are captured. EvalForge must distinguish explainability from exact replay. A result may be reproducible as evidence if all recorded inputs and versions are available, even when a provider cannot guarantee identical generated output.

## Required Disclosure

Experiment reports and gate evidence must state:

- Whether exact reproduction is expected, approximate, or impossible.
- Which captured versions and hashes define the run.
- Which external dependencies may have changed.
- Whether model-judge outputs or human reviews influenced the decision.

Related documents: [Domain Model](DOMAIN_MODEL.md), [Metric Definitions](METRIC_DEFINITIONS.md), and ADR [0002](adr/0002-versioned-artifacts-and-immutable-run-snapshots.md).
