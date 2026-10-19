# BAGO Embedded Runtime effect demo in ADL

`python scripts/ber_effect_demo.py` is an explicit local demonstration path.
It is separate from Agent Runner, which remains unavailable until the later
compatibility and standalone gates pass. The script starts the pinned BER
archive from ADL, displays the prepared effect, and prints the BAGO receipt,
ADL `LocalTrace`, and effect-profile evaluation as JSON.

## Read a workspace file

```powershell
python scripts/ber_effect_demo.py --workspace C:\work\project --effect filesystem.read --path README.md
```

The tool prompts for `APROBAR filesystem.read`. Without that exact response it
does not execute the read. The file content is returned in the execution result;
the trace records identifiers and the receipt reference, not the file content.

## Create or modify a file

```powershell
python scripts/ber_effect_demo.py --workspace C:\work\project --effect filesystem.write --path output\demo.txt --content "approved content"
```

The command creates a new file only. To modify an existing file, supply its
current SHA-256 so BAGO can reject a stale target:

```powershell
$digest = (Get-FileHash C:\work\project\output\demo.txt -Algorithm SHA256).Hash.ToLowerInvariant()
python scripts/ber_effect_demo.py --workspace C:\work\project --effect filesystem.write --path output\demo.txt --content "updated content" --expected-sha256 $digest
```

The effect requires the exact `APROBAR filesystem.write` confirmation. The
write result includes BAGO's receipt and readback digest.

## Typed process inspection

```powershell
python scripts/ber_effect_demo.py --workspace C:\work\project --effect process.inspect --executable git --cwd C:\work\project --argv status --porcelain=v1 --untracked-files=all
```

BER permits only its fixed read-only process query profile and uses
`shell=False`. `process.inspect` follows BAGO server policy and does not request
a user approval prompt. Other commands outside the profile are denied.

## Typed process execution

```powershell
python scripts/ber_effect_demo.py --workspace C:\work\project --effect process.execute --executable python --cwd C:\work\project --argv -m pytest tests\runtime\ber -q
```

BER restricts the executable/argument profile and requires the exact
`APROBAR process.execute` confirmation. Do not pass a shell command string.

The output schema is `bago.ber.effect-demo.v1`. `evaluation` is a bounded
execution-receipt evaluation; it does not claim an AgentRun, answer quality, or
the full agent workflow. `filesystem.delete` is not an available choice.
