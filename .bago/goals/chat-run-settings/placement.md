# Frozen placement and contract

Chat: message input, send, exact-file single-use authorization. No scan or cognition checkbox. Cognitive response evidence stays attached to its message.
Settings: existing dialog gets Provider & models and Cognition & context sections. Cognition mode is baseline/bago5, defaults baseline, persisted per browser; permission is not persisted. Both assistant and agent requests explicitly send cognitive_mode.
Agent Runs: navigation runner hosts the existing local deterministic directory-scan task, source scope, one-use scan authorization, report and trace. Control becomes a compatibility destination to runner and has no extra sidebar item. Generic profile execution is still unavailable. Do not fake an agent/model run.
Context metadata: GET /api/chat/context returns workspace_root, cognition {profile, capacity, max_hops, max_expansions}, paths [{id,label,path,state:present|absent,purpose}], memory {kind,state,description}. Report actual configured backend locations, including ConversationStore.path; no content reads, no mutable path selectors or invented external memory support. UI error/loading states explicit.
Read-only location labels distinguish configuration metadata from permission to send file content. Fixed paths remain read-only because arbitrary relocation is not implemented.
Legacy backend chat scan endpoints/tool remain compatible, but no scanner controls in composer.
