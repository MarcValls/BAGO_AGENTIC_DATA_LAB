"""Current API + real temporary files; never changes the selected user workspace."""
from pathlib import Path
import json
import os
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
temp = ROOT / 'output' / 'documents-check'
temp.mkdir(parents=True, exist_ok=True)
os.environ['BAGO_DATA_ROOT'] = str(temp / 'private-data')
from fastapi.testclient import TestClient
from src.api import server


def main():
    checks = []
    with tempfile.TemporaryDirectory(prefix='files-', dir=temp) as directory:
        root = Path(directory).resolve()
        with patch.object(server, 'current_workspace_root', lambda: root), TestClient(server.app) as client:
            def read(source, workspace=None):
                return client.get(f'/api/chat/context/document/{source}', params={'workspace_root': workspace or str(root)})

            assert read('project-context').json()['detail']['code'] == 'document_not_found'
            assert not (root / '.bago').exists()
            checks.append('missing_document_does_not_create_files')
            assert read('conversations').json()['detail']['code'] == 'unknown_document'
            checks.append('fixed_document_ids')
            assert read('project-context', str(root / 'other')).status_code == 409
            checks.append('workspace_mismatch_denied')
            context = root / '.bago/context/PROJECT_CONTEXT.md'
            context.parent.mkdir(parents=True)
            text = '# Proyecto\n\n## Objetivo\nTexto **estructurado**.\n'
            context.write_text(text, encoding='utf-8')
            response = read('project-context')
            assert response.status_code == 200, response.text
            assert response.json()['content'].replace('\r\n', '\n') == text
            assert response.headers['cache-control'] == 'no-store'
            checks.extend(['real_markdown_read', 'no_store'])
            state = root / '.bago/state/PROJECT_STATE.json'
            state.parent.mkdir(parents=True)
            state.write_text('{"project":"Fixture","nested":{"active":true}}', encoding='utf-8')
            assert read('project-state').json()['format'] == 'json'
            checks.append('real_nested_json_read')
            handoff = root / '.bago/runtime/ACTIVE_HANDOFF.md'
            handoff.parent.mkdir(parents=True)
            handoff.write_text('# Handoff fixture', encoding='utf-8')
            assert 'Handoff fixture' in read('active-handoff').json()['content']
            checks.append('real_handoff_read')
            context.write_bytes(b'x' * (256 * 1024 + 1))
            assert read('project-context').status_code == 413
            checks.append('size_limit')
            context.write_bytes(b'\xff\xfeinvalid')
            assert read('project-context').json()['detail']['code'] == 'invalid_document_encoding'
            checks.append('invalid_encoding')
            context.unlink()
            context.mkdir()
            assert read('project-context').json()['detail']['code'] == 'not_a_document'
            checks.append('directory_denied')
    (OUT / 'documents-final.json').write_text(json.dumps({'status': 'PASS', 'checks': checks,
        'surface': 'real candidate FastAPI in-process and real isolated files',
        'user_workspace_modified': False, 'server_sha256': __import__('hashlib').sha256((ROOT/'src/api/server.py').read_bytes()).hexdigest(), 'document_reader_sha256': __import__('hashlib').sha256((ROOT/'src/api/project_documents.py').read_bytes()).hexdigest()}, indent=2) + '\n', encoding='utf-8')
    print('PASS', len(checks), 'real-files checks')


if __name__ == '__main__':
    main()
