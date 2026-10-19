# Inspect a BER effect record in ADL

ADL's data layer has a **BER Effect Record** view for JSON output from
`scripts/ber_effect_demo.py`. It is separate from **Decision Inspector** and
does not create or impersonate an `AgentRun`.

## Produce a record

Run a bounded BER effect against a workspace you control. For example, the
read-only process inspection path uses a temporary Git repository:

```powershell
$workspace = Join-Path $env:TEMP 'adl-ber-inspector-demo'
$record = Join-Path $env:TEMP 'adl-ber-effect.json'
New-Item -ItemType Directory -Force $workspace | Out-Null
git -C $workspace init
python scripts/ber_effect_demo.py --workspace $workspace --effect process.inspect --executable git --cwd $workspace --argv status --porcelain=v1 --untracked-files=all > $record
```

For `filesystem.write`, the CLI asks for the exact text `APROBAR
filesystem.write` before BAGO executes. Do not answer the prompt unless you
intend that workspace change. The record is printed as JSON on stdout; the
prompt is written to stderr. `filesystem.delete` and `process.terminate` are
not available.

## Inspect the record

1. Open **Inspect** in ADL.
2. Select **BER Effect Record** in the data-layer navigation.
3. Choose the saved `adl-ber-effect.json` file.
4. Compare the displayed BER version, pinned source/artifact identity,
   request, execution, receipt, LocalTrace and evaluation identifiers with the
   source file.

The view accepts only successful `bago.ber.effect-demo.v1` records matching
ADL's pinned BER release. It rejects identity drift, unsupported effects,
unlinked receipts or traces, and mutating-effect records without matching
approval/execution identities. It shows neither effect arguments nor process
output or file contents.

The view verifies supplied fields and their cross-links; the JSON is not
cryptographically signed, and the importer does not verify who produced it.
ADL LocalTrace and evaluation remain projections of BAGO's execution outcome,
not BAGO execution authority. Importing a file executes no effect. This view
does not enable Agent Runner, establish migration parity or satisfy the clean
standalone-package gate.
