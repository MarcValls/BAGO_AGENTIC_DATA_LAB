"""Single-instance launcher preflight without starting or focusing the UI."""
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(os.name != "nt" or not SHELL, reason="Windows PowerShell runtime required")


def preflight_with_mocks(listeners, command_line=""):
    source = str(ROOT / "scripts" / "run-local-ui.ps1").replace("'", "''")
    mock_listeners = ",".join(
        "[pscustomobject]@{OwningProcess=%d;LocalAddress='%s';LocalPort=%d}"
        % (item[0], item[1], item[2] if len(item) > 2 else 8080)
        for item in listeners
    )
    listener_output = f"@({mock_listeners})" if mock_listeners else "@()"
    mock_command = command_line.replace("'", "''")
    code = f"""
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'PowerShell parse failed' }}
$node = $ast.Find({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-LocalUiPreflight' }}, $true)
if (-not $node) {{ throw 'Preflight function missing' }}
. ([scriptblock]::Create($node.Extent.Text))
$repoRoot = '{str(ROOT).replace("'", "''")}'
function Get-NetTCPConnection {{ param($LocalPort,$State,$ErrorAction) {listener_output} }}
function Get-Process {{ param($Id,$ErrorAction) [pscustomobject]@{{ProcessName='python'}} }}
function Get-CimInstance {{ param($ClassName,$Filter,$ErrorAction) [pscustomobject]@{{Name='python.exe';CommandLine='{mock_command}'}} }}
Get-LocalUiPreflight | ConvertTo-Json -Compress
"""
    result = subprocess.run([SHELL, "-NoProfile", "-NonInteractive", "-Command", code],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip())


def test_empty_port_is_available():
    assert preflight_with_mocks([])["State"] == "FREE"


def test_other_process_is_not_reused():
    result = preflight_with_mocks([(4312, "127.0.0.1")], '"C:\\other\\python.exe" -m other.service')
    assert result["State"] == "CONFLICT"
    assert result["Pid"] == 4312


def test_ambiguous_listeners_are_not_reused():
    result = preflight_with_mocks([(4312, "127.0.0.1"), (4313, "127.0.0.1")])
    assert result["State"] == "CONFLICT"


def test_wildcard_listener_is_not_reused():
    result = preflight_with_mocks([(4312, "0.0.0.0")])
    assert result["State"] == "CONFLICT"


def test_another_adl_port_blocks_new_instance():
    result = preflight_with_mocks([(4312, "127.0.0.1", 8081)], '"C:\\other\\python.exe" -m src.api.server')
    assert result["State"] == "CONFLICT"
    assert result["Pid"] == 4312
    assert "8081" in result["Reason"]


@pytest.mark.parametrize("address,expected", [
    ("127.0.0.1:8080", True),
    ("http://localhost:8080/settings", True),
    ("http://127.0.0.1:8080?project=1", True),
    ("https://127.0.0.1:8080", False),
    ("127.0.0.1:80801", False),
    ("http://localhost:8080.evil.example", False),
    ("https://example.org", False),
])
def test_address_recognition_does_not_accept_other_origins(address, expected):
    source = str(ROOT / "scripts" / "run-local-ui.ps1").replace("'", "''")
    value = address.replace("'", "''")
    code = f"""
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'PowerShell parse failed' }}
$node = $ast.Find({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-LocalUiAddress' }}, $true)
. ([scriptblock]::Create($node.Extent.Text))
Test-LocalUiAddress '{value}' | ConvertTo-Json -Compress
"""
    result = subprocess.run([SHELL, "-NoProfile", "-NonInteractive", "-Command", code],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) is expected


