import pytest

from compiler.syntax import ast as A
from tests.helpers import parse_prog


def ok(src):
    result = parse_prog(src)
    assert result.errors == [], [(e.code, e.message) for e in result.errors]
    return result.ast


def test_empty_program():
    assert ok("").items == []
    assert ok("// only a comment\n").items == []


def test_declarations_and_assignment():
    prog = ok("int x = 1 + 2; float y; bool b = true; x = x * 2;")
    kinds = [i.KIND for i in prog.items]
    assert kinds == ["VarDecl", "VarDecl", "VarDecl", "Assign"]
    assert prog.items[1].init is None


@pytest.mark.parametrize("src, op, rhs_op", [
    ("x += 2;", "+=", "+"), ("x -= 2;", "-=", "-"), ("x *= 2;", "*=", "*"),
    ("x /= 2;", "/=", "/"), ("x++;", "++", "+"), ("x--;", "--", "-"),
])
def test_compound_assignment_is_desugared(src, op, rhs_op):
    assign = ok(src).items[0]
    assert assign.op == op
    assert isinstance(assign.value, A.Binary) and assign.value.op == rhs_op
    assert isinstance(assign.value.left, A.Var)


def test_if_else_chain():
    prog = ok("if (a) x = 1; else if (b) x = 2; else x = 3;")
    outer = prog.items[0]
    assert isinstance(outer.else_, A.If) and outer.else_.else_ is not None


def test_dangling_else_binds_to_nearest_if():
    outer = ok("if (a) if (b) x = 1; else x = 2;").items[0]
    assert outer.else_ is None
    assert outer.then.KIND == "If" and outer.then.else_ is not None


def test_loops():
    prog = ok("while (i < 3) i++; do { i--; } while (i > 0); "
              "for (int i = 0; i < 3; i++) print(i); for (;;) break;")
    assert [i.KIND for i in prog.items] == ["While", "DoWhile", "For", "For"]
    endless = prog.items[3]
    assert endless.init is None and endless.cond is None and endless.update is None


def test_functions_and_calls():
    prog = ok("int add(int a, int b) { return a + b; } void hi() { print(\"hi\"); } "
              "hi(); int s = add(1, 2);")
    fn = prog.items[0]
    assert fn.KIND == "FuncDecl" and [p.name for p in fn.params] == ["a", "b"]
    assert prog.items[2].KIND == "CallStmt"
    assert prog.items[3].init.KIND == "Call"


def test_print_arguments():
    printed = ok('print("x =", x, 1 + 2); print();').items
    assert [a.KIND for a in printed[0].args] == ["String", "Var", "Binary"]
    assert printed[1].args == []


def test_empty_statement_body():
    stmt = ok("while (x) ;").items[0]
    assert isinstance(stmt.body, A.Block) and stmt.body.stmts == []


@pytest.mark.parametrize("src, code, line, col", [
    ("int x = 5", "E_SYN_MISSING_SEMICOLON", 1, 10),
    ("int x = 5\nint y = 2;", "E_SYN_MISSING_SEMICOLON", 1, 10),
    ("if (x > 1 { }", "E_SYN_EXPECTED", 1, 11),
    ("while x < 5 { }", "E_SYN_EXPECTED", 1, 7),
    ("{ x = 1;", "E_SYN_MISSING_RBRACE", 1, 9),
    ("}", "E_SYN_UNEXPECTED_TOKEN", 1, 1),
    ("else x = 1;", "E_SYN_ELSE_WITHOUT_IF", 1, 1),
    ("5 + 3;", "E_SYN_EXPECTED_STATEMENT", 1, 1),
    ("{ int f() { } }", "E_SYN_NESTED_FUNCTION", 1, 7),
    ("string s = 1;", "E_SYN_UNEXPECTED_TOKEN", 1, 8),
    ("int if = 3;", "E_SYN_EXPECTED", 1, 5),
    ("x = (a + b));", "E_SYN_UNMATCHED_RPAREN", 1, 12),
    ("void x;", "E_SYN_EXPECTED", 1, 7),
    ("for (x; x < 3; x++) {}", "E_SYN_EXPECTED", 1, 7),
])
def test_statement_errors(src, code, line, col):
    error = parse_prog(src).errors[0]
    assert (error.code, error.span.start.line, error.span.start.col) == (code, line, col)


def test_recovery_reports_each_missing_semicolon():
    src = "int a = 1\nint b = 2\nint c = 3\nprint(a + b + c);"
    result = parse_prog(src)
    assert [(e.code, e.span.start.line) for e in result.errors] == [
        ("E_SYN_MISSING_SEMICOLON", 1), ("E_SYN_MISSING_SEMICOLON", 2),
        ("E_SYN_MISSING_SEMICOLON", 3)]
    # phrase-level recovery keeps the statements in the AST
    assert len(result.ast.items) == 4


def test_panic_mode_recovery_continues_after_bad_statement():
    src = "int x = ;\nprint(x);\nif (x > 1 {\n  print(1);\n}\nelse y = 2;\n"
    result = parse_prog(src)
    assert [e.code for e in result.errors] == ["E_SYN_UNEXPECTED_TOKEN", "E_SYN_EXPECTED",
                                               "E_SYN_ELSE_WITHOUT_IF"]
    assert any(s.action == "recover" for s in result.trace)
    assert result.trace[-1].action == "reject"


def test_error_limit():
    result = parse_prog("else;\n" * 40)
    assert result.errors[-1].code == "E_SYN_TOO_MANY_ERRORS"


def test_program_trace_is_accepted():
    result = parse_prog("int x = 1;")
    assert result.trace[-1].action == "accept"
