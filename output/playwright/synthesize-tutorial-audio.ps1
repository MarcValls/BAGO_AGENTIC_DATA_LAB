Add-Type -AssemblyName System.Speech
$base = Join-Path $env:TEMP 'bago_interface_tutorial_20261012'
$sceneFile = Join-Path (Get-Location) 'output/playwright/tutorial-scenes.json'
$scenes = Get-Content -LiteralPath $sceneFile -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Path $base -Force | Out-Null
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$speaker.SelectVoice('Microsoft Helena Desktop')
$speaker.Rate = -1
$speaker.Volume = 95
for ($index = 0; $index -lt $scenes.Count; $index++) {
    $filename = Join-Path $base ('scene-{0:D2}.wav' -f ($index + 1))
    $speaker.SetOutputToWaveFile($filename)
    $speaker.Speak($scenes[$index].narration)
    $speaker.SetOutputToNull()
}
$speaker.Dispose()
Get-ChildItem -LiteralPath $base -Filter 'scene-*.wav' | Select-Object Name,Length
