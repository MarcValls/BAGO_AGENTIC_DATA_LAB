# Demanda de negocio para la demostración: entrega exprés tardía

> **Escenario ficticio.** Esta demanda sirve para enseñar y probar la interfaz. No es una incidencia real ni autoriza una compensación económica.

## Petición de la usuaria

Nora Salas, responsable ficticia de Operaciones de Bruma Market, necesita responder despacio y con evidencia a esta pregunta:

> “Tenemos un caso de práctica de un pedido exprés que llegó 27 horas y 30 minutos después de la hora prometida. ¿Qué establece la política vigente, qué documento valida la regla y qué podemos decirle al cliente? Señala qué dato del caso estás dando por supuesto. No tramites ni simules ningún reembolso.”

El retraso de 27 horas y 30 minutos es un **dato de entrada inventado para el ejercicio**. No aparece en los fixtures existentes y no está verificado por la aplicación.

## Qué necesita recibir Operaciones

1. Una respuesta directa sobre la regla aplicable, condicionada a que el pedido sea exprés y el retraso indicado esté confirmado.
2. La evidencia que respalda la versión de la política y la validación QA.
3. Una frase breve que Operaciones pueda revisar antes de enviarla al cliente.
4. Una separación visible entre hechos del fixture, datos que ha aportado el usuario y conclusiones.
5. El siguiente paso humano necesario para comprobar un pedido real y, si corresponde, tramitar una compensación.

## Criterios de aceptación

- Afirma que la política local de la demo devuelve el coste del envío exprés cuando el retraso supera 24 horas.
- Cita la política v2 y el acta QA con sus identificadores de evidencia.
- Aclara que el retraso de 27 h 30 min es un dato ficticio no corroborado por una fuente de pedido.
- No afirma haber buscado un pedido, contactado al cliente, actualizado el ERP ni efectuado un reembolso.
- Recomienda comprobar la hora prometida, la hora real y el tipo de envío en el sistema de pedidos antes de decidir.
- Presenta el borrador al equipo humano para revisión; no lo envía automáticamente.

## Recorrido de cobertura previsto en la interfaz

1. Abrir **Chat** y leer el alcance de la conversación general.
2. Activar **Authorize exact project files for this message** y autorizar únicamente este archivo y `docs/demo/bruma_market_empresa.md` para el turno de lectura.
3. Pedir un análisis de la política, sus citas y las incógnitas; indicar expresamente que no se ejecute ninguna acción.
4. Comparar la respuesta con la sección “Result” de `evidence/public_e2e_demo.md` y el resumen local de la demo.
5. Abrir **Inspect → Decision Inspector** para seguir conclusión, evidencia, traza, acciones y recibos de la demo local. Esta demo sirve como evidencia de la ruta de portfolio, no como evidencia del pedido inventado.
6. Abrir **Trace** y **Evaluation** para revisar la traza local y sus checks estructurales. Un PASS de evaluación no mide la calidad general de la respuesta del chat.
7. Revisar el texto propuesto. Un empleado autorizado comprobaría el pedido en el sistema de la empresa y decidiría cualquier compensación por el proceso establecido.

## Lo que la interfaz actual puede y no puede hacer en este caso

- El chat general puede responder con el proveedor Ollama configurado, leer los dos archivos permitidos para ese turno si la persona activa expresamente la lectura y navegar a vistas conocidas.
- La lectura está limitada a los ficheros indicados y no permite escribirlos ni ejecutar comandos.
- La demo local de portfolio muestra recuperación, evidencia, recibos, traza y evaluación determinista, sin llamar a un proveedor externo.
- Esta conversación no está conectada a un ERP ni dispone de una capacidad de reembolso gobernada. Por tanto, la resolución de un pedido real y cualquier efecto económico quedan fuera de alcance.

## Comprobación local sin proveedor

La ruta reproducible de cero coste está descrita en [`../public_e2e_demo.md`](../public_e2e_demo.md) y puede ejecutarse con:

```powershell
python scripts/run_public_e2e_demo.py --check
```

La ruta anterior verifica los fixtures locales de Bruma Market; no equivale a enviar la petición por el chat ni a comprobar un pedido real.
