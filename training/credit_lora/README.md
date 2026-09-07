# Detachable credit-review SFT

The immutable pre-LoRA baseline is Git tag `v1` (54ffbad). Development continues
on `codex/credit-review-harness`. Do not merge adapters into base weights.

## Data and loss

`prepare_data.py` reads the original ZIP by its pinned SHA-256. It restores
financial/source-and-use evidence for section tables, adds an explicit reference
year, removes unsupported reassurance, distinguishes support capacity from legal
commitment, and treats extension/refinancing exposure sums as assumptions.
Python calculates cash after CAPEX and cash-only maturity gaps. Repairs propagate
into bundle, section and synthesis records. Style examples require a unique
original source match; ambiguous/no-source examples are excluded.

Raw input: 4,560 SFT records across factor, bundle, section, full and style files.
Corrected v1: 4,526 records; 34 ambiguous/missing-source style examples excluded.
This is a curated synthetic dataset, not expert-validated banking gold data.
Numeric membership/rounding checks filter obvious unsupported values but do not
prove semantic equivalence. Real bank policies are never inferred from synthetic
thresholds. ALL30 evaluation records and archived DPO pairs are not trained.

Original archetype train/validation/test separation is retained. `case_id`,
`archetype_id`, target class labels and archetype names are not passed as metadata
to factor/bundle prompts. Section/full inputs legitimately contain earlier
factor judgements. Runtime-compatible `findings`/`requests` contracts are used
for factor and bundle targets; section/full outputs are Markdown.

`tokenize_data.py` uses the pinned base tokenizer and the same non-thinking
generation prefix as serving. Only assistant answer tokens receive labels;
source/system tokens have label -100. Overlength records are excluded and logged,
never silently truncated. Stratified representative selection is deterministic.

## Training

`bootstrap.py` creates a separate environment and reuses read-only inference
packages through a `.pth` path. PEFT/Accelerate/bitsandbytes install only into the
training overlay. It does not upgrade the existing inference environment.

`train.py` performs factor/style → bundle → section → full-report SFT. The default
is BF16 language attention LoRA, rank16; 4-bit NF4 is an explicit OOM fallback.
Base model revision is `4d7ae4984b7db7de8f8457170b3f1a419ee76d52`.
The model selects only language self-attention q/k/v/o modules; vision/audio
modules remain frozen. Target-module names and trainable counts are recorded.

Every four optimizer steps, a complete recovery checkpoint is packaged with
optimizer/scheduler/RNG state. Stage-best adapters are stored separately; best
validation loss is a selection metric, not a credit-quality approval. Backup
archives have byte counts and hashes. Drive upload/readback verification is an
independent requirement; a local `BACKUP_READY` message does not mean Drive saved it.

The run has stage time budgets and an absolute deadline reserving final evaluation
and inference restoration. `--stage`, `--resume` and `--adapter` support explicit
recovery/continuation. `--resume` requires a complete checkpoint, not an adapter-only
directory. For inference, load a stage adapter with PEFT or vLLM LoRA, or select
the base model independently. All base/adapter comparisons use identical sources,
prompts, decoding settings and preserved holdouts.

Private data, run state, adapters and reports belong under ignored `workspace/`
and the new project Drive folders, never the public Git repository.
