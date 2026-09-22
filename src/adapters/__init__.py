"""Adapters for external capabilities behind BAGO governance boundaries."""

from .bedrock_provider_adapter import (
    BedrockCallReceipt,
    BedrockCallResult,
    BedrockConfigurationError,
    BedrockErrorKind,
    BedrockGovernanceError,
    BedrockProviderAdapter,
    BedrockProviderPolicy,
    BedrockUsage,
    GovernedBedrockAdapter,
)
from .bedrock_kb_adapter import (
    BedrockKBAdapter,
    BedrockKBHit,
    BedrockKBReceipt,
    BedrockKBResult,
    BedrockKnowledgeBaseAdapter,
    BedrockKnowledgeBasePolicy,
    GovernedBedrockKnowledgeBaseAdapter,
)
from .mcp_adapter import (
    CapabilityDescriptor,
    CapabilityRegistry,
    GovernedMCPAdapter,
    MCPCallReceipt,
    MCPGovernanceError,
    MCPGovernancePolicy,
    RegisteredCapability,
)

__all__ = [
    "BedrockCallReceipt",
    "BedrockCallResult",
    "BedrockKBAdapter",
    "BedrockKBHit",
    "BedrockKBReceipt",
    "BedrockKBResult",
    "BedrockKnowledgeBaseAdapter",
    "BedrockKnowledgeBasePolicy",
    "BedrockConfigurationError",
    "BedrockErrorKind",
    "BedrockGovernanceError",
    "BedrockProviderAdapter",
    "BedrockProviderPolicy",
    "BedrockUsage",
    "CapabilityDescriptor",
    "CapabilityRegistry",
    "GovernedMCPAdapter",
    "MCPCallReceipt",
    "MCPGovernanceError",
    "MCPGovernancePolicy",
    "RegisteredCapability",
    "GovernedBedrockAdapter",
    "GovernedBedrockKnowledgeBaseAdapter",
]
