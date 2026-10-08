"""Public parser API: the recursive descent parser for both grammar profiles."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from ..common.diagnostics import ERROR, SYNTAX, Diagnostic
from ..common.limits import MAX_SYNTAX_ERRORS
from ..lexer.tokens import Token
from .ast import Node, number_nodes
from .expr_parser import ExpressionMixin
from .grammar import EXPRESSION
from .parse_tree import ParseNode, compute_spans
from .parser_base import ParseError, ParserBase, TooManyErrors
from .stmt_parser import StatementMixin
from .trace import TraceStep


class Parser(StatementMixin, ExpressionMixin, ParserBase):
    pass


@dataclass
class ParseResult:
    ast: Node | None
    parse_tree: ParseNode | None
    trace: list[TraceStep]
    trace_truncated: bool
    errors: list[Diagnostic]


def parse(tokens: list[Token], profile: str) -> ParseResult:
    parser = Parser(tokens, profile)
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 10_000))
    ast = None
    try:
        if profile == EXPRESSION:
            ast = parser.parse_expression_profile()
        else:
            ast = parser.parse_program()
    except ParseError as exc:
        parser.errors.append(exc.diagnostic)
    except TooManyErrors:
        last = parser.errors[-1]
        parser.errors.append(Diagnostic(
            ERROR, SYNTAX, "E_SYN_TOO_MANY_ERRORS",
            f"Parsing stopped after {MAX_SYNTAX_ERRORS} errors", last.span,
            hint="Fix the first errors and compile again."))
    finally:
        sys.setrecursionlimit(old_limit)
    if parser.root is not None:
        compute_spans(parser.root)
    if ast is not None:
        number_nodes(ast)
    return ParseResult(ast, parser.root, parser.tracer.steps, parser.tracer.truncated,
                       parser.errors)
