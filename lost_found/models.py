"""Data model for lost/found reports.

Design decision: rather than trying to parse dates out of free text like
"yesterday" or "two weeks ago" (real natural-language date parsing is a
project in itself), the report asks for the description and the
date/location as *separate* fields. In a real system, the date would
default to "today" in a submission form and the location might be a
dropdown of campus locations. Here they're just plain optional fields.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date as Date
from enum import Enum
from typing import Optional


class ReportType(Enum):
    LOST = "lost"
    FOUND = "found"


_id_counter = itertools.count(1)


@dataclass
class Report:
    type: ReportType
    description: str
    location: Optional[str] = None
    date: Optional[Date] = None
    contact: Optional[str] = None
    id: int = field(default_factory=lambda: next(_id_counter))

    def __post_init__(self) -> None:
        # Basic input validation: a report without a description is not
        # useful and shouldn't be silently accepted.
        if self.description is None or not self.description.strip():
            raise ValueError("A report must include a non-empty description.")
        self.description = self.description.strip()

        if self.location is not None:
            self.location = self.location.strip() or None

        if self.contact is not None:
            self.contact = self.contact.strip() or None

        if isinstance(self.type, str):
            self.type = ReportType(self.type.lower())

    def __str__(self) -> str:
        parts = [f"#{self.id} [{self.type.value.upper()}] {self.description}"]
        if self.location:
            parts.append(f"near {self.location}")
        if self.date:
            parts.append(f"on {self.date.isoformat()}")
        return " — ".join(parts) if len(parts) == 1 else f"{parts[0]} ({', '.join(parts[1:])})"
