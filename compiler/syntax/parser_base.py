"""Machinery shared by all parser functions: token cursor, matching, tracing, parse-tree
construction, error construction and panic-mode recovery."""

from __future__ import annotations

from ..common.diagnostics import ERROR, SYNTAX, Diagnostic
from ..common.limits import MAX_EXPR_DEPTH, MAX_NESTING, MAX_PARSE_TRACE, MAX_SYNTAX_ERRORS
from ..common.source import Span
from ..lexer.tokens import KEYWORDS, Token, TokenType, display, sorted_display
from .ast import Binary, Node, expr_depth
from .grammar import GRAMMARS, facts, production_text
from .parse_tree import ParseNode
from .trace import Tracer

T = TokenType

SYNC_KEYWORDS = {T.IF, T.WHILE, T.DO, T.FOR, T.RETURN, T.BREAK, T.CONTINUE, T.PRINT,
                 T.INT, T.FLOAT, T.BOOL, T.VOID}


class ParseError(Exception):
    def __init__(self, diagnostic: Diagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class TooManyErrors(Exception):
    pass


def quote(tok: Token) -> str:
    return "'$'" if tok.type is T.EOF else f"'{tok.lexeme}'"


class ParserBase:
    def __init__(self, tokens: list[Token], profile: str):
        self.tokens = tokens
        self.profile = profile
        self.grammar = GRAMMARS[profile]
        self.facts = facts(profile)
        self.pos = 0
        self.tracer = Tracer(MAX_PARSE_TRACE)
        self.stack: list[ParseNode] = []
        self.root: ParseNode | None = None
        self._ids = 0
        self.nesting = 0
        self.block_depth = 0
        self.errors: list[Diagnostic] = []
        self._last_error_pos = -1

    # ------------------------------------------------------------------ cursor
    @property
    def la(self) -> Token:
        return self.tokens[self.pos]

    @property
    def prev(self) -> Token | None:
        return self.tokens[self.pos - 1] if self.pos > 0 else None

    def span_from(self, start: Token | Span) -> Span:
        span = start.span if isinstance(start, Token) else start
        return span.merge(self.prev.span) if self.prev is not None else span

    # -------------------------------------------------------------- parse tree
    def _node(self, symbol: str, kind: str, **kwargs) -> ParseNode:
        self._ids += 1
        node = ParseNode(f"p{self._ids}", symbol, kind, **kwargs)
        if self.stack:
            self.stack[-1].children.append(node)
        elif self.root is None:
            self.root = node
        return node

    def _function(self) -> str:
        return self.stack[-1].symbol if self.stack else "-"

    def enter(self, symbol: str, rhs: list[str]) -> ParseNode:
        assert rhs in self.grammar[symbol], f"{symbol} → {rhs} is not in the grammar"
        prod = production_text(symbol, rhs, self.grammar)
        node = self._node(symbol, "nonterminal", production=prod)
        if len(self.grammar[symbol]) == 1:
            message = f"Expand {prod}"
        else:
            message = f"Lookahead {quote(self.la)} selects {prod}"
        node.step = self.tracer.record(len(self.stack), symbol, "enter", self.la, prod, node.id,
                                       message)
        self.stack.append(node)
        return node

    def exit(self, node: ParseNode) -> None:
        popped = self.stack.pop()
        assert popped is node, f"parse stack mismatch: {popped.symbol} vs {node.symbol}"

    def epsilon(self, symbol: str, message: str | None = None) -> None:
        prod = f"{symbol} → ε"
        node = self._node(symbol, "nonterminal", production=prod)
        if message is None:
            message = f"{quote(self.la)} ∈ FOLLOW({symbol}) → apply {prod}"
        node.step = self.tracer.record(len(self.stack), symbol, "epsilon", self.la, prod, node.id,
                                       message)
        self.stack.append(node)
        self._node("ε", "epsilon", step=node.step)
        self.stack.pop()

    def match(self, ttype: TokenType) -> Token:
        tok = self.la
        if tok.type is not ttype:
            raise self.expected_error(ttype)
        node = self._node(tok.lexeme if tok.type is not T.EOF else "$", "terminal",
                          lexeme=tok.lexeme, token_index=tok.index, span=tok.span)
        what = f"{display(ttype)} {quote(tok)}" if ttype in (T.IDENTIFIER, T.NUMBER, T.STRING) \
            else quote(tok)
        node.step = self.tracer.record(len(self.stack), self._function(), "match", tok, None,
                                       node.id, f"Match {what}")
        if tok.type is not T.EOF:
            self.pos += 1
        return tok

    def expect(self, ttype: TokenType) -> Token:
        if self.la.type is ttype:
            return self.match(ttype)
        raise self.expected_error(ttype)

    # ------------------------------------------------------------------ errors
    def error(self, code: str, message: str, *, token: Token | None = None, expected=None,
              hint: str | None = None, span: Span | None = None,
              related: tuple[Span, str] | None = None) -> ParseError:
        return ParseError(self._diagnostic(code, message, token=token, expected=expected,
                                           hint=hint, span=span, related=related))

    def _diagnostic(self, code, message, *, token=None, expected=None, hint=None, span=None,
                    related=None) -> Diagnostic:
        token = token or self.la
        diag = Diagnostic(
            ERROR, SYNTAX, code, message, span or token.span,
            found=token.describe(),
            expected=sorted_display(expected) if expected else None,
            hint=hint,
            related_span=related[0] if related else None,
            related_message=related[1] if related else None,
        )
        self.tracer.record(len(self.stack), self._function(), "error", token, None, None, message)
        return diag

    def expected_error(self, ttype: TokenType) -> ParseError:
        la = self.la
        if ttype is T.SEMICOLON and self.prev is not None:
            return ParseError(self._missing_semicolon())
        if la.type is T.EOF:
            return self.error("E_SYN_UNEXPECTED_EOF",
                              f"Unexpected end of input: expected {display(ttype)}",
                              expected=[ttype])
        if ttype is T.IDENTIFIER and la.type in KEYWORDS.values():
            return self.error("E_SYN_EXPECTED",
                              f"Expected an identifier but found the keyword '{la.lexeme}'",
                              expected=[ttype],
                              hint=f"'{la.lexeme}' is a reserved word and cannot be used as a name.")
        return self.error("E_SYN_EXPECTED", f"Expected {display(ttype)} but found {la.describe()}",
                          expected=[ttype])

    def _missing_semicolon(self) -> Diagnostic:
        prev, la = self.prev, self.la
        if la.type is T.RIGHT_PAREN:
            return self._diagnostic("E_SYN_UNMATCHED_RPAREN", "Unmatched ')' — no matching '('",
                                    expected=[T.SEMICOLON],
                                    hint="Remove the extra ')' or add the missing '('.")
        return self._diagnostic(
            "E_SYN_MISSING_SEMICOLON", f"Missing ';' after {prev.describe()}",
            span=Span(prev.span.end, prev.span.end), expected=[T.SEMICOLON],
            hint="Every statement must end with ';'.")

    def push_nesting(self, token: Token) -> None:
        self.nesting += 1
        if self.nesting > MAX_NESTING:
            raise self.error("E_SYN_TOO_DEEP", f"Nesting is deeper than {MAX_NESTING} levels",
                             token=token, hint="Simplify the code by splitting it up.")

    def make_binary(self, op: str, left: Node, right: Node, token: Token) -> Binary:
        node = Binary(op, left, right, span=left.span.merge(right.span))
        node._depth = 1 + max(expr_depth(left), expr_depth(right))
        if node._depth > MAX_EXPR_DEPTH:
            raise self.error("E_SYN_TOO_COMPLEX",
                             f"Expression has more than {MAX_EXPR_DEPTH} nested operators",
                             token=token, hint="Split the computation into several statements.")
        return node

    # ---------------------------------------------------------------- recovery
    def report(self, diag: Diagnostic) -> None:
        if self.pos == self._last_error_pos:
            return  # cascade suppression: one error per token position
        self._last_error_pos = self.pos
        self.errors.append(diag)
        if len(self.errors) >= MAX_SYNTAX_ERRORS:
            raise TooManyErrors()

    def guarded(self, parse_fn):
        """Run one list item (statement/top-level item); on error, recover in panic mode."""
        start, depth = self.pos, len(self.stack)
        nesting, blocks = self.nesting, self.block_depth
        try:
            return parse_fn()
        except ParseError as exc:
            del self.stack[depth:]
            self.nesting, self.block_depth = nesting, blocks
            self.report(exc.diagnostic)
            self.synchronize(start)
            return None

    def synchronize(self, start: int) -> None:
        skipped: list[Token] = []
        if self.pos == start and self.la.type is not T.EOF:
            skipped.append(self.la)  # guarantee progress
            self.pos += 1
        while self.la.type is not T.EOF:
            tt = self.la.type
            if tt is T.SEMICOLON:
                skipped.append(self.la)
                self.pos += 1
                break
            if tt is T.RIGHT_BRACE:
                if self.block_depth > 0:
                    break
                skipped.append(self.la)
                self.pos += 1
                continue
            if tt in SYNC_KEYWORDS or tt is T.LEFT_BRACE:
                break
            skipped.append(self.la)
            self.pos += 1
        text = " ".join(t.lexeme for t in skipped[:8]) + (" …" if len(skipped) > 8 else "")
        node = self._node("error", "error", lexeme=text or None,
                          span=skipped[0].span.merge(skipped[-1].span) if skipped else None)
        node.step = self.tracer.record(
            len(self.stack), self._function(), "recover", self.la, None, node.id,
            f"Panic mode: skipped {len(skipped)} token(s)"
            + (f" [{text}]" if text else "") + f", resuming at {quote(self.la)}")
