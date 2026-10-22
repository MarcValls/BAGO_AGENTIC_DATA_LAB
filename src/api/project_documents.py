"""Read only the selected project's three fixed continuity documents."""
import hashlib
from pathlib import Path
import stat

from fastapi import HTTPException

PROJECT_DOCUMENTS = {
    "project-context": ".bago/context/PROJECT_CONTEXT.md",
    "project-state": ".bago/state/PROJECT_STATE.json",
    "active-handoff": ".bago/runtime/ACTIVE_HANDOFF.md",
}
MAX_DOCUMENT_BYTES = 256 * 1024


def read_project_document(root: Path, source_id: str, expected_workspace: str):
    root = root.resolve()
    if expected_workspace != str(root):
        raise HTTPException(409, detail={"code": "workspace_changed", "message": "El proyecto ha cambiado. Actualiza la vista."})
    relative = PROJECT_DOCUMENTS.get(source_id)
    if relative is None:
        raise HTTPException(404, detail={"code": "unknown_document", "message": "Documento no disponible."})
    try:
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root):
            raise HTTPException(403, detail={"code": "document_outside_workspace", "message": "El archivo apunta fuera del proyecto seleccionado."})
        if not stat.S_ISREG(path.stat().st_mode):
            raise HTTPException(422, detail={"code": "not_a_document", "message": "La ruta no corresponde a un archivo."})
        with path.open("rb") as stream:
            raw = stream.read(MAX_DOCUMENT_BYTES + 1)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, detail={"code": "document_too_large", "message": "El archivo supera el límite de visualización de 256 KiB."})
        content = raw.decode("utf-8-sig")
        if "\x00" in content:
            raise UnicodeError()
    except FileNotFoundError:
        raise HTTPException(404, detail={"code": "document_not_found", "message": "Este archivo todavía no existe en el proyecto seleccionado."}) from None
    except UnicodeError:
        raise HTTPException(422, detail={"code": "invalid_document_encoding", "message": "El archivo no es texto UTF-8 válido."}) from None
    except OSError:
        raise HTTPException(403, detail={"code": "document_unreadable", "message": "No se pudo leer este archivo."}) from None
    return {"id": source_id, "workspace_root": str(root), "path": str(path),
            "format": "json" if source_id == "project-state" else "markdown",
            "content": content, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
