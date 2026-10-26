"""Model-facing read/plan tools. Execution is reserved for a trusted host review flow."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_FILE = Path(__file__).resolve().parents[2] / 'tools/filesystem-toolkit/bago_filesystem.py'
_SPEC = importlib.util.spec_from_file_location('adl_bago_filesystem', _FILE)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
FilesystemToolkit = _MODULE.FilesystemToolkit
FilesystemError = _MODULE.FilesystemError

FS_TOOL_IDS = frozenset({'filesystem_inventory', 'filesystem_plan'})


def descriptors():
    return [
        {'id': 'filesystem_inventory', 'name': 'Inventario de archivos',
         'name_en': 'Filesystem inventory', 'status': 'available', 'assignable': True,
         'summary': 'Inspecciona archivos y hashes dentro de una raíz concedida.',
         'effect': 'read', 'limits': 'No recursivo; máximo 1000 entradas; archivos hasta 16 MiB.'},
        {'id': 'filesystem_plan', 'name': 'Preparar operaciones de archivos',
         'name_en': 'Plan filesystem actions', 'status': 'available', 'assignable': True,
         'summary': 'Prepara un plan revisable; la ejecución exige aprobación separada del host.',
         'effect': 'prepare', 'limits': 'No ejecuta efectos sobre archivos del usuario; persiste planes.'},
    ]


class FilesystemSession:
    @staticmethod
    def _allowed(grant):
        if not isinstance(grant, dict) or not grant.get('root'):
            raise FilesystemError('trusted workspace grant required')
        tools = grant.get('tools', [])
        if not isinstance(tools, (list, tuple, set, frozenset)):
            raise FilesystemError('invalid assigned tool list')
        return set(tools) & FS_TOOL_IDS

    def tool_schemas(self, grant):
        allowed = self._allowed(grant)
        schemas = [
            {'type': 'function', 'function': {'name': 'filesystem_inventory',
             'description': 'List a granted folder and file hashes without recursion.',
             'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                            'additionalProperties': False}}},
            {'type': 'function', 'function': {'name': 'filesystem_plan',
             'description': 'Prepare a filesystem plan for separate human review. Does not execute the plan.',
             'parameters': {'type': 'object', 'properties': {
                 'operation': {'type': 'string', 'enum': sorted(_MODULE.OPERATIONS)},
                 **{key: {'type': 'string'} for key in ('source', 'target', 'content', 'trash_id')}},
                 'required': ['operation'], 'additionalProperties': False}}},
        ]
        return [schema for schema in schemas if schema['function']['name'] in allowed]

    def invoke(self, name, args, grant):
        if name not in self._allowed(grant):
            raise FilesystemError('tool not assigned by host')
        if not isinstance(args, dict):
            raise FilesystemError('arguments must be an object')
        accepted = {'path'} if name == 'filesystem_inventory' else {'operation', 'source', 'target', 'content', 'trash_id'}
        if set(args) - accepted:
            raise FilesystemError('unexpected arguments')
        toolkit = FilesystemToolkit(grant['root'])
        result = toolkit.inventory(**args) if name == 'filesystem_inventory' else toolkit.plan(**args)
        receipt = {'tool': name, 'root': str(toolkit.root),
                   'status': 'VERIFIED' if name == 'filesystem_inventory' else 'PREPARED',
                   'effect_status': 'read_only' if name == 'filesystem_inventory' else 'plan_persisted',
                   'plan_id': result.get('id'), 'plan_sha256': result.get('sha256')}
        return result, receipt
