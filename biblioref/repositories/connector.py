# -*- coding: utf-8 -*-
"""The connector contract and its error taxonomy.

Consumers depend on this protocol, not on any particular repository software.
A second implementation (DSpace REST, Invenio, EPrints…) must be able to
appear without any consumer noticing.
"""
from __future__ import annotations

from typing import Iterator, Optional, Protocol, Tuple, runtime_checkable

from .models import (
    RepositoryIdentity,
    RepositoryMetadataFormat,
    RepositoryRecord,
    RepositorySet,
)


class RepositoryError(Exception):
    """Base class for every repository-layer failure."""


class RepositoryTransportError(RepositoryError):
    """The response never arrived: network failure, timeout, HTTP 4xx/5xx."""

    def __init__(self, message: str, *, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status


class RepositoryResponseTooLarge(RepositoryError):
    """The response exceeded the configured byte budget and was refused."""

    def __init__(self, message: str, *, limit: Optional[int] = None) -> None:
        super().__init__(message)
        self.limit = limit


class RepositoryMalformedResponse(RepositoryError):
    """The response arrived but is not the document the protocol promises."""


class RepositoryProtocolError(RepositoryError):
    """The response is well formed but the exchange violates the protocol."""


class RepositoryOaiError(RepositoryProtocolError):
    """The repository answered with an OAI-PMH ``<error>`` element.

    The original ``code`` and ``message`` are preserved: ``idDoesNotExist``,
    ``badArgument`` and ``cannotDisseminateFormat`` mean different things and
    callers are entitled to tell them apart.
    """

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}" if message else code)


@runtime_checkable
class RepositoryConnector(Protocol):
    """What every repository connector must offer."""

    def identify(self) -> RepositoryIdentity:
        """Describe the repository itself."""

    def list_metadata_formats(self) -> Tuple[RepositoryMetadataFormat, ...]:
        """List the metadata formats the repository can disseminate."""

    def list_sets(self) -> Tuple[RepositorySet, ...]:
        """List the repository's harvestable subdivisions."""

    def get_record(self, identifier: str) -> RepositoryRecord:
        """Fetch one record by its repository identifier."""

    def harvest(
        self,
        *,
        set_spec: Optional[str] = None,
        from_date: Optional[str] = None,
        until_date: Optional[str] = None,
    ) -> Iterator[RepositoryRecord]:
        """Iterate records, transparently following the repository's paging.

        ``from_date`` and ``until_date`` are harvesting filters over the
        repository's own datestamps. They are not publication dates.
        """


__all__ = [
    "RepositoryConnector",
    "RepositoryError",
    "RepositoryMalformedResponse",
    "RepositoryOaiError",
    "RepositoryProtocolError",
    "RepositoryResponseTooLarge",
    "RepositoryTransportError",
]
