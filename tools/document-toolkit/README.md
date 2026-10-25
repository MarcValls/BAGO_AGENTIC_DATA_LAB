# BAGO Document Toolkit

Python 3.11+. Install with `python -m pip install .` from this directory.
PDF support: `python -m pip install '.[pdf]'`. PNG OCR requires `.[ocr]` and
either external Tesseract on PATH or Windows WinRT OCR with an installed
recognizer language. Version 0.2.0 includes the WinRT PowerShell bridge in the
distribution. No BAGO service is required.

`bago-documents capabilities` reports observed format availability.
`bago-documents inventory --root YOUR_FOLDER` returns bounded SHA256 records.
`bago-documents extract --root YOUR_FOLDER --arguments '{"paths":["file.txt"]}'`
returns cited segments. `python -m document_toolkit` offers the same commands.

Python API: `execute('extract', root, {'paths': ['file.txt']}, limits=Limits())`.
The API returns EXECUTED, PARTIAL or FAILED, errors, coverage and source hashes.
Relations are review candidates; no payment is confirmed. Rename generates a
plan only. Export creates a new JSON/CSV outside the source root, never replaces
source files. A missing OCR engine is reported as unavailable.

See `docs/document-tools/contracts/TOOLKIT_V1.md` in the ADL repository for the
original versioned contract, format limitations, timeout and recovery boundaries.
The additive 0.2.0 OCR derivation is documented in `TOOLKIT_V2.md` beside it.
Availability probes construct the OCR engine; only an extraction demonstrates
recognition for a particular image. Windows OCR returns engine, language, lines,
word boxes and the original PNG SHA256. It does not validate business content.
