"""Synthetic public input only; no screenshots or user documents."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/document-toolkit'))
from document_toolkit import Limits, execute
from document_toolkit.core import DocumentError
from document_toolkit.parsers import Collector, parse
from document_toolkit import windows_ocr


def png():
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1400, 260), 'white')
    ImageDraw.Draw(image).text((45, 65), 'DOCUMENTO 731942',
                              font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 64), fill='black')
    output = io.BytesIO(); image.save(output, 'PNG')
    return output.getvalue()


@pytest.mark.skipif(os.name != 'nt', reason='Real WinRT recognition needs Windows')
def test_real_winrt_text_lines_boxes_and_source(tmp_path):
    data = png(); (tmp_path / 'synthetic.png').write_bytes(data)
    assert windows_ocr.probe()['available'], 'WinRT engine required for this Windows acceptance check'
    result = windows_ocr.recognize(data, Collector(Limits()))
    assert result['ocr_engine'] == 'windows-winrt'
    assert 'DOCUMENTO 731942' in ' '.join(s['text'] for s in result['segments'])
    assert 'DOCUMENTO 731942' in result['ocr_lines'][0]['text']
    for segment in result['segments']:
        x, y, width, height = segment['location']['bbox']
        assert 0 <= x < x+width <= 1400
        assert 0 <= y < y+height <= 260
        assert segment['location']['line'] >= 1 and segment['confidence'] is None
    api = execute('extract', tmp_path, {'paths': ['synthetic.png']})
    assert api['state'] == 'EXECUTED' and not api['errors']
    assert api['version'] == '0.2.0' and api['schema'] == 'document-toolkit.result.v1'
    assert (tmp_path / 'synthetic.png').read_bytes() == data


def test_unavailable_is_explicit(monkeypatch):
    monkeypatch.setattr(windows_ocr, '_powershell', lambda: (_ for _ in ()).throw(DocumentError('OCR_ENGINE_UNAVAILABLE')))
    assert windows_ocr.probe()['available'] is False
    with pytest.raises(DocumentError, match='OCR_ENGINE_UNAVAILABLE'):
        windows_ocr._run(['-Probe'], 1)


def test_non_windows_is_unavailable(monkeypatch):
    monkeypatch.setattr(windows_ocr, 'os', SimpleNamespace(name='posix'))
    with pytest.raises(DocumentError, match='OCR_ENGINE_UNAVAILABLE'):
        windows_ocr._powershell()


def test_timeout_is_not_success(monkeypatch):
    monkeypatch.setattr(windows_ocr, '_powershell', lambda: 'powershell.exe')
    def timeout(*args, **kwargs):
        assert kwargs['timeout'] == 1
        assert kwargs.get('shell', False) is False
        raise subprocess.TimeoutExpired(args[0], 1)
    monkeypatch.setattr(windows_ocr.subprocess, 'run', timeout)
    with pytest.raises(DocumentError, match='OCR_TIMEOUT'):
        windows_ocr._run(['-Probe'], 1)


@pytest.mark.parametrize('returncode,output,error', [
    (1, '{"error":"OCR_ENGINE_UNAVAILABLE"}', 'OCR_ENGINE_UNAVAILABLE'),
    (1, '{"error":"private path or backend details"}', 'OCR_WINRT_FAILED'),
    (0, 'not json', 'OCR_WINRT_INVALID_RESPONSE'),
    (0, '[]', 'OCR_WINRT_INVALID_RESPONSE'),
])
def test_backend_errors_are_sanitized(monkeypatch, returncode, output, error):
    monkeypatch.setattr(windows_ocr, '_powershell', lambda: 'powershell.exe')
    monkeypatch.setattr(windows_ocr.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a[0], returncode, output, 'secret'))
    with pytest.raises(DocumentError, match=error):
        windows_ocr._run(['-Probe'], 1)


def test_byte_limit_precedes_backend(monkeypatch):
    monkeypatch.setattr(windows_ocr, '_run', lambda *a: pytest.fail('backend should not run'))
    with pytest.raises(DocumentError, match='FILE_BYTE_LIMIT'):
        windows_ocr.recognize(b'x'*20, Collector(Limits(max_file_bytes=10)))


def test_invalid_boxes_do_not_succeed(monkeypatch):
    monkeypatch.setattr(windows_ocr, '_run', lambda *a: {'lines': [{'line': 1, 'words': [{'word': 1, 'text': 'a', 'bbox': [0, 0, -1, 1]}]}]})
    with pytest.raises(DocumentError, match='OCR_WINRT_INVALID_RESPONSE'):
        windows_ocr.recognize(b'bounded', Collector(Limits()))


def test_validated_png_falls_back_and_retains_limits(monkeypatch):
    from document_toolkit import parsers
    from PIL import Image
    buffer = io.BytesIO(); Image.new('RGB', (10, 10), 'white').save(buffer, 'PNG')
    monkeypatch.setattr(parsers.shutil, 'which', lambda name: None)
    monkeypatch.setattr(windows_ocr, '_run', lambda *a: {'language': 'es-ES', 'lines': [{'line': 1, 'words': [{'word': 1, 'text': 'abcdef', 'bbox': [1, 1, 5, 5]}]}]})
    result = parse(buffer.getvalue(), '.png', Limits(max_chars=3))
    assert result['ocr_engine'] == 'windows-winrt' and result['truncated']
    assert result['segments'][0]['text'] == 'abc'
    assert result['ocr_lines'][0]['text'] == 'abc'


def test_tesseract_remains_preferred(monkeypatch):
    from document_toolkit import parsers
    from PIL import Image
    buffer = io.BytesIO(); Image.new('RGB', (10, 10), 'white').save(buffer, 'PNG')
    monkeypatch.setattr(parsers.shutil, 'which', lambda name: 'test-tesseract')
    monkeypatch.setattr(windows_ocr, 'recognize', lambda *a: pytest.fail('WinRT must not replace selected Tesseract'))
    def run(argv, **kwargs):
        assert argv[0] == 'test-tesseract' and argv[-1] == 'tsv'
        assert Path(argv[1]).read_bytes() == buffer.getvalue()
        return subprocess.CompletedProcess(argv, 0,
            'page_num\tleft\ttop\twidth\theight\tconf\ttext\n1\t1\t1\t5\t5\t90\tSynthetic\n', '')
    monkeypatch.setattr(parsers.subprocess, 'run', run)
    result = parse(buffer.getvalue(), '.png', Limits())
    assert result['ocr_engine'] == 'tesseract'
    assert result['segments'][0]['text'] == 'Synthetic'


def test_mislabeled_image_does_not_reach_backend(monkeypatch):
    from document_toolkit import parsers
    from PIL import Image
    buffer = io.BytesIO(); Image.new('RGB', (10, 10), 'white').save(buffer, 'JPEG')
    monkeypatch.setattr(windows_ocr, 'recognize', lambda *a: pytest.fail('invalid PNG must be rejected first'))
    with pytest.raises(DocumentError, match='IMAGE_FORMAT_MISMATCH'):
        parse(buffer.getvalue(), '.png', Limits())
