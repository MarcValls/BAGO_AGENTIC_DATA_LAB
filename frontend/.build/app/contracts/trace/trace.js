/** Decision Inspector trace contract mapped from LocalTrace; it is never an authority. */
export function validateTraceTimeline(value) {
    const errors = [];
    if (!value.traceId.trim() || !value.runId.trim())
        errors.push("trace and run ids are required");
    const ids = new Set();
    for (const event of value.events) {
        if (!event.eventId.trim())
            errors.push("event id is required");
        if (ids.has(event.eventId))
            errors.push(`duplicate event id: ${event.eventId}`);
        ids.add(event.eventId);
    }
    for (let i = 1; i < value.events.length; i += 1) {
        if (value.events[i - 1].sequence > value.events[i].sequence)
            errors.push("events must be ordered by sequence");
    }
    return errors;
}
