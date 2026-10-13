import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const output = path.join(process.cwd(), 'output', 'playwright')
const scenes = JSON.parse(fs.readFileSync(path.join(output, 'tutorial-scenes.json'), 'utf8'))
const voiceDir = path.join(os.tmpdir(), 'bago_interface_tutorial_20261012')
const pauseSeconds = 0.35
const introSilence = 2.2
const audioPath = path.join(voiceDir, 'narration.wav')
const subtitlePath = path.join(output, 'tutorial-interfaz.srt')

function wavInfo(filename) {
  const data = fs.readFileSync(filename)
  const sampleRate = data.readUInt32LE(24)
  const channels = data.readUInt16LE(22)
  const bits = data.readUInt16LE(34)
  let dataBytes = 0
  let dataOffset = 44
  for (let offset = 12; offset + 8 <= data.length;) {
    const chunk = data.toString('ascii', offset, offset + 4)
    const size = data.readUInt32LE(offset + 4)
    if (chunk === 'data') { dataBytes = size; dataOffset = offset + 8; break }
    offset += 8 + size + (size % 2)
  }
  return { data, sampleRate, channels, bits, dataBytes, dataOffset, duration: dataBytes / (sampleRate * channels * bits / 8) }
}

const voiceInfo = scenes.map((_, index) => wavInfo(path.join(voiceDir, `scene-${String(index + 1).padStart(2, '0')}.wav`)))
const { sampleRate, channels, bits } = voiceInfo[0]
const blockAlign = channels * bits / 8
const silence = Buffer.alloc(Math.round(sampleRate * blockAlign * pauseSeconds / blockAlign) * blockAlign)
const audioParts = [Buffer.alloc(Math.round(sampleRate * channels * bits / 8 * introSilence))]
for (let index = 0; index < voiceInfo.length; index += 1) {
  const voice = voiceInfo[index]
  audioParts.push(voice.data.subarray(voice.dataOffset, voice.dataOffset + voice.dataBytes))
  if (index < voiceInfo.length - 1) audioParts.push(silence)
}
const audioDataBytes = audioParts.reduce((total, part) => total + part.length, 0)
const header = Buffer.alloc(44)
header.write('RIFF', 0); header.writeUInt32LE(36 + audioDataBytes, 4); header.write('WAVE', 8)
header.write('fmt ', 12); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20)
header.writeUInt16LE(channels, 22); header.writeUInt32LE(sampleRate, 24)
header.writeUInt32LE(sampleRate * channels * bits / 8, 28); header.writeUInt16LE(channels * bits / 8, 32)
header.writeUInt16LE(bits, 34); header.write('data', 36); header.writeUInt32LE(audioDataBytes, 40)
fs.writeFileSync(audioPath, Buffer.concat([header, ...audioParts]))

function srtTime(seconds) {
  const millis = Math.round(seconds * 1000)
  const hours = Math.floor(millis / 3_600_000)
  const minutes = Math.floor((millis % 3_600_000) / 60_000)
  const secs = Math.floor((millis % 60_000) / 1000)
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(millis % 1000).padStart(3, '0')}`
}
function wrap(text, width = 46) {
  const lines = []; let line = ''
  for (const word of text.split(/\s+/)) {
    if (line && `${line} ${word}`.length > width) { lines.push(line); line = word }
    else line = line ? `${line} ${word}` : word
  }
  if (line) lines.push(line)
  return lines.join('\n')
}
let clock = introSilence
const blocks = scenes.map((scene, index) => {
  const start = clock
  const end = start + voiceInfo[index].duration
  clock = end + (index < scenes.length - 1 ? pauseSeconds : 0)
  return `${index + 1}\n${srtTime(start)} --> ${srtTime(end)}\n${wrap(scene.narration)}\n`
})
fs.writeFileSync(subtitlePath, blocks.join('\n'), 'utf8')
console.log(JSON.stringify({ audioPath, subtitlePath, durationSeconds: clock, audioBytes: fs.statSync(audioPath).size }, null, 2))
