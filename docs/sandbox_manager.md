# Governed Sandbox Layer

## Purpose

The sandbox is the technical enforcement layer below the BAGO execution
boundary:

```text
Reasoning
  → AuthorizationBoundary
  → Permit
  → ExecutionGateway
  → SandboxManager
  → LocalRestrictedBackend
  → Capability
  → Receipt / Evidence
```

`AuthorizationBoundary` decides authority. `ExecutionGateway` requires a
typed sandbox request. `SandboxManager` derives the effective limits from the
permit, and the backend materializes those limits. A profile can reduce a
permit, never increase it; an agent cannot select a broader profile.

## Implemented local scope

- workspace-root and symlink-aware path resolution;
- read/write allowlists with explicit `write_scope=workspace`;
- typed filesystem requests;
- typed `pytest` execution through `python -m pytest` with an argument
  allowlist and `shell=False`;
- read-only typed Git operations (`status`, `diff`, `log`, `show`);
- permit-bound timeout and output limits;
- filtered inherited environment and credential-like variable denial;
- receipts for success, failure, timeout and denial;
- fail-closed provisioning when OS-level network isolation is requested.

Example request:

```python
operation = ProcessRequest(
    request_id="req-tests",
    capability=Capability.RUN_TESTS,
    tool="pytest",
    arguments=("-q", "tests"),
)
result = ExecutionGateway().execute(
    request=execution_request,
    permit=permit,
    sandbox_request=SandboxRequest("req-tests", workspace_root, operation),
)
```

The receipt records the effective profile, capability, operation, exit status,
timeout, output hashes and an evidence reference. It does not record inherited
environment values.

## Explicit boundary

`LocalRestrictedBackend` is a logical policy backend, not an OS container. A
subprocess launched locally could still access operating-system resources that
Python cannot reliably deny without Windows Sandbox, a container, Hyper-V or
another OS isolation primitive. Therefore `network=allowlist` and
`os_network_isolation=required` fail closed today. No AWS, paid service or
credential is required for this block.

## Reproduction

```powershell
python -m pytest tests/test_sandbox.py -q
python scripts/run_sandbox_local_validation.py
```

The generated receipt is `evidence/sandbox_local_restricted.md`.

