"""Optional Windows OCR bridge; only private, bounded image bytes enter WinRT."""
from pathlib import Path
import json
import math
import os
import subprocess
import tempfile

from .core import DocumentError


def _powershell():
    if os.name != 'nt':
        raise DocumentError('OCR_ENGINE_UNAVAILABLE')
    # Use the Windows system binary, never an executable from the corpus or cwd.
    path = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not path.is_file():
        raise DocumentError('OCR_ENGINE_UNAVAILABLE')
    return str(path)


def _run(arguments, timeout):
    try:
        proc = subprocess.run([_powershell(), '-NoLogo', '-NoProfile', '-NonInteractive',
                               '-ExecutionPolicy', 'Bypass', '-File', str(Path(__file__).with_suffix('.ps1')),
                               *arguments], capture_output=True, timeout=timeout,
                              text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired:
        raise DocumentError('OCR_TIMEOUT') from None
    except OSError:
        raise DocumentError('OCR_ENGINE_UNAVAILABLE') from None
    try:
        result = json.loads(proc.stdout.lstrip('\ufeff'))
    except (ValueError, TypeError):
        raise DocumentError('OCR_WINRT_INVALID_RESPONSE') from None
    if not isinstance(result, dict):
        raise DocumentError('OCR_WINRT_INVALID_RESPONSE')
    if proc.returncode or result.get('error'):
        code = result.get('error')
        raise DocumentError(code if code in {'OCR_ENGINE_UNAVAILABLE', 'OCR_IMAGE_DIMENSION_LIMIT'} else 'OCR_WINRT_FAILED')
    return result


def probe():
    """Engine construction only; this is explicitly not a recognition test."""
    try:
        value = _run(['-Probe'], 8)
        return {'available': value.get('available') is True, 'language': value.get('language'),
                'recognition_verified': False, 'check': 'engine_construction'}
    except DocumentError as error:
        return {'available': False, 'code': error.code, 'recognition_verified': False}


def recognize(data, collector):
    if len(data) > collector.limits.max_file_bytes:
        raise DocumentError('FILE_BYTE_LIMIT')
    with tempfile.TemporaryDirectory(prefix='document-toolkit-winrt-') as temporary:
        target = Path(temporary) / 'image.png'
        target.write_bytes(data)
        result = _run(['-ImagePath', str(target)], max(1, collector.limits.max_seconds - 2))
    lines = result.get('lines')
    if not isinstance(lines, list):
        raise DocumentError('OCR_WINRT_INVALID_RESPONSE')
    # Keep line/word text in the same bounded Collector; line text can be
    # reconstructed without duplicating unbounded raw backend payloads.
    try:
        for line in lines:
            for word in line['words']:
                box = word['bbox']
                if (len(box) != 4 or not isinstance(word['text'], str)
                        or type(line['line']) is not int or line['line'] < 1
                        or type(word['word']) is not int or word['word'] < 1
                        or any(type(n) not in (int, float) or not math.isfinite(n) or n < 0 for n in box)
                        or box[2] <= 0 or box[3] <= 0):
                    raise ValueError('invalid word')
                collector.add(word['text'], {'page': 1, 'line': line['line'], 'word': word['word'], 'bbox': box},
                              extraction='ocr', confidence=None)
    except (KeyError, TypeError, ValueError):
        raise DocumentError('OCR_WINRT_INVALID_RESPONSE') from None
    bounded_lines = {}
    for segment in collector.segments:
        line = segment['location']['line']
        bounded_lines.setdefault(line, []).append(segment)
    summaries = []
    for number, words in bounded_lines.items():
        boxes = [s['location']['bbox'] for s in words]
        x, y = min(b[0] for b in boxes), min(b[1] for b in boxes)
        right, bottom = max(b[0]+b[2] for b in boxes), max(b[1]+b[3] for b in boxes)
        summaries.append({'line': number, 'text': ' '.join(s['text'] for s in words),
                          'bbox': [x, y, right-x, bottom-y]})
    return collector.result(ocr_engine='windows-winrt', language=result.get('language'), ocr_lines=summaries,
                            limitations=['OCR confidence is not factual verification.', 'WinRT does not provide word confidence scores.'])
