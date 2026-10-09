# -*- coding: utf-8 -*-
"""OAI-PMH 2.0 client (oai-pmh-0.1).

A generic protocol client. It knows OAI-PMH; it knows nothing about any
particular repository, university or country, and it must stay that way — a
repository is configuration, not an algorithm.

This layer harvests *metadata*. It does not fetch PDFs, and it does not
execute, render or interpret anything it receives.
"""
from __future__ import annotations

import functools
import time
import xml.etree.ElementTree as ET
from typing import Callable, Dict, Iterator, List, Mapping, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .connector import (
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

OAI_PMH_CLIENT_VERSION = "oai-pmh-0.1"
PROTOCOL = "oai-pmh"

OAI_NS = "http://www.openarchives.org/OAI/2.0/"
OAI_DC_NS = "http://www.openarchives.org/OAI/2.0/oai_dc/"
DC_NS = "http://purl.org/dc/elements/1.1/"

DEFAULT_METADATA_PREFIX = "oai_dc"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_PAGES = 500
DEFAULT_USER_AGENT = f"BiblioRef/{OAI_PMH_CLIENT_VERSION} (+metadata harvesting)"
#: Seconds between live requests. Repositories answer 429 to an impatient
#: harvester, so the default network transport paces itself.
DEFAULT_MIN_REQUEST_INTERVAL = 1.0
DEFAULT_MAX_RETRIES = 3
#: Longest delay honoured from a ``Retry-After`` header or a backoff.
MAX_RETRY_DELAY = 60.0
RETRYABLE_STATUSES = frozenset({429, 503})

#: ``(url, headers, timeout) -> response bytes``. Injectable so the protocol
#: can be tested without a network.
Transport = Callable[[str, Mapping[str, str], float], bytes]

# Dublin Core element -> RepositoryRecord field holding its repeated values.
_DC_TUPLE_FIELDS = {
    "creator": "creators",
    "date": "dates",
    "type": "types",
    "subject": "subjects",
    "language": "languages",
    "description": "descriptions",
    "identifier": "identifiers",
    "rights": "rights",
}


def _read_limited(reader, max_bytes: int) -> bytes:
    """Read at most ``max_bytes``; refuse anything longer.

    Reads one byte past the budget so an oversized body is detected instead of
    being silently truncated into a "valid" document.
    """
    payload = reader.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise RepositoryResponseTooLarge(
            f"response exceeds {max_bytes} bytes", limit=max_bytes
        )
    return payload


def _urllib_transport(
    url: str,
    headers: Mapping[str, str],
    timeout: float,
    *,
    max_bytes: int,
) -> bytes:
    request = Request(url, headers=dict(headers), method="GET")
    with urlopen(request, timeout=timeout) as response:  # nosec - scheme validated upstream
        return _read_limited(response, max_bytes)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(element: Optional[ET.Element]) -> Optional[str]:
    """Collapse an element's text, or ``None`` when there is nothing to keep.

    Whitespace runs collapse because XML pretty-printing splits long titles
    across lines. Characters are never transliterated or stripped.
    """
    if element is None or element.text is None:
        return None
    text = " ".join(element.text.split())
    return text or None


def _texts(parent: ET.Element, namespace: str, name: str) -> Tuple[str, ...]:
    values: List[str] = []
    for child in parent.findall(f"{{{namespace}}}{name}"):
        text = _text(child)
        if text:
            values.append(text)
    return tuple(values)


class OaiPmhConnector:
    """Harvest Dublin Core metadata from an OAI-PMH 2.0 endpoint."""

    def __init__(
        self,
        source: RepositorySource,
        *,
        transport: Optional[Transport] = None,
        metadata_prefix: str = DEFAULT_METADATA_PREFIX,
        timeout: float = DEFAULT_TIMEOUT,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_pages: int = DEFAULT_MAX_PAGES,
        user_agent: str = DEFAULT_USER_AGENT,
        min_request_interval: Optional[float] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if source.protocol != PROTOCOL:
            raise ValueError(
                f"OaiPmhConnector requires protocol {PROTOCOL!r}, got {source.protocol!r}"
            )
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self.source = source
        self.metadata_prefix = metadata_prefix
        self.timeout = float(timeout)
        self.max_response_bytes = int(max_response_bytes)
        self.max_pages = int(max_pages)
        self.user_agent = user_agent
        self.max_retries = max(0, int(max_retries))
        self._transport: Transport = transport or functools.partial(
            _urllib_transport, max_bytes=self.max_response_bytes
        )
        # Pacing belongs to the network: an injected transport is a test
        # double or a cache, and slowing it down would buy nothing.
        if min_request_interval is None:
            min_request_interval = 0.0 if transport is not None else DEFAULT_MIN_REQUEST_INTERVAL
        self.min_request_interval = max(0.0, float(min_request_interval))
        self._sleep = sleeper
        self._last_request_at: Optional[float] = None

    # -- transport ---------------------------------------------------------

    def _pace(self) -> None:
        """Keep a minimum distance between two live requests."""
        if self.min_request_interval <= 0:
            return
        if self._last_request_at is not None:
            waited = time.monotonic() - self._last_request_at
            remaining = self.min_request_interval - waited
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = time.monotonic()

    def _retry_delay(self, error: HTTPError, attempt: int) -> float:
        """How long to wait before retrying: the server's word, or a backoff."""
        headers = getattr(error, "headers", None)
        raw = headers.get("Retry-After") if headers is not None else None
        if raw is not None:
            try:
                return min(MAX_RETRY_DELAY, max(0.0, float(str(raw).strip())))
            except ValueError:
                pass  # an HTTP-date; fall back to our own backoff
        base = self.min_request_interval or 1.0
        return min(MAX_RETRY_DELAY, base * (2**attempt))

    def _fetch(self, params: Mapping[str, str]) -> bytes:
        url = f"{self.source.base_url}?{urlencode(params)}"
        headers = {"User-Agent": self.user_agent, "Accept": "text/xml"}
        attempt = 0
        while True:
            try:
                self._pace()
                payload = self._transport(url, headers, self.timeout)
            except HTTPError as exc:
                # 429/503 is the repository asking for patience, not a failure.
                if exc.code in RETRYABLE_STATUSES and attempt < self.max_retries:
                    self._sleep(self._retry_delay(exc, attempt))
                    attempt += 1
                    continue
                raise RepositoryTransportError(
                    f"HTTP {exc.code} from {self.source.id}", status=exc.code
                ) from exc
            except RepositoryResponseTooLarge:
                raise
            except OSError as exc:  # URLError, timeouts, connection resets
                raise RepositoryTransportError(f"transport failure: {exc}") from exc
            if len(payload) > self.max_response_bytes:
                raise RepositoryResponseTooLarge(
                    f"response exceeds {self.max_response_bytes} bytes",
                    limit=self.max_response_bytes,
                )
            return payload

    def _request(self, verb: str, **params: Optional[str]) -> ET.Element:
        """Perform one OAI-PMH request and return the verb's element."""
        query = {"verb": verb}
        query.update({key: value for key, value in params.items() if value is not None})
        payload = self._fetch(query)
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise RepositoryMalformedResponse(f"invalid XML from {self.source.id}: {exc}") from exc
        if root.tag != f"{{{OAI_NS}}}OAI-PMH":
            raise RepositoryMalformedResponse(
                f"not an OAI-PMH response (root element {root.tag!r})"
            )
        error = root.find(f"{{{OAI_NS}}}error")
        if error is not None:
            raise RepositoryOaiError(
                error.get("code") or "unknownError", _text(error) or ""
            )
        element = root.find(f"{{{OAI_NS}}}{verb}")
        if element is None:
            raise RepositoryMalformedResponse(f"response carries no <{verb}> element")
        return element

    # -- verbs -------------------------------------------------------------

    def identify(self) -> RepositoryIdentity:
        element = self._request("Identify")
        return RepositoryIdentity(
            repository_name=_text(element.find(f"{{{OAI_NS}}}repositoryName")) or "",
            base_url=_text(element.find(f"{{{OAI_NS}}}baseURL")) or self.source.base_url,
            protocol_version=_text(element.find(f"{{{OAI_NS}}}protocolVersion")) or "",
            earliest_datestamp=_text(element.find(f"{{{OAI_NS}}}earliestDatestamp")),
            deleted_record_policy=_text(element.find(f"{{{OAI_NS}}}deletedRecord")),
            granularity=_text(element.find(f"{{{OAI_NS}}}granularity")),
            admin_emails=_texts(element, OAI_NS, "adminEmail"),
        )

    def list_metadata_formats(self) -> Tuple[RepositoryMetadataFormat, ...]:
        element = self._request("ListMetadataFormats")
        formats = []
        for node in element.findall(f"{{{OAI_NS}}}metadataFormat"):
            prefix = _text(node.find(f"{{{OAI_NS}}}metadataPrefix"))
            if not prefix:
                continue
            formats.append(
                RepositoryMetadataFormat(
                    prefix=prefix,
                    schema=_text(node.find(f"{{{OAI_NS}}}schema")),
                    namespace=_text(node.find(f"{{{OAI_NS}}}metadataNamespace")),
                )
            )
        return tuple(formats)

    def _paginated(self, verb: str, params: Dict[str, Optional[str]]) -> Iterator[ET.Element]:
        """Yield each page's element, following ``resumptionToken``.

        Shared by every list verb: ListSets pages just like ListRecords, and a
        repository with hundreds of collections would otherwise be silently
        truncated at its first page.
        """
        seen_tokens: set[str] = set()
        pages = 0
        while True:
            if pages >= self.max_pages:
                raise RepositoryProtocolError(
                    f"{verb} exceeded its budget of {self.max_pages} page(s) "
                    f"on {self.source.id}"
                )
            element = self._request(verb, **params)
            pages += 1
            yield element

            token = _text(element.find(f"{{{OAI_NS}}}resumptionToken"))
            if not token:
                return
            if token in seen_tokens:
                raise RepositoryProtocolError(
                    f"repeated resumptionToken {token!r} from {self.source.id}"
                )
            seen_tokens.add(token)
            # Once resuming, the token is the only legal parameter besides the verb.
            params = {"resumptionToken": token}

    def list_sets(self) -> Tuple[RepositorySet, ...]:
        nodes = (
            node
            for page in self._paginated("ListSets", {})
            for node in page.findall(f"{{{OAI_NS}}}set")
        )
        sets = []
        for node in nodes:
            spec = _text(node.find(f"{{{OAI_NS}}}setSpec"))
            if not spec:
                continue
            sets.append(
                RepositorySet(
                    spec=spec,
                    name=_text(node.find(f"{{{OAI_NS}}}setName")) or spec,
                    description=self._set_description(node),
                )
            )
        return tuple(sets)

    @staticmethod
    def _set_description(node: ET.Element) -> Optional[str]:
        """Flatten ``setDescription`` into readable text, if there is any.

        The element is a container for arbitrary XML, so the text of its
        descendants is all that can be promised across repositories.
        """
        description = node.find(f"{{{OAI_NS}}}setDescription")
        if description is None:
            return None
        chunks = [" ".join((element.text or "").split()) for element in description.iter()]
        text = " ".join(chunk for chunk in chunks if chunk)
        return text or None

    def get_record(
        self,
        identifier: str,
        *,
        metadata_prefix: Optional[str] = None,
    ) -> RepositoryRecord:
        element = self._request(
            "GetRecord",
            identifier=identifier,
            metadataPrefix=metadata_prefix or self.metadata_prefix,
        )
        node = element.find(f"{{{OAI_NS}}}record")
        if node is None:
            raise RepositoryMalformedResponse("GetRecord response carries no <record>")
        return self._record(node)

    def harvest(
        self,
        *,
        set_spec: Optional[str] = None,
        from_date: Optional[str] = None,
        until_date: Optional[str] = None,
        metadata_prefix: Optional[str] = None,
    ) -> Iterator[RepositoryRecord]:
        """Yield every matching record, following ``resumptionToken`` paging.

        ``from_date``/``until_date`` filter the repository's datestamps — when
        a record was deposited or modified, not when the work was published.
        """
        params: Dict[str, Optional[str]] = {
            "metadataPrefix": metadata_prefix or self.metadata_prefix,
            "set": set_spec,
            "from": from_date,
            "until": until_date,
        }
        pages = self._paginated("ListRecords", params)
        while True:
            try:
                page = next(pages)
            except StopIteration:
                return
            except RepositoryOaiError as exc:
                if exc.code == "noRecordsMatch":
                    # An empty result, not a failure: the filters matched nothing.
                    return
                raise
            for node in page.findall(f"{{{OAI_NS}}}record"):
                yield self._record(node)

    # -- record mapping ----------------------------------------------------

    def _record(self, node: ET.Element) -> RepositoryRecord:
        header = node.find(f"{{{OAI_NS}}}header")
        if header is None:
            raise RepositoryMalformedResponse("record carries no <header>")
        identifier = _text(header.find(f"{{{OAI_NS}}}identifier"))
        if not identifier:
            raise RepositoryMalformedResponse("record header carries no <identifier>")

        deleted = (header.get("status") or "").strip().lower() == "deleted"
        raw = self._raw_metadata(node)
        fields = {
            attribute: raw.get(element, ())
            for element, attribute in _DC_TUPLE_FIELDS.items()
        }
        titles = raw.get("title", ())
        return RepositoryRecord(
            repository_id=self.source.id,
            identifier=identifier,
            datestamp=_text(header.find(f"{{{OAI_NS}}}datestamp")),
            title=titles[0] if titles else None,
            sets=_texts(header, OAI_NS, "setSpec"),
            deleted=deleted,
            raw_metadata=raw,
            **fields,
        )

    @staticmethod
    def _raw_metadata(node: ET.Element) -> Dict[str, Tuple[str, ...]]:
        """Collect every metadata value, keyed by element local name.

        Deleted records and records whose format carries no payload simply
        have nothing to collect; that is not an error.
        """
        metadata = node.find(f"{{{OAI_NS}}}metadata")
        if metadata is None:
            return {}
        container = metadata.find(f"{{{OAI_DC_NS}}}dc")
        if container is None:
            # Another metadata format, or oai_dc under an unexpected wrapper:
            # take the single child element the protocol guarantees.
            children = list(metadata)
            if not children:
                return {}
            container = children[0]
        collected: Dict[str, List[str]] = {}
        for child in container:
            text = _text(child)
            if not text:
                continue
            collected.setdefault(_local_name(child.tag), []).append(text)
        return {key: tuple(values) for key, values in collected.items()}


__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MIN_REQUEST_INTERVAL",
    "DEFAULT_MAX_PAGES",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DEFAULT_METADATA_PREFIX",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "OAI_PMH_CLIENT_VERSION",
    "OaiPmhConnector",
    "Transport",
]
