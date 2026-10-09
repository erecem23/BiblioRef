"""Validated user input models for manual bibliography zones."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ManualZoneSpec:
    start_page: int
    start_y: float
    end_page: int
    end_y: Optional[float] = None
    heading_text: str = "Manual bibliography zone"
    note: str = ""

    def validate(self, page_count: int) -> None:
        if not 1 <= self.start_page <= page_count:
            raise ValueError("La página inicial está fuera del PDF.")
        if not self.start_page <= self.end_page <= page_count:
            raise ValueError("La página final debe ser igual o posterior a la inicial.")
        if self.end_page == self.start_page and self.end_y is not None:
            if self.end_y <= self.start_y:
                raise ValueError("El final debe estar debajo del inicio en una zona de una página.")
