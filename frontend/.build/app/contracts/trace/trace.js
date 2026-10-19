/**
 * Read-only projection of supplied trace events. Correlation fields are copied
 * from explicit source identifiers; this contract grants no execution authority.
 */
/** Contract-level validation; data gaps remain inspectable and are not repaired. */
export function validateTraceTimeline(value) {
    const errors = [];
    if (!value.traceId?.trim() || !value.runId?.trim())
        errors.push("trace and run ids are required");
    const ids = new Set();
    let previousSequence = -1;
    for (const event of value.events) {
        if (!event.eventId?.trim())
            errors.push("event id is required");
        if (ids.has(event.eventId))
            errors.push(`duplicate event id: ${event.eventId}`);
        ids.add(event.eventId);
        if (!Number.isInteger(event.sequence) || event.sequence < 0)
            errors.push(`invalid sequence for event ${event.eventId}`);
        if (event.sequence < previousSequence)
            errors.push("events must be ordered by sequence");
        previousSequence = event.sequence;
        if (!event.status?.trim())
            errors.push(`status is required for event ${event.eventId}`);
        if (event.parentState === "missing" && !value.gaps.some(gap => gap.kind === "missing_parent" && gap.eventId === event.eventId)) {
            errors.push(`missing parent is not represented as a gap for event ${event.eventId}`);
        }
    }
    return errors;
}
