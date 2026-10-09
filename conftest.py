"""Aislamiento del workspace para toda la suite de tests.

``app`` fija su workspace al importarse (``BIBLIOREF_WORKSPACE`` o
``~/.biblioref/projects/default``) y ``Store.save`` reescribe ``project.json``
entero. El 2026-09-23 un test que reemplaza ``STORE.data`` en memoria y llama a
un endpoint que guarda dejó el proyecto real con un solo documento sintético.

pytest carga este archivo antes que cualquier módulo de test, así que ningún
test puede ver ni escribir el workspace real, aunque se corra sin variables de
entorno. Un test que necesite un workspace propio lo sigue fijando él.
"""
import os
import tempfile
from pathlib import Path

_REAL = (Path.home() / ".biblioref" / "projects" / "default").resolve()
_configured = os.environ.get("BIBLIOREF_WORKSPACE")
if not _configured or Path(_configured).resolve() == _REAL:
    os.environ["BIBLIOREF_WORKSPACE"] = tempfile.mkdtemp(prefix="biblioref_test_workspace_")


def pytest_sessionstart(session):
    workspace = Path(os.environ["BIBLIOREF_WORKSPACE"]).resolve()
    assert workspace != _REAL, "los tests nunca corren sobre el workspace real"
