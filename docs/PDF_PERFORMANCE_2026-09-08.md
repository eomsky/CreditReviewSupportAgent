# Preserving PDF recognition while reducing CPU time

The development branch retains the v0.17 extraction rules and classifier. A
builder-local cache reuses exact scalar/region/candidate features and batches
unchanged ExtraTrees predictions. It does not replace OCR, omit pages, or reduce
table detail. Set `CREDIT_SPT_CACHE=0` to use the original builder.

Measured on the same 277-page PDF (769 tables, 1,068 chunks):

| Environment | Original structure | Cached structure | Comparison |
| --- | ---: | ---: | --- |
| Local Windows | 20.885 s | 5.237 s | MASTER and chunks deeply equal |
| Codespaces, 2 CPUs | 67.376 s | 15.308 s | MASTER and chunks deeply equal |

The Codespaces cached run additionally took 28.685 s for fresh raw extraction and
0.405 s for chunks: 44.397 s across those three measured stages. The original
structure control reused the same raw document, taking 0.951 s to read it, so
that control is not a second fresh-extraction measurement. Each measurement is
one run, not a latency percentile. Serialization, upload, OCR fallback, indexing,
LLM generation and UI delivery are outside this timing sum. This does not yet
establish a complete report within 120 seconds.

Reproduce with `scripts/profile_pdf.py PDF OUTPUT --cached-builder`, then run
the original builder with `--master OUTPUT/MASTER.json` into a different output
directory. Compare parsed JSON for both `MASTER.json` and `chunks.json`.

The frozen v1 tag remains unchanged. This optimization is on the subsequent
development branch. The private benchmark artifacts retain source hashes and
full outputs; source documents are not committed to the public repository.
