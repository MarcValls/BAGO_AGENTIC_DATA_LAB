$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$audio = Join-Path $root 'audio'
New-Item -ItemType Directory -Force -Path $audio | Out-Null
$scenes = Get-Content (Join-Path $root 'narration.json') -Raw | ConvertFrom-Json
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice('Microsoft Helena Desktop')
$speaker.Rate = 0
$speaker.Volume = 92
for ($i = 0; $i -lt $scenes.Count; $i++) {
  $name = 'scene-{0:D2}.wav' -f ($i + 1)
  $speaker.SetOutputToWaveFile((Join-Path $audio $name))
  $speaker.Speak([string]$scenes[$i])
  $speaker.SetOutputToNull()
}
$speaker.Dispose()
Write-Output "Generated $($scenes.Count) Spanish voice segments locally with Windows Speech."
