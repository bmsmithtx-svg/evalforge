# Metric Definitions

## Status

This document defines planned metric meanings and contracts. It does not implement metric calculation.

## Metric Layers

- Raw observations are direct measurements or evaluator outputs such as tokens, latency, retrieved document IDs, judge rationales, or reviewer choices.
- Per-test-case scores normalize observations for one test case, attempt, run, or review item.
- Aggregations summarize scores across datasets, variants, repetitions, reviewers, or slices.
- Slices partition results by metadata such as dataset label, risk class, route, language, model, prompt, retrieval configuration, tool, or workflow.
- Confidence intervals communicate uncertainty where the sample size and metric type support it.
- Deployment-gate decisions apply versioned thresholds to stored evidence and may consider metrics, review decisions, and authorized overrides.

## Planned Metrics

| Metric | Intended meaning | Required inputs | Output type | Aggregation behavior and interpretation | Known limitations |
| --- | --- | --- | --- | --- | --- |
| Answer correctness | Whether the answer satisfies the expected answer or rubric. | Generated answer, reference answer or rubric, evaluator version. | Boolean, ordinal, or numeric score. | Aggregate as pass rate or mean score; interpret as task success evidence. | Reference ambiguity and incomplete rubrics can mislabel acceptable answers. |
| Semantic similarity | Degree of semantic overlap between generated and reference text. | Generated answer, reference text, embedding or judge configuration. | Numeric score. | Average by dataset or slice; interpret as approximate semantic closeness. | Similarity is not correctness and may miss factual errors. |
| Groundedness | Whether answer claims are supported by retrieved or provided context. | Answer, context passages, citations when present, evaluator version. | Numeric or categorical score. | Aggregate mean or failure rate; interpret as support from provided evidence. | Entailment judgments can be uncertain and context may be incomplete. |
| Faithfulness | Whether the answer avoids claims not supported by source material. | Answer, source context, evaluator version. | Numeric or categorical score. | Aggregate mean or violation rate; interpret as source adherence. | Does not prove the source itself is correct. |
| Hallucination rate | Frequency of unsupported or fabricated claims. | Answer, source context or references, claim extraction rules. | Rate or count. | Aggregate as unsupported claims per answer or affected-case rate. | Claim extraction and support checks can miss subtle fabrications. |
| Retrieval precision | Fraction of retrieved items that are relevant. | Retrieved item set, relevance labels. | Numeric ratio. | Average across cases and slices; interpret as retrieved-set purity. | Requires reliable relevance labels. |
| Retrieval recall | Fraction of relevant items retrieved. | Retrieved item set, known relevant items. | Numeric ratio. | Average across cases; interpret as coverage of relevant material. | Unknown relevant material reduces reliability. |
| Recall at K | Fraction of relevant items present in top K. | Ranked retrieval list, relevance labels, K. | Numeric ratio. | Average by K; interpret as top-K coverage. | Sensitive to K choice and label quality. |
| Precision at K | Fraction of top K retrieved items that are relevant. | Ranked retrieval list, relevance labels, K. | Numeric ratio. | Average by K; interpret as top-K relevance density. | Does not reward relevant items below K. |
| Mean reciprocal rank | Rank quality of the first relevant result. | Ranked retrieval list, relevance labels. | Numeric score. | Mean reciprocal rank across cases; higher means relevant result appears earlier. | Ignores additional relevant results after the first. |
| Normalized discounted cumulative gain | Ranking quality with graded relevance. | Ranked retrieval list, graded relevance labels, K when applicable. | Numeric score. | Average by query or slice; interpret as graded ranking quality. | Requires consistent graded labels. |
| Context relevance | Relevance of supplied context to the task. | Prompt, query, context passages, relevance evaluator. | Numeric or categorical score. | Aggregate as mean or low-relevance rate. | Relevance can be task-dependent and subjective. |
| Citation presence | Whether answers include required citations. | Answer, citation parser, task requirements. | Boolean or count. | Aggregate as citation-inclusion rate. | Presence does not imply validity. |
| Citation validity | Whether citation identifiers resolve to supplied or allowed sources. | Answer citations, source registry or retrieved context. | Boolean or ratio. | Aggregate as valid-citation rate. | Valid source references can still fail to support claims. |
| Citation entailment | Whether cited sources support cited claims. | Answer claims, citations, cited source text, evaluator version. | Numeric or categorical score. | Aggregate as supported-citation rate. | Entailment may require human review for high-risk claims. |
| Citation completeness | Whether material claims needing citation are cited. | Answer claims, citation requirements, source mapping. | Numeric ratio. | Aggregate as completeness rate. | Claim segmentation and citation requirements can vary. |
| Tool-selection accuracy | Whether the selected tool matches expected or acceptable tool choices. | Tool-call trace, expected tool set or rubric, tool definitions. | Boolean or numeric score. | Aggregate as accuracy or pass rate. | Multiple tool paths may be valid. |
| Tool-argument validity | Whether tool arguments satisfy schema and task constraints. | Tool-call arguments, tool schema, reference constraints. | Boolean, error count, or score. | Aggregate as validity rate and error categories. | Schema validity does not prove business correctness. |
| Tool-call sequence correctness | Whether tool calls occur in an acceptable order. | Tool-call trace, workflow version, expected sequence or policy. | Boolean or sequence score. | Aggregate as sequence pass rate. | Flexible workflows may require rubric-based evaluation. |
| Agent-trajectory success | Whether the agent reaches the intended outcome through acceptable steps. | Full trace, workflow policy, outcome rubric. | Boolean, ordinal, or numeric score. | Aggregate by task class and failure mode. | Requires rich traces and may be subjective. |
| Step efficiency | How many steps or tool calls are used relative to expected effort. | Trace spans, expected step budget or baseline. | Count, ratio, or score. | Aggregate mean, percentile, or over-budget rate. | Fewer steps are not always better if quality falls. |
| Policy compliance | Whether behavior satisfies versioned policy rules. | Trace, answer, tool outputs, policy version, evaluator version. | Boolean, count, or severity. | Aggregate violation rate by policy and severity. | Policies can be incomplete or require human interpretation. |
| Safety violation rate | Frequency of safety-policy failures. | Outputs, traces, safety evaluator, policy version. | Rate or count. | Aggregate by severity and scenario. | Detection can miss adversarial or ambiguous content. |
| Refusal appropriateness | Whether the system refuses when it should and answers when it should. | Prompt, answer, policy labels, evaluator version. | Categorical or score. | Aggregate as appropriate-refusal rate and false-refusal rate. | Requires well-labeled boundary cases. |
| Latency | Total elapsed time for a request, run, span, or workflow. | Timestamps or timing spans. | Duration. | Aggregate mean, median, percentiles, and slow-case rate. | Client, network, and provider timing may differ. |
| Time to first token | Delay before first generated token or streamed output. | Streaming timestamps or provider telemetry. | Duration. | Aggregate percentile and threshold violations. | Not available for all providers or non-streaming paths. |
| Token usage | Number of input, output, and total tokens. | Provider token counts or tokenizer version. | Count. | Aggregate totals, means, and per-case distributions. | Tokenization differs by provider and model. |
| Model cost | Cost attributed to model calls. | Token usage, provider, model, pricing version. | Currency amount. | Aggregate total, mean per case, and slice cost. | Pricing changes and discounts can alter real invoices. |
| Total experiment cost | Total estimated cost across model, embedding, retrieval, tool, storage, and execution components where measured. | Run costs, pricing versions, provider telemetry, execution metadata. | Currency amount. | Aggregate by experiment, variant, and repetition. | Some indirect costs may be estimated or unavailable. |
| Human-review agreement | Agreement among reviewers for a specific rubric or decision. | Multiple human reviews, rubric version, item IDs. | Ratio or categorical summary. | Aggregate by rubric, reviewer group, and task type. | High agreement does not guarantee correctness. |
| Inter-rater agreement | Statistical agreement beyond chance where applicable. | Reviewer labels, rubric categories, calculation method. | Numeric statistic. | Report by dataset and rubric; interpret as review consistency. | Requires enough reviewers and compatible label types. |
| Regression magnitude | Size of degradation from baseline to candidate. | Baseline metrics, candidate metrics, comparison configuration. | Difference, percent change, or effect size. | Aggregate by metric, slice, and confidence interval where applicable. | Small samples can overstate or hide change. |
| Pass rate | Fraction of cases or gates that pass criteria. | Per-case pass flags or gate decisions. | Ratio. | Aggregate by dataset, variant, metric, or gate. | Binary pass criteria can hide severity and near misses. |
| Error rate | Fraction of cases, runs, spans, or evaluator invocations ending in error. | Error events, attempts, run counts, evaluator logs. | Ratio. | Aggregate by component, provider, variant, and slice. | Error classification must be consistent to compare variants. |

Related documents: [Evaluation Taxonomy](EVALUATION_TAXONOMY.md), [Reproducibility Contract](REPRODUCIBILITY_CONTRACT.md), and [Product Requirements](PRODUCT_REQUIREMENTS.md).
