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
        for row, cells in enumerate(csv.reader(io.StringIO(text, newline=""), dialect), 1):
            for column, value in enumerate(cells, 1):
                collector.add(value, {"row": row, "column": column})
            if row >= limits.max_cells:
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
