"""Data models for PolicyDhara."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Policy:
    """A single policy item tracked by PolicyDhara."""

    id: str
    title: str
    description: str = ""
    link: str = ""
    date: str = ""
    source_id: str = ""
    source_name: str = ""
    source_short: str = ""
    sectors: list[str] = field(default_factory=list)
    sector_slugs: list[str] = field(default_factory=list)
    type: str = "policy"
    level: str = "central"
    state: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Policy:
        """Create a Policy from a dictionary, ignoring unknown fields."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @staticmethod
    def generate_id(title: str, source: str) -> str:
        """Generate a deterministic unique ID for a policy item."""
        raw = f"{source}:{title}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    @staticmethod
    def sector_slug(sector: str) -> str:
        """Convert sector name to URL-friendly slug."""
        return sector.lower().replace(" & ", "-").replace(" ", "-")

    @property
    def year(self) -> Optional[int]:
        """Extract year from the date string."""
        if not self.date:
            return None
        try:
            return int(self.date[:4])
        except (ValueError, IndexError):
            return None

    def matches(self, query: str) -> bool:
        """Check if this policy matches a search query (case-insensitive)."""
        q = query.lower()
        return q in self.title.lower() or q in self.description.lower()

    def __str__(self) -> str:
        sectors_str = ", ".join(self.sectors) if self.sectors else "Uncategorized"
        return f"[{self.date}] {self.title} ({sectors_str}) — {self.source_short or self.source_name}"
