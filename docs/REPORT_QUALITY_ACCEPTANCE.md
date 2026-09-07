# Report quality and latency acceptance

The target is an evidence-grounded credit-review draft comparable in analytical
depth to the supplied reference reports, completed within 120 seconds. Report
length, 30 populated factors and valid JSON are not sufficient acceptance criteria.

## Required review

| Dimension | Evidence of an acceptable result |
| --- | --- |
| Facts and scope | Correct company, date, consolidated/separate scope and units; sources support each material amount. |
| Financial interpretation | Explain drivers and alternative explanations, connecting earnings, working capital, investment and cash available for debt service. |
| Debt service | Distinguish principal maturity from interest repricing, unrestricted cash from restricted balances, and debt balances from contractual cash flows including interest. |
| Transaction specificity | Distinguish the requested facility from historical borrowing; missing application terms limit the conclusion rather than becoming invented terms. |
| Risk and mitigation | A mitigation has a documented mechanism and scale; an unused commitment is not assumed to be available, and a support-capacity index is not a guarantee. |
| Coverage and relevance | Address the relevant factors without filling forecast analysis with unrelated pension assumptions or bank exposure with borrower financial assets. |
| Cross-factor consistency | Figures, period, scope and causal conclusions agree across factors and synthesis. Contradictory evidence is reconciled or explicitly bounded. |
| Reproducibility | Preserve document/page/table locations, calculation inputs and executed results, model/adapter revisions and request traces internally. |

Material unsupported reassurance, invented terms or figures, and incorrect debt
maturity/scope interpretation are hard failures. A model's own FULFILLED status
is not evidence that these criteria passed. An incomplete run must retain its
report while clearly identifying interruption; it must not be counted as complete.

Display a coherent report and concise progress summaries. Keep raw JSON, tool
traces and unresolved-work queues internal. Necessary factual qualifications
remain in report prose so that presentation does not misrepresent the evidence.

## Timing protocol

Record separately: upload/extraction/OCR, index construction, first report text,
analysis and Python time, final synthesis, and total completion. Cached-document
benchmarks must be labelled as such. A successful cached run under 120 seconds
does not establish fresh-document latency or reliability.

Use identical sources, prompts and decoding limits for base/adapter comparisons.
Select on validation cases; reserve held-out test cases for the final comparison.
Balance execution order and exclude a separately recorded warmup. Preserve failed
and timed-out runs, not just the fastest successful result.
