# ADL-CORE-001 · Paquete candidato de implementación

**Estado:** código implementado y probado de forma aislada; repositorio GitHub sin modificar; `NO_GO` para promoción a `main` hasta validación integrada.

## Entregables

- `docs/adl-core/BASELINE_FROZEN_MANIFEST.json`: anclaje del baseline remoto por SHA de commit y hashes Git de módulos conservados. No es un tag Git.
- `docs/adl-core/ADL_CORE_001_CONTRACT_v0.1.md`: modelo de entidades, capacidades, evidencia, invariantes, límites.
- `src/adl_core/core.py`: implementación modular Python stdlib con SQLite y CAS, sin ejecución de código entrante.
- `tests/test_adl_core.py`: 20 vectores positivos/negativos.
- `scripts/run_adl_core_demo.py`: demostración de dos versiones de una entidad, con regresión deliberada en muestras.
- `scripts/verify_adl_core_independent.py`: verificador independiente del módulo de producción.
- `scripts/run_independent_retest.py`: cuatro comprobaciones, incluyendo tres mutaciones adversariales.
- `docs/adl-core/CRIT_ADL_CORE_001.md`: dictamen, comandos y límites de la evidencia.
- `evidence/`: resultados reales de ejecución local, artefactos CAS y la base de datos de la demo. No instalar esta carpeta en el repositorio.
- `INSTALL_ADL_CORE_001.ps1`: copia segura y aditiva para Windows cuando el HEAD coincide exactamente con el baseline y el worktree está limpio. Modo lectura por defecto, `-Apply` para copiar.

## Ejecución local sin dependencias de red

Desde la raíz de este paquete:

```bash
python -m pytest tests/test_adl_core.py -q
python scripts/run_adl_core_demo.py --store evidence/demo_store --output evidence/demo_result.json
python scripts/verify_adl_core_independent.py --store evidence/demo_store --output evidence/independent_retest.json
python scripts/run_independent_retest.py --store evidence/demo_store --output evidence/adversarial_retest.json
```

Para aplicar los archivos al repositorio en Windows PowerShell 7, en un árbol limpio con el commit baseline exacto:

```powershell
./INSTALL_ADL_CORE_001.ps1 -RepositoryPath 'C:\ruta\BAGO_AGENTIC_DATA_LAB'
./INSTALL_ADL_CORE_001.ps1 -RepositoryPath 'C:\ruta\BAGO_AGENTIC_DATA_LAB' -Apply
```

El instalador no realiza commit, no sobrescribe archivos, no ejecuta pruebas automáticamente y no altera la configuración existente.

## Límites importantes

El escenario compara **bytes aportados por un productor**; los resultados no acreditan que un programa haya ejecutado la capacidad real, ni autentican quién produjo las muestras. ADL conserva la diferencia entre afirmación, inspección, ejecución y certificación. No se confiere ningún permiso al importar.

La suite completa ADL, la misión `teamctl`, la re-generación del README, la integración UI y un retest Windows no se han ejecutado en este entorno. No se debe anunciar merge-ready.
