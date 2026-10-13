import json, pathlib, subprocess, wave, hashlib
from PIL import Image, ImageDraw, ImageFont
base=pathlib.Path('output/playwright/tutorial-otras-pantallas').resolve(); W,H=1600,900
navy='#0b1524'; white='#f2f6fb'; muted='#b5c5d8'; blue='#63a8ff'; amber='#ffc766'
fontp='C:/Windows/Fonts/segoeui.ttf'; boldp='C:/Windows/Fonts/segoeuib.ttf'
def ft(n,b=False): return ImageFont.truetype(boldp if b else fontp,n)
scenes=[
 ('02-summary.png','Resumen del caso','La pantalla Summary agrupa el estado del caso ficticio Bruma Market. Aquí la interfaz muestra siete comprobaciones, dos resultados de recuperación y quince eventos de traza. Son artefactos de una demo precargada; PASS no certifica una operación real ni una conexión activa a AWS.'),
 ('03-retrieval.png','Recuperación y ontología','Retrieval and Ontology enseña cómo se filtraron documentos, qué fragmentos se recuperaron y qué citas los respaldan. La misma vista presenta rutas y consultas de ontología. En esta demo son resultados ya guardados, no una búsqueda nueva.'),
 ('04-authorization.png','Autorización y recibos','Authorization reúne propuestas de herramientas, permisos y recibos del proveedor y del sandbox. Sirve para revisar el límite entre una propuesta y su ejecución. Los recibos visibles pertenecen al paquete de demostración; no los tomes como actividad nueva de esta grabación.'),
 ('05-trace.png','Traza del flujo','Trace muestra quince eventos ordenados, sus identificadores y referencias de evidencia. La vista permite desplegar atributos y referencias por evento. La pantalla es una traza local del paquete de demo y no está exportada a una plataforma cloud.'),
 ('06-evaluation.png','Evaluación de gobernanza','Evaluation presenta siete comprobaciones, su puntuación y las referencias de respaldo. El PASS refleja únicamente esos artefactos y reglas de demo. Para validar un negocio real habría que contrastar las reglas y los datos de entrada con sus responsables.'),
 ('07-inspector.png','Decision Inspector','Decision Inspector conecta una conclusión con claims, evidencia, procedencia, traza y acciones propuestas. Los claims no se inventan a partir del texto de respuesta: la interfaz distingue lo que aportó la fuente de lo que puede comprobarse.'),
 ('09-capabilities.png','Capacidades disponibles','Capabilities lista operaciones reconocidas por la app y su disponibilidad. Es una pantalla útil para saber qué herramientas están expuestas antes de diseñar un agente; disponibilidad no significa que una ejecución haya ocurrido.'),
 ('08-jobs.png','Historial y límite actual','Job History devuelve cero trabajos y muestra “No jobs yet”. Agent Runner, en cambio, indica que la ejecución gobernada no está disponible. Así que el caso de Bruma que vimos antes vive como paquete de artefactos, no como un job registrado aquí.'),
]
narr=[]
for i,(file,title,voice) in enumerate(scenes,1):
 im=Image.new('RGB',(W,H),navy); d=ImageDraw.Draw(im)
 shot=Image.open(base/file).convert('RGB'); shot.thumbnail((1540,690),Image.Resampling.LANCZOS)
 im.paste(shot,((W-shot.width)//2,135+(690-shot.height)//2)); d.rectangle((0,0,W,118),fill=navy);d.text((54,28),title,font=ft(37,True),fill=white)
 d.rectangle((0,830,W,H),fill=navy);d.text((54,846),'BAGO · CAPTURAS DE LA APP · CASO BRUMA MARKET FICTICIO',font=ft(18,True),fill=blue)
 # subtle screenshot border
 d.rectangle((29,134,1570,826),outline='#34506f',width=2)
 im.save(base/f'scene-{i:02}.png');narr.append(voice)
(base/'narration.json').write_text(json.dumps(narr,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(base/'make-local-voice.ps1').write_text("$ErrorActionPreference='Stop'\nAdd-Type -AssemblyName System.Speech\n$root=Split-Path -Parent $MyInvocation.MyCommand.Path\n$audio=Join-Path $root 'audio'\nNew-Item -ItemType Directory -Force -Path $audio | Out-Null\n$scenes=Get-Content (Join-Path $root 'narration.json') -Raw | ConvertFrom-Json\n$s=New-Object System.Speech.Synthesis.SpeechSynthesizer\n$s.SelectVoice('Microsoft Helena Desktop'); $s.Rate=0; $s.Volume=92\nfor($i=0;$i -lt $scenes.Count;$i++){ $name='scene-{0:D2}.wav' -f ($i+1); $s.SetOutputToWaveFile((Join-Path $audio $name)); $s.Speak([string]$scenes[$i]); $s.SetOutputToNull() }\n$s.Dispose()\n",encoding='utf-8')
subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(base/'make-local-voice.ps1')],check=True)
durations=[]
for i in range(1,len(scenes)+1):
 with wave.open(str(base/'audio'/f'scene-{i:02}.wav'),'rb') as w:durations.append(w.getnframes()/w.getframerate())
pad=.35
with wave.open(str(base/'audio'/'scene-01.wav'),'rb') as w: params=w.getparams();silence=b'\0'*int(params.framerate*pad)*params.nchannels*params.sampwidth
with wave.open(str(base/'audio'/'silence.wav'),'wb') as w:w.setparams(params);w.writeframes(silence)
vid=[];aud=[]
for i,dur in enumerate(durations,1):
 vid += [f"file '{(base/f'scene-{i:02}.png').as_posix()}'\n",f'duration {dur+pad:.3f}\n'];aud.append(f"file '{(base/'audio'/f'scene-{i:02}.wav').as_posix()}'\n")
 if i<len(durations):aud.append(f"file '{(base/'audio'/'silence.wav').as_posix()}'\n")
vid.append(f"file '{(base/f'scene-{len(durations):02}.png').as_posix()}'\n")
(base/'video-scenes.txt').write_text(''.join(vid),encoding='utf8');(base/'audio-scenes.txt').write_text(''.join(aud),encoding='utf8')
subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(base/'audio-scenes.txt'),'-c:a','pcm_s16le',str(base/'narration.wav')],check=True)
total=sum(durations)+pad*(len(durations)-1)
video=base/'tutorial-otras-pantallas.mp4'
subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(base/'video-scenes.txt'),'-i',str(base/'narration.wav'),'-vf','fps=25,format=yuv420p','-c:v','libx264','-preset','medium','-crf','21','-c:a','aac','-b:a','160k','-t',f'{total:.3f}','-movflags','+faststart',str(video)],check=True)
def tm(x):
 ms=round(x*1000);return f'{ms//3600000:02}:{(ms%3600000)//60000:02}:{(ms%60000)//1000:02},{ms%1000:03}'
