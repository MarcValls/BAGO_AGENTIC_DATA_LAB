"""Single execution boundary that delegates material effects to the sandbox."""

from __future__ import annotations

from typing import Optional

from src.orchestration.state_graph import ExecutionRequest, Permit
from src.sandbox.manager import SandboxManager, SandboxRequest
from src.sandbox.receipt import SandboxExecutionResult


class ExecutionGateway:
    """Require a typed sandbox request before any local effect can execute."""

    def __init__(self, *, sandbox_manager: SandboxManager | None = None) -> None:
        self.sandbox_manager = sandbox_manager or SandboxManager()

    def execute(
        self,
        *,
        request: ExecutionRequest,
        permit: Optional[Permit],
        sandbox_request: SandboxRequest | None,
    ) -> SandboxExecutionResult:
        if sandbox_request is None:
            return self.sandbox_manager.deny(
                request_id=request.request_id,
                permit_id=permit.permit_id if permit else "",
                capability="unknown",
                error_code="SANDBOX_REQUEST_REQUIRED",
                error_message="material effects require a typed SandboxRequest",
            )
        if sandbox_request.request_id != request.request_id:
            return self.sandbox_manager.deny(
                request_id=request.request_id,
                permit_id=permit.permit_id if permit else "",
                capability=sandbox_request.capability.value,
                error_code="SANDBOX_REQUEST_MISMATCH",
                error_message="sandbox request does not match ExecutionRequest",
            )
        return self.sandbox_manager.execute(permit=permit, request=sandbox_request)

