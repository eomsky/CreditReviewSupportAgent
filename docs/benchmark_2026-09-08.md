# Bounded live benchmark, 2026-09-08

## Follow-up: focused evidence and prepared continuation

Code `ea00b53`, deployed to Codespaces. Same saved PDF extraction and 60-second
watchdog. Run `run_b1b6e803b1b84d75b075a09730332d91`.

- First saved factor opinion: **26.287237792002998 seconds** (worker measurement;
  excludes upload/extraction and browser rendering).
- At **60.0323310140011 seconds**, watchdog terminated worker, exit -9 confirmed.
- **5/30** opinions saved: F01, F02, F04, F06, F09. Previous run: 0/30 at 60 seconds.
- Five completed LLM calls recorded. Saved replies: 14 read, 5 conclude, 2 search.
  These action counts cover different factor progress from the previous run and
  must not be presented as a like-for-like search cost reduction.
- Full report still incomplete. Opinion storage and reference checks do not
  establish semantic correctness or sufficient analytical depth. Observed business
  and market-position opinions remain largely descriptive.
- Local suite: **67 tests passed in 3.67s**. UI reload adjustment: its 3 existing
  tests passed in 1.63s. No extended inference run performed.

Fixes preserve the factor-specific evidence window when searching prior work,
retain complete explicitly read passages, use document vocabulary for initial
retrieval, locally preload the top matched table for numeric questions, and allow
one early grouped continuation after retrieval. Original source artifacts and
checks remain intact. The live test demonstrates earlier partial output, not the
one-minute full-report target.

## Follow-up: fused inquiry and action

Code `9b17e7f`, deployed to Codespaces before the run. Same source extraction and
60-second watchdog as below. Run `run_426fb85cf679459fa2be85863e168cab`.

- Watchdog elapsed **60.0341712920017 seconds**, worker terminated, exit -9.
- **8** completed calls recorded; **0/30** judgements; report incomplete.
- Saved replies: **22 search, 8 read, 0 plan** actions. Saved factor errors: none.
- Planning-only responses were eliminated, but no report latency improvement was
  demonstrated. No longer benchmark was run. Retrieval/read rounds still consume
  the deadline before conclusions; fewer planning steps alone do not meet the target.
- Local validation: **63 tests passed in 3.43 seconds**, including same-response
  inquiry/read, changed-inquiry/search, schema requirements and planning-only rejection.

The batch schema now requires inquiry alongside a useful action for fresh factors.
An optional changed inquiry on a subsequent action records a reframe before the
action executes, subject to the existing reframe limit. Table-read requirements,
Python calculation execution and provenance checks remain in force. Legacy
single-factor actions remain compatible; planning-only actions are blocked in batches.

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
## Bounded request queue and CPU overlap (2026-09-08)

Code `2c82eef`, fast-forward verified in Codespaces. Same prepared STX input and
60-second watchdog. Run `run_f4379def543b4ed38dd264850bf5e755`.

- Analysis stopped at **47.3015 seconds** after a repeated identical action with
  no new evidence. Parent process finished at **54.0337 seconds**, exit 0;
  report completion is **false**, irrespective of the process exit status.
- **7/30** judgements: F01, F02, F04, F06, F07, F08, F09. First content **27.1237s**.
- Previous baseline: 5/30 at the 60-second limit, first content 26.2872s.
  Coverage improved in this single run; first content did not improve, and full
  report latency and financial reasoning quality remain unproven.
- Seven completed calls, one still in flight at the saved stop snapshot. The
  coordinator stops accepting replies after cancellation; the parent confirms
  process exit. HTTP occupancy **92.89%**, mean concurrent requests **1.842**,
  no-request interval total **3.365s**. These are not GPU utilization counters.
- Successful response prompt tokens: **5031, 6536, 9685, 10638, 11411, 10513, 9522**.
  Completion tokens: **1036, 1280, 947, 774, 1719, 493, 524**. Thus input volume is
  substantial, but volume alone does not establish evidence sufficiency.
- Returned actions: 21 read, 7 conclude, 1 dataset, 1 search. The dataset failed
  row cell-provenance validation; no calculate action executed in this run.
- Local apply work overlapped HTTP activity for **0.0743s**. A dedicated test
  verifies local processing can run while another LLM request remains active;
  this live run does not demonstrate GPU/Python calculation throughput gains.
- RAM tool-cache hits: 356. Existing exact-input run caches and bounded document
  index caches retained. No Colab RAM or VRAM allocation was changed.
- **73 tests passed in 3.93s** before deployment. No extended or repeat live run.

Keep the bounded queue for the observed coverage gain. Next bottleneck is
redundant evidence reads and invalid dataset construction, not a demonstrated
shortage of RAM or a long idle interval between HTTP requests.
## Paired rows, reread constraints and live report view

Code `09db8ad`, verified in Codespaces. User extended this test's watchdog to
**90 seconds**; the finished-report target remains one minute. Same saved STX
extraction. Run `run_384930aab37c4bedb285206587edc992`.

- At **60.392s** analysis time: **8/30** judgements. This milestone excludes
  preflight/upload/OCR; it is not exactly the prior wall-clock watchdog boundary.
- At **69.122s**: **9/30** judgements, 8 marked fulfilled and F03 qualified.
  Stopped after two follow-ups produced no new progress. Parent process exited
  normally at **77.602s**, before the 90s cap. Full report incomplete.
- First opinion **30.402s**, versus 27.124s in the previous queue run. No first
  content latency improvement. More opinions with a longer budget does not
  demonstrate a major report-completion speedup.
- Ten completed calls. Returned actions: 22 read, 9 conclude, 4 dataset, 2 search,
  1 reuse. Missing numeric units blocked F10/F11/F12. Previous row/provenance
  length errors were not seen. No calculate action was returned.
- HTTP occupancy **93.83%**; local apply/HTTP overlap **0.151s**. Neither is a
  hardware utilization measurement.
- Live viewer at `?benchmark=latest` showed the current run's paragraphs growing
  and then changed to ended status. It only reads saved state/artifacts; it never
  calls the LLM, rebuilds indexes, or writes analysis state. Verified by UI test
  and actual browser observation. **77 tests passed in 4.06s** before deployment.

Follow-up schema correction requires a nonempty explicit unit for numeric
columns, matching existing validation; column names alone do not supply units.
Unknown units must still be read from evidence, never invented. This correction
is locally tested but has not had another live timing run. No extended rerun was
performed after the stagnation stop.
