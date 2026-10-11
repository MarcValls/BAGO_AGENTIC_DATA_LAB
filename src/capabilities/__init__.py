"""Backend-owned capability catalog and non-authorizing proposal store."""

from src.capabilities.manager import (
    CapabilityNotFound,
    CapabilityProposalConflict,
    CapabilityProposalNotFound,
    CapabilityStore,
    capability_catalog,
)

__all__ = [
    "CapabilityNotFound",
    "CapabilityProposalConflict",
    "CapabilityProposalNotFound",
    "CapabilityStore",
    "capability_catalog",
]
