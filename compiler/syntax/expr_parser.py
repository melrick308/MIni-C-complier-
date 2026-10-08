"""Expression parsing functions. One method per grammar non-terminal.

Precedence comes from the grammar levels (Or → And → Eq → Rel → E → T → U → F).
Left associativity comes from passing the AST built so far into each X' function
as an inherited attribute and folding new operands onto it from the left.
"""

from __future__ import annotations

from ..lexer.tokens import TokenType
from .ast import Call, Literal, Node, Unary, Var, expr_depth
from .first_follow import EPSILON
from .grammar import EXPRESSION, terminal_types
from .parser_base import quote

T = TokenType

ADD_OPS = {T.PLUS: "+", T.MINUS: "-"}
MUL_OPS_EXPR = {T.MULTIPLY: "*", T.DIVIDE: "/"}
MUL_OPS = {T.MULTIPLY: "*", T.DIVIDE: "/", T.MODULO: "%"}
REL_OPS = {T.LESS: "<", T.LESS_EQUAL: "<=", T.GREATER: ">", T.GREATER_EQUAL: ">="}
EQ_OPS = {T.EQUAL: "==", T.NOT_EQUAL: "!="}
OPERAND_START = {T.IDENTIFIER, T.NUMBER, T.LEFT_PAREN, T.TRUE, T.FALSE, T.NOT, T.STRING}
ARITHMETIC_TERMINALS = {T.IDENTIFIER, T.NUMBER, T.PLUS, T.MINUS, T.MULTIPLY, T.DIVIDE,
                        T.LEFT_PAREN, T.RIGHT_PAREN, T.EOF}
MINIC_ONLY = set(TokenType) - ARITHMETIC_TERMINALS - {T.ASSIGN}


