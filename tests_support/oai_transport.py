# -*- coding: utf-8 -*-
"""Offline transport double for the OAI-PMH connector tests.

The connector receives an injected transport, so every protocol test in this
suite runs without touching the network.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping
from urllib.parse import parse_qs, urlsplit

FIXTURES = Path(__file__).resolve().parent / "repository_fixtures"


def fixture_bytes(name: str) -> bytes:
    """Read an OAI-PMH fixture as raw bytes, exactly as HTTP would deliver it."""
    return (FIXTURES / name).read_bytes()


@dataclass(frozen=True)
class TransportCall:
    url: str
    headers: Dict[str, str]
    timeout: float

    @property
    def params(self) -> Dict[str, List[str]]:
        return parse_qs(urlsplit(self.url).query, keep_blank_values=True)

    def param(self, name: str) -> str | None:
        values = self.params.get(name)
        return values[0] if values else None


class FakeTransport:
    """Replay queued payloads and record every request the connector makes."""

    def __init__(self, *payloads: Any) -> None:
        self._payloads = list(payloads)
        self.calls: List[TransportCall] = []

    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> bytes:
        self.calls.append(TransportCall(url, dict(headers), timeout))
        if not self._payloads:
            raise AssertionError(f"unexpected extra request: {url}")
        payload = self._payloads.pop(0)
        if isinstance(payload, BaseException):
            raise payload
        return payload

    @property
    def urls(self) -> List[str]:
        return [call.url for call in self.calls]

    def call(self, index: int) -> TransportCall:
        return self.calls[index]
