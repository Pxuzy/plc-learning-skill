---
name: plc-program-learning
description: Use when a user asks to understand, learn from, or review PLC program code, project exports, or control logic.
---

# PLC Program Learning

Explain PLC code to learners using the source and evidence actually available. A pasted ST or Ladder excerpt is enough for a useful explanation; vendor adapters, scripts, shell access, and network access are optional and must never block the core explanation.

## Route by request

- A brief factual question gets a brief, source-grounded answer. Do not force a full tutorial, annotated listing, or review section when no code explanation was requested.
- A code explanation covers the requested readable scope. For detailed teaching, follow [the explanation workflow](references/workflows/explain-code.md) and [the evidence rules](references/common/evidence-and-causality.md).
- Whole-project structure, vendor-specific project formats, I/O mapping, events, or diagnostics trigger additional evidence gathering. Load the relevant vendor note only when applicable. Vendor folders indicate planned research areas, not supported or verified formats.
- Skill maintenance and evaluation are not part of ordinary PLC explanation. Use [maintainer checks](evals/README.md) only for this repository.

## Core requirements

- Preserve visible source characters in any reproduced listing. Do not silently fix, normalize, or replace source with a paraphrase. Keep original comments; put added teaching comments only in a separate copy and prefix each feasible non-empty source line with `AI:`. State every omitted-line exception and why it could not be safely annotated. Never write the teaching copy back to a PLC project.
- Explain block responsibility and execution causality: conditions and branch relationships, reads, writes, order visible in the code, resulting state, and what is not written. A line-by-line gloss does not replace block-level explanation.
- Separate source facts, explicit paper-trace assumptions, inferences, and unknowns. Bound each unknown by naming the missing evidence. Never invent types, callers, execution order beyond visible code, scan timing, device actions, reset paths, author intent, or validation results.
- For large nested `IF`, `CASE`, or loop structures, first identify the complete outer block and its entry condition; explain inner branches in chunks with enough context; then summarize the full flow and state effects. Preserve complete source coverage and do not imply an unselected branch ran.
- After a requested code explanation, include a distinct **Critical review** section. Separate confirmed source issues, conditional risks, and questions blocked by missing evidence. If no issue is established, say so without calling the program perfect; state review limits and unperformed validation.
- Prioritize P0 truthfulness, requested-scope coverage, causal explanation, annotation, readability, critical review, and honest verification. Apply P1 only when triggered (for example, project-wide mapping or vendor-specific behavior). Use P2 teaching methods selectively. P3 repository governance belongs only to maintenance work.

## Progressive disclosure

Load [common evidence rules](references/common/evidence-and-causality.md) and [the detailed explanation workflow](references/workflows/explain-code.md) when explaining code in depth. Load vendor material only for the identified platform and only at its stated evidence level. See [vendor coverage](references/vendors/README.md), [standards notes](references/standards/README.md), and [external references](references/external/README.md) for limits. These notes do not establish parser or product support.
