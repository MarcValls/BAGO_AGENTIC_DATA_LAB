#!/usr/bin/env python3
"""Manual BAGO Agentic Data Lab: lectura de ejecución. Fuente original preservada."""
import os
from pathlib import Path
from html import escape
from weasyprint import HTML
from PIL import Image

ROOT=Path(__file__).resolve().parent
OUT=ROOT
ASSETS=ROOT / 'MANUAL_PARA_DUMMIES_assets'

# Recortes editoriales de las cuatro capturas auténticas.
# Los originales se conservan sin manipulación en assets/; ningún dibujo sustituye una captura.
# Todos los parámetros de recorte están en píxeles del PNG de origen.
CROPS = {
    'overview': (195, 340, 1330, 900),
    'trace': (100, 285, 665, 503),
    'actions': (218, 1115, 1305, 1585),
    'jaeger': (0, 145, 1020, 570),
}
TITLES = {
    'overview': 'DECISION · RESPUESTA Y REFERENCIAS',
    'trace': 'TRACE · EVENTOS EN SECUENCIA',
    'actions': 'ACTIONS · RESULTADO Y RECIBO',
    'jaeger': 'JAEGER · TIMELINE DE SPANS',
}
def diagram(screen, body):
    image=ASSETS/f'{screen}.png'
    if not image.is_file():
        raise FileNotFoundError(f'Captura original obligatoria ausente: {image}')
    with Image.open(image) as src:
        box = CROPS[screen]
        if box[2]>src.width or box[3]>src.height:
            raise ValueError(f'El recorte {screen} {box} excede {src.size}')
        preview=src.crop(box)
        dst=OUT/f'{screen}_recorte.png'
        preview.save(dst,optimize=True)
    return (f'<figure class="real-figure figure-{screen}">'
            f'<div class="capture-tag"><b>CAPTURA ORIGINAL · RECORTE AMPLIADO</b><span>{TITLES[screen]}</span></div>'
            f'<img src="{screen}_recorte.png" alt="Recorte auténtico: {escape(screen)}">'
            f'</figure>')

def p(text,cls=''):
    return f'<p class="{cls}">{text}</p>'

def bullets(items, classes=''):
    return '<ul class="bullets '+classes+'">'+''.join(f'<li>{x}</li>' for x in items)+'</ul>'

overview = diagram('overview', '''
    <div class="tab-row"><b>DECISION</b><span>TRACE</span><span>ACTIONS</span><span>JAEGER</span></div>
    <div class="screen-body">
      <div class="screen-topline"><span class="smallhint">RUN ID</span><span class="id-line">Identificador de la ejecución</span></div>
      <div class="stat-row"><div><small>EVIDENCIA</small><b>Referencias</b></div><div><small>CLAIMS</small><b>Not provided</b></div><div><small>TRAZA</small><b>Eventos</b></div><div><small>ACCIONES</small><b>Registro</b></div></div>
      <div class="screen-two"><div class="whitebox"><strong>Respuesta</strong><span>Texto producido por la ejecución</span><span class="placeholder-line"></span><span class="placeholder-line short"></span></div><div class="whitebox"><strong>Evidencia recuperada</strong><span>Referencia consultada ≠ afirmación demostrada</span><span class="placeholder-line"></span></div></div>
    </div>''')

trace = diagram('trace', '''
    <div class="tab-row"><span>DECISION</span><b>TRACE</b><span>ACTIONS</span><span>JAEGER</span></div>
    <div class="trace-screen"><div class="trace-tick"><em>01</em><div><b>Evento de LocalTrace</b><small>Secuencia cronológica</small></div></div><div class="trace-tick"><em>02</em><div><b>Evento siguiente</b><small>Relación padre solo si la fuente la registra</small></div></div><div class="trace-tick"><em>03</em><div><b>Otro evento</b><small>El orden no demuestra por sí mismo causalidad</small></div></div></div>
''')

