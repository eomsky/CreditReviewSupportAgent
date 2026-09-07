# Verified project structure — 2026-09-08

Inspected before training implementation. Selection: add a separate training namespace; preserve the existing application and Drive organization.

## Git / Codespaces

- Git remote: `https://github.com/eomsky/CreditReviewSupportAgent.git` (public; never commit private reports, connection keys, training examples or model weights).
- Working branch: `codex/credit-review-harness`.
- Codespaces root: `/workspaces/CreditReviewSupportAgent`.
- Local checkout: `C:/Users/Lenovo/Documents/ChatGPT/여신 심사지원 에이전트/CreditReviewSupportAgent`.
- Application: `app/workbench.py` (Streamlit, port 8501).
- Engine: `src/credit_review/`, prompts under `src/credit_review/prompts/`.
- Reused PDF extraction: `src/credit_review/vendor/spt017/` with original model/provenance.
- Runtime data / connection: `workspace/` (ignored by Git).
- Server builder: `scripts/build_colab_server.py`.
- Server notebook: `notebooks/CreditReviewSupportAgent_Gemma4_A100_Server.ipynb`.
- Tests: `tests/`; calculator isolation: `docker/`.
- No prior training code, adapter folder or checkpoint manager was present at the start of this task.

## Existing Colab / Drive

- Project folder: https://drive.google.com/drive/folders/18nkqLMhn5K24Ks8zDuhftML98lOC0TsS
- Folder listing before writes contained only the existing test server notebook.
- Notebook: https://colab.research.google.com/drive/1vpkVhpXVoHtLMws9khrKlbdSQMRr6tVK
- Colab runtime root: `/content/credit_llm_server`.
- Inference environment: `/content/credit_llm_server/venv`.
- Verified GPU: NVIDIA A100-SXM4-80GB, 81,920 MiB.
- Runtime system RAM approximately 167 GB.
- Base model: `google/gemma-4-26B-A4B-it`; revision must be recorded from the actual cached snapshot before training.
- Inference process and training must not compete for this GPU at full allocation.

## New paths and role mapping

| Role | Git / local code | Colab temporary work | Drive persistence |
|---|---|---|---|
| Training code and contracts | `training/credit_lora/` | checked-out repository | run code/config snapshot |
| Original + corrected data | ignored `workspace/training-data/` | `/content/credit_training/data/` | project `training-data/credit_lora_v2_2/` |
| Training run / resume state | ignored `workspace/training-runs/` | `/content/credit_training/runs/<run-id>/` | project `training-runs/<run-id>/` |
| Detachable adapters | config + loader code only | run adapter directories | project `model-assets/adapters/<run-id>/` |
| Evaluation | code and aggregate metrics only | per-run private outputs | project training run evaluations |

Drive subfolders above are planned additions, not claimed as existing until creation/readback is logged in a run manifest. Checkpoints, best adapters and production candidates are separate. Base weights are retained separately and are not merged or uploaded repeatedly.

## Preserved assets

Do not move, rename, overwrite or integrate the prior SemanticPromptTransfer / CreditReviewWorkbench frozen production versions or old HTML. The old launcher v0.3.0 is not a version of all accumulated assets. This task changes only the test project and its newly created training assets.

## Training boundaries

Use the supplied v2.2 synthetic bundle for SFT only, after evidence/numeric/split checks and correction. Exclude DPO and ALL30 evaluation-only records from training. Preserve archetype-separated train/validation/test groups. Record model/tokenizer revisions, data hashes, Git revision, dependencies, run limits and backup verification in each run.
