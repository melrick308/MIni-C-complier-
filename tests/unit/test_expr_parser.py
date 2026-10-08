import pytest

from compiler.syntax.ast import to_infix
from compiler.syntax.parse_tree import to_sexpr
from tests.helpers import parse_expr, parse_prog


@pytest.mark.parametrize("src, infix", [
    ("a + b", "(a + b)"),
    ("a + b * c", "(a + (b * c))"),
    ("a * b + c", "((a * b) + c)"),
    ("(a + b) * c", "((a + b) * c)"),
    ("10 + 20 * 5", "(10 + (20 * 5))"),
    ("(10 + 5) / 3", "((10 + 5) / 3)"),
    ("a * (b + c) - d", "((a * (b + c)) - d)"),
    ("10 - 4 - 3", "((10 - 4) - 3)"),
    ("100 / 10 / 2", "((100 / 10) / 2)"),
    ("a - b + c", "((a - b) + c)"),
    ("2 * (3 + 4) * 5", "((2 * (3 + 4)) * 5)"),
    ("((((1))))", "1"),
    ("num1 * 3.14", "(num1 * 3.14)"),
])
def test_arithmetic_profile_ast(src, infix):
    result = parse_expr(src)
    assert result.errors == []
    assert to_infix(result.ast) == infix


@pytest.mark.parametrize("src, code, col, expected", [
    ("a + * b", "E_SYN_UNEXPECTED_TOKEN", 5, ["identifier", "number", "'('"]),
    ("(a + b", "E_SYN_MISSING_RPAREN", 7, ["')'"]),
    ("((a)", "E_SYN_MISSING_RPAREN", 5, ["')'"]),
    ("a + b)", "E_SYN_UNMATCHED_RPAREN", 6, None),
    ("", "E_SYN_EMPTY", 1, None),
    ("   ", "E_SYN_EMPTY", 4, None),
    ("a +", "E_SYN_UNEXPECTED_EOF", 4, None),
    ("a b", "E_SYN_MISSING_OPERATOR", 3,
     ["'+'", "'-'", "'*'", "'/'", "')'", "end of input"]),
    ("2(3)", "E_SYN_MISSING_OPERATOR", 2, None),
    ("()", "E_SYN_EMPTY_PARENS", 2, None),
    ("-5", "E_SYN_UNARY_NOT_SUPPORTED", 1, None),
    ("a + -b", "E_SYN_UNARY_NOT_SUPPORTED", 5, None),
    ("* a", "E_SYN_UNEXPECTED_TOKEN", 1, None),
    ("a = 5", "E_SYN_UNEXPECTED_TOKEN", 3, None),
    ("a < b", "E_SYN_UNEXPECTED_TOKEN", 3, None),
])
def test_arithmetic_profile_errors(src, code, col, expected):
    result = parse_expr(src)
    assert result.ast is None
    error = result.errors[0]
    assert (error.code, error.span.start.col) == (code, col)
    if expected is not None:
        assert error.expected == expected


def test_missing_rparen_points_at_opening_paren():
    error = parse_expr("(a + b").errors[0]
    assert error.related_span.start.col == 1


def test_golden_parse_tree():
    tree = parse_expr("a + b * c").parse_tree
    assert to_sexpr(tree) == "E(T(F(a) T'(ε)) E'(+ T(F(b) T'(* F(c) T'(ε))) E'(ε)))"


def test_golden_trace():
    steps = [(s.function, s.action, s.lookahead.lexeme) for s in parse_expr("a + b * c").trace]
    assert steps == [
        ("E", "enter", "a"), ("T", "enter", "a"), ("F", "enter", "a"), ("F", "match", "a"),
        ("T'", "epsilon", "+"), ("E'", "enter", "+"), ("E'", "match", "+"),
        ("T", "enter", "b"), ("F", "enter", "b"), ("F", "match", "b"),
        ("T'", "enter", "*"), ("T'", "match", "*"), ("F", "enter", "c"), ("F", "match", "c"),
        ("T'", "epsilon", "$"), ("E'", "epsilon", "$"), ("E", "accept", "$"),
    ]


def test_trace_depth_and_nodes():
    result = parse_expr("(a)")
    depths = [s.depth for s in result.trace]
    assert min(depths) == 0
    assert all(s.node_id for s in result.trace if s.action in ("enter", "match", "epsilon"))


def test_error_trace_ends_with_error_step():
    result = parse_expr("a + * b")
    assert result.trace[-1].action == "error"
    assert result.trace[-1].lookahead.lexeme == "*"


def expr_of(src: str):
    """Parse `int r = <src>;` and return the initializer expression."""
    result = parse_prog(f"int r = {src};")
    assert result.errors == [], result.errors
    return result.ast.items[0].init


@pytest.mark.parametrize("src, infix", [
    ("!a && b || c", "(((!a) && b) || c)"),
    ("-x * y", "((-x) * y)"),
    ("- - x", "(-(-x))"),
    ("1 + 2 < 3 * 4", "((1 + 2) < (3 * 4))"),
    ("a < b == c > d", "((a < b) == (c > d))"),
    ("a || b && c", "(a || (b && c))"),
    ("a % b * c", "((a % b) * c)"),
    ("f(1, g(x), 2 + 3)", "f(1, g(x), (2 + 3))"),
    ("f()", "f()"),
    ("true && !false", "(true && (!false))"),
    ("(a || b) && c", "((a || b) && c)"),
])
def test_minic_expression_levels(src, infix):
    assert to_infix(expr_of(src)) == infix


@pytest.mark.parametrize("src, code", [
    ("int r = a < b < c;", "E_SYN_CHAINED_COMPARISON"),
    ("int r = a == b != c;", "E_SYN_CHAINED_COMPARISON"),
    ("int r = a b;", "E_SYN_MISSING_OPERATOR"),
    ("int r = + a;", "E_SYN_UNEXPECTED_TOKEN"),
    ("int r = ;", "E_SYN_UNEXPECTED_TOKEN"),
    ('int r = "s";', "E_SYN_UNEXPECTED_TOKEN"),
    ("int r = (a + b;", "E_SYN_MISSING_RPAREN"),
])
def test_minic_expression_errors(src, code):
    assert parse_prog(src).errors[0].code == code


def test_nesting_limit():
    src = "(" * 150 + "1" + ")" * 150
    assert parse_expr(src).errors[0].code == "E_SYN_TOO_DEEP"


def test_expression_complexity_limit():
    src = "int r = " + " + ".join(["1"] * 300) + ";"
    assert parse_prog(src).errors[0].code == "E_SYN_TOO_COMPLEX"
