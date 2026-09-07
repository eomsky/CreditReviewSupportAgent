# Five-hour optimization and SFT record

Execution window: 2026-09-08 01:49:39–06:49:39 KST. This record is being
completed during the authorized window; final runtime verification is recorded
separately below. The original Drive production and HTML are outside this change.

## Acceptance and selection

The immutable first-hour `v1` tag points to `54ffbad`. It is a reproducible test
baseline, not an expert-quality certification. Later improvements remain on
`codex/credit-review-harness`; the tag is not moved.

**The combined target of reference-quality analysis and reliable two-minute
completion has not been demonstrated.** One fresh-PDF run finished in 113.78
seconds, but skipped the separate review and contained material interpretation
errors. Cached-report completion under two minutes is repeatable across several
configurations, but neither 30 populated factors nor a successful JSON contract
establishes credit-review quality.

Keep the base model as the default. SFT adapters are saved, unmerged, and available
for explicit comparison. The held-out comparison did not justify promoting an
adapter. No held-out result was used for another training pass.

## Measured report executions

Parent time includes process startup. Worker time includes preflight and index
construction. Cached runs reuse saved extraction; fresh runs re-extract the PDF.
Neither includes browser upload or rendering, and filesystem/model caches can be
warm. These are individual measurements, not a latency percentile or an SLA.

| Configuration | Parent seconds | Worker seconds | Factors | Calls | Material finding |
| --- | ---: | ---: | ---: | ---: | --- |
| First-hour v1, 54ffbad | 103.07 | 99.34 | 30 | 9 | Python executed; semantic defects remain |
| 56cd27e, cached | 84.49 | — | 30 | 9 | Bounded reference arrays stopped repeated-ID output |
| 5c2581f, cached, review thinking 768 | 80.77 | — | 30 | 9 | Scope/unit and guarantee interpretation errors |
| 69880e7, cached, base-only server | 85.15 | 82.97 | 30 | 9 | Optional Python plan omitted; quality fails |
| 69880e7, fresh 277-page PDF | 113.78 | 111.37 | 30 | 8 | Extraction 56.20s; no separate review or Python plan |
| bd2543e, cached, review thinking 1536 | — | 95.34 | 30 | 9 | Required Python plan executed; note-scope consistency improved; other errors remain |
| d650727, initial numeric-bundle thinking 1536 | — | 84.56 | 30 | 8 | Separate review explicitly skipped; some improvements, still unsupported conclusions |
| b249f33, cached, app-default concurrency 2 | 86.70 | 84.25 | 30 | 9 | Python executed; guarantee direction/currency errors and an unsupported maturity percentage remain |
| b249f33, fresh PDF, app-default concurrency 2 | 107.42 | 105.06 | 20 | 5 | Read timeout, no final synthesis; explicitly incomplete |
| b249f33, refined adapter after serving restore, cached | 107.65 | 105.07 | 0 | 3 | Repeated summary sentence hit 6,000-token cap; foundation provenance invalid |
| b249f33, base on same restored adapter-enabled server, cached | 91.20 | 88.48 | 30 | 9 | Full generation; separate quality assessment still required |

The last experiment is opt-in and is not selected merely because it uses more
reasoning tokens. Changes to scope, calculation requirements and thinking policy
also change the task; timing differences are not isolated causal estimates.

The base-only versus LoRA-enabled backend was separately tested with the same
512-output-token prompt. Three base-only trials took 5.019, 3.786 and 3.782 seconds;
the LoRA-enabled backend serving the base took 4.241, 4.498 and 3.805 seconds.
This small decode probe found no dramatic serving gain. It is not report quality
or employee latency evidence.

The fresh default run is a counterexample to reliable two-minute completion.
It is not a successful 107-second report. Its preserved partial content remains
available for diagnosis. The cached default run's first report appeared at 15.88s;
the fresh run's first partial report appeared at 73.84s.

## Changes retained

- Reuse document extraction and retrieval indexes. Table discovery indexes titles,
  row/column labels and locators, with full selected table bodies loaded for use.
  Repeated page openings are shared once in prompts.
- Preserve document coordinates and explicit statement sections through nested
  notes, so unlabelled separate-statement notes do not silently enter consolidated
  analysis. Original document text and extraction artifacts are unchanged.
- Build a shared, source-bound financial dataframe using literal table values.
  Require an LLM-authored Python plan alongside the dataframe, execute it in an
  isolated networkless container, and reuse executed results across factors.
- Bound reference arrays and factor-specific requirement keys. Configure compact
  JSON in the actual vLLM engine; a request-level whitespace flag was ineffective.
- Perform cross-factor review before F30 synthesis. Persist accepted, rejected,
  skipped and failed review states, without treating schema acceptance as expert
  validation. Preserve partial reports on interruption.
