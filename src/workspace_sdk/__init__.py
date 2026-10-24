"""Load the byte-preserved standalone SDK and its adjacent pure dependencies."""
import importlib.util
from pathlib import Path
import sys

_root = Path(__file__).resolve().parent
for _name in ('reused_primitives', 'sync_primitives', 'auth_primitives'):
    _path = _root / (_name + '.py')
    if _name in sys.modules:
        if Path(sys.modules[_name].__file__).resolve() != _path:
            raise ImportError('Workspace SDK dependency name already bound to another source: ' + _name)
    else:
        _spec = importlib.util.spec_from_file_location(_name, _path)
        _module = importlib.util.module_from_spec(_spec)
        sys.modules[_name] = _module
        _spec.loader.exec_module(_module)
from .workspace_service import API, ServiceError, WorkspaceService

__all__ = ['API', 'ServiceError', 'WorkspaceService']
