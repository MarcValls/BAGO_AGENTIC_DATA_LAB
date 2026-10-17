# Perfil de empresa para la demostración: Bruma Market

> **Caso completamente ficticio.** La empresa, el personaje y todos los datos operativos de este perfil se han creado para practicar. No identifican a una empresa o persona real.

## La empresa

Bruma Market es un minorista online ficticio. En esta práctica atiende pedidos de alimentación y productos de consumo a través de su web. Su promesa comercial incluye una modalidad de envío exprés.

Los siguientes detalles son contexto inventado para hacer el ejercicio comprensible; no forman parte de los artefactos de evaluación del repositorio:

- **Tamaño de ejemplo:** 38 personas.
- **Operación:** un centro de preparación y transportistas externos.
- **Canal de atención:** equipo de operaciones y atención al cliente.
- **Prioridad del equipo:** responder con una política vigente y evidencia verificable antes de ofrecer compensaciones.
- **Responsable ficticia:** Nora Salas, responsable de Operaciones. El nombre es inventado y no representa a una persona real.

## Contexto que sí respalda la demo local

El repositorio incluye una demo determinista con fixtures de Bruma Market. En esa demo:

- La política vigente de envío exprés indica devolver el coste del envío cuando la entrega supera las 24 horas de retraso.
- Un acta de QA valida la regla de la política vigente frente a la versión anterior.
- La respuesta de referencia cita `fixtures/bruma-delivery-policy-v2.md#revision=2.0.0` y `fixtures/bruma-delivery-policy-qa.md#revision=1.0.0`.
- Esas referencias son identificadores de evidencia de los fixtures locales de la demo; no son expedientes de un ERP ni documentos de un cliente real.

Fuentes locales descriptivas:

- [`evidence/public_e2e_demo.md`](../../evidence/public_e2e_demo.md)
- [`docs/public_e2e_demo.md`](../public_e2e_demo.md)
- [`demo_output/latest/summary.json`](../../demo_output/latest/summary.json)

## Límites del perfil

Este perfil no contiene pedidos, nombres de clientes, direcciones, importes de compra ni credenciales. No debe usarse para inferir datos de pedidos reales, cobertura logística o resultados financieros de Bruma Market.