- Record per-call input, output and reasoning token usage, request durations,
  first report text and final streaming times. HTTP occupancy is labelled as
  client request activity, not GPU utilization.
- Add content-addressed report archives with full-hash verification on restore.
  Private documents, results, credentials and weights remain outside Git.

The optional PDF process pool preserved extraction output in the tested document,
but did not speed up the Codespaces raw extraction. Its default remains one
worker. The source-cell-address experiment did not demonstrate reliable output
and remains disabled by default.

## SFT and recovery

See [SFT evaluation](SFT_EVALUATION_2026-09-08.md) for exact stage counts and
comparisons. Four curriculum stages completed, followed by a train-only mixed
refinement. Data repairs preserve original archetype splits, source evidence,
units and explicit assumptions. No DPO or ALL30 evaluation records were trained.

The adapters use rank-16 language-attention LoRA on the pinned Gemma base revision.
Base weights were never merged with an adapter. Stage adapters, corrected data,
training/evaluation logs and recoverable optimizer checkpoints were backed up to
the new project Drive folders. A Drive-restored checkpoint actually resumed from
step 116 through step 120 with optimizer, scheduler and RNG state.

The final untouched four-prompt served test recorded normal completion for all
base, bundle and refined responses. The refined adapter emitted 57% fewer tokens;
its shorter elapsed time therefore does not demonstrate equal analytical depth.
Manual review found material semantic failures in all three modes.

## Remaining limitations

Important errors still include monetary multipliers in prose, provided versus
received guarantees, contractual debt cash flows versus balance-sheet debt, and
unsupported reassurance about repayment. Selective self-review does not reliably
correct these. Prompt instructions alone are insufficient safeguards.

The fast prepared engine supports the common dataframe/Python preparation, but
does not yet expose the queued engine's full arbitrary factor-specific calculation
loop. It must not be described as already completing every dynamic calculation
request. Retrieved evidence coverage and claim-level semantic validation need
further work before the reports meet the supplied reference standard.

Evaluation should require correct material claims, scope and units, independently
checked calculations, relevant transaction conditions and consistent synthesis.
Then measure fresh multi-document latency and repeatability. Do not weaken these
criteria to obtain a two-minute completion number.

## Next acceptance work

1. Bind each material numeric claim to a source cell or executed calculation,
   including period, scope, currency, multiplier and role (for example a guarantee
   received versus one provided). Numeric membership alone is insufficient.
2. Execute factor-specific calculations in the prepared path. The model must
   request missing calculations rather than manufacture new ratios in prose.
3. Supply transaction terms and the actual review question. An annual report by
   itself cannot establish a proposed loan amount, repayment schedule or bank
   exposure. Preserve such limitations in the opinion instead of filling them
   with unrelated facts.
4. Assess relevant claims and synthesis against both supplied example reports.
   Use fresh unseen cases for further model selection after the recorded test.
5. Once these checks pass, compare end-to-end fresh multi-PDF runs and cached
   employee interactions with identical work and documented latency distributions.

Final code regression: 128 tests passed. The regenerated three-cell server
notebook compiles and pins the same model revision as the adapters; it writes a
private recovery command and redacts the API key in displayed startup errors.
An entirely new Colab runtime installation was not repeated during this window.

The last refined-adapter failure was not just initial server compilation: the
preserved response repeated the same business-address confirmation sentence
until the 6,000-token cap. The server did log first-shape JIT latency, which is
also retained in the audit. The subsequent base run completed on that same
server. This is additional evidence against promoting this adapter, not proof
that all LoRA configurations degrade quality.

## Actual upload-screen check

At code `134a88b`, the PDF was uploaded through the normal workbench, with a new
case name. The screen confirmed that its cached document preparation was ready
before analysis. The saved run completed all 30 judgements and final synthesis
in 85.58 seconds of internal processing, using 9 LLM calls; its first-report
metric was 13.59 seconds. The UTC observation immediately before clicking was
21:22:00, and completion was saved at 21:23:30.992 (about 91 seconds apart).
This is not a precise browser instrumentation measurement. Intermediate content
and the final completion banner were visually observed.

The normal UI therefore functions after inference restoration. The generated
content still contains the material semantic defects described above and is
not promoted as an accepted credit review. Its source PDF and full case archive
are preserved separately. A subsequent presentation-only change limits visible
progress questions to two so the status block does not obscure the report.

Archive verification also exposed an incorrect-root call that produced an empty
ZIP. It was not uploaded as a valid backup. The packer now rejects missing case
directories and empty selections, and supports explicit single-case archives.
The corrected UI archive restores 67 files with the original case path.