actions = diagram('actions', '''
    <div class="tab-row"><span>DECISION</span><span>TRACE</span><b>ACTIONS</b><span>JAEGER</span></div>
    <div class="action-screen"><div class="status-sample"><span>Propuesta</span><b>≠ Autorización</b></div><div class="status-sample"><span>Autorización</span><b>≠ Ejecución</b></div><div class="status-sample highlight"><span>Recibo del mismo run</span><b>Verificación</b></div></div>
''')

jaeger = diagram('jaeger', '''
    <div class="jaeger-header"><b>Jaeger · Lookup by Trace ID</b><span>bago-agentic-data-lab · agent.run</span></div>
    <svg class="jaeger-drawing" viewBox="0 0 650 160" role="img" aria-label="Representación conceptual de relaciones entre spans">
      <path d="M100 80 H205 M205 80 V30 H310 M205 80 H310 M205 80 V132 H310 M423 30 H528 M423 80 H528 M423 132 H528" fill="none" stroke="#92b1c3" stroke-width="3"/>
      <rect x="15" y="58" width="125" height="43" rx="6" fill="#16394f"/><text x="77" y="84" font-size="13" fill="#fff" text-anchor="middle" font-family="sans-serif">agent.run</text>
      <rect x="310" y="11" width="113" height="37" rx="5" fill="#e6f0f4" stroke="#b9d0da"/><text x="366" y="35" fill="#294a5d" font-size="13" text-anchor="middle" font-family="sans-serif">span</text>
      <rect x="310" y="62" width="113" height="37" rx="5" fill="#e6f0f4" stroke="#b9d0da"/><text x="366" y="86" fill="#294a5d" font-size="13" text-anchor="middle" font-family="sans-serif">span</text>
      <rect x="310" y="113" width="113" height="37" rx="5" fill="#e6f0f4" stroke="#b9d0da"/><text x="366" y="137" fill="#294a5d" font-size="13" text-anchor="middle" font-family="sans-serif">span</text>
      <circle cx="545" cy="30" r="12" fill="#c7dbe3"/><circle cx="545" cy="80" r="12" fill="#c7dbe3"/><circle cx="545" cy="132" r="12" fill="#c7dbe3"/>
    </svg>
    <div class="jaeger-info"><div><b>15</b><span>spans enviados</span></div><div><b>15</b><span>spans observados</span></div></div>
''')

pages=[]

pages.append('''<article class="leaf cover">
  <div class="cover-rail"></div>
  <div class="brand">BAGO <span>·</span> AGENTIC DATA LAB <small>· GUÍA DE USO</small></div>
  <div class="cover-middle">
    <div class="cover-label">MANUAL PARA DUMMIES</div>
    <div class="cover-class">CLASE 01</div>
    <h1>Cómo leer<br><i>una ejecución</i></h1>
    <div class="cover-line"></div>
    <p>¿Cómo sé qué hizo un agente y qué evidencia respalda su respuesta?</p>
    <p class="cover-sub">Una ruta visual: decisión, traza, acción y recibo.</p>
  </div>
  <div class="cover-number">01</div>
  <div class="cover-footer"><div>DOCUMENTACIÓN DE PRODUCTO<br>Clase 01</div><div>Marc Valls</div></div>
</article>''')

