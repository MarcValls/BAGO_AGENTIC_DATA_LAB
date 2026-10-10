import json
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CAPTURE = ROOT / "capture"
META = json.loads((ROOT / "audio" / "metadata.json").read_text(encoding="utf-8-sig"))
SCENE_DATA = json.loads((CAPTURE / "scenes.json").read_text(encoding="utf-8-sig"))
if SCENE_DATA["errors"]:
    raise SystemExit("Capture contains errors; review capture/scenes.json before rendering.")

scene_by_id = {scene["narration_id"]: scene for scene in SCENE_DATA["scenes"]}
ordered = [row for row in META if row["id"] in scene_by_id]
if len(ordered) != len(META):
    raise SystemExit("Not every narration scene was recorded.")

raw = ROOT / "capture" / "raw" / "adl-first-user-tutorial-source.webm"
trimmed = ROOT / "capture" / "video-cut.mp4"
final = ROOT / "ADL_videotutorial_primer_usuario.mp4"
voice = ROOT / "audio" / "voiceover.wav"
srt = ROOT / "ADL_videotutorial_primer_usuario.es.srt"

filters = []
labels = []
for index, row in enumerate(ordered):
    scene = scene_by_id[row["id"]]
    start = scene["start_ms"] / 1000
    end = scene["end_ms"] / 1000
    label = f"v{index}"
    filters.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[{label}]")
    labels.append(f"[{label}]")
filters.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0[outv]")
subprocess.run([
    "ffmpeg", "-y", "-i", str(raw), "-filter_complex", ";".join(filters),
    "-map", "[outv]", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(trimmed),
], check=True)

with wave.open(str(ROOT / ordered[0]["file"]), "rb") as first:
    params = first.getparams()
    silence = b"\x00" * int(params.framerate * 0.25) * params.nchannels * params.sampwidth

with wave.open(str(voice), "wb") as output:
    output.setparams(params)
    for row in ordered:
        with wave.open(str(ROOT / row["file"]), "rb") as clip:
            clip_params = clip.getparams()
            if clip_params[:3] != params[:3] or clip_params[4:] != params[4:]:
                raise SystemExit(f"Audio format mismatch in {row['file']}")
            output.writeframes(clip.readframes(clip.getnframes()))
            output.writeframes(silence)

def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    whole, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{whole:02},{millis:03}"

cursor = 0.0
subtitle_lines = []
for number, row in enumerate(ordered, start=1):
    start = cursor
    cursor += row["duration"]
    subtitle_lines.extend([str(number), f"{srt_time(start)} --> {srt_time(cursor)}", row["text"], ""])
    cursor += 0.25
srt.write_text("\n".join(subtitle_lines), encoding="utf-8")

subprocess.run([
    "ffmpeg", "-y", "-i", str(trimmed), "-i", str(voice), "-map", "0:v:0", "-map", "1:a:0",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
    "-metadata", "title=Agentic Data Lab - videotutorial para el primer usuario",
    "-metadata:s:a:0", "language=spa", "-movflags", "+faststart", "-shortest", str(final),
], check=True)

print(json.dumps({
    "video": str(final),
    "subtitles": str(srt),
    "duration_s": round(cursor, 1),
    "size_bytes": final.stat().st_size,
}, ensure_ascii=False, indent=2))