def test_unique_matching_address_is_focused_without_prompt():
    source = str(ROOT / "scripts" / "run-local-ui.ps1").replace("'", "''")
    code = f"""
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'PowerShell parse failed' }}
$node = $ast.Find({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Resolve-BrowserWindowAction' }}, $true)
. ([scriptblock]::Create($node.Extent.Text))
function Get-VisibleBrowserWindows {{ [pscustomobject]@{{ProcessId=4312; ProcessName='brave'; Title='fixture'; AddressState='MATCH'}} }}
function Read-Host {{ throw 'Unexpected PID prompt' }}
function Write-Host {{ param($Object) }}
Resolve-BrowserWindowAction | Select-Object Action,BagoRecognized | ConvertTo-Json -Compress
"""
    result = subprocess.run([SHELL, "-NoProfile", "-NonInteractive", "-Command", code],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {"Action": "focus", "BagoRecognized": True}


def test_matching_windows_remain_selectable_when_multiple_addresses_match():
    source = str(ROOT / "scripts" / "run-local-ui.ps1").replace("'", "''")
    code = f"""
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'PowerShell parse failed' }}
$node = $ast.Find({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Resolve-BrowserWindowAction' }}, $true)
. ([scriptblock]::Create($node.Extent.Text))
function Get-VisibleBrowserWindows {{
  [pscustomobject]@{{ProcessId=4312; ProcessName='brave'; Title='fixture 1'; AddressState='MATCH'}}
  [pscustomobject]@{{ProcessId=4313; ProcessName='brave'; Title='fixture 2'; AddressState='MATCH'}}
}}
function Read-Host {{ param($Prompt) '4313' }}
function Write-Host {{ param($Object) }}
$result = Resolve-BrowserWindowAction
[pscustomobject]@{{ Action=$result.Action; Pid=$result.Window.ProcessId; Recognized=$result.BagoRecognized }} | ConvertTo-Json -Compress
"""
    result = subprocess.run([SHELL, "-NoProfile", "-NonInteractive", "-Command", code],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {"Action": "focus", "Pid": 4313, "Recognized": True}


@pytest.mark.parametrize("shell", [SHELL, shutil.which("powershell.exe")])
@pytest.mark.parametrize("case,expected", [("valid", True), ("pid", False), ("path", False), ("hash", False)])
def test_runtime_identity_binds_pid_source_and_loaded_bytes(case, expected, shell):
    if shell is None:
        pytest.skip("PowerShell runtime not available")
    source = str(ROOT / "scripts" / "run-local-ui.ps1").replace("'", "''")
    backend = str(ROOT / "src" / "api" / "server.py").replace("'", "''")
    backend_hash = hashlib.sha256((ROOT / "src" / "api" / "server.py").read_bytes()).hexdigest()
    code = f"""
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'PowerShell parse failed' }}
$node = $ast.Find({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-LocalUiRuntimeIdentity' }}, $true)
. ([scriptblock]::Create($node.Extent.Text))
$expectedSource = '{backend}'
$runtime = [pscustomobject]@{{ process_id=4312; server_source_path=$expectedSource; server_source_sha256_at_import='{backend_hash}' }}
switch ('{case}') {{
    'pid' {{ $runtime.process_id = 4313 }}
    'path' {{ $runtime.server_source_path = $expectedSource + '.other' }}
    'hash' {{ $runtime.server_source_sha256_at_import = '0' * 64 }}
}}
Test-LocalUiRuntimeIdentity $runtime $expectedSource 4312 | ConvertTo-Json -Compress
"""
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", code],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) is expected


@pytest.mark.parametrize("shell", [SHELL, shutil.which("powershell.exe")])
@pytest.mark.parametrize("case,expected", [('valid', True), ('persisted', True), ('missing', False), ('version', False),
                                           ('pid', False), ('start', False), ('tick', False), ('persisted_tick', False),
                                           ('timezone', False), ('persisted_timezone', False), ('root', False),
                                           ('backend', False), ('frontend', False), ('dist', False)])
def test_reuse_requires_matching_start_receipt(case, expected, shell):
    if shell is None:
        pytest.skip('PowerShell runtime not available')
    source = str(ROOT / 'scripts' / 'run-local-ui.ps1').replace("'", "''")
    repo = str(ROOT).replace("'", "''")
    code = f"""
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'PowerShell parse failed' }}
$node = $ast.Find({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-LocalUiFreshnessProof' }}, $true)
. ([scriptblock]::Create($node.Extent.Text))
$repoRoot = '{repo}'
$start = [datetime]::Parse('2026-11-23T10:00:00.1234567Z').ToUniversalTime()
$proof = [pscustomobject]@{{ managed_by='bago-agent-chat-launcher'; fingerprint_version='bago-runtime-inputs-v1'; repo_root=$repoRoot; listener_pid=4312; listener_start_utc=$start.ToString('o'); input_fingerprints=[pscustomobject]@{{backend=('a'*64); frontend=('b'*64); dist=('c'*64)}} }}
function Get-LocalUiInputFingerprint {{ param($kind) switch ($kind) {{ backend {{'a'*64}} frontend {{'b'*64}} dist {{'c'*64}} }} }}
switch ('{case}') {{
  persisted {{ $proof=$proof | ConvertTo-Json -Depth 5 | ConvertFrom-Json }}
  missing {{ $proof=$null }}
  version {{ $proof.fingerprint_version='older' }}
  pid {{ $proof.listener_pid=4313 }}
  start {{ $proof.listener_start_utc=$start.AddSeconds(-1).ToString('o') }}
  tick {{ $proof.listener_start_utc=$start.AddTicks(1).ToString('o') }}
  persisted_tick {{ $proof.listener_start_utc=$start.AddTicks(1).ToString('o'); $proof=$proof | ConvertTo-Json -Depth 5 | ConvertFrom-Json }}
  timezone {{ $proof.listener_start_utc='2026-11-23T10:00:00.1234567' }}
  persisted_timezone {{ $proof.listener_start_utc='2026-11-23T10:00:00.1234567'; $proof=$proof | ConvertTo-Json -Depth 5 | ConvertFrom-Json }}
  root {{ $proof.repo_root=$repoRoot+'-different' }}
  backend {{ $proof.input_fingerprints.backend='d'*64 }}
  frontend {{ $proof.input_fingerprints.frontend='d'*64 }}
  dist {{ $proof.input_fingerprints.dist='d'*64 }}
}}
Test-LocalUiFreshnessProof $proof 4312 $start | ConvertTo-Json -Compress
"""
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-Command', code],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) is expected


@pytest.mark.parametrize("shell", [SHELL, shutil.which("powershell.exe")])
@pytest.mark.parametrize("listeners,expected", [([], True), ([4312], False), ([4312, 4313], False)])
def test_port_availability_accepts_pipeline_cardinality_under_strict_mode(shell, listeners, expected):
    if shell is None:
        pytest.skip("PowerShell runtime not available")
    source = str(ROOT / "scripts" / "run-local-ui.ps1").replace("'", "''")
    values = ",".join(map(str, listeners))
    code = f"""
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'PowerShell parse failed' }}
$node = $ast.Find({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-LocalPortAvailable' }}, $true)
. ([scriptblock]::Create($node.Extent.Text))
function Get-ListenerProcessIds {{ param($Port) @({values}) }}
Set-StrictMode -Version Latest
Test-LocalPortAvailable 0 | ConvertTo-Json -Compress
"""
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", code],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) is expected


def test_start_lock_serializes_competing_processes():
    source = str(ROOT / "scripts" / "run-local-ui.ps1").replace("'", "''")
    name = "Local\\BAGO_TEST_" + uuid.uuid4().hex
    load = f"""
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'PowerShell parse failed' }}
$node = $ast.Find({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Enter-LocalUiStartLock' }}, $true)
. ([scriptblock]::Create($node.Extent.Text))
$lock = Enter-LocalUiStartLock '{name}'
"""
    holder = subprocess.Popen([SHELL, "-NoProfile", "-NonInteractive", "-Command", load + """
if (-not $lock) { throw 'Could not acquire test lock' }
[Console]::WriteLine('READY'); [Console]::Out.Flush()
[Console]::In.ReadLine() | Out-Null
$lock.ReleaseMutex(); $lock.Dispose()
"""], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8")
    try:
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(holder.stdout.readline()), daemon=True).start()
        assert lines.get(timeout=20).strip() == "READY"
        contender = subprocess.run([SHELL, "-NoProfile", "-NonInteractive", "-Command", load + """
if ($lock) { $lock.ReleaseMutex(); $lock.Dispose(); Write-Output 'ACQUIRED' }
else { Write-Output 'BUSY' }
"""], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert contender.returncode == 0, contender.stderr
        assert contender.stdout.strip() == "BUSY"
        holder.stdin.write("release\n")
        holder.stdin.flush()
        holder.wait(timeout=20)
        assert holder.returncode == 0
        after = subprocess.run([SHELL, "-NoProfile", "-NonInteractive", "-Command", load + """
if ($lock) { $lock.ReleaseMutex(); $lock.Dispose(); Write-Output 'ACQUIRED' }
else { Write-Output 'BUSY' }
"""], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert after.returncode == 0, after.stderr
        assert after.stdout.strip() == "ACQUIRED"
    finally:
        if holder.poll() is None:
            holder.terminate()
            holder.wait(timeout=10)
