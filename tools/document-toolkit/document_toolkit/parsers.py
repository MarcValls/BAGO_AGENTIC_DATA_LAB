"""Format decoding worker; started as a separate process with a caller timeout."""
from __future__ import annotations

from email import policy
from email.parser import BytesParser
from pathlib import Path
import base64
import csv
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

from .core import DocumentError, Limits, digest


class Collector:
    def __init__(self, limits):
        self.limits = limits
        self.segments = []
        self.characters = 0
        self.truncated = False

    def add(self, text, location, **extra):
        if not isinstance(text, str) or not text:
            return
        remaining = self.limits.max_chars-self.characters
        if remaining <= 0 or len(self.segments) >= self.limits.max_cells:
            self.truncated = True
            return
        self.truncated |= len(text) > remaining
        text = text[:remaining]
        self.characters += len(text)
        self.segments.append({"text": text, "location": location, **extra})

    def result(self, **extra):
        return {"segments": self.segments, "truncated": self.truncated, **extra}


def xml(payload):
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise DocumentError("XML_ENTITY_REJECTED")
    return ET.fromstring(payload)


def _zip(data, limits):
    archive = zipfile.ZipFile(io.BytesIO(data))
    entries = archive.infolist()
    if len(entries) > limits.max_cells or sum(e.file_size for e in entries) > limits.max_bytes:
        raise DocumentError("ARCHIVE_EXPANSION_LIMIT")
    if len({e.filename for e in entries}) != len(entries) or any(e.flag_bits & 1 for e in entries):
        raise DocumentError("ARCHIVE_DUPLICATE_OR_ENCRYPTED")
    return archive


def _docx(data, collector):
    with _zip(data, collector.limits) as archive:
        tree = xml(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    body = tree.find("w:body", ns)
    if body is None:
        raise DocumentError("DOCX_BODY_MISSING")
    pnum = tnum = 0
    for block in body:
        if block.tag.endswith("}p"):
            pnum += 1
            collector.add("".join(block.itertext()) if not list(block) else "".join(t.text or "" for t in block.findall(".//w:t", ns)), {"paragraph": pnum})
        elif block.tag.endswith("}tbl"):
            tnum += 1
            for rownum, row in enumerate(block.findall("w:tr", ns), 1):
                for colnum, cell in enumerate(row.findall("w:tc", ns), 1):
                    collector.add("".join(t.text or "" for t in cell.findall(".//w:t", ns)), {"table": tnum, "row": rownum, "column": colnum})
    return collector.result()


def _xlsx(data, collector):
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    relns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with _zip(data, collector.limits) as archive:
        names = set(archive.namelist())
        strings = []
        if "xl/sharedStrings.xml" in names:
            shared = xml(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in item.findall(".//s:t", ns)) for item in shared]
            if len(strings) > collector.limits.max_cells:
                raise DocumentError("SHARED_STRING_LIMIT")
        workbook = xml(archive.read("xl/workbook.xml"))
        relationships = xml(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in relationships if r.attrib.get("TargetMode") != "External"}
        cellcount = 0
        for sheet in workbook.findall("s:sheets/s:sheet", ns):
            target = targets.get(sheet.attrib.get(relns), "")
            if not target or ".." in target.split("/"):
                raise DocumentError("INVALID_WORKBOOK_RELATIONSHIP")
            member = target.lstrip("/") if target.startswith("/") else "xl/"+target
            tree = xml(archive.read(member))
            for cell in tree.findall(".//s:sheetData/s:row/s:c", ns):
                cellcount += 1
                if cellcount > collector.limits.max_cells:
                    collector.truncated = True
                    return collector.result()
                value = cell.find("s:v", ns)
                formula = cell.find("s:f", ns)
                text = value.text or "" if value is not None else ""
                if cell.attrib.get("t") == "s":
                    text = strings[int(text)]
                elif cell.attrib.get("t") == "inlineStr":
                    text = "".join(t.text or "" for t in cell.findall(".//s:t", ns))
                location = {"sheet": sheet.attrib.get("name", ""), "cell": cell.attrib.get("r", "")}
                if formula is not None:
                    collector.add("="+(formula.text or ""), location, value_kind="formula", cached_value=text or None,
                                  recalculated=False)
                else:
                    collector.add(text, location, value_kind=cell.attrib.get("t", "number"))
    return collector.result()