class ExpressionMixin:
    # ------------------------------------------------------------ entry points
    def parse_expression_profile(self) -> Node:
        if self.la.type is T.EOF:
            raise self.error("E_SYN_EMPTY", "Empty expression",
                             hint="Type an arithmetic expression such as a + b * c.")
        ast = self.E()
        if self.la.type is not T.EOF:
            if self.la.type is T.RIGHT_PAREN:
                raise self.error("E_SYN_UNMATCHED_RPAREN", "Unexpected ')' — no matching '('",
                                 expected=[T.EOF],
                                 hint="Remove the extra ')' or add the missing '('.")
            raise self.error("E_SYN_UNEXPECTED_TOKEN", f"Unexpected token {self.la.describe()}",
                             expected=[T.EOF])
        self.tracer.record(0, "E", "accept", self.la, None, None,
                           "Input fully consumed → expression accepted")
        return ast

    # ---------------------------------------------------------- MiniC levels
    def Expr(self) -> Node:
        node = self.enter("Expr", ["Or"])
        result = self.Or()
        self.exit(node)
        return result

    def Or(self) -> Node:
        node = self.enter("Or", ["And", "Or'"])
        result = self._chain("Or'", {T.OR: "||"}, self.And, "And", self.And())
        self.exit(node)
        return result

    def And(self) -> Node:
        node = self.enter("And", ["Eq", "And'"])
        result = self._chain("And'", {T.AND: "&&"}, self.Eq, "Eq", self.Eq())
        self.exit(node)
        return result

    def Eq(self) -> Node:
        node = self.enter("Eq", ["Rel", "Eq'"])
        result = self._single("Eq'", EQ_OPS, self.Rel, "Rel", self.Rel())
        self.exit(node)
        return result

    def Rel(self) -> Node:
        node = self.enter("Rel", ["E", "Rel'"])
        result = self._single("Rel'", REL_OPS, self.E, "E", self.E())
        self.exit(node)
        return result

    # ------------------------------------------------- arithmetic (both profiles)
    def E(self) -> Node:
        node = self.enter("E", ["T", "E'"])
        left = self.T()
        result = self._chain("E'", ADD_OPS, self.T, "T", left)
        self.exit(node)
        return result

    def T(self) -> Node:
        if self.profile == EXPRESSION:
            node = self.enter("T", ["F", "T'"])
            result = self._chain("T'", MUL_OPS_EXPR, self.F, "F", self.F())
        else:
            node = self.enter("T", ["U", "T'"])
            result = self._chain("T'", MUL_OPS, self.U, "U", self.U())
        self.exit(node)
        return result

    def U(self) -> Node:
        la = self.la
        if la.type in (T.MINUS, T.NOT):
            node = self.enter("U", [la.type.value, "U"])
            self.match(la.type)
            self.push_nesting(la)
            operand = self.U()
            self.nesting -= 1
            result = Unary("-" if la.type is T.MINUS else "!", operand,
                           span=la.span.merge(operand.span))
            result._depth = 1 + expr_depth(operand)
            self.exit(node)
            return result
        if la.type.value in self.facts.first["F"]:
            node = self.enter("U", ["F"])
            result = self.F()
            self.exit(node)
            return result
        raise self.operand_error(terminal_types(self.facts.first["U"]))

    def F(self) -> Node:
        la = self.la
        if la.type is T.LEFT_PAREN:
            inner_symbol = "E" if self.profile == EXPRESSION else "Expr"
            node = self.enter("F", ["LEFT_PAREN", inner_symbol, "RIGHT_PAREN"])
            open_tok = self.match(T.LEFT_PAREN)
            self.push_nesting(open_tok)
            inner = self.E() if self.profile == EXPRESSION else self.Expr()
            if self.la.type is not T.RIGHT_PAREN:
                where = (f"column {open_tok.col}" if self.profile == EXPRESSION
                         else f"line {open_tok.line}, column {open_tok.col}")
                raise self.error("E_SYN_MISSING_RPAREN", "Missing closing parenthesis ')'",
                                 expected=[T.RIGHT_PAREN],
                                 hint=f"The '(' at {where} is never closed.",
                                 related=(open_tok.span, "'(' opened here"))
            self.match(T.RIGHT_PAREN)
            self.nesting -= 1
            self.exit(node)
            return inner
        if la.type is T.IDENTIFIER:
            if self.profile == EXPRESSION:
                node = self.enter("F", ["IDENTIFIER"])
                tok = self.match(T.IDENTIFIER)
                self.exit(node)
                return Var(tok.lexeme, span=tok.span)
            node = self.enter("F", ["IDENTIFIER", "CallSuffix"])
            tok = self.match(T.IDENTIFIER)
            if self.la.type is T.LEFT_PAREN:
                suffix = self.enter("CallSuffix", ["LEFT_PAREN", "Args", "RIGHT_PAREN"])
                self.match(T.LEFT_PAREN)
                args = self.Args()
                close = self.expect(T.RIGHT_PAREN)
                self.exit(suffix)
                result: Node = Call(tok.lexeme, args, span=tok.span.merge(close.span))
            else:
                self.epsilon("CallSuffix",
                             f"{quote(self.la)} is not '(' → CallSuffix → ε (a variable, not a call)")
                result = Var(tok.lexeme, span=tok.span)
            self.exit(node)
            return result
        if la.type is T.NUMBER:
            node = self.enter("F", ["NUMBER"])
            tok = self.match(T.NUMBER)
            self.exit(node)
            return Literal(tok.value, tok.lexeme, span=tok.span)
        if self.profile != EXPRESSION and la.type in (T.TRUE, T.FALSE):
            node = self.enter("F", [la.type.value])
            tok = self.match(la.type)
            self.exit(node)
            return Literal(tok.value, tok.lexeme, span=tok.span)
        raise self.operand_error(terminal_types(self.facts.first["F"]))

    def Args(self) -> list[Node]:
        if self.la.type is T.RIGHT_PAREN:
            self.epsilon("Args", "')' ∈ FOLLOW(Args) → Args → ε (no arguments)")
            return []
        node = self.enter("Args", ["Expr", "ArgList"])
        args = [self.Expr()]
        opened = []
        while self.la.type is T.COMMA:
            opened.append(self.enter("ArgList", ["COMMA", "Expr", "ArgList"]))
            self.match(T.COMMA)
            args.append(self.Expr())
        self.epsilon("ArgList", f"{quote(self.la)} is not ',' → ArgList → ε")
        for n in reversed(opened):
            self.exit(n)
        self.exit(node)
        return args

    # ---------------------------------------------------------------- helpers
    def _chain(self, prime: str, ops: dict, operand_fn, operand_symbol: str, left: Node) -> Node:
        """X' → op Y X' | ε, written as a loop that still builds the nested parse tree.

        `left` is the inherited attribute: each new operand is folded onto it, giving
        left associativity (a - b - c == (a - b) - c).
        """
        opened = []
        while self.la.type in ops:
            tok = self.la
            opened.append(self.enter(prime, [tok.type.value, operand_symbol, prime]))
            self.match(tok.type)
            right = operand_fn()
            left = self.make_binary(ops[tok.type], left, right, tok)
        self.prime_epsilon(prime)
        for node in reversed(opened):
            self.exit(node)
        return left

    def _single(self, prime: str, ops: dict, operand_fn, operand_symbol: str, left: Node) -> Node:
        """Non-associative level: X' → op Y | ε."""
        if self.la.type not in ops:
            self.prime_epsilon(prime)
            return left
        tok = self.la
        node = self.enter(prime, [tok.type.value, operand_symbol])
        self.match(tok.type)
        right = operand_fn()
        result = self.make_binary(ops[tok.type], left, right, tok)
        if self.la.type in ops:
            example = "(a < b) && (b < c)" if ops is REL_OPS else "(a == b) && (b == c)"
            raise self.error("E_SYN_CHAINED_COMPARISON",
                             f"Comparison operators cannot be chained ({quote(tok)} followed by "
                             f"{quote(self.la)})",
                             expected=None, hint=f"Write it explicitly, e.g. {example}.")
        self.exit(node)
        return result

    def prime_epsilon(self, prime: str) -> None:
        la = self.la
        follow = self.facts.follow[prime]
        if la.type.value in follow:
            self.epsilon(prime)
            return
        expected = terminal_types((self.facts.first[prime] | follow) - {EPSILON})
        if self.profile == EXPRESSION:
            raise self._strict_error(expected)
        prev = self.prev
        if la.type in OPERAND_START and prev is not None and la.line == prev.line:
            raise self.error("E_SYN_MISSING_OPERATOR",
                             f"Missing operator before {la.describe()}", expected=expected,
                             hint="Two operands must be separated by an operator, e.g. a * b.")
        self.epsilon(prime, f"{quote(la)} cannot continue the expression → {prime} → ε "
                            "(the enclosing rule checks it)")

    def _strict_error(self, expected):
        la = self.la
        if la.type in (T.IDENTIFIER, T.NUMBER, T.LEFT_PAREN):
            return self.error("E_SYN_MISSING_OPERATOR", f"Missing operator before {la.describe()}",
                              expected=expected,
                              hint="Implicit multiplication such as 2(3) or 2a is not supported; "
                                   "write 2 * (3).")
        if la.type is T.ASSIGN:
            hint = ("Assignment is not part of an arithmetic expression. "
                    "Set variable values in the Variables panel.")
        elif la.type in MINIC_ONLY:
            hint = (f"{la.describe()} is not part of the arithmetic grammar. "
                    "Switch to Program mode to use it.")
        else:
            hint = "An operator (+ - * /), ')' or the end of the expression is expected here."
        return self.error("E_SYN_UNEXPECTED_TOKEN", f"Unexpected token {la.describe()}",
                          expected=expected, hint=hint)

    def operand_error(self, expected):
        la, prev = self.la, self.prev
        if la.type is T.EOF:
            if prev is None:
                return self.error("E_SYN_EMPTY", "Empty expression")
            return self.error("E_SYN_UNEXPECTED_EOF",
                              f"Expression ends unexpectedly after {prev.describe()}",
                              expected=expected,
                              hint="An operand (identifier, number or '(') is expected here.")
        if la.type is T.RIGHT_PAREN and prev is not None and prev.type is T.LEFT_PAREN:
            return self.error("E_SYN_EMPTY_PARENS", "Empty parentheses '()'", expected=expected,
                              hint="Put an expression inside the parentheses.")
        if self.profile == EXPRESSION:
            if la.type in (T.MINUS, T.PLUS):
                return self.error(
                    "E_SYN_UNARY_NOT_SUPPORTED",
                    f"Unary {la.describe()} is not supported by the arithmetic grammar",
                    expected=expected,
                    hint="Write (0 - 5) instead of -5, or use Program mode, which supports "
                         "unary minus.")
            return self.error("E_SYN_UNEXPECTED_TOKEN", f"Unexpected token {la.describe()}",
                              expected=expected,
                              hint="An operand (identifier, number or '(') is expected here.")
        hint = None
        if la.type is T.PLUS:
            hint = "Unary plus is not supported; just remove the '+'."
        elif la.type is T.STRING:
            hint = "Strings can only be used directly as print(...) arguments."
        return self.error("E_SYN_UNEXPECTED_TOKEN",
                          f"Expected an expression but found {la.describe()}",
                          expected=expected, hint=hint)
