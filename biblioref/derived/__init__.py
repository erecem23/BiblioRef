# -*- coding: utf-8 -*-
"""Derived analysis store for BiblioRef.

A sqlite sidecar next to ``project.json``. It exists so that corpus-scale
resolution and bibliometrics do not have to be written into the project index,
which is loaded and rewritten whole on every edit.

Nothing in this package writes to ``project.json`` or to parser output, and
nothing here is authoritative: the tables are rebuilt from the project store,
with the single exception of ``resolution_cache``, which holds external backend
answers keyed by query content so they survive rebuilds.
"""

from .schema import (
    DERIVED_SCHEMA_VERSION,
    DERIVED_STORE_VERSION,
    connect,
    create_schema,
    schema_version,
)
from .sync import (
    DERIVED_FILENAME,
    QUERY_BUILD_VERSION,
    SyncReport,
    corpus_stats,
    default_project_file,
    default_store_path,
    default_workspace,
    open_store,
    query_for_reference,
    query_sha,
    source_fingerprint,
    sync_documents,
    sync_from_file,
)

__all__ = [
    "DERIVED_SCHEMA_VERSION",
    "DERIVED_STORE_VERSION",
    "DERIVED_FILENAME",
    "QUERY_BUILD_VERSION",
    "SyncReport",
    "connect",
    "create_schema",
    "schema_version",
    "corpus_stats",
    "default_project_file",
    "default_store_path",
    "default_workspace",
    "open_store",
    "query_for_reference",
    "query_sha",
    "source_fingerprint",
    "sync_documents",
    "sync_from_file",
]
