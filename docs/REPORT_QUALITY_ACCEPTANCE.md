# Report quality and latency acceptance

The target is an evidence-grounded credit-review draft comparable in analytical
depth and visible structure to the supplied reference report. The normative
outline and one-pass generation contract are in
[`REFERENCE_REPORT_BLUEPRINT.md`](REFERENCE_REPORT_BLUEPRINT.md). Report length,
30 populated factors, seven completed calls and valid JSON are not sufficient
acceptance criteria.

The production inference path is sequential and bounded: one LLM call for each
of the seven report sections, in display order. There is no foundation-inference
call, follow-up inference, quality re-inference, per-factor prose rewrite or extra
synthesis call. OCR, extraction, calculations, tables and charts are local code.

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

Record separately: upload/extraction/OCR, index construction, each of the seven
section calls, local calculation/chart time, first report text, and total completion. Cached-document
benchmarks must be labelled as such. A successful cached run under 120 seconds
does not establish fresh-document latency or reliability.

Use identical sources, prompts and decoding limits for base/adapter comparisons.
Select on validation cases; reserve held-out test cases for the final comparison.
Balance execution order and exclude a separately recorded warmup. Preserve failed
and timed-out runs, not just the fastest successful result.

## Depth observed in the supplied reference reports

The two reference examples connect a facility's purpose and before/after debt
structure to repayment capacity. Their useful depth includes:

- Sources and uses reconcile; refinancing, new cash, shareholder repayment and
  debt-to-equity conversion are distinguished. Conditions precedent, evidence of
  disbursement and remaining implementation milestones affect the conclusion.
- Industry demand, selling prices, utilization and planned capacity are linked
  to revenue and margin assumptions. Forecasts are separated from realized data;
  peer comparisons and downside sensitivities test those assumptions.
- Accounting losses, impairments, depreciation, cash investment and actual debt
  service are distinguished. Interest capitalization or payment deferral does
  not automatically eliminate the eventual cash obligation.
- Parent support and contingent liabilities are traced through specific entities,
  obligations and timing. Share ownership, asset value or group reputation alone
  is not an available repayment source.
- Borrower repayment, collateral recovery, bank exposure, covenants and bank
  profitability answer different questions and require their own evidence.

These are evaluation dimensions, not permission to invent missing application
terms or copy reference-company facts into another borrower report. Reference
wording is not automatically ground truth: material reassurance still requires
source and cash-flow verification. Reference images remain private and are not
part of the SFT dataset.
