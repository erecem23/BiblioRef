from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator


_ACTIVE_CONTEXT: ContextVar["ExtractionContext | None"] = ContextVar(
    "biblioref_extraction_context", default=None
)


@dataclass
class ExtractionContext:
    resolved_path: str
    backend: str
    reuse_enabled: bool = True
    size_bytes: int | None = None
    mtime_ns: int | None = None
    full_layout: tuple[Any, ...] | None = None
    full_layout_y_tolerance: float | None = None
    full_layout_slice_safe: bool = False
    lines_by_page: dict[int, tuple[Any, ...]] = field(default_factory=dict)
    range_layout_cache: dict[tuple[int, int, float], tuple[Any, ...]] = field(default_factory=dict)
    page_dimensions_cache: dict[int, tuple[float, float]] = field(default_factory=dict)
    counters: Counter = field(default_factory=Counter)
    timings: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    @classmethod
    def for_pdf(cls, pdf_path, backend: str, reuse_enabled: bool = True):
        path = Path(pdf_path).expanduser().resolve()
        return cls(
            resolved_path=str(path),
            backend=str(backend),
            reuse_enabled=bool(reuse_enabled),
        )

    def matches(self, pdf_path, backend: str) -> bool:
        return (
            str(Path(pdf_path).expanduser().resolve()) == self.resolved_path
            and str(backend) == self.backend
        )

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[str(name)] += int(value)

    def register_full_layout(self, lines, *, y_tolerance: float, slice_safe: bool) -> None:
        frozen = tuple(lines)
        grouped: dict[int, list[Any]] = defaultdict(list)
        for line in frozen:
            grouped[int(line.page)].append(line)
        self.full_layout = frozen
        self.full_layout_y_tolerance = float(y_tolerance)
        self.full_layout_slice_safe = bool(slice_safe)
        self.lines_by_page = {
            page: tuple(page_lines) for page, page_lines in grouped.items()
        }

    def get_cached_range(self, start_page: int, end_page: int, y_tolerance: float):
        return self.range_layout_cache.get(
            (int(start_page), int(end_page), float(y_tolerance))
        )

    def store_cached_range(
        self,
        start_page: int,
        end_page: int,
        y_tolerance: float,
        lines,
    ) -> None:
        self.range_layout_cache[
            (int(start_page), int(end_page), float(y_tolerance))
        ] = tuple(lines)

    def get_cached_dimensions(self, page_number: int):
        return self.page_dimensions_cache.get(int(page_number))

    def store_cached_dimensions(self, page_number: int, dimensions) -> None:
        width, height = dimensions
        self.page_dimensions_cache[int(page_number)] = (float(width), float(height))

    def get_full_layout_range(
        self,
        start_page: int,
        end_page: int,
        y_tolerance: float,
    ):
        if not self.reuse_enabled or not self.full_layout_slice_safe:
            return None
        if self.full_layout_y_tolerance != float(y_tolerance):
            return None
        start = int(start_page)
        end = int(end_page)
        if start <= 0 or end < start or not self.lines_by_page:
            return None
        # Fail closed. A full-layout snapshot does not encode blank pages or
        # document page_count, so reuse only ranges for which every requested
        # page is explicitly represented. Blank or out-of-range requests stay
        # authoritative in the historical range extractor.
        if any(page not in self.lines_by_page for page in range(start, end + 1)):
            return None
        return tuple(
            line
            for page in range(start, end + 1)
            for line in self.lines_by_page[page]
        )

    def snapshot(self) -> dict:
        return {
            "backend": self.backend,
            "reuse_enabled": self.reuse_enabled,
            "counters": dict(self.counters),
            "timings": dict(self.timings),
        }


def current_extraction_context():
    return _ACTIVE_CONTEXT.get()


@contextmanager
def use_extraction_context(context: ExtractionContext) -> Iterator[ExtractionContext]:
    token = _ACTIVE_CONTEXT.set(context)
    try:
        yield context
    finally:
        _ACTIVE_CONTEXT.reset(token)


@contextmanager
def timed_extraction_stage(name: str):
    context = current_extraction_context()
    if context is None:
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        context.timings[str(name)] += perf_counter() - started
