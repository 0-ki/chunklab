from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    line_start: int | None = None
    line_end: int | None = None
    span_start: int | None = None
    span_end: int | None = None
    mapped: bool = True
    note: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "line_start": self.line_start,
            "line_end": self.line_end,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "mapped": self.mapped,
            "note": self.note,
        }


@dataclass
class Block:
    id: str
    type: str
    text: str
    heading_path: list[str]
    source: SourceSpan
    order: int
    indivisible: bool = False
    flags: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    id: str
    order: int
    text: str
    heading_path: list[str]
    source: SourceSpan
    block_ids: list[str]
    block_types: list[str]
    budget_count: int
    flags: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)


@dataclass
class Issue:
    id: str
    severity: str
    message: str
    block_id: str
    block_type: str
    budget_count: int
    source: SourceSpan
    heading_path: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "message": self.message,
            "block_id": self.block_id,
            "block_type": self.block_type,
            "budget_count": self.budget_count,
            "source": self.source.to_json(),
            "heading_path": self.heading_path,
        }