pages.append('''<article class="leaf intro">
  <div class="eyebrow">CLASE 01 · ANTES DE EMPEZAR</div>
  <h2 class="page-title">La pregunta<br>de entrada</h2>
  <div class="qbox"><div class="micro">PREGUNTA DE ENTRADA</div><p>¿Cómo sé qué hizo un agente y qué evidencia respalda su respuesta?</p><div class="qsub">Una ruta visual: decisión, traza, acción y recibo.</div></div>
  <p class="lead">En esta clase aprenderás a reconocer los identificadores, seguir los eventos y comprobar si una acción tiene un recibo válido.</p>
  <div class="flow-label">RUTA DE LECTURA</div>
  <table class="route"><tr><td><b>01</b><strong>DECISION</strong><small>Respuesta</small></td><td><b>02</b><strong>TRACE</strong><small>Eventos</small></td><td><b>03</b><strong>ACTIONS</strong><small>Recibos</small></td><td><b>04</b><strong>JAEGER</strong><small>Spans</small></td></tr></table>
  <h3>Antes de empezar</h3>
  <table class="prep-table"><tr><td><em>01</em><span>Identifica el Run ID de la ejecución.</span></td><td><em>02</em><span>Distingue respuesta, evidencia y claims.</span></td></tr><tr><td><em>03</em><span>Lee los eventos de Trace en orden.</span></td><td><em>04</em><span>Comprueba autorización, ejecución y recibo.</span></td></tr></table>
  <h3>Abre estas ubicaciones</h3>
  <div class="locations">
    <div><small>REPOSITORIO</small><span class="repo-path">C:&#92;Users&#92;AMTEC_Terminal_1º&#92;BAGO_AGENTIC_DATA_LAB</span></div>
    <div><small>DECISION INSPECTOR</small><a href="http://127.0.0.1:8082">http://127.0.0.1:8082</a></div>
    <div><small>JAEGER LOCAL</small><a href="http://localhost:16686">http://localhost:16686</a></div>
    <div><small>DOCUMENTACIÓN</small><span>docs/decision-inspector dentro del repositorio</span></div>
  </div>
  <div class="side-note"><b>Cómo usar este manual.</b> Lee, observa, practica y verifica antes de avanzar.</div>
  <div class="side-note warning"><b>Aviso.</b> La interfaz es de solo lectura: no aprueba ni ejecuta acciones.</div>
</article>''')

pages.append(f'''<article class="leaf lesson lesson-decision">
  <div class="eyebrow">LECCIÓN 01 <span>·</span> OBSERVAR</div>
  <h2 class="page-title">Leer la<br>decisión</h2>
  <p class="lead">Abre <a href="http://127.0.0.1:8082">http://127.0.0.1:8082</a>. La primera vista resume una ejecución real. Anota el Run ID para saber qué ejecución estás mirando.</p>
  <p>Los contadores muestran cuánta evidencia recuperó la ejecución, si hay claims estructurados, cuántos eventos de traza llegaron y cuántas acciones aparecen.</p>
  {overview}
  <p class="caption">Vista Decision: captura real, recortada al resumen de ejecución, evidencias y claims disponibles.</p>
  <h3>Cómo interpretar esta pantalla</h3>
  <div class="quad-list">
    <div><b>01</b><p>La respuesta es el texto producido por la ejecución.</p></div>
    <div><b>02</b><p>Una referencia recuperada es un documento consultado; no demuestra por sí sola que apoye una frase concreta.</p></div>
    <div><b>03</b><p>“Structured claims: Not provided” significa que la fuente no separó la respuesta en afirmaciones verificables.</p></div>
    <div><b>04</b><p>Si falta el vínculo claim→evidencia, el Inspector lo deja indicado. No inventa la relación.</p></div>
  </div>
  <div class="worksheet"><div class="ws-head"><b>PRÁCTICA DEL ALUMNO</b><span>OBSERVA · NO DEDUZCAS</span></div><div class="ws-row"><label>Run ID</label><i></i></div><div class="ws-row"><label>Referencias recuperadas</label><i></i></div><div class="ws-row"><label>¿Claims estructurados?</label><i></i></div><div class="ws-row"><label>¿Qué vínculo claim→evidencia aparece?</label><i></i></div></div>
</article>''')

