"""Server-owned authentication and principal resolution for GEX."""

from .session import (
    AuthenticatedPrincipal,
    AuthenticationError,
    GexIdentityStore,
    IdentityProvisioningError,
    default_identity_database_path,
)

__all__ = [
    "AuthenticatedPrincipal",
    "AuthenticationError",
    "GexIdentityStore",
    "IdentityProvisioningError",
    "default_identity_database_path",
]
