$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$audio=Join-Path $root 'audio'
New-Item -ItemType Directory -Force -Path $audio | Out-Null
$scenes=Get-Content (Join-Path $root 'narration.json') -Raw | ConvertFrom-Json
$s=New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Helena Desktop'); $s.Rate=0; $s.Volume=92
for($i=0;$i -lt $scenes.Count;$i++){ $name='scene-{0:D2}.wav' -f ($i+1); $s.SetOutputToWaveFile((Join-Path $audio $name)); $s.Speak([string]$scenes[$i]); $s.SetOutputToNull() }
$s.Dispose()
