"""Records every decision the recursive descent parser makes."""

from __future__ import annotations

from dataclasses import dataclass

from ..lexer.tokens import Token


@dataclass
class TraceStep:
    step: int
    depth: int
    function: str
    action: str  # enter | match | epsilon | error | recover | accept
    lookahead: Token
    production: str | None
    node_id: str | None
    message: str

    def to_dict(self) -> dict:
        data = {
            "step": self.step,
            "depth": self.depth,
            "function": self.function,
            "action": self.action,
            "la": self.lookahead.index,
            "lexeme": self.lookahead.lexeme,
            "message": self.message,
        }
        if self.production is not None:
            data["production"] = self.production
        if self.node_id is not None:
            data["node"] = self.node_id
        return data


class Tracer:
    def __init__(self, limit: int):
        self.limit = limit
        self.steps: list[TraceStep] = []
        self.truncated = False

    def record(self, depth, function, action, lookahead, production=None, node_id=None,
               message="") -> int | None:
        if len(self.steps) >= self.limit:
            self.truncated = True
            return None
        step = TraceStep(len(self.steps) + 1, depth, function, action, lookahead, production,
                         node_id, message)
        self.steps.append(step)
        return step.step
