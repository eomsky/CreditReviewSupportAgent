# Bounded live benchmark, 2026-09-08

Code: `a100d72`. Live model: `google/gemma-4-26B-A4B-it`.

- Source: saved STX PDF extraction from `run_0947b80597d946e58a3023ce6edc3211`.
- Result: `run_ec3c022048cd48b8ad0f999464f8c1e5` under `workspace/benchmarks/cases/full/runs`.
- Watchdog elapsed: **60.032475041 seconds**, killed worker, exit -9, process stopped confirmed.
- Completed calls recorded: **7**. Completed judgements: **0/30**. Report incomplete.
- Saved valid replies contained **24 plan actions and 6 read actions**.
- This test reused extraction and excluded upload/OCR/browser rendering. It does
  not establish the requested one-minute end-to-end target or a speed improvement.

Input overhead has been reduced, and structured tables now support deferred
reads, but the first round still spends the deadline on planning/reading without
producing judgements. Next optimization should combine inquiry definition with a
useful tool action in one response and reduce planning-only turns. It must retain
source checks, Python calculations, and qualified conclusions. Do not extend this
failed benchmark or treat its early termination as faster report completion.

Validation: 61 local tests passed in 3.36 seconds, including table discovery/read
separation, shared reads, and preventing cached searches from counting as reads.
Codespaces fast-forward to a100d72 verified before the live benchmark.

Context capacity: notebook setting saved as 49,152; the live endpoint last reported
28,672. Colab UI remained at Connecting; no successful server restart or expanded
live capacity has been verified.
