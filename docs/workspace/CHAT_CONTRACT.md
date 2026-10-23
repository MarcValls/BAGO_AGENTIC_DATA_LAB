# Workspace chat proposal v1 — frozen before chat implementation

Scope extension CR-WS-001 authorized by root/user chat-first requirement. Resolver may propose `decision:workspace_action`, reply, `intent:manage|create|open|files|git`, optional name (ASCII folder token <=80) and path (relative safe portable <=240). No workspace ID/root, command, confirmation, content mutation, delete/commit or permission fields from the model. Additional proposal fields are rejected.

Backend returns operation workspace_action and workspace_proposal `{intent,name?,path?}` and persists it in assistant message references. It does not execute the SDK or create a workspace. AgentChat renders the SAME WorkspaceManager inline, prefilling only name/path/tab. The user selects a managed project, reads current hashes and explicitly reviews/executes the action. Missing data remains incomplete. A proposal is not authorization. Existing read/scan tools keep their own authorization boundary.

No live provider, browser or production workspace test by this agent; root performs host Chat→card→create→context proof. Fixture model decisions and actual HTTP SDK calls cover local integration.
