# Adaptive analysis and report streaming

The LLM selects plan, search, read, dataset, calculate, reframe and conclude actions.
An inquiry stores concise questions, competing hypotheses, evidence tests and the
reason for changing the approach. It is an auditable decision summary, not private
chain-of-thought. Existing evidence and executed calculations survive reframing.
Each factor has a 24-step budget, three reframes and two consecutive validation
repair attempts. Errors and the rejected response are returned as context. Network
and execution failures are not silently treated as successful analysis.

The UI shows the active inquiry and the actual selected tool stage. Related factor
findings are available to subsequent analysis; final synthesis compares completed
judgements. This is adaptive analysis within factors, not an unrestricted global
planner that autonomously reopens all completed factors.

After reference validation, report prose is generated through OpenAI-compatible SSE.
Only content deltas are rendered; reasoning and tool fields are excluded. Reports
are drafts: the editorial model is instructed not to add facts, but automated
semantic verification is not yet complete. Structured source and calculation
artifacts remain the audit record. Raw Python objects are no longer rendered.

Completed streamed sections are persisted and can be resumed. Interrupted prose
is retained as an internal partial artifact, while the prior committed section
remains visible. A stream cut off by length is not committed as complete.
