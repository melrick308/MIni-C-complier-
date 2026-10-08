import pytest

from compiler import compile_source
from tests.helpers import codes, output, run


@pytest.mark.parametrize("src, expected", [
    ("print(7 / 2, 7.0 / 2, -7 / 2, 7 % 3, -7 % 3);", "3 3.5 -3 1 -1"),
    ("print(1 < 2, 2 <= 1, 3 == 3.0, true != false);", "true false true true"),
    ("print(0.1 + 0.2);", "0.3"),
    ("float f = 2; print(f, f / 4);", "2.0 0.5"),
    ("print(!true || false, -(-3));", "false 3"),
    ('print("a\\tb", "q\\"q");', 'a\tb q"q'),
    ("print();", ""),
    ("print(123456789 * 1000000);", "123456789000000"),
])
def test_values_and_formatting(src, expected):
    assert output(src) == [expected]


def test_recursion():
    src = "int fib(int n) { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); } print(fib(15));"
    assert output(src) == ["610"]


def test_globals_modified_in_function():
    assert output("int c = 0; void inc() { c = c + 1; } inc(); inc(); print(c);") == ["2"]


def test_locals_are_per_call():
    src = ("int f(int n) { int local = n * 10; if (n > 0) { int ignored = f(n - 1); } "
           "return local; } print(f(3));")
    assert output(src) == ["30"]


@pytest.mark.parametrize("src, code, line", [
    ("int a = 0;\nprint(10 / a);", "E_RT_DIV_ZERO", 2),
    ("int a = 0;\nprint(10 % a);", "E_RT_MOD_ZERO", 2),
    ("while (true) { }", "E_RT_STEP_LIMIT", 1),
    ("int f(int n) { return f(n + 1); } print(f(0));", "E_RT_CALL_DEPTH", 1),
    ("for (;;) { print(1); }", "E_RT_OUTPUT_LIMIT", 1),
    ("float f = 1.0; while (true) { f = f * 1000.0; }", "E_RT_OVERFLOW", 1),
])
def test_runtime_errors(src, code, line):
    result = run(src)
    assert result["phases"]["execution"]["status"] == "error"
    assert [(c, ln) for c, ln, _ in codes(result)] == [(code, line)]


def test_output_before_runtime_error_is_kept():
    result = run('print("before");\nint z = 0;\nprint(1 / z);')
    assert result["phases"]["execution"]["output"] == ["before"]
    assert result["phases"]["execution"]["trace"][-1]["error"] == "Division by zero"


def test_execution_trace_records_calls_and_writes():
    result = run("int sq(int n) { return n * n; }\nint r = sq(4);\nprint(r);")
    trace = result["phases"]["execution"]["trace"]
    call = next(s for s in trace if s.get("event") == "call")
    assert call["call"]["func"] == "sq"
    assert {"name": "n", "value": "4", "scope": "local"} in call["writes"]
    ret = next(s for s in trace if s.get("event") == "return")
    assert ret["return"]["value"] == "16"
    assert result["phases"]["execution"]["globals"]["r"] == "16"
    assert result["phases"]["execution"]["max_depth"] == 1


def test_expression_mode_evaluation():
    def ev(src, **variables):
        return compile_source(src, "expression", variables=variables)["evaluation"]

    assert ev("10 + 5 * 2")["value"] == "20"
    assert ev("(10 + 5) * 2")["value"] == "30"
    assert ev("5 + 3 * 2")["value"] == "11"
    assert ev("(10 + 5) / 3")["value"] == "5"
    assert ev("10 - 4 - 3")["value"] == "3"
    assert ev("100 / 10 / 2")["value"] == "5"
    assert ev("7 / 2")["value"] == "3.5"
    assert ev("a + b * (c - 2)", a=3, b=4, c=7)["value"] == "23"
    assert ev("a * (b + c) - d", a=2, b=3, c=4, d=5)["value"] == "9"
    skipped = ev("a + b * c", a=1)
    assert skipped["status"] == "skipped" and skipped["missing"] == ["b", "c"]
    assert ev("8 / (4 - 4)")["status"] == "error"


def test_run_can_be_disabled():
    result = compile_source("print(1);", run=False)
    assert result["phases"]["execution"]["status"] == "skipped"
