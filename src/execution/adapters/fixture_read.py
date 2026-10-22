"""One immutable in-memory fixture exposed as a typed read operation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json

from src.sandbox.backend import LocalRestrictedBackend, SandboxHandle
from src.sandbox.exceptions import SandboxViolation
from src.sandbox.filesystem import FilesystemOperation, FilesystemRequest
from src.sandbox.receipt import BackendExecution, SandboxStatus
from src.sandbox.specification import Capability
from src.sandbox.manager import SandboxPolicy


class FixtureReadPolicy(SandboxPolicy):
    """Narrow the shared sandbox derivation to the signed fixture byte limit.

    The generic legacy policy does not parse max_output_bytes. This adapter
    policy explicitly does, so its backend handle receives the actual bound.
    """
    def derive(self, permit, request):
        specification = super().derive(permit, request)
        raw = self._require_single(self._constraint_values(permit), "max_output_bytes")
        if not raw.isdigit() or not 1 <= int(raw) <= 65536:
            raise SandboxViolation("invalid fixture output limit", code="OUTPUT_LIMIT")
        return replace(specification, max_output_bytes=int(raw), allowed_git_operations=frozenset())

FIXTURE_ID = "adl.synthetic.customer-summary.v1"
FIXTURE_BYTES = b'{"customer_id":"fixture-customer-001","status":"synthetic","open_invoice_count":2}\n'
FIXTURE_SHA256 = sha256(FIXTURE_BYTES).hexdigest()
_INTERNAL_PATH = "__adl_gex_registered_fixture_v1__"


@dataclass(frozen=True)
class FixtureReadRequest:
    request_id: str
    fixture_id: str

    def __post_init__(self) -> None:
        if not self.request_id or self.fixture_id != FIXTURE_ID:
            raise ValueError("only the registered synthetic fixture can be read")

    @property
    def operation_digest(self) -> str:
        raw = json.dumps({"fixture_id": self.fixture_id, "operation": "READ", "version": 1},
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(raw).hexdigest()


class FixtureSandboxBackend(LocalRestrictedBackend):
    """Sandbox backend that maps one internal path to fixed bytes, never disk."""

    def execute(self, sandbox: SandboxHandle, request):  # type: ignore[no-untyped-def]
        if (isinstance(request, FilesystemRequest)
                and request.operation is FilesystemOperation.READ
                and request.relative_path == _INTERNAL_PATH
                and request.content is None):
            self._require_capability(sandbox.specification, Capability.FILESYSTEM_READ)
            if len(FIXTURE_BYTES) > sandbox.specification.max_output_bytes:
                raise SandboxViolation("registered fixture exceeds output limit", code="OUTPUT_LIMIT")
            return BackendExecution(status=SandboxStatus.SUCCESS, operation="fixture_read",
                                    value=FIXTURE_BYTES.decode("utf-8"))
        raise SandboxViolation("operation is outside the registered fixture adapter", code="FIXTURE_OPERATION_DENIED")


def sandbox_operation(request: FixtureReadRequest) -> FilesystemRequest:
    """Translate only after the public typed fixture request has been validated."""
    return FilesystemRequest(request_id=request.request_id, operation=FilesystemOperation.READ,
                             relative_path=_INTERNAL_PATH)
