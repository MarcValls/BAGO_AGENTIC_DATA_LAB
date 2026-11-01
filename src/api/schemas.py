"""Pydantic request and response models used by the ADL HTTP API."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.agent_tasks import TaskDefinition
from src.capabilities.manager import agent_tool_catalog
from src.conversations.library import normalize_conversation_labels
from src.providers import model_policy, registration

AGENT_TOOL_ALLOWLIST = frozenset(item["id"] for item in agent_tool_catalog())


class DemoRequest(BaseModel):
    write_evidence: bool = False
    json_output: bool = False

class ContextPathCheckRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)

class DemoRunResponse(BaseModel):
    status: str
    exit_code: int
    stdout: str
    stderr: str

class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    task_scope: str | None = Field(default=None, max_length=8000)
    type: Literal["rag", "tool", "multi-agent"]
    system_prompt: str = Field(min_length=1, max_length=12000)
    # Older user-created agents predate provider/model pinning. Keep them
    # readable without migrating their persisted records as a side effect.
    provider_id: Literal["ollama-cloud", "codex", "openai-platform", "github-copilot"] | None = None
    model_id: str | None = Field(default=None, min_length=1, max_length=128)
    tools: list[str] = Field(default_factory=list, max_length=20)
    retrieval_config: dict[str, Any] | None = None
    sandbox_profile: str | None = Field(default=None, max_length=100)
    task: TaskDefinition | None = None

    @field_validator("tools")
    @classmethod
    def only_registered_tools(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(tool not in AGENT_TOOL_ALLOWLIST for tool in value):
            raise ValueError("Agent contains an unregistered tool.")
        return value

    @field_validator("model_id")
    @classmethod
    def valid_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not registration.MODEL_RE.fullmatch(value):
            raise ValueError("Model identifier is invalid.")
        return value

class OllamaConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_mode: Literal["api_key", "local_cli"]
    api_key: str | None = Field(default=None, max_length=4096)
    model_id: str | None = Field(default=None, max_length=128)

class OllamaVerifyRequest(BaseModel):
    model_id: str | None = Field(default=None, max_length=128)

class GithubCopilotModelsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_mode: Literal["copilot_cli", "token"] = "copilot_cli"
    api_key: str | None = Field(default=None, max_length=4096)

class CodexLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_mode: Literal["chatgpt", "api_key"] = "chatgpt"
    api_key: SecretStr | None = Field(default=None, max_length=4096)

class ProviderRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_mode: str = Field(min_length=1, max_length=40)
    model_id: str | None = Field(default=None, max_length=128)
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)

class AgentCreateRequest(BaseModel):
    """Create body also accepts the legacy Builder shape without provider fields."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    task_scope: str | None = Field(default=None, max_length=8000)
    type: Literal["rag", "tool", "multi-agent"]
    system_prompt: str = Field(min_length=1, max_length=12000)
    provider_id: Literal["ollama-cloud", "codex", "openai-platform", "github-copilot"] | None = None
    model_id: str | None = Field(default=None, max_length=128)
    tools: list[str] = Field(default_factory=list, max_length=20)
    retrieval_config: dict[str, Any] | None = None
    sandbox_profile: str | None = Field(default=None, max_length=100)
    task: TaskDefinition | None = None

    @field_validator("tools")
    @classmethod
    def only_registered_tools(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(tool not in AGENT_TOOL_ALLOWLIST for tool in value):
            raise ValueError("Agent contains an unregistered tool.")
        return value

    @field_validator("model_id")
    @classmethod
    def valid_model(cls, value: str | None) -> str | None:
        if not value:
            return None
        if not registration.MODEL_RE.fullmatch(value):
            raise ValueError("Model identifier is invalid.")
        return value

class CsvReadOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=512)
    delimiter: Literal["auto", ",", ";", "\t", "|"] = "auto"
    decimal_separator: Literal[".", ","] = "."


class CsvReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=8000)
    csv_read: CsvReadOptions


class ReadProjectExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    project_id: str = Field(min_length=1, max_length=128)
    binding: str = Field(min_length=1, max_length=4096)
    revision: str = Field(min_length=1, max_length=128)


class ControlChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["chat", "help", "list_agents", "draft_agent", "navigate"] = "chat"
    message: str = Field(default="", max_length=8000)
    view: Literal["inspector", "builder", "chat", "workspace", "runner", "control", "jobs", "traces", "summary", "retrieval", "authorization", "evaluation", "evaluation_lab", "provider_settings", "cognition_settings", "capabilities", "communications", "whatsapp_settings"] | None = None
    capability_id: Literal["workspace.scan_duplicates"] | None = None
    conversation_id: str
    revision: int = Field(ge=0)
    web_read_authorization_id: str | None = Field(default=None, max_length=128)
    workspace_read_authorization_id: str | None = Field(default=None, max_length=128)
    workspace_scan_authorization_id: str | None = Field(default=None, max_length=128)
    cognitive_mode: Literal["baseline", "bago5"] = "baseline"
    csv_read: CsvReadOptions | None = None

class ProviderSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=128)

class ModelPolicyRequest(model_policy.Policy):
    expected_revision: str = Field(min_length=1, max_length=64)

class KnowledgeIngestAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=512)
    question: str = Field(min_length=1, max_length=4000)
    source_authority: Literal["PROPOSED", "VERIFIED"]
    minimum_authority: Literal["PROPOSED", "VERIFIED"]

class OpenMetadataLiveValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_run: bool

class OntologyProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=512)

class OntologyApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_ids: list[str] = Field(min_length=1, max_length=100)

class OntologyQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)

class AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str
    revision: int = Field(ge=0)
    web_read_authorization_id: str | None = Field(default=None, max_length=128)
    workspace_read_authorization_id: str | None = Field(default=None, max_length=128)
    workspace_scan_authorization_id: str | None = Field(default=None, max_length=128)
    allow_workspace_write_proposals: bool = False
    document_authorization_id: str | None = Field(default=None, max_length=128)
    cognitive_mode: Literal["baseline", "bago5"] = "baseline"

class WebReadAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_kind: Literal["assistant", "agent"]
    owner_id: str = Field(min_length=1, max_length=128)
    conversation_id: str
    revision: int = Field(ge=0)
    urls: list[str] = Field(min_length=1, max_length=8)

class WorkspaceReadAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_kind: Literal["assistant", "agent"]
    owner_id: str = Field(min_length=1, max_length=128)
    conversation_id: str
    revision: int = Field(ge=0)
    paths: list[str] = Field(min_length=1, max_length=20)
    csv_request: CsvReadRequest | None = None
    expected_project: ReadProjectExpectation | None = None


class WorkspaceReadRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    owner_kind: Literal["assistant", "agent"]
    owner_id: str = Field(min_length=1, max_length=128)
    conversation_id: str
    revision: int = Field(ge=0)

class WorkspaceScanAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_kind: Literal["assistant", "agent"]
    owner_id: str = Field(min_length=1, max_length=128)
    conversation_id: str
    revision: int = Field(ge=0)
    directories: list[str] = Field(min_length=1, max_length=5)

class WorkspaceScanRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    revision: int = Field(ge=0)
    authorization_id: str = Field(min_length=32, max_length=128)
    directory: str = Field(min_length=1, max_length=512)

class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_kind: Literal["assistant", "agent"]
    owner_id: str = Field(default="app-assistant", min_length=1, max_length=128)
    title: str = Field(default="New conversation", min_length=1, max_length=160)

class ConversationRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)

class ConversationPermanentDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    confirmed: bool

class CapabilityProposalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_.-]*$")
    summary: str = Field(min_length=1, max_length=500)
    requested_scope: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, min_length=37, max_length=37, pattern=r"^conv_[0-9a-f]{32}$")

    @field_validator("summary", "requested_scope")
    @classmethod
    def clean_proposal_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value or any(ord(character) < 32 for character in value):
            raise ValueError("Proposal text must be plain non-empty text.")
        if re.search(
            r"(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)\s*[:=]\s*\S+|"
            r"\bBearer\s+\S+|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            value,
            re.IGNORECASE,
        ):
            raise ValueError("Proposal text must not contain credentials.")
        return value

class CapabilityProposalCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)

class EvaluationSuiteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    agent_id: str = Field(min_length=1, max_length=64)
    cases: list[dict[str, Any]] = Field(min_length=1, max_length=10)

class EvaluationSuiteUpdateRequest(EvaluationSuiteCreateRequest):
    expected_revision: int = Field(ge=0)

class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    model_id: str = Field(min_length=1, max_length=128)

class ConversationRenameRequest(ConversationRevisionRequest):
    title: str = Field(min_length=1, max_length=160)

class ConversationLabelsRequest(ConversationRevisionRequest):
    model_config = ConfigDict(extra="forbid", strict=True)

    labels: list[str] = Field(max_length=20)

    @field_validator("labels")
    @classmethod
    def clean_labels(cls, value: list[str]) -> list[str]:
        return normalize_conversation_labels(value)

class AgentResponse(BaseModel):
    id: str
    config: AgentConfig
    created_at: str

class JobResponse(BaseModel):
    job_id: str
    agent_id: str | None
    job_type: str
    status: str
    created_at: str
    completed_at: str | None
    duration_ms: int | None
    exit_code: int | None
    cost_usd: float
    metrics: dict[str, Any] | None

__all__ = [
    "AGENT_TOOL_ALLOWLIST",
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
]
