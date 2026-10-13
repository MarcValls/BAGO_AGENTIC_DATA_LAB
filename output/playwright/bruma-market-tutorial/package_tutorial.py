import csv
import hashlib
import json
import pathlib
import re
import subprocess
import wave
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
RUNS = ROOT / 'cloud-runs'
ASSETS = ROOT / 'slides'
AUDIO = ROOT / 'audio'
EXTRACTED = ROOT / 'extracted'
for folder in (ASSETS, AUDIO, EXTRACTED):
    folder.mkdir(exist_ok=True)

def answer_json(run_name, opening, closing):
    record = json.loads((RUNS / run_name).read_text(encoding='utf-8'))
    text = record['assistant_message']
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.S)
    if not match:
        raise ValueError(f'No JSON code block in {run_name}')
    data = json.loads(match.group(1))
    if record['source'] != 'ollama' or record['trace']['trace_state'] != 'local_only':
        raise ValueError('Unexpected provider or trace state')
    if not record.get('read_events') or any(item['decision'] != 'ALLOW' for item in record['read_events']):
        raise ValueError('Cloud run did not produce all-ALLOW read receipts')
    return record, data

extract_run, extracted = answer_json('run-1.json', '{', '}')
policy_run, decisions = answer_json('run-2.json', '{', '}')
orders = extracted.get('orders', [])
rows = list(csv.DictReader((ROOT / 'inputs' / 'orders.csv').open(encoding='utf-8-sig', newline='')))
assert len(orders) == len(rows) == 4
assert [o['order_id'] for o in orders] == [r['order_id'] for r in rows]
assert [o['delay_hours'] for o in orders] == [32, 24, 48, None]
assert orders[0]['evidence_paths'] == []  # Model missed JSON citations; trace receipt below binds the source.
assert len(decisions.get('decisions', [])) == 4
assert [d['decision'] for d in decisions['decisions']] == ['ELIGIBLE', 'NOT_ELIGIBLE', 'NOT_ELIGIBLE', 'PENDING']
assert decisions['decisions'][0]['refund_shipping_fee_eur'] == 7.9
assert decisions['actions_executed'] == []

def source_receipts(record):
    return [{k: item.get(k) for k in ('path','start_line','end_line','decision','file_sha256','content_sha256','attempt')} for item in record.get('read_events', [])]

