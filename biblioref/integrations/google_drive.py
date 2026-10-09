"""Read-only Google Drive integration for the BiblioRef desktop app.

Authentication uses an OAuth *Desktop app* client configured by the user. The
refresh token is stored only on the local machine. BiblioRef requests
``drive.readonly`` and never writes to Drive.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

GOOGLE_DRIVE_INTEGRATION_VERSION = "google-drive-readonly-0.2"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
PDF_MIME = "application/pdf"
ZIP_MIMES = {"application/zip", "application/x-zip-compressed", "application/octet-stream"}
FILE_FIELDS = "id,name,mimeType,size,modifiedTime,parents,shortcutDetails(targetId,targetMimeType)"
MAX_SEARCH_RESULTS = 200

try:  # Optional dependency; the rest of BiblioRef must work without it.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_DRIVE_LIBS_AVAILABLE = True
except Exception:  # pragma: no cover - exercised on installs without the extra
    Request = Credentials = InstalledAppFlow = build = MediaIoBaseDownload = None
    GOOGLE_DRIVE_LIBS_AVAILABLE = False


class GoogleDriveError(RuntimeError):
    pass


def default_config_dir() -> Path:
    return Path(os.environ.get("BIBLIOREF_CONFIG_DIR", Path.home() / ".biblioref"))


def default_client_secret_path() -> Path:
    env = os.environ.get("BIBLIOREF_GOOGLE_CLIENT_SECRET")
    return Path(env).expanduser() if env else default_config_dir() / "google_drive_client_secret.json"


def default_token_path() -> Path:
    env = os.environ.get("BIBLIOREF_GOOGLE_TOKEN")
    return Path(env).expanduser() if env else default_config_dir() / "google_drive_token.json"


def validate_client_secret_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise GoogleDriveError("El archivo OAuth debe ser un objeto JSON")
    block = data.get("installed") or data.get("web")
    if not isinstance(block, dict):
        raise GoogleDriveError("El JSON no contiene una configuración OAuth de Google ('installed' o 'web')")
    required = {"client_id", "client_secret", "auth_uri", "token_uri"}
    missing = sorted(k for k in required if not block.get(k))
    if missing:
        raise GoogleDriveError("Configuración OAuth incompleta: faltan " + ", ".join(missing))
    return data


def save_client_secret_bytes(raw: bytes, path: Path | None = None) -> Path:
    target = path or default_client_secret_path()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise GoogleDriveError("El archivo de credenciales no es JSON válido") from exc
    validate_client_secret_data(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def _require_libs() -> None:
    if not GOOGLE_DRIVE_LIBS_AVAILABLE:
        raise GoogleDriveError(
            "Faltan dependencias de Google Drive. Instalá requirements-app.txt de esta versión."
        )


def _load_credentials(token_path: Path | None = None):
    _require_libs()
    path = token_path or default_token_path()
    if not path.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(path), [DRIVE_READONLY_SCOPE])
    except Exception:
        return None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            path.write_text(creds.to_json(), encoding="utf-8")
        except Exception:
            return None
    return creds if creds and creds.valid else None


def connect(client_secret_path: Path | None = None, token_path: Path | None = None):
    _require_libs()
    client = client_secret_path or default_client_secret_path()
    token = token_path or default_token_path()
    if not client.exists():
        raise GoogleDriveError("Primero configurá el archivo OAuth de Google Drive")
    validate_client_secret_data(json.loads(client.read_text(encoding="utf-8-sig")))
    token.parent.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(client), [DRIVE_READONLY_SCOPE])
    # A short-lived loopback server is the recommended installed-app flow. It
    # opens the user's normal browser; the BiblioRef desktop shell remains local.
    creds = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True, authorization_prompt_message="")
    token.write_text(creds.to_json(), encoding="utf-8")
    try:
        os.chmod(token, 0o600)
    except OSError:
        pass
    return creds


def disconnect(token_path: Path | None = None) -> None:
    (token_path or default_token_path()).unlink(missing_ok=True)


def service():
    creds = _load_credentials()
    if not creds:
        raise GoogleDriveError("Google Drive no está conectado")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def status() -> dict[str, Any]:
    configured = default_client_secret_path().exists()
    connected = False
    user = None
    error = None
    if GOOGLE_DRIVE_LIBS_AVAILABLE and configured:
        creds = _load_credentials()
        connected = bool(creds)
        if connected:
            try:
                about = build("drive", "v3", credentials=creds, cache_discovery=False).about().get(
                    fields="user(displayName,emailAddress)"
                ).execute()
                user = about.get("user") or None
            except Exception as exc:  # keep status usable even if Drive is transiently unavailable
                error = str(exc)
    return {
        "integration_version": GOOGLE_DRIVE_INTEGRATION_VERSION,
        "available": GOOGLE_DRIVE_LIBS_AVAILABLE,
        "configured": configured,
        "connected": connected,
        "scope": "drive.readonly",
        "read_only": True,
        "auth_mode": "user_oauth_desktop",
        "capabilities": {
            "browse": True,
            "search": True,
            "import_pdf": True,
            "import_zip": True,
            "import_folder_recursive": True,
            "write_drive": False,
        },
        "user": user,
        "error": error,
    }


def effective_mime(item: dict[str, Any]) -> str:
    if item.get("mimeType") == SHORTCUT_MIME:
        return str((item.get("shortcutDetails") or {}).get("targetMimeType") or "")
    return str(item.get("mimeType") or "")


def effective_id(item: dict[str, Any]) -> str:
    if item.get("mimeType") == SHORTCUT_MIME:
        return str((item.get("shortcutDetails") or {}).get("targetId") or item.get("id") or "")
    return str(item.get("id") or "")


def supported_item(item: dict[str, Any]) -> bool:
    mime = effective_mime(item)
    name = str(item.get("name") or "").lower()
    return mime == FOLDER_MIME or mime == PDF_MIME or name.endswith(".pdf") or name.endswith(".zip")


def _public_item(item: dict[str, Any]) -> dict[str, Any]:
    mime = effective_mime(item)
    size = str(item.get("size") or "")
    return {
        "id": str(item.get("id") or ""),
        "effective_id": effective_id(item),
        "name": item.get("name") or "",
        "mime_type": mime,
        "is_folder": mime == FOLDER_MIME,
        "is_shortcut": item.get("mimeType") == SHORTCUT_MIME,
        "size": int(size) if size.isdigit() else None,
        "modified_time": item.get("modifiedTime"),
        "parents": tuple(item.get("parents") or ()),
    }


def _escape_drive_query_literal(value: str) -> str:
    """Escape a string embedded in a Drive API single-quoted query literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _clean_search_term(value: str) -> str:
    term = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(term) < 2:
        raise GoogleDriveError("La búsqueda necesita al menos 2 caracteres")
    if len(term) > 200:
        raise GoogleDriveError("La búsqueda es demasiado larga")
    return term


