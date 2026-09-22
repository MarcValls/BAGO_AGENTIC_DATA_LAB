"""Context contracts for binding governed work to one repository."""

from .workspace_binding import (
    WorkspaceBinding,
    WorkspaceBindingError,
    bind_workspace,
    normalize_repository_identity,
    workspace_binding_is_governed,
)

__all__ = [
    "WorkspaceBinding",
    "WorkspaceBindingError",
    "bind_workspace",
    "normalize_repository_identity",
    "workspace_binding_is_governed",
]
