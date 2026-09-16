# Cloud continuation checkpoint

Status: **migration in progress, not a production release**.

This branch preserves the latest local runtime integration before structural cleanup. It is not the clean candidate yet. Existing experiment Codespace must remain unchanged.

## Verified starting point

- Baseline commit: `6be6c8d`.
- Local runtime integration: C20.47.3; structured SQL context added to the existing generation pipeline.
- Yesterday's accepted experiments use a different SQL-first path. End-to-end equivalence and the 20-minute target remain unverified.
- The old experiment dashboard and accepted artifacts remain private, outside this repository.
- Private continuation archive: `CreditReview_Cloud_Handoff_20260916.zip` in the owner's existing CreditReviewSupportAgent Google Drive folder. Read its `CLOUD_RESUME.md` and verify `CLOUD_MANIFEST.json` before restoring data.
- Never commit that archive, source documents, generated reports, SQLite databases, connection credentials, or private QA notes to this public repository.

## Next work, in order

1. Read the private QA continuity, resume, and alignment audit documents from the archive.
2. Generalize the accepted SQL-first path and compare its input, prompt, source coverage, cache reuse and calls against the current runtime. Do not silently omit mandatory documents.
3. Build the clean candidate in this branch with explicit screen/API/pipeline/prompt/model/storage mappings. Preserve fixed tables and prose quality.
4. Provide a source-to-destination migration map, rationale, meaningful tests, unresolved items, and a code-review reading order.
5. Create the second Codespace for this branch, isolate its data/cache from the experiment environment, and test portable startup.
6. Validate affected stages and the full connected pipeline before promotion. Do not rerun accepted steps just to recreate the monitor display.

## Proposed layout

```text
apps/server/                   HTTP routes and application bootstrap
apps/web/                      screens, components, monitoring
config/models/                 LLM and embedding configuration
config/pipelines/              executable step order and dependencies
config/profiles/               local, Codespaces and server profiles
prompts/                       common, preparation, generation, review
templates/                     fixed and adaptive report templates
src/credit_review/
  orchestration/ ingestion/ evidence/ generation/ review/
  llm/ embeddings/ storage/ observability/
tests/                         unit, integration, regression, migration, E2E
tools/                         backup, migration and diagnostics
deploy/                        container and launch definitions
docs/                          architecture, operations and review guide
```

Runtime documents, DBs, indexes, caches, run traces, and outputs belong in a separately configured private data directory. Record effective model, prompt and retrieval configuration per run. A release label must state its actual validation scope.

## Current startup limitations

The existing script still depends on a sample PDF in the user's Downloads folder and a generated prompt pack under outputs. Remove these sample dependencies before declaring the new candidate portable. Embedding runtime also requires fastembed, qdrant-client and tokenizers beyond the older pyproject defaults. Credentials and a working model endpoint must be configured on the new host.

No local server, browser session, Colab runtime, or active task is automatically moved by this Git checkpoint.
