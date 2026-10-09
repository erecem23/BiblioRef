# -*- coding: utf-8 -*-
"""Academic repository connectivity (repository-core-0.1).

This package turns a repository endpoint into interoperable metadata:

    OAI-PMH endpoint -> RepositoryRecord

It is deliberately isolated from the bibliographic pipeline. Repository,
institution, country, language and collection are provenance metadata — they
never act as signals for extraction, detection, segmentation, parsing or
StyleProfiler. Importing this package must not pull those modules in.

Fetching full text is a later phase; this one harvests metadata only.
"""
from __future__ import annotations

from .connector import (
    RepositoryConnector,
    RepositoryError,
    RepositoryMalformedResponse,
    RepositoryOaiError,
    RepositoryProtocolError,
    RepositoryResponseTooLarge,
    RepositoryTransportError,
)
from .models import (
    RepositoryIdentity,
    RepositoryMetadataFormat,
    RepositoryRecord,
    RepositorySet,
    RepositorySource,
)
from .oai import OAI_PMH_CLIENT_VERSION, OaiPmhConnector

REPOSITORY_CORE_VERSION = "repository-core-0.1"

__all__ = [
    "OAI_PMH_CLIENT_VERSION",
    "OaiPmhConnector",
    "REPOSITORY_CORE_VERSION",
    "RepositoryConnector",
    "RepositoryError",
    "RepositoryIdentity",
    "RepositoryMalformedResponse",
    "RepositoryMetadataFormat",
    "RepositoryOaiError",
    "RepositoryProtocolError",
    "RepositoryRecord",
    "RepositoryResponseTooLarge",
    "RepositorySet",
    "RepositorySource",
    "RepositoryTransportError",
]