pages.append(f'''<article class="leaf lesson lesson-trace">
  <div class="eyebrow">LECCIÓN 02 <span>·</span> SEGUIR</div>
  <h2 class="page-title">Leer la<br>cronología</h2>
  <p class="lead">Selecciona Trace en la barra superior. Cada tarjeta representa un evento de LocalTrace. El número de secuencia indica el orden. La relación padre solo expresa causalidad cuando la fuente la registró.</p>
  {trace}
  <p class="caption">Vista Trace: primeros eventos de la cronología LocalTrace, recorte de la captura auténtica.</p>
  <h3>Tres identificadores</h3>
  <table class="ids"><tr><th>run_id</th><td>identifica la ejecución del agente.</td></tr><tr><th>LocalTrace trace_id</th><td>identifica el registro local de eventos.</td></tr><tr><th>Jaeger trace ID</th><td>identifica la traza que Jaeger indexó. En esta validación:<br><code class="breakcode">04b58bb123bb6cc94a8cc0d60c7145ae</code>.</td></tr></table>
  <div class="callout caution"><div class="callout-title">AVISO · NO CONFUNDIR IDENTIFICADORES</div><p>La pantalla dice que no hay correlación directa con Jaeger en este payload. El grafo existe, pero el Inspector no tiene un enlace automático entre ambos IDs.</p></div>
  <div class="worksheet"><div class="ws-head"><b>REGISTRA TUS IDENTIFICADORES</b><span>EVITA SUPONER CORRELACIONES</span></div><div class="ws-row"><label>Run ID</label><i></i></div><div class="ws-row"><label>LocalTrace trace_id</label><i></i></div><div class="ws-row"><label>Jaeger trace ID</label><i></i></div></div>
</article>''')

pages.append(f'''<article class="leaf lesson lesson-actions">
  <div class="eyebrow">LECCIÓN 03 <span>·</span> COMPROBAR</div>
  <h2 class="page-title">Revisar acciones<br>y recibos</h2>
  <p class="lead">Selecciona Actions. Lee los estados de arriba abajo: capacidad, elegibilidad, autorización, disponibilidad, ejecución y recibo. Cada uno responde a una pregunta distinta.</p>
  <div class="stages"><span>CAPACIDAD</span><i>›</i><span>ELEGIBILIDAD</span><i>›</i><span>AUTORIZACIÓN</span><i>›</i><span>DISPONIBILIDAD</span><i>›</i><span>EJECUCIÓN</span><i>›</i><span>RECIBO</span></div>
  {actions}
  <p class="caption">Vista Actions: recorte real del bloque de ejecución y recibo; el original conserva la escalera de autorización completa.</p>
  <h3>Regla práctica</h3>
  <div class="line-rule"><b>01</b><p>Una propuesta dice qué se podría hacer. No significa que esté autorizado.</p></div>
  <div class="line-rule"><b>02</b><p>Una autorización no demuestra que la acción se ejecutó.</p></div>
  <div class="line-rule"><b>03</b><p>Para confirmar ejecución hace falta un recibo asociado a la misma ejecución.</p></div>
  <div class="line-rule"><b>04</b><p>Si al recibo le falta run_id o pertenece a otro run, no se acepta como éxito verificado.</p></div>
  <div class="callout red"><div class="callout-title">EJEMPLO</div><p>Ejemplo: “SUCCESS” sin un recibo válido se muestra como “unverified”.</p></div>
  <div class="worksheet"><div class="ws-head"><b>COMPROBACIÓN DEL RECIBO</b><span>EL RECIBO MANDA</span></div><div class="ws-row"><label>run_id de la ejecución</label><i></i></div><div class="ws-row"><label>run_id del recibo</label><i></i></div><div class="ws-choices">¿Coinciden? <span>□ Sí</span><span>□ No</span><span>□ No consta</span></div></div>
</article>''')

pages.append(f'''<article class="leaf lesson lesson-jaeger">
  <div class="eyebrow">LECCIÓN 04 <span>·</span> LOCALIZAR</div>
  <h2 class="page-title">Encontrar el grafo<br>en Jaeger</h2>
  <p class="lead">Abre <a href="http://localhost:16686">http://localhost:16686</a>. Es otra pantalla: busca y dibuja los spans que recibió el colector local.</p>
  <div class="search-options"><div><small>BÚSQUEDA DIRECTA</small><p>Búsqueda directa: pega <code class="breakcode">04b58bb123bb6cc94a8cc0d60c7145ae</code> en “Lookup by Trace ID”.</p></div><div><small>BÚSQUEDA POR SERVICIO</small><p>Búsqueda por servicio: elige <code>bago-agentic-data-lab</code>, selecciona <code>agent.run</code> y pulsa Find Traces.</p></div></div>
  {jaeger}
  <p class="caption">Captura real de la traza local en Jaeger (recorte de la línea temporal). La imagen completa se conserva en el paquete.</p>
  <h3>Qué demuestra este grafo</h3>
  <div class="quad-list">
    <div><b>01</b><p>Jaeger encontró la traza local.</p></div>
    <div><b>02</b><p>Se enviaron 15 spans y Jaeger observó 15.</p></div>
    <div><b>03</b><p>Los nodos son spans; las flechas muestran su relación en la traza.</p></div>
    <div><b>04</b><p>Esto no demuestra envío a AWS ni a un colector remoto.</p></div>
  </div>
  <div class="worksheet"><div class="ws-head"><b>LOCALIZA LA TRAZA</b><span>DATOS QUE OBSERVAS</span></div><div class="ws-row"><label>Trace ID buscado</label><i></i></div><div class="ws-row"><label>Servicio / operación</label><i></i></div><div class="ws-row"><label>Spans encontrados</label><i></i></div></div>
</article>''')