def _text(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf16")
    return data.decode("utf-8-sig", errors="strict")



_CSV_DELIMITERS = (",", ";", "\t", "|")


def _validate_csv_quotes(text, delimiter):
    """Enforce strict table quoting beyond csv.reader's strict=True checks."""
    field_start, quoted, closed = True, False, False
    index = 0
    while index < len(text):
        char = text[index]
        if quoted:
            if char == '"':
                if index + 1 < len(text) and text[index + 1] == '"':
                    index += 2
                    continue
                quoted, closed = False, True
        elif closed:
            if char == delimiter or char in "\r\n":
                field_start, closed = True, False
            else:
                raise DocumentError("CSV_MALFORMED_QUOTES")
        elif char == '"':
            if not field_start:
                raise DocumentError("CSV_MALFORMED_QUOTES")
            quoted, field_start = True, False
        elif char == delimiter or char in "\r\n":
            field_start = True
        else:
            field_start = False
        index += 1
    if quoted:
        raise DocumentError("CSV_MALFORMED_QUOTES")


def _csv_records(text, delimiter, *, dialect=None):
    """Shared record locations; preserve the existing extraction dialect.

    The calculation table chooses strict RFC-style double quotes. Legacy
    extraction keeps Sniffer's complete dialect, including quotechar and
    skipinitialspace, so adding this table does not reinterpret old documents.
    """
    if dialect is None:
        _validate_csv_quotes(text, delimiter)
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter,
                            quotechar='"', doublequote=True, strict=True)
    else:
        reader = csv.reader(io.StringIO(text, newline=""), dialect)
    previous_line = 0
    try:
        for row, cells in enumerate(reader, 1):
            yield {"row": row, "start_line": previous_line + 1,
                   "end_line": reader.line_num, "cells": cells}
            previous_line = reader.line_num
    except csv.Error:
        raise DocumentError("CSV_MALFORMED") from None


def parse_csv_table(data, *, delimiter="auto", max_rows=250, max_columns=128,
                    max_cells=32000):
    """Decode one complete bounded UTF-8 CSV snapshot for exact calculations.

    max_rows includes the header. Auto detection requires exactly one consistent
    multi-column dialect; ambiguous separators require an explicit user choice.
    Header names and cell bytes-as-text are never silently trimmed or repaired.
    """
    if not isinstance(data, bytes) or len(data) > 256 * 1024:
        raise DocumentError("CSV_BYTE_LIMIT")
    if any(type(value) is not int or value < 1 for value in (max_rows, max_columns, max_cells)):
        raise DocumentError("CSV_INVALID_LIMIT")
    if max_rows > 250 or max_columns > 128 or max_cells > 32000:
        raise DocumentError("CSV_INVALID_LIMIT")
    if delimiter not in ("auto", *_CSV_DELIMITERS):
        raise DocumentError("CSV_DELIMITER_INVALID")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DocumentError("CSV_NOT_UTF8") from None
    if not text or "\x00" in text:
        raise DocumentError("CSV_EMPTY_OR_BINARY")
    total_lines = sum(1 for _ in io.StringIO(text, newline=""))
    if total_lines > max_rows:
        raise DocumentError("CSV_ROW_LIMIT")

    def records_for(sep):
        records, cells_seen = [], 0
        for record in _csv_records(text, sep):
            if len(records) >= max_rows:
                raise DocumentError("CSV_ROW_LIMIT")
            if len(record["cells"]) > max_columns:
                raise DocumentError("CSV_COLUMN_LIMIT")
            cells_seen += len(record["cells"])
            if cells_seen > max_cells:
                raise DocumentError("CSV_CELL_LIMIT")
            records.append(record)
        if not records or not records[0]["cells"]:
            raise DocumentError("CSV_EMPTY_OR_BINARY")
        return records

    if delimiter == "auto":
        candidates, single, errors = [], [], []
        structural_separator = False
        for sep in _CSV_DELIMITERS:
            try:
                records = records_for(sep)
                widths = {len(record["cells"]) for record in records}
                structural_separator |= any(width > 1 for width in widths)
                if len(widths) == 1 and next(iter(widths)) > 1:
                    candidates.append((sep, records))
                elif widths == {1}:
                    single.append((sep, records))
            except DocumentError as error:
                errors.append(error)
        if len(candidates) > 1:
            raise DocumentError("CSV_DELIMITER_AMBIGUOUS")
        if candidates:
            delimiter, records = candidates[0]
        elif any(error.code.endswith("_LIMIT") for error in errors):
            raise next(error for error in errors if error.code.endswith("_LIMIT"))
        elif single and not structural_separator:
            delimiter, records = single[0]
        else:
            # Never fall back to a different one-column interpretation of a
            # malformed multi-column file.
            limits = next((error for error in errors if error.code.endswith("_LIMIT")), None)
            raise limits or DocumentError("CSV_MALFORMED")
    else:
        records = records_for(delimiter)

    columns = records[0]["cells"]
    if any(not column.strip() or len(column) > 256 for column in columns):
        raise DocumentError("CSV_HEADER_INVALID")
    if len({column.strip().casefold() for column in columns}) != len(columns):
        raise DocumentError("CSV_HEADER_DUPLICATE")
    if any(len(record["cells"]) != len(columns) for record in records[1:]):
        raise DocumentError("CSV_COLUMN_COUNT")
    return {"columns": columns, "rows": records[1:], "delimiter": delimiter,
            "total_lines": total_lines}


