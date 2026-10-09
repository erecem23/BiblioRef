# -*- coding: utf-8 -*-
"""Crossref REST backend for BiblioRef metadata resolution.

Crossref is an optional downstream service. Only citation/reference metadata is
sent; this module never uploads a PDF and never writes back to parser output.
Network transport is injectable so tests remain fully offline.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, Mapping, Optional, Sequence
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .models import Candidate, ResolverQuery
from .normalize import clean_text

CROSSREF_BACKEND_VERSION = "crossref-v0.1"
DEFAULT_BASE_URL = "https://api.crossref.org/v1"

JsonTransport = Callable[[str, Mapping[str, str], float], Mapping[str, Any]]


def _default_transport(url: str, headers: Mapping[str, str], timeout: float) -> Mapping[str, Any]:
    request = Request(url, headers=dict(headers), method="GET")
    with urlopen(request, timeout=timeout) as response:  # nosec - fixed API URL by default
        return json.loads(response.read().decode("utf-8"))


def _first(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return next((item for item in value if clean_text(item)), None)
    return value


def _crossref_year(item: Mapping[str, Any]) -> Optional[str]:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        obj = item.get(key)
        if not isinstance(obj, Mapping):
            continue
        parts = obj.get("date-parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            try:
                year = int(parts[0][0])
            except (TypeError, ValueError):
                continue
            if 1800 <= year <= 2099:
                return str(year)
    return None


def _author_rows(value: Any) -> Sequence[Dict[str, Any]]:
    if not isinstance(value, list):
        return ()
    out = []
    for author in value:
        if not isinstance(author, Mapping):
            continue
        out.append({
            "family": author.get("family"),
            "given": author.get("given"),
            "literal": author.get("name"),
        })
    return tuple(out)


def _candidate(item: Mapping[str, Any], *, method: str, rank: int) -> Candidate:
    mapped = {
        "id": item.get("DOI"),
        "DOI": item.get("DOI"),
        "title": _first(item.get("title")),
        "authors": _author_rows(item.get("author")),
        "year": _crossref_year(item),
        "container_title": _first(item.get("container-title")),
        "publisher": item.get("publisher"),
        "type": item.get("type"),
        "URL": item.get("URL"),
        "score": item.get("score"),
    }
    return Candidate.from_mapping(
        "crossref",
        mapped,
        source_id=item.get("DOI"),
        retrieval_method=method,
        provider_score=item.get("score"),
        rank=rank,
    )


class CrossrefBackend:
    """Resolve a parsed reference against the public Crossref REST API."""

    name = "crossref"

    def __init__(
        self,
        *,
        email: Optional[str] = None,
        rows: int = 5,
        timeout: float = 10.0,
        base_url: str = DEFAULT_BASE_URL,
        transport: JsonTransport = _default_transport,
    ) -> None:
        self.email = clean_text(email) or None
        self.rows = max(1, min(int(rows), 20))
        self.timeout = float(timeout)
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    def _headers(self) -> Dict[str, str]:
        agent = "BiblioRef-metadata-resolver/0.1"
        if self.email:
            agent += f" (mailto:{self.email})"
        return {"Accept": "application/json", "User-Agent": agent}

    def _request(self, url: str) -> Mapping[str, Any]:
        payload = self.transport(url, self._headers(), self.timeout)
        if not isinstance(payload, Mapping):
            raise ValueError("Crossref response is not a JSON object")
        return payload

    def search(self, query: ResolverQuery) -> Sequence[Candidate]:
        if query.doi:
            return self._by_doi(query.doi)
        return self._by_bibliographic_query(query)

    def _by_doi(self, doi: str) -> Sequence[Candidate]:
        url = f"{self.base_url}/works/{quote(doi, safe='')}"
        if self.email:
            url += "?" + urlencode({"mailto": self.email})
        payload = self._request(url)
        item = payload.get("message")
        if not isinstance(item, Mapping):
            return ()
        return (_candidate(item, method="doi_exact", rank=1),)

    def _by_bibliographic_query(self, query: ResolverQuery) -> Sequence[Candidate]:
        citation = query.raw_reference or " ".join(
            part for part in (
                query.authors[0] if query.authors else None,
                query.year,
                query.title,
                query.journal,
            ) if part
        )
        citation = clean_text(citation)
        if not citation:
            return ()
        params = {
            "query.bibliographic": citation,
            "rows": str(self.rows),
        }
        if self.email:
            params["mailto"] = self.email
        url = f"{self.base_url}/works?{urlencode(params)}"
        payload = self._request(url)
        message = payload.get("message")
        if not isinstance(message, Mapping):
            return ()
        items = message.get("items")
        if not isinstance(items, list):
            return ()
        return tuple(
            _candidate(item, method="query_bibliographic", rank=index)
            for index, item in enumerate(items, start=1)
            if isinstance(item, Mapping)
        )
