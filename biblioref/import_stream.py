"""Incremental local imports with durable per-PDF results and real progress."""
from __future__ import annotations

import asyncio
from concurrent.futures import FIRST_COMPLETED, wait
from concurrent.futures.process import BrokenProcessPool
import json
from pathlib import Path
import queue
import shutil
import tempfile
import threading
import time
import uuid

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from biblioref.ingestion import extract_pdfs_from_zip, ZipIngestionError
from biblioref.projects import project_tree, relative_path
from biblioref.pdf_workers import get_pool, prepare_pdf, worker_count, discard_broken_pool
from biblioref.duplicates import DuplicateDocument, content_hash, sha256_file


async def stage_and_stream(app, files, project):
    temporary = tempfile.TemporaryDirectory(prefix="biblioref_import_", dir=str(app.WORKSPACE))
    root = Path(temporary.name)
    staged, warnings = [], []
    try:
        for uploaded in files:
            if not uploaded.filename:
                continue
            try:
                logical = relative_path(uploaded.filename)
            except ValueError as exc:
                warnings.append(f"Archivo omitido: {exc}")
                continue
            name = app._safe_name(logical.rsplit("/", 1)[-1])
            if not name.lower().endswith((".pdf", ".zip")):
                warnings.append(f"Formato omitido: {name}")
                continue
            path = root / f"{uuid.uuid4().hex}{Path(name).suffix}"

            def copy_upload():
                with path.open("wb") as target:
                    shutil.copyfileobj(uploaded.file, target, length=4 * 1024 * 1024)

            await asyncio.to_thread(copy_upload)
            staged.append((path, name, {"relative_path": logical, "project_id": project["id"],
                "source": "folder" if "/" in logical else ("zip" if name.lower().endswith(".zip") else "local_upload")}))
    except BaseException:
        temporary.cleanup()
        raise

    events = queue.Queue()
    disconnected = threading.Event()

    def emit(kind, **data):
        if not disconnected.is_set():
            events.put({"type": kind, **data})

    def run():
        started = time.monotonic()
        imported = completed = skipped = 0
        pool = None
        pending = {}
        try:
            candidates = []
            for index, (path, name, context) in enumerate(staged):
                emit("progress", phase="discover", filename=name, file_index=index + 1,
                     file_total=len(staged), elapsed_seconds=round(time.monotonic() - started))
                if path.suffix.lower() == ".pdf":
                    candidates.append((path, name, context))
                    continue
                try:
                    pdfs, notices = extract_pdfs_from_zip(path, root / f"zip_{index}")
                    warnings.extend(notices)
                    for item in pdfs:
                        provenance = item.provenance()
                        provenance.update(context)
                        chain = list(provenance.get("archive_chain") or [])
                        if chain:
                            chain[0] = name
                        provenance.update(archive_chain=chain, container_filename=name, archive_filename=name)
                        candidates.append((item.path, app._safe_name(item.display_name), provenance))
                except ZipIngestionError as exc:
                    warnings.append(f"{name}: {exc}")
            # The same PDF (by its bytes) is added once: not again if it is already in the
            # project, and not twice when a folder and a ZIP of that folder are loaded together.
            with app.STORE.lock:
                known = {}
                for existing in app.STORE.docs().values():
                    if existing.get("project_id") == project["id"]:
                        digest = content_hash(existing)
                        if digest:
                            known.setdefault(digest, existing)
            unique = []
            for path, name, context in candidates:
                try:
                    digest = context.get("sha256") or sha256_file(path)
                except OSError as exc:
                    warnings.append(f"{name}: no se pudo leer ({exc}).")
                    continue
                context["sha256"] = digest
                if digest in known:
                    other = known[digest]
                    code = other.get("thesis_id") if isinstance(other, dict) else other
                    where = "en el proyecto" if isinstance(other, dict) else "en esta misma carga"
                    warnings.append(f"{name}: ya estaba {where} como {code} (mismo archivo); no se volvió a agregar.")
                    skipped += 1
                    continue
                known[digest] = f"«{name}»"
                unique.append((path, name, context))
            candidates = unique
            total = len(candidates)
            if not total:
                if skipped:
                    emit("done", imported=0, skipped_duplicates=skipped, warnings=warnings,
                         elapsed_seconds=round(time.monotonic() - started))
                    return
                raise ValueError("No se encontró ningún PDF para cargar. " + "; ".join(warnings[:5]))
            capacity = min(worker_count(), total)
            pool = get_pool()
            todo = iter(candidates)

            def fill():
                while len(pending) < capacity:
                    item = next(todo, None)
                    if item is None:
                        break
                    path, name, _ = item
                    pending[pool.submit(prepare_pdf, str(path), name)] = (item, time.monotonic())

            def progress():
                now = time.monotonic()
                emit("progress", phase="read", total=total, completed=completed, imported=imported,
                     workers=capacity, elapsed_seconds=round(now - started),
                     active=[{"filename": item[2].get("archive_member") or item[2].get("relative_path") or item[1],
                              "seconds": round(now - since)} for item, since in pending.values()])

            fill()
            progress()
            while pending:
                finished, _ = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
                for future in finished:
                    (path, name, provenance), _ = pending.pop(future)
                    try:
                        result = future.result()
                    except BrokenProcessPool:
                        raise
                    except Exception as exc:
                        warnings.append(f"{name}: {exc}")
                        completed += 1
                        continue
                    destination = app.UPLOAD_DIR / f"doc_{uuid.uuid4().hex}_{name}"
                    shutil.move(str(path), destination)
                    # A single owner assigns IDs and saves. A failed checkpoint
                    # must never be announced as a successfully saved document.
                    with app.STORE.lock:
                        try:
                            doc = app._register_prepared_document(destination, name, provenance,
                                result["preflight"], result["title"], result["title_source"], extras=result["extras"])
                        except DuplicateDocument as exc:
                            destination.unlink(missing_ok=True)
                            warnings.append(str(exc))
                            skipped += 1
                            completed += 1
                            continue
                        project["updated_at"] = time.time()
                        try:
                            app.STORE.save()
                        except Exception:
                            app.STORE.docs().pop(doc["id"], None)
                            destination.unlink(missing_ok=True)
                            raise
                    imported += 1
                    completed += 1
                    emit("document", document=app._public_doc(doc, True),
                         tree_branch=project_tree(project, [doc]))
                fill()
                progress()
            if not imported:
                raise ValueError("No se pudo abrir ningún PDF. " + "; ".join(warnings[:5]))
            temporary.cleanup()
            emit("done", imported=imported, skipped_duplicates=skipped, warnings=warnings,
                 elapsed_seconds=round(time.monotonic() - started))
        except Exception as exc:
            if isinstance(exc, BrokenProcessPool) and pool is not None:
                discard_broken_pool(pool)
            message = ("Se interrumpió uno de los procesos de lectura. Las tesis ya guardadas se conservan."
                       if isinstance(exc, BrokenProcessPool) else str(exc))
            emit("error", detail=message, imported=imported, warnings=warnings)
        finally:
            # Wait before removing files still opened by a process (also Windows).
            for future in pending:
                future.cancel()
            if pending:
                wait(pending)
            temporary.cleanup()

    async def stream():
        threading.Thread(target=run, name="biblioref-import", daemon=True).start()
        try:
            while True:
                try:
                    event = await asyncio.to_thread(events.get, True, 1.0)
                except queue.Empty:
                    event = {"type": "heartbeat"}
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if event["type"] in {"done", "error"}:
                    break
        finally:
            # Continue checkpointing the batch if the tab closes. Never hold a
            # disconnected client's event queue in memory for the entire batch.
            disconnected.set()

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})
