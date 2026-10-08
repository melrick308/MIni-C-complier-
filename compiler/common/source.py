"""Source text, positions and spans. Lines and columns are 1-based."""

from __future__ import annotations

import bisect
from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    line: int
    col: int
    offset: int = 0

    def to_dict(self) -> dict:
        return {"line": self.line, "col": self.col}


@dataclass(frozen=True)
class Span:
    """Half-open range: `end` is the position just after the last character."""

    start: Position
    end: Position

    def to_dict(self) -> list[int]:
        """Compact form used in JSON: [line, col, end_line, end_col]."""
        return [self.start.line, self.start.col, self.end.line, self.end.col]

    def merge(self, other: Span | None) -> Span:
        if other is None:
            return self
        start = self.start if self.start.offset <= other.start.offset else other.start
        end = self.end if self.end.offset >= other.end.offset else other.end
        return Span(start, end)


def merge_spans(*spans: Span | None) -> Span | None:
    result = None
    for span in spans:
        if span is None:
            continue
        result = span if result is None else result.merge(span)
    return result


class SourceFile:
    def __init__(self, text: str):
        self.text = text
        self._line_starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]

    def position(self, offset: int) -> Position:
        index = bisect.bisect_right(self._line_starts, offset) - 1
        return Position(index + 1, offset - self._line_starts[index] + 1, offset)

    def span(self, start: int, end: int) -> Span:
        return Span(self.position(start), self.position(end))

    @property
    def line_count(self) -> int:
        return len(self._line_starts)

    def line_text(self, line: int) -> str:
        if line < 1 or line > len(self._line_starts):
            return ""
        start = self._line_starts[line - 1]
        end = self.text.find("\n", start)
        return self.text[start:] if end == -1 else self.text[start:end].rstrip("\r")
