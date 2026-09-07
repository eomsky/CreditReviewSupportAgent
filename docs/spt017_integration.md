# v0.17 PDF structure integration

The PDF upload adapter uses the original SemanticPromptTransfer v0.17 extractor,
the v0.15/v0.16/v0.17 structural rules, and its hierarchical chunk builder.
Source and model hashes are recorded in `vendor/spt017/provenance.json`.
The saved boundary model is loaded with scikit-learn 1.8.0. No training, Drive
mount, or writes to the original project are performed.

Each upload caches MASTER.json, chunks.json and a manifest alongside its source
records. Table cells, merged spans, inherited headers, continuation relationships,
page coordinates, units and notes remain available in structured metadata. Search
indexes structural chunks; raw pages remain accessible as parent evidence.
Document-prefixed source IDs prevent collisions between multiple PDFs.

The cache version is `spt017-structural-v1`. Starting a new analysis uses this
pipeline. Resuming an existing run preserves its original extraction and evidence.
This is structural extraction from PDF text and geometry, not OCR; image-only
documents still require a separate recognition step.

Validation on the original STX Engine annual report dated 2026-03-23:

- 277 pages, 769 physical tables, 1,068 structural chunks; about 39 seconds locally.
- Page 198 table P0198_T003: three header rows and one stub column restored.
- Page 199 P0199_T001: inherited header and confirmed continuation from that table.
- 36 automated tests pass, including saved-model inference, merged-cell boundary
  protection, document-scoped evidence and artifact persistence.

These checks establish extraction integration and the specific regression cases;
they do not establish accuracy for every document or end-to-end report quality.
