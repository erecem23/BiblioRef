# -*- coding: utf-8 -*-
"""Data contracts for academic repository provenance (repository-core-0.1).

These objects describe where a document came from. Provenance is metadata: it
never reaches detection, segmentation, parsing or StyleProfiler, and nothing
here decides what a document *says*.

Two rules shape the design:

* nothing is discarded — Dublin Core is repeatable, so every value a
  repository publishes is preserved, and normalisation ("which of these three
  dates is the publication year?") belongs to a later layer;
* nothing is required — a repository that omits title, author, language or
  rights yields a record, not an exception.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple
from urllib.parse import urlsplit

ALLOWED_SCHEMES = ("http", "https")


def _as_text_tuple(values: Any) -> Tuple[str, ...]:
    """Coerce a value into a tuple of strings without dropping duplicates."""
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,)
    if isinstance(values, Iterable):
        return tuple(str(value) for value in values)
    return (str(values),)


def _as_raw_metadata(values: Any) -> Dict[str, Tuple[str, ...]]:
    if not values:
        return {}
    if not isinstance(values, Mapping):
        raise TypeError("raw_metadata must be a mapping of field name to values")
    return {str(key): _as_text_tuple(value) for key, value in values.items()}


def _require_text(value: Any, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"RepositorySource.{field_name} must not be empty")
    return text


@dataclass(frozen=True)
class RepositorySource:
    """A configured repository endpoint.

    This is configuration, never algorithm: no code may branch on a particular
    repository's ``id`` to change how documents are read.
    """

    id: str
    name: str
    protocol: str
    base_url: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_text(self.id, "id"))
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "protocol", _require_text(self.protocol, "protocol"))
        base_url = _require_text(self.base_url, "base_url")
        parts = urlsplit(base_url)
        if parts.scheme.lower() not in ALLOWED_SCHEMES or not parts.netloc:
            raise ValueError(
                "RepositorySource.base_url must be an http(s) URL, got: " f"{base_url!r}"
            )
        object.__setattr__(self, "base_url", base_url)


@dataclass(frozen=True)
class RepositoryIdentity:
    """What a repository answers about itself (OAI-PMH ``Identify``)."""

    repository_name: str
    base_url: str
    protocol_version: str
    earliest_datestamp: Optional[str] = None
    deleted_record_policy: Optional[str] = None
    granularity: Optional[str] = None
    admin_emails: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "admin_emails", _as_text_tuple(self.admin_emails))


@dataclass(frozen=True)
class RepositorySet:
    """A harvestable subdivision of a repository (community, collection…)."""

    spec: str
    name: str
    description: Optional[str] = None


@dataclass(frozen=True)
class RepositoryMetadataFormat:
    """A metadata format the repository can disseminate."""

    prefix: str
    schema: Optional[str] = None
    namespace: Optional[str] = None


@dataclass(frozen=True)
class RepositoryRecord:
    """One record as the repository publishes it.

    The named fields are the common Dublin Core subset; ``raw_metadata`` keeps
    every field the repository actually sent, including the ones this contract
    does not name. Repeated values stay repeated.
    """

    repository_id: str
    identifier: str
    datestamp: Optional[str] = None

    title: Optional[str] = None

    creators: Tuple[str, ...] = ()
    dates: Tuple[str, ...] = ()
    types: Tuple[str, ...] = ()
    subjects: Tuple[str, ...] = ()
    languages: Tuple[str, ...] = ()
    descriptions: Tuple[str, ...] = ()
    identifiers: Tuple[str, ...] = ()
    rights: Tuple[str, ...] = ()

    sets: Tuple[str, ...] = ()
    deleted: bool = False

    raw_metadata: Dict[str, Tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "creators",
            "dates",
            "types",
            "subjects",
            "languages",
            "descriptions",
            "identifiers",
            "rights",
            "sets",
        ):
            object.__setattr__(self, name, _as_text_tuple(getattr(self, name)))
        object.__setattr__(self, "deleted", bool(self.deleted))
        object.__setattr__(self, "raw_metadata", _as_raw_metadata(self.raw_metadata))

    def values(self, name: str) -> Tuple[str, ...]:
        """Every value the repository published for a metadata field."""
        return self.raw_metadata.get(name, ())

    def first(self, name: str) -> Optional[str]:
        """The first published value of a field, or ``None``.

        A convenience for display. It is not a normalisation decision: the
        remaining values stay available through :meth:`values`.
        """
        values = self.values(name)
        return values[0] if values else None
