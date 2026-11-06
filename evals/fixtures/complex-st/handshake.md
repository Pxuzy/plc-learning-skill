# Case: Request Handshake With Missing Caller

**Learner task:** Explain each block's visible reads/writes, identify the handshake behavior that is and is not established, and review the source without inventing cross-block execution order.

**Source and exact scope:** `handshake.st`, the complete definitions of `FB_RequestProducer` and `FB_RequestConsumer`. No instance declarations, caller, task configuration, or scheduling evidence is included.

**Directly visible facts:** Producer clears `Request` when `Ack` is true; otherwise `NewRequest` sets it true; with both false it does not assign `Request`. Consumer assigns `Ack := FALSE` each invocation. When `Request AND Permit` is true it sets `Busy := TRUE`. Its second condition is `Request AND NOT Request`.

**Deliberately unknown:** Whether either output is retained between calls, initial values, how instances are connected, whether producer or consumer executes first, whether `Ack` is fed back, task timing, and the intended handshake protocol.

**Expected observations and paper trace:** For producer initial `Request=FALSE`, `Ack=FALSE`, `NewRequest=TRUE`, it takes the `ELSIF`, writes `Request=TRUE`, and retains no other output. For consumer initial `Busy=FALSE`, `Ack=TRUE`, `Request=TRUE`, `Permit=TRUE`, it first writes `Ack=FALSE`, sets `Busy=TRUE`, then evaluates a false condition because `Request` cannot simultaneously be true and not true; it does not write `Busy` or `Ack` in that second `IF`. Cross-block traces must not assume producer/consumer order or same-cycle visibility.

**Critical review rubric:** Identify `Request AND NOT Request` as an unconditional logical contradiction in ordinary Boolean logic, so that its body is unreachable from the shown source regardless of platform call order. As a result this block has no visible path that clears `Busy` or asserts `Ack`; note that `Busy` is also not reset elsewhere in the block. Do not infer whether the defect violates requirements absent a protocol specification. Producer's retained value when neither condition matches depends on output storage semantics not provided.

**Likely hallucination traps:** Saying the consumer acknowledges a completed request; assuming block invocation order from file order; asserting outputs are retained or initialized by a platform; treating the impossible condition as a valid falling edge detector; claiming a real system deadlocks without task/protocol evidence.

**Acceptance checklist:**
- Preserve source exactly in any teaching copy; prefix each feasible non-empty source line's added explanation with `AI:`.
- Explain the two blocks separately and state that caller connections and cross-block order are absent.
- Provide per-block paper traces with explicit starting values and distinguish untouched outputs from written values.
- Detect the impossible conjunction as a confirmed source defect; avoid silently correcting it or claiming requirement impact as fact.
- Mark initialization, retention, task order, and handshake intent unknown; no runtime or compile claim.
