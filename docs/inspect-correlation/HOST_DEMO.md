# Integración y demostración visibles pendientes

Root ejecuta estos pasos tras fusionar sólo el patch allowlist en I, combinando sus propios App/AgentChat/server. No sustituir frontend completo ni copiar fuentes antiguas sobre cinco capacidades existentes.

1. Arrancar candidata I con puerto/source SHA/DB/config/traces/LOCALAPPDATA aislados. No reutilizar perfil real ni generar inferencia para esta reparación.
2. Sembrar conversaciones de fixture mediante ConversationStore y referencias.trace; copiar REPLAY pública496fac a raíz de trazas, sin conectar proveedor. Etiquetar datos como REPLAY y no como nuevo GPT.
3. Abrir conversación A; Inspeccionar ejecución→dialog Inspect muestra convA/trace496fac/runagent-chat275b… e integridad según referencia real. No Bruma5b385699. La traza antigua sinhash debe decirlegacy_unverified; hashfixture sólo prueba integridad de esa copia esperada.
4. En B sintraza, Inspect indica no_artifacts, nunca datos A/Bruma. Cambiar A→B con respuestas retrasadas no muestraA trasB. Capturas propias actuales anonimizadas; no usar fotos/contactos privados.
5. Conversación con varias ejecuciones: elegir por ID, paginar y cotejarconsulta. Archivo borrado/modificado/hashincorrecto oIDdeotraConv no se convierte en éxito; datos anteriores desaparecen.
6. Botón Demo histórica es selección explícita separada; confirma que DecisionInspector conserva checksinternos runID yfailclosed. Su evaluación no valida la conversación.
7. Verificar que cardsComms/Workspace, gestiónAgentes, papelera yproveedores conservan sus props/IDs tras3vías. Este patch no contiene esas candidatas, sólo fuentesbase+hunksIR01.
8. Reejecutar tests/backend/frontend de I, suite completa yREADMEcanónico de I; revisión independiente ygateIR02. No atribuir alfrontendcompuesto las pruebas deJ.

Contrato nuevo read-only: GET /api/conversations/{conversation_id}/inspection?trace_id=...&execution_id=...&offset=0&limit=20. Núcleo estándar src/observability/chat_inspection.py ofrece inspection(conversation,roots,trace_id=None,execution_id=None,offset=0,limit=20), callable desde otra carpeta sin servidorBAGO/importsdelhost. STANDALONE.json verifica copiaexacta con CWDexterno sinPYTHONPATH/BAGO_*.