def parse(data, suffix, limits):
    collector = Collector(limits)
    if suffix == ".txt":
        for line, text in enumerate(_text(data).splitlines(), 1):
            collector.add(text, {"line": line})
    elif suffix == ".csv":
        text = _text(data)
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        for record in _csv_records(text, dialect.delimiter, dialect=dialect):
            for column, value in enumerate(record["cells"], 1):
                collector.add(value, {"row": record["row"], "column": column})
            if record["row"] >= limits.max_cells:
                collector.truncated = True; break
    elif suffix == ".docx":
        return _docx(data, collector)
    elif suffix == ".xlsx":
        return _xlsx(data, collector)
    elif suffix == ".eml":
        message = BytesParser(policy=policy.default).parsebytes(data)
        for name in ("From", "To", "Date", "Subject", "Message-ID"):
            if message.get(name):
                collector.add(str(message[name]), {"header": name})
        attachments = []
        for index, part in enumerate(message.walk(), 1):
            if index > limits.max_cells:
                collector.truncated = True; break
            if part.is_multipart():
                continue
            payload = part.get_payload(decode=True) or b""
            if part.get_content_disposition() == "attachment" or part.get_filename():
                attachments.append({"part": index, "filename": part.get_filename(), "sha256": digest(payload), "bytes": len(payload), "extracted": False})
            elif part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf8"
                for line, text in enumerate(payload.decode(charset, errors="strict").splitlines(), 1):
                    collector.add(text, {"part": index, "line": line})
        return collector.result(attachments=attachments, limitations=["HTML mail parts are not rendered; attachments are inventoried only."])
    elif suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise DocumentError("PDF_DEPENDENCY_UNAVAILABLE") from None
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise DocumentError("ENCRYPTED_PDF")
        pages = len(reader.pages)
        for number, page in enumerate(reader.pages[:limits.max_pages], 1):
            text = page.extract_text() or ""
            collector.add(text, {"page": number}, extraction="embedded_text")
        collector.truncated |= pages > limits.max_pages
        return collector.result(page_count=pages, needs_ocr=not bool(collector.segments),
                                limitations=["Embedded PDF text only; scanned pages need a separate OCR operation."])
    elif suffix == ".png":
        executable = shutil.which("tesseract")
        try:
            from PIL import Image
        except ImportError:
            raise DocumentError("IMAGE_DEPENDENCY_UNAVAILABLE") from None
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height > 20_000_000:
                raise DocumentError("IMAGE_PIXEL_LIMIT")
            if image.format != "PNG":
                raise DocumentError("IMAGE_FORMAT_MISMATCH")
            image.verify()
        if not executable:
            from .windows_ocr import recognize
            return recognize(data, collector)
        with tempfile.TemporaryDirectory(prefix="document-toolkit-ocr-") as temporary:
            target = Path(temporary)/"image.png"; target.write_bytes(data)
            try:
                proc = subprocess.run([executable, str(target), "stdout", "--psm", "6", "tsv"], capture_output=True,
                                      timeout=max(1, limits.max_seconds-2), text=True, encoding="utf8")
            except subprocess.TimeoutExpired:
                raise DocumentError("OCR_TIMEOUT") from None
        if proc.returncode:
            raise DocumentError("OCR_FAILED")
        for row in csv.DictReader(io.StringIO(proc.stdout), delimiter="\t"):
            if row.get("text", "").strip():
                collector.add(row["text"], {"page": int(row["page_num"]), "bbox": [int(row[k]) for k in ("left", "top", "width", "height")]},
                              confidence=float(row["conf"]), extraction="ocr")
        return collector.result(ocr_engine="tesseract", language="engine_default", limitations=["OCR confidence is not factual verification."])
    else:
        raise DocumentError("UNSUPPORTED_FORMAT")
    return collector.result()


def main():
    try:
        request = json.load(sys.stdin)
        limits = Limits(**request["limits"])
        data = base64.b64decode(request["bytes"], validate=True)
        if len(data) > limits.max_file_bytes:
            raise DocumentError("FILE_BYTE_LIMIT")
        result = parse(data, request["suffix"], limits)
    except Exception as error:
        result = {"error": getattr(error, "code", "INVALID_DOCUMENT")}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