(EXTRACTED / 'orders.json').write_text(json.dumps(extracted, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(EXTRACTED / 'policy-decisions.json').write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
report = {
    'status': 'VERIFIED',
    'provider': 'ollama-cloud',
    'model_id': 'gemma4:31b',
    'fictional_demo': True,
    'profiles': json.loads((RUNS / 'profiles.json').read_text(encoding='utf-8')),
    'runs': [
        {'agent_id': extract_run['agent_id'], 'conversation_id': extract_run['conversation_id'], 'trace': extract_run['trace'], 'sources': source_receipts(extract_run), 'cloud_answer_citations_note': 'The extraction JSON omitted evidence_paths; the read receipt records the exact authorized CSV and its SHA-256.'},
        {'agent_id': policy_run['agent_id'], 'conversation_id': policy_run['conversation_id'], 'trace': policy_run['trace'], 'sources': source_receipts(policy_run)},
    ],
    'validation': {'four_rows': True, 'delay_hours': [32,24,48,None], 'decisions': [d['decision'] for d in decisions['decisions']], 'eligible_shipping_fee_eur': 7.9, 'actions_executed': []},
}
(EXTRACTED / 'run-evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

W, H = 1600, 900
NAVY = '#0b1524'; PANEL = '#122238'; BLUE = '#63a8ff'; WHITE = '#f2f6fb'; MUTED = '#b5c5d8'; GREEN = '#55d6a0'; AMBER = '#ffc766'
font_path = 'C:/Windows/Fonts/segoeui.ttf'
bold_path = 'C:/Windows/Fonts/segoeuib.ttf'
def font(size, bold=False):
    return ImageFont.truetype(bold_path if bold else font_path, size)

def base(title, subtitle, screenshot=None):
    im = Image.new('RGB', (W,H), NAVY)
    d = ImageDraw.Draw(im)
    if screenshot and screenshot.exists():
        src = Image.open(screenshot).convert('RGB').resize((W,H))
        im.paste(src)
        d.rectangle((0,0,W,126), fill=NAVY)
        d.rectangle((0,H-135,W,H), fill=NAVY)
    else:
        d.rectangle((0,0,W,16), fill=BLUE)
    d.text((76,34), title, font=font(38,True), fill=WHITE)
    d.text((78,84), subtitle, font=font(22), fill=MUTED)
    if screenshot:
        d.text((76,H-92), 'BRUMA MARKET · DEMO FICTICIA', font=font(19,True), fill=BLUE)
    return im, d

scenes = [
('Bruma Market: crear agentes y extraer datos', 'Tutorial práctico · dos perfiles · Ollama Cloud · dataset completamente sintético', 'Creamos dos agentes para una tienda ficticia, leemos pedidos con autorización limitada y contrastamos resultados con una política de ejemplo. Todo el dataset es sintético.'),
('1 · Diseña el agente extractor', 'Agent Builder · tipo RAG · salida JSON · sin herramientas de acción', 'En Agent Builder crea el perfil Extractor de pedidos. Define un prompt con campos cerrados, cálculo de retraso solo cuando existan ambas fechas, y valores nulos cuando falte información.'),
('2 · Diseña el revisor de política', 'Segundo perfil especializado · umbral estricto · cero acciones', 'Crea un segundo perfil para revisar elegibilidad. Especifica la regla de más de veinticuatro horas, los métodos incluidos, las citas de evidencia y que no ejecute reembolsos.'),
('3 · Prepara datos y reglas', 'orders.csv + policy.md + qa-expected.md · casos límite incluidos', 'Los cuatro pedidos incluyen un retraso de treinta y dos horas, uno de exactamente veinticuatro, un envío estándar y una entrega sin fecha. Así comprobamos límites y datos incompletos.'),
('4 · Ejecuta extracción en cloud', 'Gemma 4 · lectura de un solo archivo autorizada por turno', 'Selecciona el extractor en Chat, autoriza únicamente orders.csv y solicita el JSON. Ollama Cloud devuelve cuatro registros y el recibo local confirma la ruta y el hash del archivo leído.'),
('5 · Contrasta con la política', 'BM-1001 elegible: 7,90 € · sin reembolsos ejecutados', 'El revisor marca BM-1001 elegible por siete euros con noventa. BM-1002 no pasa porque son exactamente veinticuatro horas; BM-1003 usa envío estándar; BM-1004 queda pendiente.'),
('6 · Revisa trazas y límites', '2 perfiles · 2 respuestas Ollama · trazas local_only · 0 acciones', 'La aplicación guardó dos respuestas del proveedor Ollama y recibos ALLOW con hashes. Las trazas son solo locales; no hubo exportación a Jaeger ni acciones financieras.'),
('7 · Adáptalo a tu empresa', 'Sustituye fixtures · confirma políticas reales · añade validación humana', 'Para adaptarlo, reemplaza el CSV y la política ficticia por fuentes aprobadas, conserva el esquema JSON, añade reglas para datos faltantes y valida cada resultado antes de conectarlo a operaciones reales.'),
]
shots = [None, RUNS/'01-builder-1.png', RUNS/'01-builder-2.png', None, RUNS/'03-result-1.png', RUNS/'03-result-2.png', None, None]
for index, ((title, subtitle, narration), shot) in enumerate(zip(scenes, shots), 1):
    im,d = base(title, subtitle, shot)
    if index == 1:
        d.rounded_rectangle((76,220,800,535), radius=26, fill=PANEL, outline='#28415f', width=2)
        d.text((118,266),'2 AGENTES',font=font(27,True),fill=BLUE)
        d.text((118,325),'EXTRAER  →  EVALUAR',font=font(39,True),fill=WHITE)
        d.text((118,395),'DATOS FICTICIOS · OLLAMA CLOUD',font=font(22),fill=MUTED)
        d.text((118,459),'Del Agent Builder al JSON con evidencia',font=font(25),fill=GREEN)
    elif index == 4:
        d.rounded_rectangle((76,170,1524,735), radius=24, fill=PANEL, outline='#28415f', width=2)
        lines = ['BM-1001  express  7,90 €  retraso 32 h', 'BM-1002  express  5,95 €  retraso 24 h', 'BM-1003  estándar  0,00 € retraso 48 h', 'BM-1004  express  9,10 €  entrega pendiente']
        for n,line in enumerate(lines): d.text((125,230+n*82),line,font=font(30, n==0),fill=GREEN if n==0 else WHITE)
        d.text((125,610),'Política demo: EXPRESS y >24 h → devolver solo el coste del envío.',font=font(24),fill=AMBER)
    elif index == 5:
        d.rounded_rectangle((80,220,1520,710),radius=24,fill=PANEL,outline='#28415f',width=2)
        d.text((130,270),'4 PEDIDOS EXTRAÍDOS',font=font(33,True),fill=GREEN)
        d.text((130,355),'32 h  ·  24 h  ·  48 h  ·  sin fecha',font=font(34,True),fill=WHITE)
        d.text((130,460),'Lectura autorizada: orders.csv · líneas 1–5',font=font(25),fill=BLUE)
        d.text((130,520),'SHA-256 del contenido: '+extract_run['sources'][0]['content_sha256'][:24]+'…',font=font(20),fill=MUTED)
        d.text((130,605),'Nota: el modelo omitió las rutas en su JSON; el recibo sí acredita el archivo.',font=font(21),fill=AMBER)
    elif index == 6:
        table=[('BM-1001','ELEGIBLE','7,90 €'),('BM-1002','NO ELEGIBLE','—'),('BM-1003','NO ELEGIBLE','—'),('BM-1004','PENDIENTE','—')]
        d.rounded_rectangle((76,190,1524,705),radius=24,fill=PANEL,outline='#28415f',width=2)
        d.text((130,225),'PEDIDO',font=font(22,True),fill=BLUE);d.text((550,225),'RESULTADO',font=font(22,True),fill=BLUE);d.text((1160,225),'IMPORTE',font=font(22,True),fill=BLUE)
        for n,(oid,state,amt) in enumerate(table):
            yy=295+n*90; color=GREEN if n==0 else (AMBER if n==3 else WHITE)
            d.text((130,yy),oid,font=font(29,True),fill=WHITE); d.text((550,yy),state,font=font(28,True),fill=color);d.text((1160,yy),amt,font=font(28),fill=WHITE)
    elif index == 7:
        d.rounded_rectangle((76,190,1524,700),radius=24,fill=PANEL,outline='#28415f',width=2)
        d.text((124,235),'Extractor',font=font(24,True),fill=BLUE);d.text((430,235),extract_run['agent_id'],font=font(21),fill=WHITE)
        d.text((124,330),'Revisor',font=font(24,True),fill=BLUE);d.text((430,330),policy_run['agent_id'],font=font(21),fill=WHITE)
        d.text((124,425),'Trazas',font=font(24,True),fill=BLUE);d.text((430,425),extract_run['trace']['trace_id']+' · '+policy_run['trace']['trace_id'],font=font(21),fill=WHITE)
        d.text((124,520),'Fuentes',font=font(24,True),fill=BLUE);d.text((430,520),'3 archivos · 5 eventos ALLOW',font=font(24),fill=WHITE)
        d.text((124,615),'Acciones',font=font(24,True),fill=BLUE);d.text((430,615),'Ninguna ejecutada · Jaeger no exportado',font=font(24),fill=AMBER)
    elif index == 8:
        d.rounded_rectangle((76,205,1524,695),radius=24,fill=PANEL,outline='#28415f',width=2)
        tips=['1. Usa fuentes aprobadas y versionadas.', '2. Define salidas y datos faltantes explícitamente.', '3. Restringe lectura a rutas exactas.', '4. Valida contra QA antes de una aprobación humana.']
        for n,line in enumerate(tips): d.text((130,270+n*86),line,font=font(28),fill=WHITE)
    im.save(ASSETS / f'scene-{index:02}.png')

narration = [item[2] for item in scenes]
(ROOT/'narration.json').write_text(json.dumps(narration,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
ps = ROOT/'make-local-voice.ps1'
if not ps.exists():
    raise FileNotFoundError('make-local-voice.ps1 must be created before packaging')
subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ps)],check=True)

durations=[]
for i in range(1,len(scenes)+1):
    with wave.open(str(AUDIO/f'scene-{i:02}.wav'),'rb') as wav:
        durations.append(wav.getnframes()/wav.getframerate())
pad=0.35
concat=ROOT/'video-scenes.txt'
with concat.open('w',encoding='utf-8') as f:
    for i,duration in enumerate(durations,1):
        f.write(f"file '{(ASSETS/f'scene-{i:02}.png').as_posix()}'\n")
        f.write(f'duration {duration+pad:.3f}\n')
    f.write(f"file '{(ASSETS/f'scene-{len(scenes):02}.png').as_posix()}'\n")
audio_list=ROOT/'audio-scenes.txt'
silence=AUDIO/'silence.wav'
with wave.open(str(AUDIO/'scene-01.wav'),'rb') as sample:
    params=sample.getparams()
    silence_frames=b'\x00' * int(params.framerate*pad) * params.nchannels * params.sampwidth
with wave.open(str(silence),'wb') as wav:
    wav.setparams(params)
    wav.writeframes(silence_frames)
audio_parts=[]
for i in range(1,len(scenes)+1):
    audio_parts.append(f"file '{(AUDIO/f'scene-{i:02}.wav').as_posix()}'\n")
    if i<len(scenes): audio_parts.append(f"file '{silence.as_posix()}'\n")
audio_list.write_text(''.join(audio_parts),encoding='utf-8')
joined=ROOT/'narration.wav'
subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(audio_list),'-c:a','pcm_s16le',str(joined)],check=True)
video=ROOT/'tutorial-bruma-market.mp4'
target_duration=sum(durations)+pad*(len(scenes)-1)
subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-i',str(joined),'-vf','fps=25,format=yuv420p','-c:v','libx264','-preset','medium','-crf','21','-c:a','aac','-b:a','160k','-t',f'{target_duration:.3f}','-movflags','+faststart',str(video)],check=True)

def srt_time(sec):
    ms=round(sec*1000);h=ms//3600000;m=(ms%3600000)//60000;s=(ms%60000)//1000;rest=ms%1000
    return f'{h:02}:{m:02}:{s:02},{rest:03}'
blocks=[]; clock=0.0
for i,((_,__,line),duration) in enumerate(zip(scenes,durations),1):
    blocks.append(f'{i}\n{srt_time(clock)} --> {srt_time(clock+duration)}\n{line}\n')
    clock += duration+pad
(ROOT/'tutorial-bruma-market.srt').write_text('\n'.join(blocks),encoding='utf-8')

manifest={}
for p in sorted(ROOT.rglob('*')):
    if p.is_file() and p.name not in {'sha256-manifest.json'}:
        manifest[p.relative_to(ROOT).as_posix()]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(ROOT/'sha256-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'video':str(video),'seconds':round(sum(durations),2),'profiles':len(report['profiles']),'cloud_runs':2,'rows':len(orders),'decisions':[d['decision'] for d in decisions['decisions']]},ensure_ascii=False))
