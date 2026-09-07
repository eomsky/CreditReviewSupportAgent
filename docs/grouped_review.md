# Upload preparation and grouped review

New LIVE runs use `ReviewState.review_strategy = grouped`. Old runs retain the
adaptive strategy when resumed. Frozen Drive assets are not changed.

Uploads start a two-worker preparation queue before Analysis Start. The cache is
keyed by PDF bytes, pipeline version and publication date under workspace/documents.
An already extracted document can be rebound to a new publication date without
re-extracting its geometry. Previous case-scoped v0.17 caches are adopted. Lexical
and configured dense indexes are reused by exact text/model keys in a bounded
process cache. Model or text changes do not reuse the same index.

Seven related factor groups receive deduplicated sources, datasets, calculations
and prior findings. Each LLM response may take one action per factor. A dataset is
validated and shared once inside a group; Python executes proposed calculations,
and subsequent LLM responses interpret the returned results. Reference validation
is unchanged. Candidate evidence is not semantic verification.

Two groups can run simultaneously. There are at most four grouped rounds before
unresolved work returns to the existing adaptive search/reframe/calculation loop.
Repayment capacity (F24) and overall risk (F30) follow prerequisite analyses.
Completed factors are skipped on resume, and each accepted judgement immediately
updates the report. Final narrative retains the existing SSE streaming path.

performance.json distinguishes `llm_next_actions` from individual LLM calls and
records preparation wait and first accepted report content. Grouping is a request
count optimization, not a guaranteed wall-clock speedup. Measure cold upload,
prepared-input first content, total completion, fallback rate and content coverage
with the same source documents. Shared calculations do not replace source or
semantic verification.