cursor=0;subs=[]
for i,((_,title,voice),dur) in enumerate(zip(scenes,durations),1):subs.append(f'{i}\n{tm(cursor)} --> {tm(cursor+dur)}\n{title}: {voice}\n');cursor+=dur+pad
(base/'tutorial-otras-pantallas.srt').write_text('\n'.join(subs),encoding='utf8')
probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size','-of','json',str(video)],capture_output=True,text=True,check=True)
report={'capture_report':'screen-capture-report.json','javascript_errors':json.loads((base/'screen-capture-report.json').read_text())['page_errors'],'scene_count':len(scenes),'duration_expected_seconds':round(total,2),'ffprobe':json.loads(probe.stdout),'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest()}
(base/'video-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
readme='''# Recorrido por otras pantallas de BAGO\n\n- Video: [tutorial-otras-pantallas.mp4](tutorial-otras-pantallas.mp4)\n- Subtítulos: [tutorial-otras-pantallas.srt](tutorial-otras-pantallas.srt)\n- Evidencia de capturas y texto de pantalla: [screen-capture-report.json](screen-capture-report.json)\n- Verificación de reproducción/huella: [video-verification.json](video-verification.json)\n\nEl recorrido muestra Summary, Retrieval & Ontology, Authorization, Trace, Evaluation, Decision Inspector, Capabilities, Job History y Agent Runner. Las capturas se obtuvieron navegando la app local `http://127.0.0.1:8081` en modo lectura. La llamada de navegación solo consultó artefactos ya cargados y el endpoint de historial. No se lanzó una llamada al modelo.\n\nBruma Market es un cliente ficticio. PASS, sus conteos, trazas y recibos son artefactos de demostración; AWS Live consta como NOT_RUN. La traza del paquete es local. Job History mostró cero trabajos y Agent Runner señaló que la ejecución gobernada no está disponible.\n\nLas imágenes `scene-*.png` contienen capturas reales de las pantallas con título de capítulo. El WAV y los WAV por capítulo se generaron localmente con la voz del sistema.\n'''
(base/'README.md').write_text(readme,encoding='utf8')
manifest={}
for p in sorted(base.rglob('*')):
 if p.is_file() and p.name!='sha256-manifest.json': manifest[p.relative_to(base).as_posix()]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(base/'sha256-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))

