# Upload preparation and grouped review

New and resumed LIVE runs use `ReviewState.review_strategy = grouped`. Existing
evidence, calculations and accepted judgements are preserved. Frozen Drive assets are not changed.

Uploads start a two-worker preparation queue before Analysis Start. The cache is
keyed by PDF bytes, pipeline version and publication date under workspace/documents.
An already extracted document can be rebound to a new publication date without
re-extracting its geometry. Previous case-scoped v0.17 caches are adopted. Lexical
and configured dense indexes are reused by exact text/model keys in a bounded
process cache. Model or text changes do not reuse the same index.

The central queue gathers up to six ready factors per request, including every
follow-up. It searches run-local prior requests/replies, source lookups, validated
datasets and executed calculations before each call. A lightweight lexical index
uses names/questions to select candidates; it does not make an extra LLM call.
Candidate evidence and previous LLM responses are not semantic verification.
Entity, period, scope, units and assumptions remain explicit in shared inputs.

Identical search/read/dataset/calculation actions reuse successful results. Code,
dataset IDs and assumptions are preserved in calculation cache keys. Failed
calculations are not reused. Accepted judgements remain factor-specific.
Two bounded service slots allow independent batches to overlap. Only the
coordinator applies replies and changes shared state. Each input is rebuilt at
dispatch from the latest shared results. Financial batches share one lane to
avoid duplicate extraction; repayment and overall conclusions wait for their
dependencies. Context size may reduce a batch. A concurrency of one retains the
serial engine for comparison.

While one HTTP request runs, the coordinator can retrieve evidence, validate
another reply and execute its Python calculation. Existing run-scoped RAM caches
reuse exact search/read/calculation results, and a bounded four-entry process
cache reuses document indexes. These caches are in Codespaces RAM, not Colab VRAM.
Local processing and request overlap, request occupancy, and server-reported
prompt/completion tokens are recorded in performance.json. HTTP occupancy and
local processing intervals are not hardware GPU/CPU utilization measurements.

All unresolved work stays in the shared queue, including schema repairs and
critical rechecks. There is no individual-call fallback. At most six queue rounds
are allowed. Repeated identical requests or two rounds without new evidence,
datasets, calculations or judgements stop early. A material gap/conflict receives
one recheck; any retained judgement remains qualified, never marked verified.
The default execution budget is 60 seconds from the shared measurements start.
The HTTP client receives that deadline through synthesis and final streaming.
The standalone full benchmark also has a 60-second process watchdog, covering
preparation and stuck calls, and preserves saved progress before reporting failure.
Completed factors are skipped on resume, and each accepted judgement immediately
updates the report. Final narrative retains the existing SSE streaming path.

performance.json distinguishes `llm_next_actions` from individual LLM calls and
records preparation wait and first accepted report content. Grouping is a request
count optimization, not a guaranteed wall-clock speedup. Measure cold upload,
prepared-input first content, total completion, fallback rate and content coverage
with the same source documents. Shared calculations do not replace source or
semantic verification.

Live smoke validation on 2026-09-07 with saved STX annual-report evidence:
F01/F02/F03 produced reference-validated judgements in one Gemma call, 14.78 seconds
total (11.86 seconds in the LLM call). This excludes initial PDF extraction, is
not a 30-factor completion benchmark, and does not establish semantic accuracy.
# Table discovery and deferred reads (2026-09-08)

SPT v0.17 structured tables now use title, section, row/column paths, units,
segment and source/page locators for lexical/dense retrieval. Numeric body cells
are excluded from this search representation. Unstructured legacy sources keep
their existing text path; no headers are invented.

The prompt initially receives a discovery card. An explicit `read` loads the
complete existing row segment and notes; it is shared across factors and is not
cut by the normal paragraph excerpt limit. Large tables remain segmented by the
existing extractor. Original artifacts retain cell provenance and geometry.
Dataset creation and conclusions cannot cite a structured table that has only
been discovered. A cached search does not count as an explicit read.

The earlier saved six-factor input measured 23,011 tokens before bookkeeping
compaction and 16,773 after (27.1% reduction), using the live server tokenizer.
This comparison predates deferred table reads; it is not an end-to-end latency
claim. The server reported 28,672 context tokens at measurement time; the notebook
setting of 49,152 requires a server restart and separate live verification.
