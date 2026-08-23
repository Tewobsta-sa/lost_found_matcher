"""A tiny in-memory store for reports, with optional JSON persistence.

Kept deliberately simple: a real system would use a database, but for an
app of this scope a list in memory (with optional save/load to a JSON
file) is enough to demonstrate the workflow without adding infrastructure.
"""

from __future__ import annotations

import json
from datetime import date as Date
from pathlib import Path
from typing import List, Optional

from .matcher import MatchResult, find_matches
from .models import Report, ReportType


class ReportStore:
    def __init__(self) -> None:
        self._reports: List[Report] = []

    def add(self, report: Report) -> Report:
        self._reports.append(report)
        return report

    def add_lost(self, description: str, location: Optional[str] = None,
                 date: Optional[Date] = None, contact: Optional[str] = None) -> Report:
        return self.add(Report(ReportType.LOST, description, location, date, contact))

    def add_found(self, description: str, location: Optional[str] = None,
                  date: Optional[Date] = None, contact: Optional[str] = None) -> Report:
        return self.add(Report(ReportType.FOUND, description, location, date, contact))

    def all(self) -> List[Report]:
        return list(self._reports)

    def lost_reports(self) -> List[Report]:
        return [r for r in self._reports if r.type == ReportType.LOST]

    def found_reports(self) -> List[Report]:
        return [r for r in self._reports if r.type == ReportType.FOUND]

    def get(self, report_id: int) -> Optional[Report]:
        return next((r for r in self._reports if r.id == report_id), None)

    def matches_for(self, report: Report, threshold: float = 0.30) -> List[MatchResult]:
        opposite = self.found_reports() if report.type == ReportType.LOST else self.lost_reports()
        return find_matches(report, opposite, threshold=threshold)

    # -- Optional JSON persistence -----------------------------------
    def to_json(self) -> str:
        def enc(r: Report):
            return {
                "id": r.id, "type": r.type.value, "description": r.description,
                "location": r.location, "date": r.date.isoformat() if r.date else None,
                "contact": r.contact,
            }
        return json.dumps([enc(r) for r in self._reports], indent=2)

    def save(self, path: str) -> None:
        Path(path).write_text(self.to_json())

    def load(self, path: str) -> None:
        data = json.loads(Path(path).read_text())
        for item in data:
            d = Date.fromisoformat(item["date"]) if item.get("date") else None
            self.add(Report(ReportType(item["type"]), item["description"], item.get("location"), d, item.get("contact")))
