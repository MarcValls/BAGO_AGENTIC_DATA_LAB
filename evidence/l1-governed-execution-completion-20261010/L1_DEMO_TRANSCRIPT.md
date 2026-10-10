# L1 integrated graph demo transcript

Source HEAD at execution: `f19ab7f2e1cebf5118989735227911a712c8cc05`

The graph retrieved governed local evidence, paused before the write, resumed with the exact fingerprint, and routed the operation through `ExecutionGateway` and `SandboxManager`.

- RUN allowed: paused before effect; file_exists=False
- RUN allowed: file_sha256=783be0f6caec66bc797a4e60da244489e13cae79d68172ca941416ff2ba73d96; receipt=sbxreceipt-f05fe68766434a47; status=SUCCESS
- RUN denied: no file created; receipt=sbxreceipt-d5c3f311e8244c69; error=PERMIT_REQUIRED
- RUN replay: receipt=sbxreceipt-9e80c7e9ef284f20; error=PERMIT_REPLAY
- RUN path_escape_failure: receipt=sbxreceipt-c0d5b221381a4611; error=PATH_ESCAPE; outside_file_exists=false
- RUN process_timeout: receipt=sbxreceipt-6ee815a8f49241fc; status=TIMEOUT; timeout_seconds=2

A LocalTrace was built from each graph result and the sandbox receipts. Replay was rejected within the same in-memory manager. No video was recorded. This demonstrates local logical workspace controls, not OS/network isolation or authenticated production identity.
