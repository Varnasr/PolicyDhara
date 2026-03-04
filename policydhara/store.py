"""
PolicyStore — load, search, filter, and export policy data.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Optional

from policydhara.models import Policy


class PolicyStore:
    """In-memory store for querying policy data."""

    def __init__(self, policies: list[Policy] | None = None):
        self.policies: list[Policy] = policies or []

    def __len__(self) -> int:
        return len(self.policies)

    def __iter__(self):
        return iter(self.policies)

    def __getitem__(self, index):
        return self.policies[index]

    # ── Loading ──────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path | None = None) -> PolicyStore:
        """
        Load policies from a JSON file.

        If no path is given, tries to find policies.json in the standard
        locations (data/, public/data/, src/data/).
        """
        if path:
            p = Path(path)
        else:
            candidates = [
                Path("data/policies.json"),
                Path("public/data/policies.json"),
                Path("src/data/policies.json"),
            ]
            p = next((c for c in candidates if c.exists()), None)
            if not p:
                raise FileNotFoundError(
                    "No policies.json found. Pass an explicit path or run from the project root."
                )

        with open(p) as f:
            raw = json.load(f)

        policies = [Policy.from_dict(item) for item in raw]
        return cls(policies)

    @classmethod
    def from_dicts(cls, data: list[dict]) -> PolicyStore:
        """Create a store from a list of dictionaries."""
        return cls([Policy.from_dict(d) for d in data])

    # ── Search & Filter ──────────────────────────────────────────────

    def search(self, query: str, limit: int = 0) -> list[Policy]:
        """Full-text search across title and description."""
        results = [p for p in self.policies if p.matches(query)]
        return results[:limit] if limit else results

    def filter_by_sector(self, sector: str | list[str]) -> list[Policy]:
        """Filter policies by sector name(s)."""
        if isinstance(sector, str):
            sector = [sector]
        sector_lower = {s.lower() for s in sector}
        return [
            p for p in self.policies
            if any(s.lower() in sector_lower for s in p.sectors)
        ]

    def filter_by_state(self, state: str) -> list[Policy]:
        """Filter policies by state name."""
        state_lower = state.lower()
        return [p for p in self.policies if p.state.lower() == state_lower]

    def filter_by_type(self, policy_type: str) -> list[Policy]:
        """Filter policies by type (legislation, scheme, notification, etc.)."""
        return [p for p in self.policies if p.type == policy_type]

    def filter_by_source(self, source_id: str) -> list[Policy]:
        """Filter policies by source ID."""
        return [p for p in self.policies if p.source_id == source_id]

    def filter_by_level(self, level: str) -> list[Policy]:
        """Filter policies by level (central, state)."""
        return [p for p in self.policies if p.level == level]

    def filter_by_date_range(
        self, start: Optional[str] = None, end: Optional[str] = None
    ) -> list[Policy]:
        """Filter policies by date range (YYYY-MM-DD strings)."""
        results = []
        for p in self.policies:
            if not p.date:
                continue
            if start and p.date < start:
                continue
            if end and p.date > end:
                continue
            results.append(p)
        return results

    def query(
        self,
        text: Optional[str] = None,
        sector: Optional[str | list[str]] = None,
        state: Optional[str] = None,
        policy_type: Optional[str] = None,
        source: Optional[str] = None,
        level: Optional[str] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        limit: int = 0,
    ) -> list[Policy]:
        """Combined query with multiple filters."""
        results = list(self.policies)

        if text:
            q = text.lower()
            results = [p for p in results if p.matches(q)]
        if sector:
            sectors = [sector] if isinstance(sector, str) else sector
            sector_lower = {s.lower() for s in sectors}
            results = [
                p for p in results
                if any(s.lower() in sector_lower for s in p.sectors)
            ]
        if state:
            state_lower = state.lower()
            results = [p for p in results if p.state.lower() == state_lower]
        if policy_type:
            results = [p for p in results if p.type == policy_type]
        if source:
            results = [p for p in results if p.source_id == source]
        if level:
            results = [p for p in results if p.level == level]
        if date_start:
            results = [p for p in results if p.date and p.date >= date_start]
        if date_end:
            results = [p for p in results if p.date and p.date <= date_end]

        return results[:limit] if limit else results

    # ── Aggregation ──────────────────────────────────────────────────

    def sector_counts(self) -> dict[str, int]:
        """Count policies per sector."""
        counts: dict[str, int] = {}
        for p in self.policies:
            for s in p.sectors:
                counts[s] = counts.get(s, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def source_counts(self) -> dict[str, int]:
        """Count policies per source."""
        counts: dict[str, int] = {}
        for p in self.policies:
            counts[p.source_id] = counts.get(p.source_id, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def type_counts(self) -> dict[str, int]:
        """Count policies per type."""
        counts: dict[str, int] = {}
        for p in self.policies:
            counts[p.type] = counts.get(p.type, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def get_ids(self) -> set[str]:
        """Return set of all policy IDs."""
        return {p.id for p in self.policies}

    # ── Export ────────────────────────────────────────────────────────

    def to_json(self, path: Optional[str | Path] = None, indent: int = 2) -> str:
        """Export policies as JSON. Writes to file if path given, else returns string."""
        data = [p.to_dict() for p in self.policies]
        json_str = json.dumps(data, indent=indent, ensure_ascii=False)
        if path:
            with open(path, "w") as f:
                f.write(json_str)
        return json_str

    def to_csv(self, path: Optional[str | Path] = None) -> str:
        """Export policies as CSV. Writes to file if path given, else returns string."""
        if not self.policies:
            return ""

        output = io.StringIO()
        fieldnames = [
            "id", "title", "description", "link", "date",
            "source_id", "source_name", "sectors", "type", "level", "state",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for p in self.policies:
            row = p.to_dict()
            row["sectors"] = "; ".join(row.get("sectors", []))
            writer.writerow(row)

        csv_str = output.getvalue()
        if path:
            with open(path, "w") as f:
                f.write(csv_str)
        return csv_str
