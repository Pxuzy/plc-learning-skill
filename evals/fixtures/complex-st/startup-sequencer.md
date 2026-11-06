# Case: Stateful Startup Sequencer

**Learner task:** Explain the state progression, output timing, timeout/fault behavior, hold/resume behavior, and review findings for the visible block.

**Source and exact scope:** `startup-sequencer.st`, the complete shown `FB_StartupSequencer` definition only. No caller, task, variable initialization, target runtime, or I/O mapping is supplied.

**Directly visible facts:** `RunCommand` is assigned `FALSE` at the start of each invocation. State values are represented as `0` idle, `10` starting, `20` running, `30` held, and `90` fault by their case branches. Reset clears state/fault/attempt count only when the incoming state is 90. Interlocks are checked in starting, running, and held. `ElapsedMs` and `TimeoutMs` are inputs; no timer is called.

**Deliberately unknown:** Initial values and persistence/retention; caller and invocation order; scan period; whether `ElapsedMs` is monotonic, reset externally, or expressed in the same units as `TimeoutMs`; any requirements for restart, output de-energization, fault latching, or reset; physical meaning and safety role of outputs.

**Expected observations and paper trace:** The `CASE` selects one branch once, using the value of `State` after the preceding reset logic. A write to `State` inside that selected branch does not switch to another branch during the same `CASE` invocation. Thus, from state 0, a start with interlocks true changes state to 10 but remains in case 0; `RunCommand` stays false from the invocation default. On the next call in state 10 with interlocks true, feedback false, `ElapsedMs=0`, and `TimeoutMs=3000`, the final `ELSE` writes `RunCommand=TRUE`. A following call in state 10 with `Feedback=TRUE` changes state to 20 without writing `RunCommand`, so it remains false from the invocation default; state 20 can assert it on a later invocation if interlocks remain true and hold is false. This is a source-visible output gap across the transition. In state 20 with `Hold=TRUE`, state becomes 30 and command remains false. In state 30 with `Hold=FALSE`, state becomes 20 but command remains false until a later invocation in state 20 with interlocks true and hold false. State 10 with `ElapsedMs >= TimeoutMs` faults and leaves command false. These are paper traces, not execution results.

**Critical review rubric:** Identify the source-visible output gaps on transitions into and out of states 20/30 and on the first transition out of idle. No requirements are supplied, so describe these as observed behavior and do not label them a requirements violation. Check that reset is only effective while state is 90 and that state 0 clears `Fault` on its next case invocation. `StartAttempts` has no visible consumer. Timeout correctness is conditional on caller-provided elapsed-time behavior and units. Do not claim timer semantics, output safety, or restart requirements without missing evidence.

**Likely hallucination traps:** Claiming a TON is used; claiming the elapsed value is measured/reset here; assuming initial state is zero; claiming a reset works from any state; asserting output stays on through state transitions; assigning equipment meaning to `RunCommand`.

**Acceptance checklist:**
- Preserve every source character in any reproduced teaching copy; annotate each feasible non-empty source line with `AI:` and retain syntax/text separately from added comments.
- Explain the whole block and how the `CASE` selection relates to preceding and within-branch writes.
- Paper trace includes concrete initial values, branch decisions, output writes and retained/defaulted values; it is not presented as runtime evidence.
- Name absent initialization, caller/task, elapsed-time, requirement, and platform evidence as unknowns.
- Critical review identifies visible output-transition behavior and distinguishes conditional timeout concerns; do not repair source.
