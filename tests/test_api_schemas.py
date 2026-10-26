from __future__ import annotations

from pydantic import BaseModel

from src.api import schemas, server


MODEL_NAMES = (
    "DemoRequest",
    "ContextPathCheckRequest",
    "DemoRunResponse",
    "AgentConfig",
    "OllamaConfigRequest",
    "OllamaVerifyRequest",
    "GithubCopilotModelsRequest",
    "CodexLoginRequest",
    "ProviderRegistrationRequest",
    "AgentCreateRequest",
    "ControlChatRequest",
    "ProviderSelectionRequest",
    "ModelPolicyRequest",
    "KnowledgeIngestAnswerRequest",
    "OpenMetadataLiveValidationRequest",
    "OntologyProposalRequest",
    "OntologyApprovalRequest",
    "OntologyQueryRequest",
    "AgentChatRequest",
    "WebReadAuthorizationRequest",
    "WorkspaceReadAuthorizationRequest",
    "WorkspaceScanAuthorizationRequest",
    "WorkspaceScanRunRequest",
    "ConversationCreateRequest",
    "ConversationRevisionRequest",
    "ConversationPermanentDeleteRequest",
    "CapabilityProposalCreateRequest",
    "CapabilityProposalCancelRequest",
    "EvaluationSuiteCreateRequest",
    "EvaluationSuiteUpdateRequest",
    "EvaluationRunRequest",
    "ConversationRenameRequest",
    "AgentResponse",
    "JobResponse",
)


def test_server_reexports_the_schema_module_models_without_wrapping_them() -> None:
    assert server.AGENT_TOOL_ALLOWLIST is schemas.AGENT_TOOL_ALLOWLIST
    for name in MODEL_NAMES:
        model = getattr(schemas, name)
        assert getattr(server, name) is model
        assert issubclass(model, BaseModel)