pages.append('''<article class="leaf lesson lesson-practice">
  <div class="eyebrow">LECCIÓN 05 <span>·</span> PRACTICAR</div>
  <h2 class="page-title">Repetir el<br>recorrido</h2>
  <h3>La demostración registrada</h3>
  <div class="demo"><div class="demo-upper"><span>LOCALTRACE</span><span>OTLP/HTTP</span><span>JAEGER</span></div><div class="demo-ids"><div><small>LocalTrace</small><b>trace-5b385699ffda0529</b></div><span class="arr">→</span><div><small>Jaeger</small><b>04b58bb123bb6cc94a8cc0d60c7145ae</b></div></div><div class="demo-counter">15 enviados <span>·</span> 15 observados</div></div>
  <p>LocalTrace trace-5b385699ffda0529 se proyectó por OTLP/HTTP a Jaeger. Jaeger encontró la traza 04b58bb123bb6cc94a8cc0d60c7145ae y observó sus 15 spans. El informe está en <code>evidence/l15_otel_jaeger_live.md</code>.</p>
  <h3>Repite la lectura</h3>
  <div class="steps">
    <div><span>01</span><p>Abre el Inspector y anota Run ID.</p></div>
    <div><span>02</span><p>Mira los contadores. Si claims dice “Not provided”, no hay claims estructurados.</p></div>
    <div><span>03</span><p>Abre Trace; anota trace_id y revisa el orden y los avisos.</p></div>
    <div><span>04</span><p>Abre Actions; comprueba el recibo y su run_id.</p></div>
    <div><span>05</span><p>Abre Jaeger y busca el ID de Jaeger del informe. Una ejecución nueva tendrá IDs distintos.</p></div>
    <div><span>06</span><p>Compara las operaciones y los spans encontrados.</p></div>
  </div>
  <div class="callout key"><div class="callout-title">CLAVE</div><p>Conclusión correcta: “Jaeger recibió y mostró esta traza local”. No afirmes que el Inspector enlaza automáticamente con Jaeger o que la traza llegó a AWS.</p></div>
  <div class="worksheet"><div class="ws-head"><b>RESULTADO DE MI REPETICIÓN</b><span>ANOTA LO QUE HAS COMPROBADO</span></div><div class="ws-row"><label>¿Encontré la traza?</label><i></i></div><div class="ws-row"><label>¿Cuántos spans observé?</label><i></i></div><div class="ws-row"><label>¿Qué puedo afirmar?</label><i></i></div></div>
</article>''')

