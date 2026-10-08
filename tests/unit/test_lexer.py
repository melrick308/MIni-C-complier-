import pytest

from compiler.lexer.lexer import tokenize
from compiler.lexer.tokens import TokenType as T


def types(src):
    tokens, err = tokenize(src)
    assert err is None
    return [t.type for t in tokens]


def test_problem_statement_example():
    tokens, err = tokenize("a + b * (c - 5)")
    assert err is None
    assert [t.type for t in tokens] == [T.IDENTIFIER, T.PLUS, T.IDENTIFIER, T.MULTIPLY,
                                        T.LEFT_PAREN, T.IDENTIFIER, T.MINUS, T.NUMBER,
                                        T.RIGHT_PAREN, T.EOF]
    assert [t.col for t in tokens] == [1, 3, 5, 7, 9, 10, 12, 14, 15, 16]


@pytest.mark.parametrize("src, expected", [
    ("num1*3.14", [T.IDENTIFIER, T.MULTIPLY, T.NUMBER, T.EOF]),
    ("1abc", [T.NUMBER, T.IDENTIFIER, T.EOF]),
    ("a<=b&&!c", [T.IDENTIFIER, T.LESS_EQUAL, T.IDENTIFIER, T.AND, T.NOT, T.IDENTIFIER, T.EOF]),
    ("x+=1;y--", [T.IDENTIFIER, T.PLUS_ASSIGN, T.NUMBER, T.SEMICOLON, T.IDENTIFIER, T.DECREMENT,
                  T.EOF]),
    ("a==b!=c", [T.IDENTIFIER, T.EQUAL, T.IDENTIFIER, T.NOT_EQUAL, T.IDENTIFIER, T.EOF]),
    ("if else while do for", [T.IF, T.ELSE, T.WHILE, T.DO, T.FOR, T.EOF]),
    ("int float bool void", [T.INT, T.FLOAT, T.BOOL, T.VOID, T.EOF]),
    ("true false print return break continue",
     [T.TRUE, T.FALSE, T.PRINT, T.RETURN, T.BREAK, T.CONTINUE, T.EOF]),
    ("intx _a1", [T.IDENTIFIER, T.IDENTIFIER, T.EOF]),
    ("{ } ( ) , ;", [T.LEFT_BRACE, T.RIGHT_BRACE, T.LEFT_PAREN, T.RIGHT_PAREN, T.COMMA,
                     T.SEMICOLON, T.EOF]),
    ("a % b", [T.IDENTIFIER, T.MODULO, T.IDENTIFIER, T.EOF]),
    ("", [T.EOF]),
    ("   \t\n  ", [T.EOF]),
    ("// comment only", [T.EOF]),
    ("a /* block\ncomment */ b", [T.IDENTIFIER, T.IDENTIFIER, T.EOF]),
    ('print("hi")', [T.PRINT, T.LEFT_PAREN, T.STRING, T.RIGHT_PAREN, T.EOF]),
])
def test_token_types(src, expected):
    assert types(src) == expected


def test_values():
    tokens, _ = tokenize('42 3.5 true "a\\nb"')
    assert tokens[0].value == 42 and isinstance(tokens[0].value, int)
    assert tokens[1].value == 3.5
    assert tokens[2].value is True
    assert tokens[3].value == "a\nb"


def test_positions_across_lines_and_crlf():
    tokens, _ = tokenize("int x;\r\n  x = 1;\n// c\ny")
    x2 = tokens[3]
    assert (x2.lexeme, x2.line, x2.col) == ("x", 2, 3)
    assert (tokens[-2].lexeme, tokens[-2].line, tokens[-2].col) == ("y", 4, 1)


def test_eof_position_is_after_input():
    tokens, _ = tokenize("(a + b")
    assert tokens[-1].type is T.EOF and tokens[-1].col == 7


@pytest.mark.parametrize("src, code, col, found", [
    ("a + @ + b", "E_LEX_INVALID_CHAR", 5, "@"),
    ("3.", "E_LEX_MALFORMED_NUMBER", 1, "3."),
    (".5", "E_LEX_INVALID_CHAR", 1, "."),
    ("x = 1 # 2", "E_LEX_INVALID_CHAR", 7, "#"),
    ("a & b", "E_LEX_INVALID_CHAR", 3, "&"),
    ('print("abc', "E_LEX_UNTERMINATED_STRING", 7, '"abc'),
    ("a /* never closed", "E_LEX_UNTERMINATED_COMMENT", 3, "/*"),
    ("a × b", "E_LEX_INVALID_CHAR", 3, "×"),
])
def test_lexical_errors(src, code, col, found):
    tokens, err = tokenize(src)
    assert err is not None
    assert (err.code, err.span.start.col, err.found) == (code, col, found)
    assert tokens[-1].type is T.EOF


def test_hints():
    _, err = tokenize("a & b")
    assert "&&" in err.hint
    _, err = tokenize(".5")
    assert "0.5" in err.hint
