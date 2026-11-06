# Case: Abstract Branch Control

**Learner task:** Explain the represented series and parallel paths, their visible reads and writes, and the relationship between the two rungs without assigning vendor-specific instruction semantics.

**Source and exact scope:** `branch-control.txt`, both complete rungs in this abstract text representation. This is not valid source claimed for any vendor IDE.

**Directly visible facts:** Rung 1 shows `Enable` in series with a parallel choice between `AutoMode` and `ManualMode`, leading to `FeedValve`. Rung 2 shows `Enable` in series with a parallel choice between `FeedValve` and `Alarm`, leading to `Indicator`. The text drawing represents branches and joins explicitly.

**Deliberately unknown:** Whether the representation uses normally-open/closed contacts, instruction semantics, whether coils are retentive, rung evaluation/update model, task order, I/O mapping, and whether Rung 2 sees a same-cycle or prior value of `FeedValve`.

**Expected observations and paper trace:** Under only the abstract Boolean path assumption, Rung 1's depicted path is `Enable AND (AutoMode OR ManualMode)` and Rung 2's is `Enable AND (FeedValve OR Alarm)`. With initial abstract values `Enable=TRUE`, `AutoMode=FALSE`, `ManualMode=TRUE`, `FeedValve=FALSE`, `Alarm=FALSE`, the first path is true and the second path is false using the stated initial `FeedValve` value. If both represented rungs are evaluated sequentially with immediate abstract writes, the second rung could instead observe the first rung's write; that ordering/update behavior is intentionally not established. Label the trace as conditional paper reasoning only.

**Critical review rubric:** No source-level defect is confirmed by this abstract drawing. Flag same-cycle dependency/update visibility and contact/coil meanings as unresolved platform/representation questions. Do not certify the diagram as valid Ladder source or infer physical behavior.

**Likely hallucination traps:** Calling contacts normally open; claiming a latch or retentive coil; assuming rung order or immediate writes; claiming vendor/IDE compatibility, device mapping, or safety properties.

**Acceptance checklist:**
- Preserve the visible branch layout in any teaching copy and annotate feasible lines with `AI:` without obscuring joins.
- Explain both series/parallel paths and visible conditions/output labels at the abstract level.
- Trace uses explicit values, identifies the conditional update assumption, and retains unknown same-cycle behavior.
- Critical review reports no confirmed defect while naming representation/platform limits; never claim compile, runtime, or safety validation.
