"""Adapters for external capabilities behind BAGO governance boundaries."""

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
    "CapabilityDescriptor",
    "CapabilityRegistry",
    "GovernedMCPAdapter",
    "MCPCallReceipt",
    "MCPGovernanceError",
    "MCPGovernancePolicy",
    "RegisteredCapability",
]