def list_folder(folder_id: str = "root") -> dict[str, Any]:
    svc = service()
    q = f"'{_escape_drive_query_literal(folder_id)}' in parents and trashed = false"
    items: list[dict[str, Any]] = []
    token = None
    while True:
        result = svc.files().list(
            q=q,
            spaces="drive",
            pageSize=1000,
            pageToken=token,
            fields=f"nextPageToken,files({FILE_FIELDS})",
            orderBy="folder,name_natural",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        items.extend(result.get("files") or [])
        token = result.get("nextPageToken")
        if not token:
            break
    out = [_public_item(item) for item in items if supported_item(item)]
    folder_name = "Mi unidad" if folder_id == "root" else folder_id
    if folder_id != "root":
        try:
            meta = svc.files().get(fileId=folder_id, fields="id,name,parents", supportsAllDrives=True).execute()
            folder_name = meta.get("name") or folder_id
        except Exception:
            pass
    return {"folder_id": folder_id, "folder_name": folder_name, "items": out}


def search_items(query: str, *, max_results: int = 100) -> dict[str, Any]:
    """Search supported Drive items by name across accessible Drive spaces.

    The server-side query is deliberately limited to file names. BiblioRef does
    not index document contents and does not broaden the OAuth scope.
    """
    term = _clean_search_term(query)
    limit = max(1, min(int(max_results), MAX_SEARCH_RESULTS))
    svc = service()
    escaped = _escape_drive_query_literal(term)
    drive_q = f"trashed = false and name contains '{escaped}'"
    out: list[dict[str, Any]] = []
    token = None
    exhausted = False
    # We may need more than `limit` raw rows because unsupported Drive items are
    # filtered locally. Pagination stops as soon as enough supported rows exist.
    while len(out) < limit and not exhausted:
        result = svc.files().list(
            q=drive_q,
            spaces="drive",
            pageSize=min(1000, max(50, limit * 2)),
            pageToken=token,
            fields=f"nextPageToken,files({FILE_FIELDS})",
            orderBy="folder,name_natural",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        for item in result.get("files") or []:
            if supported_item(item):
                out.append(_public_item(item))
                if len(out) >= limit:
                    break
        token = result.get("nextPageToken")
        exhausted = not bool(token)
    return {
        "query": term,
        "items": out[:limit],
        "limit": limit,
        "truncated": bool(token) or len(out) > limit,
        "integration_version": GOOGLE_DRIVE_INTEGRATION_VERSION,
    }


def get_item(file_id: str) -> dict[str, Any]:
    svc = service()
    item = svc.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,parents,shortcutDetails(targetId,targetMimeType)",
        supportsAllDrives=True,
    ).execute()
    return item


def iter_folder_files(folder_id: str, *, recursive: bool = True) -> Iterable[dict[str, Any]]:
    listing = list_folder(folder_id)
    for item in listing["items"]:
        if item["is_folder"]:
            if recursive:
                yield from iter_folder_files(item["effective_id"], recursive=True)
        else:
            yield item


def download_blob(file_id: str, destination: str | Path) -> Path:
    svc = service()
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    with target.open("wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=4 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return target


__all__ = [
    "GOOGLE_DRIVE_INTEGRATION_VERSION", "DRIVE_READONLY_SCOPE", "FOLDER_MIME",
    "GOOGLE_DRIVE_LIBS_AVAILABLE", "GoogleDriveError", "validate_client_secret_data",
    "save_client_secret_bytes", "connect", "disconnect", "status", "list_folder", "search_items",
    "get_item", "iter_folder_files", "download_blob", "supported_item", "effective_mime", "effective_id",
]
