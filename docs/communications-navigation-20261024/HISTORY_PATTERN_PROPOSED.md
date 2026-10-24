# Patrón común de historial por entidad — PROPUESTO

El usuario propone agrupar cada área por sus entidades y mantener un historial filtrable: Comunicaciones (contactos, mensajes y futuras entidades de comunicaciones), Workspace, Chat y Agentes.

Esta ronda implementa la agrupación lateral Comunicaciones y la coherencia visual/funcional de sus tres destinos. El historial actual consume `/api/communications/runs`: son ejecuciones de mensajes. No existe evidencia aquí de un registro exhaustivo de altas/cambios/importaciones de contactos. No se renombra ese historial como auditoría general ni se presenta un filtro sin eventos subyacentes.

Pendiente separado: contrato de eventos con identidad de entidad/operación/fecha/resultado/recibo y fuentes reales; integración de contactos y mensajes, pruebas positivas/negativas y filtros en UI; después adaptar el mismo patrón al resto de áreas conservando aislamiento de contexto. Cierre: un filtro por entidad devuelve sólo registros propios persistidos y trazables, incluyendo eventos positivos/negativos de fuentes reales y recuperación tras reinicio. No simular eventos históricos ni mezclar recibos de otra entidad.
