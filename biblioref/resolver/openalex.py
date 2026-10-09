# -*- coding: utf-8 -*-
"""OpenAlex API backend for BiblioRef metadata resolution.

OpenAlex is optional and downstream. It receives only citation metadata, never
PDF bytes, and returned candidates remain separate from parser output.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Mapping, Optional, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Candidate, ResolverQuery
from .normalize import clean_text

OPENALEX_BACKEND_VERSION = "openalex-v0.2"
DEFAULT_BASE_URL = "https://api.openalex.org"

# OpenAlex answers HTTP 400 for some punctuation in ``search`` instead of
# ignoring it. The question mark is the common case, and it is not rare in this
# domain: titles phrased as questions are ordinary in psychology, and every one
# of them was failing. Search is tokenised anyway, so dropping punctuation
# keeps the words and costs nothing.
_SEARCH_UNSAFE_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def search_text(value: Any) -> str:
    """Reduce a title to text the ``search`` parameter accepts."""
    text = _SEARCH_UNSAFE_RE.sub(" ", clean_text(value))
    return re.sub(r"\s+", " ", text).strip()

JsonTransport = Callable[[str, Mapping[str, str], float], Mapping[str, Any]]


def _default_transport(url: str, headers: Mapping[str, str], timeout: float) -> Mapping[str, Any]:
    request = Request(url, headers=dict(headers), method="GET")
    with urlopen(request, timeout=timeout) as response:  # nosec - fixed API URL by default
        return json.loads(response.read().decode("utf-8"))


def _authors(item: Mapping[str, Any]) -> Sequence[Dict[str, Any]]:
    out = []
    for authorship in item.get("authorships") or ():
        if not isinstance(authorship, Mapping):
            continue
        author = authorship.get("author")
        if not isinstance(author, Mapping):
            continue
        name = clean_text(author.get("display_name"))
        if name:
            out.append({"display_name": name})
    return tuple(out)


def _container(item: Mapping[str, Any]) -> Optional[str]:
    location = item.get("primary_location")
    if not isinstance(location, Mapping):
        return None
    source = location.get("source")
    if not isinstance(source, Mapping):
        return None
    return clean_text(source.get("display_name")) or None


def _candidate(item: Mapping[str, Any], *, method: str, rank: int) -> Candidate:
    mapped = {
        "id": item.get("id"),
        "doi": item.get("doi"),
        "title": item.get("title") or item.get("display_name"),
        "authors": _authors(item),
        "publication_year": item.get("publication_year"),
        "container_title": _container(item),
        "type": item.get("type"),
        "url": item.get("id"),
        "score": item.get("relevance_score"),
    }
    return Candidate.from_mapping(
        "openalex",
        mapped,
        source_id=item.get("id"),
        retrieval_method=method,
        provider_score=item.get("relevance_score"),
        rank=rank,
    )


class OpenAlexBackend:
    """Resolve parsed references against OpenAlex Works."""

    name = "openalex"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        rows: int = 5,
        timeout: float = 10.0,
        base_url: str = DEFAULT_BASE_URL,
        transport: JsonTransport = _default_transport,
    ) -> None:
        self.api_key = clean_text(api_key) or None
        self.rows = max(1, min(int(rows), 20))
        self.timeout = float(timeout)
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "BiblioRef-metadata-resolver/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, params: Mapping[str, str]) -> Mapping[str, Any]:
        url = f"{self.base_url}/works?{urlencode(dict(params))}"
        payload = self.transport(url, self._headers(), self.timeout)
        if not isinstance(payload, Mapping):
            raise ValueError("OpenAlex response is not a JSON object")
        return payload

    def search(self, query: ResolverQuery) -> Sequence[Candidate]:
        if query.doi:
            return self._by_doi(query.doi)
        return self._by_search(query)

    def _by_doi(self, doi: str) -> Sequence[Candidate]:
        payload = self._request({
            "filter": f"doi:https://doi.org/{doi}",
            "per_page": str(self.rows),
        })
        results = payload.get("results")
        if not isinstance(results, list):
            return ()
        return tuple(
            _candidate(item, method="doi_exact", rank=index)
            for index, item in enumerate(results, start=1)
            if isinstance(item, Mapping)
        )

    def _by_search(self, query: ResolverQuery) -> Sequence[Candidate]:
        text = search_text(query.title or query.raw_reference)
        if not text:
            return ()
        params = {
            "search": text,
            "per_page": str(self.rows),
        }
        if query.year:
            params["filter"] = f"publication_year:{query.year}"
        payload = self._request(params)
        results = payload.get("results")
        if not isinstance(results, list):
            return ()
        return tuple(
            _candidate(item, method="title_search", rank=index)
            for index, item in enumerate(results, start=1)
            if isinstance(item, Mapping)
        )