pages.append('''<article class="leaf support">
  <div class="eyebrow">GUÍA DE APOYO <span>·</span> RESOLVER</div>
  <h2 class="page-title">Si una página<br>no abre</h2>
  <div class="rule-top"><span>01 / SERVICIO DE INSPECCIÓN</span></div>
  <h3>Decision Inspector</h3>
  <p>Desde PowerShell, comprueba el servicio:</p>
  <div class="code"><div class="code-head">POWERSHELL · COMPROBACIÓN</div><pre>Invoke-RestMethod http://127.0.0.1:8082/api/health</pre></div>
  <p>La respuesta esperada contiene status “ok”. Si el servicio está detenido y sus dependencias instaladas, desde la raíz del repo:</p>
  <div class="code"><div class="code-head">POWERSHELL · ARRANQUE LOCAL</div><pre>python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8082</pre></div>
  <div class="rule-top"><span>02 / VISUALIZACIÓN DE TRAZAS</span></div>
  <h3>Jaeger</h3>
  <p>Desde la raíz del repo, inicia Jaeger local con Docker Compose:</p>
  <div class="code"><div class="code-head">POWERSHELL · DOCKER COMPOSE</div><pre>docker compose -p bago-otel -f infra/observability/docker-compose.yml up -d</pre></div>
  <p>Después abre <a href="http://localhost:16686">http://localhost:16686</a>.</p>
  <div class="assist-bottom"><div><small>RECUERDA</small><b>Inspector ≠ Jaeger</b></div><p>Son pantallas diferentes: una permite revisar la ejecución; la otra permite localizar y leer los spans recibidos localmente.</p></div>
  <div class="worksheet"><div class="ws-head"><b>CONFIRMA LOS SERVICIOS</b><span>RESULTADO LOCAL</span></div><div class="ws-row"><label>Inspector /api/health</label><i></i></div><div class="ws-row"><label>Jaeger / 16686</label><i></i></div></div>
</article>''')

pages.append('''<article class="leaf glossary">
  <div class="eyebrow">CIERRE DE CLASE <span>·</span> CONSOLIDAR</div>
  <h2 class="page-title">Glosario rápido</h2>
  <div class="gloss-grid">
    <div><b>Ejecución o run</b><p>operación completa del agente, identificada por run_id.</p></div>
    <div><b>Claim</b><p>afirmación concreta que se revisa frente a evidencia.</p></div>
    <div><b>Evidencia</b><p>documento, fragmento o referencia recuperada.</p></div>
    <div><b>LocalTrace</b><p>registro local de eventos; es la fuente de trazabilidad de este proyecto.</p></div>
    <div><b>Span</b><p>una operación individual dibujada como nodo en Jaeger.</p></div>
    <div><b>OTLP</b><p>transporte usado para enviar spans a Jaeger.</p></div>
    <div><b>Recibo</b><p>registro del resultado de una acción.</p></div>
  </div>
  <h3>Límites conocidos</h3>
  <ul class="limits"><li>La ejecución actual no tiene claims ni relaciones claim→evidencia estructuradas.</li><li>La UI no muestra un enlace directo al Jaeger trace ID.</li><li>La demostración cubre Jaeger local; AWS y colectores remotos quedan fuera de este recorrido.</li><li>La navegación accesible con lector de pantalla requiere una revisión específica.</li></ul>
  <div class="checklist"><div class="check-title">COMPRUEBA LO APRENDIDO</div><div class="check-row"><span>□</span><p>Puedo distinguir run_id de Jaeger trace ID.</p></div><div class="check-row"><span>□</span><p>Puedo explicar por qué una cita no demuestra por sí sola una claim.</p></div><div class="check-row"><span>□</span><p>Puedo comprobar que el recibo pertenece al mismo run.</p></div></div>
  <div class="conclusion"><small>IDEA FINAL</small><p>Identifica la ejecución, sigue su traza y exige un recibo válido antes de dar una acción por confirmada.</p></div>
</article>''')

# Build HTML
html='''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BAGO Agentic Data Lab · Cómo leer una ejecución · Manual 01</title><link rel="stylesheet" href="estilos.css"></head><body>'''+"\n".join(pages)+'''</body></html>'''
(OUT/'manual.html').write_text(html,encoding='utf-8')
HTML(string=html,base_url=str(OUT)+'/').write_pdf(str(OUT/'BAGO_ADL_MANUAL_COMO_LEER_UNA_EJECUCION_v1.2.pdf'),stylesheets=[str(OUT/'estilos.css')])
print('PDF:',OUT/'BAGO_ADL_MANUAL_COMO_LEER_UNA_EJECUCION_v1.2.pdf')
print('Capturas auténticas integradas:',[x for x in ['overview','trace','actions','jaeger'] if (ASSETS/(x+'.png')).is_file()])
