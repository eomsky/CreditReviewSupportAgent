# SFT run and evaluation record

Base: `google/gemma-4-26B-A4B-it`, revision
`4d7ae4984b7db7de8f8457170b3f1a419ee76d52`. Unmerged BF16 attention LoRA:
rank 16, alpha 32, 11,489,280 trainable parameters. Vision/audio weights are frozen.
The pre-LoRA `v1` tag remains at `54ffbad`.

## Initial curriculum

The four-stage run completed at 2026-09-07 18:59:52 UTC. Selected examples retain
the original archetype-based split. No DPO or ALL30 evaluation records were trained.

| Stage | Selected examples | Optimizer steps | Best validation loss |
| --- | ---: | ---: | ---: |
| Factor/style | 384 | 192 | 0.8653614 |
| Bundle | 240 | 120 | 0.4976020 |
| Section | 160 | 80 | 0.2647998 |
| Full report | 64 | 32 | 0.1562181 |

Losses across stages have different target distributions and are not directly
comparable quality scores. Stage-best adapters and full recovery checkpoints are
separate artifacts. The private Drive run archive contains data, weights, hashes
and generated responses; they are excluded from this public repository.

## Initial generation comparison

Four held-out validation prompts, one per stage, were run against the base and
all four adapters. The same prompts, greedy decoding, rotated model order and
60-second/1,600-new-token limits were used. This comparison uses Transformers
generation and is **not** a measurement of vLLM production throughput.

| Mode | Responses recorded | Ended normally within limits | Timeout count |
| --- | ---: | ---: | ---: |
| Base | 4 | 2 | 2 |
| Factor/style adapter | 4 | 1 | 3 |
| Bundle adapter | 4 | 1 | 3 |
| Section adapter | 4 | 3 | 1 |
| Full-report adapter | 4 | 3 | 1 |

These are a small diagnostic sample, not a statistically reliable ranking.
The first summary used `completed` to count any recorded text. The evaluator now
distinguishes `responses_recorded` from EOS completion within the time/token cap;
the table above is recomputed from the original raw response flags.

Manual source review found material weaknesses: omission of supplied figures,
generic repeated cautions, malformed JSON, and unsupported causal conclusions.
Zero numeric-membership flags does not mean the answer used the necessary figures
or interpreted them correctly. No adapter is approved on this evidence alone.

## Train-only refinement

`prepare_refinement.py` builds a separate mixed rehearsal set of 592 records:
320 factor, 160 bundle, 80 section, and 32 full report. The original validation
and test records are unchanged. Revised training targets connect cash after
CAPEX, cash-only maturity gaps, plan versus break-even assumptions, and contingent
liabilities to qualified repayment conclusions. Known negative litigation flags
are preserved rather than described as missing. Irrelevant shared calculation
payloads are omitted from nonnumeric factor prompts.

The actual Colab tokenized set contains 715,343 training tokens, with maximum
sequence length 4,800 and no truncation. Cross-platform line endings change file
hashes; parsed canonical records were separately verified identical before use.
The actual tokenized data archive was uploaded to Drive and downloaded for full
SHA-256 verification. Refinement starts from the bundle adapter at learning rate
5e-6, with 80 planned steps and a ten-minute training cap. All 80 steps completed
at 19:25:08 UTC in 492.02 seconds, with best validation loss 0.5974601.
The adapter and a recoverable optimizer checkpoint were uploaded to Drive,
downloaded, reassembled and verified by SHA-256 and ZIP CRC.

## Recovery verified

A checkpoint at step 116 was downloaded from Drive in five pieces, reassembled,
hash-checked, then uploaded to a fresh Colab path. Actual training resumed through
step 120 with optimizer, scheduler and RNG state, retaining the original 192-step
learning-rate schedule. It ended as `RECOVERY_SMOKE_COMPLETE` at 19:16:28 UTC.
The four-stage final checkpoint was also downloaded from Drive and fully verified.

## Actual serving validation and untouched test

The restored vLLM server exposes the base and unmerged adapter names. A two-prompt
validation run found a full-report adapter looping until its output-token cap;
that adapter was excluded from the final served test comparison. A refined
adapter improved format adherence but still produced generic, incomplete analysis.

Four untouched test prompts (one per stage) were then compared with identical
messages, temperature 0, seed 42, rotated order, separate warmups and a 60-second /
6,000-output-token limit. Input was 7,172 tokens in total for every model.
No test result was added to training data or used for another training pass.

| Served model | Normal completion | Exact factor JSON (2 applicable prompts) | Total output tokens | Total seconds |
| --- | ---: | ---: | ---: | ---: |
| Base | 4/4 | 0/2 | 2,850 | 22.47 |
| Bundle adapter | 4/4 | 2/2 | 1,967 | 20.24 |
| Refined adapter | 4/4 | 2/2 | 1,220 | 12.78 |

This evaluator deliberately does not impose a JSON grammar. Production requests
do impose one, so the format advantage is not itself a production quality gain.
The refined adapter emitted 57% fewer tokens than the base. Lower elapsed time
therefore does not establish higher token throughput or equivalent report depth.

Manual review found hard failures despite zero automatic numeric-membership flags:
the refined adapter changed a dimensionless support index into a monetary amount
and changed its definition; the bundle adapter reversed the label of a leverage
ratio in one section. Both omitted important qualifications in some outputs.
The base also made unsupported reassurance claims. All three fail the expert
quality acceptance test on this small diagnostic sample.

## Report-harness comparison and current selection

Before later source-structure corrections, the same cached PDF and concurrency 3
produced a base run in 113.40 seconds with only 27 factors (one JSON response
hit the token cap), and a refined-adapter run in 69.23 seconds with 30 factors.
The latter mixed financial-statement scopes, misstated monetary units and copied
evaluation instructions into report prose. It is **not** selected on speed alone.

Keep the base as the default and retain the adapters for explicit A/B evaluation.
Later source-cell and retrieval changes require separate end-to-end validation;
they do not retroactively make these earlier reports correct.

## Remaining report acceptance work

Compare base and candidate adapters in the actual vLLM server, then run the same
report harness with a 120-second cap. Evaluate complete report content against
source material, not only JSON validity or response speed. Keep the base available
as a selectable model and promote an adapter only if the measured quality warrants
it. The untouched test comparison above is complete; its semantic failures remain
recorded rather than being hidden by aggregate speed or JSON metrics.
