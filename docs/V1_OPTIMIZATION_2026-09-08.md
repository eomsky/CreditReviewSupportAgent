# v1 optimization measurements

Time box: 2026-09-08 01:49:39–02:49:39 KST. This record is updated until the freeze.
Same saved STX PDF extraction, Gemma 4 26B A4B BF16, A100-SXM4-80GB.
Parent watchdog includes process startup and retrieval index creation. Upload/OCR,
model cold start and browser rendering are excluded: these are **not** measured
as full employee upload-to-result latency.

| Revision | Parent seconds | Opinions / 30 | Calls | Full document | Finding |
|---|---:|---:|---:|---|---|
| 91f6cc7 | 78.272 | 10 | 12 | No | Repeated routing stopped analysis |
| cfe4f83 | 101.674 | 3 | 6 | No | Prefetch alone did not fix repeated routing |
| 9c946e6 | 120.034 | 9 | 19 | No | Watchdog; generated Python referenced unavailable dataframe |
| 85faff0 | 82.939 | 30 | 8 | Yes | Foundation failed; material scope/units/semantic errors |
| 7dc4da6 | 98.818 | 15 | 6 | No | Financial extraction hit 5,000 output-token cap |
| dcb23dd | 78.442 | 30 | 8 | Yes | Foundation 13.38s; dataset retained, Python lacked result assignment |
| 54ffbad | 103.069 | 30 | 9 | Yes | Shared dataframe result and critical-factor review; remaining semantic defects |

Document completion is not a quality pass. Manual comparison found errors even
when all 30 opinions existed and schema validation passed. Remaining concerns:
company and bank exposure distinction, consolidated/separate data consistency,
repayment maturity versus interest-reset schedules, off-topic pension assumptions
in forecasts, and unsupported reassurance about repayment or customer concentration.

Changes preserve source artifacts and calculation plans. New logic prepares shared
financial data once, computes through isolated Python, reviews related factors in
six bundles with two concurrent HTTP slots, and performs bounded cross-checks before
streaming a synthesis. Table search uses labels and retrieval locators; loaded
table prompts omit duplicate structural labels while retaining the complete selected
segment, scope headers, units and source identifiers. Missing evidence remains
internal while material qualifications remain in report prose.

The old frozen Drive production and old HTML were not changed. This v1 is a test
project baseline, not a replacement for prior production assets or a declaration
that the supplied reference-report quality has been achieved.
