import csv, hashlib, json, pathlib, re, subprocess, wave
from PIL import Image, ImageDraw, ImageFont

BASE=pathlib.Path(__file__).resolve().parent
OUTS=['tutorial-peluquerias','tutorial-kebap']
W,H=1600,900
NAVY='#0b1524'; PANEL='#122238'; BLUE='#63a8ff'; WHITE='#f2f6fb'; MUTED='#b5c5d8'; GREEN='#55d6a0'; AMBER='#ffc766'
FONT='C:/Windows/Fonts/segoeui.ttf'; BOLD='C:/Windows/Fonts/segoeuib.ttf'
def font(size,bold=False): return ImageFont.truetype(BOLD if bold else FONT,size)
def parse_answer(run):
    match=re.search(r'```(?:json)?\s*(.*?)\s*```',run['assistant_message'],re.S)
    if not match: raise ValueError('No JSON response block')
    return json.loads(match.group(1))
def hash_file(path): return hashlib.sha256(path.read_bytes()).hexdigest()

for slug in OUTS:
    root=BASE/slug; cfg=json.loads((root/'demo.json').read_text(encoding='utf-8'))
    runs=[json.loads((root/'cloud-runs'/f'run-{i}.json').read_text(encoding='utf-8')) for i in (1,2)]
    if any(r.get('source')!='ollama' or r.get('trace',{}).get('trace_state')!='local_only' for r in runs): raise ValueError('Expected confirmed Ollama runs with local traces')
    if any(not r.get('read_events') or any(e.get('decision')!='ALLOW' for e in r['read_events']) for r in runs): raise ValueError('Missing/denied read evidence')
    extracted=parse_answer(runs[0]); decisions=parse_answer(runs[1])
    group='appointments' if slug=='tutorial-peluquerias' else 'orders'
    primary=extracted[group]
    keys=[row['booking_id'] for row in primary]
    if keys!=cfg['expected']['primary_values']: raise ValueError(f'{slug}: extracted booking IDs differ from QA')
    review=decisions['decisions']
    if [d['decision'] for d in review]!=cfg['expected']['decisions']: raise ValueError(f'{slug}: decisions differ from QA')
    refund_key='refund_eur' if slug=='tutorial-peluquerias' else 'refund_delivery_fee_eur'
    refunds=[float(d[refund_key] or 0) for d in review]
    if refunds!=cfg['expected']['refunds_eur']: raise ValueError(f'{slug}: amounts differ from QA: {refunds}')
    if decisions.get('actions_executed')!=[]: raise ValueError('Unexpected executed action')
    if slug=='tutorial-kebap' and [o['delay_minutes'] for o in primary]!=cfg['expected']['delay_minutes']: raise ValueError('Kebap delay arithmetic mismatch')
    (root/'extracted').mkdir(exist_ok=True); (root/'slides').mkdir(exist_ok=True); (root/'audio').mkdir(exist_ok=True)
    (root/'extracted'/f'{group}.json').write_text(json.dumps(extracted,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (root/'extracted'/'decisions.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    receipts=[]
    for run in runs:
        receipts.append({'agent_id':run['agent_id'],'conversation_id':run['conversation_id'],'trace':run['trace'],'sources':[{k:e.get(k) for k in ('path','start_line','end_line','decision','file_sha256','content_sha256','attempt')} for e in run.get('read_events',[])]})
    (root/'extracted'/'run-evidence.json').write_text(json.dumps({'status':'VERIFIED','fictional_demo':True,'provider':'ollama-cloud','model_id':'gemma4:31b','runs':receipts,'validation':{'ids':keys,'decisions':[d['decision'] for d in review],refund_key:refunds,'actions_executed':[]}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    if slug=='tutorial-peluquerias':
        title='Corte y Tono'; section='cadena ficticia de peluquerías'; input_label='appointments.csv'
        narrations=[
            'Tutorial de Corte y Tono, una cadena ficticia de peluquerías. Crearemos agentes para extraer reservas y evaluar una política de depósitos con datos completamente sintéticos.',
            'En Agent Builder creamos el extractor. Su prompt limita la lectura a ficheros autorizados, define los campos JSON y evita solicitar nombres u otros datos personales.',
            'El segundo perfil revisa depósitos. La regla distingue cancelaciones con menos de doce horas, cancelaciones más tempranas, citas completadas y ausencias.',
            'El conjunto incluye dos sucursales y cuatro situaciones: servicio completado, cancelación con cuatro horas, cancelación con veinticuatro horas y ausencia.',
            'El extractor devolvió cuatro reservas con sucursal, servicio, estado, precio y depósito. El recibo del runtime confirma qué CSV leyó y su huella.',
            'El revisor clasificó S-501 sin devolución; S-502 con quince euros de devolución; S-503 con devolución íntegra de veinte euros; y S-504 con el depósito retenido.',
            'El chat terminó a través de Ollama Cloud. El runtime guardó trazas local_only y recibos ALLOW para los datos. No se ejecutó ninguna devolución.',
            'Para adaptar este patrón a una cadena real, conecta fuentes aprobadas, versiona la política, revisa citas y datos incompletos, y exige validación humana antes de pagos.'
        ]
        rows=[('S-501','Completada','0,00 €'),('S-502','Cancelada 4 h antes','15,00 €'),('S-503','Cancelada 24 h antes','20,00 €'),('S-504','No-show · depósito retenido','0,00 €')]
        note='Extractor: el modelo dejó vacía la lista evidence_paths; el recibo del runtime acredita appointments.csv y su SHA-256.'
    else:
        title='Kebap Ruta 7'; section='cadena ficticia de kebaps y reparto'; input_label='orders.csv'
        narrations=[
            'Tutorial de Kebap Ruta 7, una cadena ficticia. Crearemos perfiles para extraer pedidos y revisar el tiempo de reparto usando solo datos sintéticos.',
            'En Agent Builder configuramos un extractor que devuelve los campos del pedido y calcula minutos tarde únicamente cuando constan ambas marcas horarias.',
            'El perfil revisor aplica un SLA simple: reparto con más de treinta minutos tarde puede optar a recuperar la tarifa de envío; recogida no aplica.',
            'El CSV cubre cuarenta y dos minutos tarde, treinta minutos exactos, una recogida y un pedido sin hora de finalización.',
            'El extractor calculó cuarenta y dos, treinta y sesenta y cinco minutos; para el pedido abierto devolvió null. El recibo enlaza el CSV y su huella.',
            'El revisor marcó K-901 elegible por 2,50 euros. K-902 y K-903 no son elegibles; K-904 queda pendiente. No ejecutó ninguna acción.',
            'Las respuestas llegaron por Ollama Cloud, con eventos de lectura ALLOW y trazas local_only guardadas en el proyecto.',
            'En una empresa real, sustituye este fixture por datos aprobados, fija los límites del SLA, contrasta resultados con QA y mantén revisión humana antes de reembolsar.'
        ]
        rows=[('K-901','42 min · delivery','Elegible · 2,50 €'),('K-902','30 min exactos','No elegible'),('K-903','Pickup','No elegible'),('K-904','Sin finalización','Pendiente')]
        note='Extractor: evidence_paths salió vacío; el recibo del runtime acredita orders.csv y su SHA-256.'

    cards=[
        (f'{title}: agentes y datos extraídos',f'{section} · Ollama Cloud · dataset sintético'),
        ('1 · Crear el extractor','Agent Builder · campos JSON · acceso limitado'),
        ('2 · Crear el revisor','Política y QA · casos límite · sin acciones'),
        ('3 · Preparar el dataset','CSV ficticio · cuatro registros de muestra'),
        ('4 · Extraer datos','Respuesta del modelo y recibo de lectura'),
        ('5 · Revisar resultados','Decisiones contrastadas contra QA'),
        ('6 · Comprobar evidencias','Trazas locales · hashes · acciones cero'),
        ('7 · Adaptar a tu negocio','Fuentes aprobadas · reglas claras · revisión humana'),
    ]
    shots=[None,root/'cloud-runs'/'builder-extractor.png',root/'cloud-runs'/'builder-reviewer.png',None,None,root/'cloud-runs'/'result-1.png',root/'cloud-runs'/'result-2.png',None]
    for ix,((head,sub),narration,shot) in enumerate(zip(cards,narrations,shots),1):
        im=Image.new('RGB',(W,H),NAVY); d=ImageDraw.Draw(im)
        if shot and shot.exists():
            im.paste(Image.open(shot).convert('RGB').resize((W,H))); d.rectangle((0,0,W,125),fill=NAVY);d.rectangle((0,H-125,W,H),fill=NAVY)
        d.text((72,32),head,font=font(37,True),fill=WHITE); d.text((74,82),sub,font=font(21),fill=MUTED)
        if ix==1:
            d.rounded_rectangle((75,235,860,590),radius=28,fill=PANEL,outline='#28415f',width=2)
            d.text((125,300),'2 AGENTES',font=font(28,True),fill=BLUE);d.text((125,370),'EXTRAER  →  EVALUAR',font=font(38,True),fill=WHITE);d.text((125,460),'FICTICIO · OLLAMA CLOUD',font=font(23),fill=GREEN)
        elif ix==4:
            d.rounded_rectangle((76,170,1524,730),radius=25,fill=PANEL,outline='#28415f',width=2)
            for i,row in enumerate(rows): d.text((125,235+i*94),'  ·  '.join(row),font=font(29,i==0),fill=GREEN if i==0 else WHITE)
        elif ix==5:
            d.rounded_rectangle((76,180,1524,690),radius=25,fill=PANEL,outline='#28415f',width=2)
            d.text((124,230),'4 FILAS EXTRAÍDAS · '+input_label,font=font(28,True),fill=GREEN)
            for i,record in enumerate(primary):
                visible=' · '.join(str(record.get(k,'')) for k in ('booking_id','branch','status'))
                if slug=='tutorial-kebap':
                    minutes=record.get('delay_minutes')
                    visible+=' · '+(str(minutes)+' min' if minutes is not None else 'pendiente (null)')
                d.text((126,300+i*72),visible,font=font(24),fill=WHITE)
            d.text((126,610),note,font=font(17),fill=AMBER)
        elif ix==6:
            d.rounded_rectangle((76,180,1524,690),radius=25,fill=PANEL,outline='#28415f',width=2)
            for i,(item,result,value) in enumerate(rows):
                y=240+i*95; d.text((120,y),item,font=font(27,True),fill=WHITE);d.text((375,y),result,font=font(25),fill=BLUE);d.text((1100,y),value,font=font(25,True),fill=GREEN if i==0 else WHITE)
        elif ix==7:
            d.rounded_rectangle((76,190,1524,680),radius=25,fill=PANEL,outline='#28415f',width=2)
            d.text((120,230),'Proveedor: ollama-cloud · gemma4:31b',font=font(24),fill=WHITE)
            d.text((120,300),'Trazas: '+runs[0]['trace']['trace_id']+' / '+runs[1]['trace']['trace_id'],font=font(22),fill=BLUE)
            d.text((120,370),'Eventos de lectura: '+str(sum(len(r.get('read_events',[])) for r in runs))+' ALLOW · sin denegaciones',font=font(23),fill=GREEN)
            d.text((120,440),'Salidas contrastadas con 4 casos QA',font=font(23),fill=WHITE)
            d.text((120,510),'Trazas local_only · acciones ejecutadas: 0',font=font(23),fill=AMBER)
            d.text((120,585),'Hash del CSV: '+runs[0]['sources'][0]['file_sha256'][:32]+'…',font=font(18),fill=MUTED)
        elif ix==8:
            d.rounded_rectangle((76,200,1524,695),radius=25,fill=PANEL,outline='#28415f',width=2)
            for i,line in enumerate(['1. Cambia los fixtures por fuentes aprobadas.','2. Expresa reglas y umbrales sin ambigüedad.','3. Autoriza rutas mínimas y revisa recibos.','4. Contrasta con QA y solicita aprobación humana.']):d.text((125,260+i*88),line,font=font(27),fill=WHITE)
        d.text((72,H-72),'DEMO SINTÉTICA · SIN CLIENTES REALES NI ACCIONES FINANCIERAS',font=font(18,True),fill=BLUE)
        im.save(root/'slides'/f'scene-{ix:02}.png')
    (root/'narration.json').write_text(json.dumps(narrations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (root/'make-local-voice.ps1').write_text("$ErrorActionPreference='Stop'\nAdd-Type -AssemblyName System.Speech\n$root=Split-Path -Parent $MyInvocation.MyCommand.Path\n$audio=Join-Path $root 'audio'\nNew-Item -ItemType Directory -Force -Path $audio | Out-Null\n$scenes=Get-Content (Join-Path $root 'narration.json') -Raw | ConvertFrom-Json\n$s=New-Object System.Speech.Synthesis.SpeechSynthesizer\n$s.SelectVoice('Microsoft Helena Desktop'); $s.Rate=0; $s.Volume=92\nfor($i=0;$i -lt $scenes.Count;$i++){ $name='scene-{0:D2}.wav' -f ($i+1); $s.SetOutputToWaveFile((Join-Path $audio $name)); $s.Speak([string]$scenes[$i]); $s.SetOutputToNull() }\n$s.Dispose()\n",encoding='utf-8')
    subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'make-local-voice.ps1')],check=True)
    durations=[]
    for i in range(1,9):
        with wave.open(str(root/'audio'/f'scene-{i:02}.wav'),'rb') as wav: durations.append(wav.getnframes()/wav.getframerate())
    pad=.35; silence_path=root/'audio'/'silence.wav'
    with wave.open(str(root/'audio'/'scene-01.wav'),'rb') as w: params=w.getparams();silence=b'\0'*int(params.framerate*pad)*params.nchannels*params.sampwidth
    with wave.open(str(silence_path),'wb') as w:w.setparams(params);w.writeframes(silence)
    vidlist=[]; audlist=[]
    for i in range(1,9):
        vidlist.extend([f"file '{(root/'slides'/f'scene-{i:02}.png').as_posix()}'\n",f'duration {durations[i-1]+pad:.3f}\n'])
        audlist.append(f"file '{(root/'audio'/f'scene-{i:02}.wav').as_posix()}'\n")
        if i<8:audlist.append(f"file '{silence_path.as_posix()}'\n")
    vidlist.append(f"file '{(root/'slides'/'scene-08.png').as_posix()}'\n")
    (root/'video-scenes.txt').write_text(''.join(vidlist),encoding='utf-8');(root/'audio-scenes.txt').write_text(''.join(audlist),encoding='utf-8')
    audio=root/'narration.wav';video=root/f'{slug}.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(root/'audio-scenes.txt'),'-c:a','pcm_s16le',str(audio)],check=True)
    total=sum(durations)+pad*7
    subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(root/'video-scenes.txt'),'-i',str(audio),'-vf','fps=25,format=yuv420p','-c:v','libx264','-preset','medium','-crf','21','-c:a','aac','-b:a','160k','-t',f'{total:.3f}','-movflags','+faststart',str(video)],check=True)
    def t(sec):
        ms=round(sec*1000);return f'{ms//3600000:02}:{(ms%3600000)//60000:02}:{(ms%60000)//1000:02},{ms%1000:03}'
    cursor=0;blocks=[]
    for i,(line,dur) in enumerate(zip(narrations,durations),1):blocks.append(f'{i}\n{t(cursor)} --> {t(cursor+dur)}\n{line}\n');cursor+=dur+pad
    (root/f'{slug}.srt').write_text('\n'.join(blocks),encoding='utf-8')
    sha_manifest={p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':hash_file(p)} for p in sorted(root.rglob('*')) if p.is_file() and p.name!='sha256-manifest.json'}
    (root/'sha256-manifest.json').write_text(json.dumps(sha_manifest,indent=2)+'\n',encoding='utf-8')
    readme=f'''# Tutorial demo: {title}\n\nVideo en español: [`{slug}.mp4`]({slug}.mp4). Subtítulos: [`{slug}.srt`]({slug}.srt).\n\n> Empresa, sucursales, registros, reglas y QA ficticios. Se usaron dos perfiles guardados en la aplicación y dos turnos de agente mediante Ollama Cloud (`gemma4:31b`). No hay datos de clientes reales ni se ejecutaron pagos o reembolsos.\n\n## Recorrido\n\n1. En Agent Builder crea el extractor y el revisor descritos en [`cloud-runs/profiles.json`](cloud-runs/profiles.json). El perfil hereda el modelo del proveedor configurado.\n2. En Chat elige el extractor y autoriza solo `inputs/{input_label}` para ese mensaje. Pide el JSON con campos explícitos y nulos para lo desconocido.\n3. Elige el revisor; autoriza el CSV, `inputs/policy.md` y `inputs/qa-expected.md`. Pide decisiones por registro, cita de rutas/líneas y confirma que no se ejecutaron acciones.\n4. Compara la salida y los cuatro casos con los recibos, trazas locales y QA.\n\n## Fixtures y resultados\n\nEntradas: [`inputs/{input_label}`](inputs/{input_label}), [`inputs/policy.md`](inputs/policy.md), [`inputs/qa-expected.md`](inputs/qa-expected.md). La extracción JSON está en [`extracted/{group}.json`](extracted/{group}.json); el análisis, en [`extracted/decisions.json`](extracted/decisions.json). Las respuestas originales y perfiles se conservan en `cloud-runs/`; evidencia y hashes, en [`extracted/run-evidence.json`](extracted/run-evidence.json).\n\n| ID | Resultado | Valor calculado |\n|---|---|---|\n'''+''.join(f'| {a} | {b} | {c} |\n' for a,b,c in rows)+f'''\nTodos los eventos de lectura registrados fueron ALLOW. Las trazas de esta ejecución son `local_only`, no exportadas a Jaeger/cloud. El extractor omitió `evidence_paths` en su JSON, aunque los recibos locales enlazan archivos y hashes; se explica en el video.\n\n## Alcance\n\nTipo de perfil `RAG` no significa que se haya creado un índice vectorial del negocio: este tutorial lee ficheros autorizados por mensaje. Los resultados solo validan los fixtures, no una política comercial real. Antes de producción deben verificarse las reglas con el negocio y revisarse manualmente antes de actuar.\n'''
    (root/'README.md').write_text(readme,encoding='utf-8')
    sha_manifest={p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':hash_file(p)} for p in sorted(root.rglob('*')) if p.is_file() and p.name!='sha256-manifest.json'}
    (root/'sha256-manifest.json').write_text(json.dumps(sha_manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'video':str(video),'duration_seconds':round(total,1),'validated_decisions':[d['decision'] for d in review],'read_events':sum(len(r.get('read_events',[])) for r in runs)},ensure_ascii=False))
