# Evidence and Causality

## Evidence labels

- **Source fact:** directly visible in the supplied code or verified project artifact. Point to the line, object, declaration, or file when available.
- **Paper trace:** a conditional walkthrough using explicit starting values and assumptions. It is not a runtime result.
- **Inference:** a plausible interpretation not established by source. Name the evidence that would confirm it.
- **Unknown:** required evidence is absent or unreadable. State what is missing; do not fill the gap with convention or a variable name.

Treat a pasted excerpt as evidence only for its visible text. Do not call it a complete project. Comments can explain intent but do not prove runtime behavior. General PLC knowledge may explain syntax, but platform behavior requires matching platform and version evidence.

## Explain execution

For each relevant block, connect condition or input to reads, branch choice, writes, and resulting state. Distinguish a value written here from a value left unchanged. Explain whether branches are mutually exclusive or independent as shown by the syntax. A later write can replace an earlier write only when the visible execution path establishes that order; cross-object order requires call or task evidence.

When the user requests detailed beginner teaching, or state conditions make tracing useful, include a labeled paper trace with concrete initial values and explicit assumptions, each relevant branch decision, resulting writes, and retained values. Never present a paper trace as a runtime outcome, compilation, simulation, trace capture, or hardware validation. Keep short factual answers proportional. If no grounded trace is possible, state which missing values or semantics block it.

For pasted Ladder, preserve the visible rung/branch layout and contact, coil, and instruction relationships. Explain paths in represented order; distinguish series and parallel paths and branch joins only when the representation makes them clear. List visible reads/conditions and writes/effects. Cropped, flattened, or ambiguous layout and vendor-specific instruction semantics remain unknown; do not reconstruct an unseen IDE/network or assign platform-specific meanings without matching evidence. Name the missing view, connection, instruction definition, or platform/version evidence needed to resolve an unknown.

## Scope and review

Name the source and range covered when known, and list material missing from the request. Review only claims supported by the visible code or cited evidence. Separate confirmed defects from risks conditional on requirements/platform behavior and questions requiring more evidence. Consider branch overlap, overwrite order, hold/clear behavior, bounds, fault paths, timing assumptions, diagnostics, and safety context when relevant. Do not certify safety.
