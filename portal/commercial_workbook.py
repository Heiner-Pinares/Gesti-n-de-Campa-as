"""Gestión segura de la fuente comercial Excel administrada por el portal."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

from django.utils import timezone
from openpyxl import load_workbook

from .models import ChangeAudit


MAX_ARCHIVE_ENTRIES = 2_000
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
REQUIRED_SHEET = "campanas"


class CommercialWorkbookError(ValueError):
    """Error esperado al validar o reemplazar la fuente comercial."""


def _normalized(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(character for character in text if not unicodedata.combining(character)).casefold()


def _safe_archive(path):
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names:
                raise CommercialWorkbookError("El archivo no tiene una estructura XLSX válida.")
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise CommercialWorkbookError("El archivo contiene demasiados elementos internos.")
            if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES:
                raise CommercialWorkbookError("El contenido descomprimido del archivo supera 100 MB.")
            if any(name.casefold().endswith("vbaproject.bin") for name in names):
                raise CommercialWorkbookError("No se permiten libros con macros.")
    except (zipfile.BadZipFile, OSError) as error:
        raise CommercialWorkbookError("El archivo no es un libro XLSX válido.") from error


def inspect_commercial_workbook(path):
    """Valida la estructura y devuelve únicamente metadatos del libro."""
    path = Path(path)
    if not path.is_file():
        return {"exists": False, "filename": path.name, "sheets": []}

    _safe_archive(path)
    try:
        workbook = load_workbook(
            path,
            read_only=True,
            data_only=True,
            keep_links=False,
        )
        sheets = [
            {
                "name": sheet.title,
                "rows": max(sheet.max_row or 0, 0),
                "columns": max(sheet.max_column or 0, 0),
            }
            for sheet in workbook.worksheets
        ]
        workbook.close()
    except Exception as error:
        raise CommercialWorkbookError("No se pudo leer el contenido del libro XLSX.") from error

    if not sheets:
        raise CommercialWorkbookError("El libro debe contener al menos una hoja.")
    campaign_sheet = next(
        (sheet for sheet in sheets if _normalized(sheet["name"]) == REQUIRED_SHEET),
        None,
    )
    if not campaign_sheet:
        raise CommercialWorkbookError('El libro debe incluir la hoja "Campañas".')
    if campaign_sheet["rows"] < 2:
        raise CommercialWorkbookError('La hoja "Campañas" no contiene registros para revisar.')

    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.get_current_timezone())
    return {
        "exists": True,
        "filename": path.name,
        "size": stat.st_size,
        "size_mb": f"{stat.st_size / (1024 * 1024):.2f}",
        "modified_at": modified,
        "modified_iso": modified.isoformat(),
        "sheets": sheets,
        "sheet_count": len(sheets),
        "campaign_rows": max(campaign_sheet["rows"] - 1, 0),
        "checksum": digest.hexdigest(),
    }


def current_commercial_workbook(path):
    try:
        return inspect_commercial_workbook(path)
    except CommercialWorkbookError as error:
        return {
            "exists": Path(path).is_file(),
            "filename": Path(path).name,
            "sheets": [],
            "invalid": True,
            "error": str(error),
        }


def _audit_payload(info):
    if not info or not info.get("exists"):
        return {"exists": False}
    return {
        "exists": True,
        "filename": info.get("filename"),
        "size": info.get("size"),
        "modified_at": info.get("modified_iso"),
        "sheet_count": info.get("sheet_count"),
        "campaign_rows": info.get("campaign_rows"),
        "checksum_sha256": info.get("checksum"),
    }


def replace_commercial_workbook(uploaded_file, target_path, user, ip_address=None):
    """Valida, respalda y reemplaza atómicamente el libro; revierte si falla la auditoría."""
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    old_info = current_commercial_workbook(target_path)
    backup_path = target_path.with_name(f"{target_path.stem}.previous{target_path.suffix}")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target_path.parent,
        prefix=".commercial-upload-",
        suffix=".xlsx",
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    had_previous = target_path.is_file()

    try:
        with temporary_path.open("wb") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        new_info = inspect_commercial_workbook(temporary_path)
        if had_previous:
            shutil.copy2(target_path, backup_path)
        os.replace(temporary_path, target_path)
        new_info = inspect_commercial_workbook(target_path)
        try:
            ChangeAudit.objects.create(
                entidad="FUENTE_COMERCIAL",
                id_entidad=0,
                accion="ACTUALIZAR",
                valor_anterior_json=json.dumps(
                    _audit_payload(old_info), ensure_ascii=False, default=str
                ),
                valor_nuevo_json=json.dumps(
                    _audit_payload(new_info), ensure_ascii=False, default=str
                ),
                usuario=user,
                direccion_ip=ip_address,
            )
        except Exception:
            if had_previous and backup_path.is_file():
                shutil.copy2(backup_path, target_path)
            elif target_path.is_file():
                target_path.unlink()
            raise
        return new_info, backup_path if had_previous else None
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
