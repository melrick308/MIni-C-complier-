import pytest

from tests.helpers import codes, run


def sem_errors(src):
    result = run(src)
    assert result["failed_phase"] in (None, "semantic"), result["diagnostics"]
    return codes(result)


@pytest.mark.parametrize("src, expected", [
    ("x = 3;", [("E_SEM_UNDECLARED", 1, 1)]),
    ("print(y);", [("E_SEM_UNDECLARED", 1, 7)]),
    ("int a; int a;", [("E_SEM_REDECLARED", 1, 12)]),
    ("int x = true;", [("E_SEM_TYPE_MISMATCH", 1, 9)]),
    ("int x = 1.5;", [("E_SEM_LOSSY_ASSIGN", 1, 9)]),
    ("bool b = 1;", [("E_SEM_TYPE_MISMATCH", 1, 10)]),
    ("int x = 1; if (x) { }", [("E_SEM_CONDITION_NOT_BOOL", 1, 16)]),
    ("while (5) { }", [("E_SEM_CONDITION_NOT_BOOL", 1, 8)]),
    ("for (;1;) { }", [("E_SEM_CONDITION_NOT_BOOL", 1, 7)]),
    ("bool b = 1 + true;", [("E_SEM_INVALID_OPERANDS", 1, 10)]),
    ("float f = 2.5 % 2;", [("E_SEM_INVALID_OPERANDS", 1, 11)]),
    ("bool b = 1 && true;", [("E_SEM_INVALID_OPERANDS", 1, 10)]),
    ("bool b = !5;", [("E_SEM_INVALID_OPERANDS", 1, 10)]),
    ("int n = -true;", [("E_SEM_INVALID_OPERANDS", 1, 9)]),
    ("break;", [("E_SEM_BREAK_OUTSIDE_LOOP", 1, 1)]),
    ("continue;", [("E_SEM_BREAK_OUTSIDE_LOOP", 1, 1)]),
    ("return 1;", [("E_SEM_RETURN_OUTSIDE_FUNCTION", 1, 1)]),
    ("int f() { }", [("E_SEM_MISSING_RETURN", 1, 5)]),
    ("int f(int a) { if (a > 0) { return 1; } }", [("E_SEM_MISSING_RETURN", 1, 5)]),
    ("void f() { return 1; }", [("E_SEM_RETURN_TYPE", 1, 19)]),
    ("int f() { return true; }", [("E_SEM_RETURN_TYPE", 1, 18)]),
    ("int f() { return; }", [("E_SEM_RETURN_TYPE", 1, 11)]),
    ("int add(int a, int b) { return a + b; } int s = add(1);", [("E_SEM_ARG_COUNT", 1, 49)]),
    ("int sq(int a) { return a * a; } int s = sq(true);", [("E_SEM_ARG_TYPE", 1, 44)]),
    ("void f() { } int x = f();", [("E_SEM_VOID_VALUE", 1, 22)]),
    ("int x = 1; x();", [("E_SEM_NOT_A_FUNCTION", 1, 12)]),
    ("void f() { } int y = f + 1;", [("E_SEM_NOT_A_VARIABLE", 1, 22)]),
    ("void f() { } f = 1;", [("E_SEM_NOT_A_VARIABLE", 1, 14)]),
    ("g();", [("E_SEM_UNDECLARED", 1, 1)]),
    ("void f() { } void f() { }", [("E_SEM_REDECLARED", 1, 19)]),
    ("{ int y = 1; } print(y);", [("E_SEM_UNDECLARED", 1, 22)]),
    ("for (int i = 0; i < 3; i++) { } print(i);", [("E_SEM_UNDECLARED", 1, 39)]),
])
def test_semantic_errors(src, expected):
    assert sem_errors(src) == expected


@pytest.mark.parametrize("src", [
    "int x = 1; print(x);",
    "float f = 3; print(f);",  # int widens to float
    "int f(int n) { if (n > 0) { return 1; } else { return 2; } } print(f(1));",
    "int f(int n) { return n; } print(f(2) + f(3));",
    "print(twice(2)); int twice(int n) { return 2 * n; }",  # functions are hoisted
    "int x = 1; { int x = 2; print(x); } print(x);",
    "bool b = 1 < 2 && 2.5 >= 1; print(b);",
    "bool b = true == false; print(b);",
    "float f(float x) { return x; } print(f(1));",
])
def test_valid_programs_have_no_errors(src):
    assert sem_errors(src) == []


def test_errors_are_all_collected():
    result = run("x = 1;\ny = 2;\nint z = true;")
    assert [c[0] for c in codes(result)] == ["E_SEM_UNDECLARED", "E_SEM_UNDECLARED",
                                             "E_SEM_TYPE_MISMATCH"]


def test_unused_variable_warning():
    result = run("int unused = 1; int used = 2; print(used);")
    assert codes(result, "warning") == [("W_SEM_UNUSED", 1, 5)]
    assert result["success"]


def test_scopes_and_symbols():
    result = run("int g = 1; int f(int p) { int l = p; return l; } "
                 "{ int g = 2; print(g); } print(f(g));")
    sem = result["phases"]["semantic"]
    kinds = [s["kind"] for s in sem["scopes"]]
    assert kinds == ["global", "function", "block"]
    shadow = [s for s in sem["symbols"] if s["name"] == "g"]
    assert [s["ir_name"] for s in shadow] == ["g", "g_2"]
    assert next(s for s in sem["symbols"] if s["name"] == "f")["signature"] == "int f(int)"


def test_ast_is_annotated_with_types():
    result = run("float f = 1 + 2.5; print(f);")
    types = {n["label"]: n["type"] for n in result["phases"]["syntax"]["ast"]["nodes"]}
    assert types["+"] == "float"
    assert types["1"] == "int"
