from compiler import compile_source
from tests.helpers import run


def tac(src, mode="program", **kw):
    result = compile_source(src, mode, **kw)
    assert result["phases"]["ir"]["status"] == "ok", result["diagnostics"]
    return [i["text"] for i in result["phases"]["ir"]["tac"]]


def test_problem_statement_tac():
    assert tac("a + b * c", "expression") == ["t1 = b * c", "t2 = a + t1"]
    assert tac("(a + b) * (c - d)", "expression") == ["t1 = a + b", "t2 = c - d", "t3 = t1 * t2"]
    assert tac("a + b * (c - 2)", "expression") == ["t1 = c - 2", "t2 = b * t1", "t3 = a + t2"]
    assert tac("10 - 4 - 3", "expression") == ["t1 = 10 - 4", "t2 = t1 - 3"]
    assert tac("a", "expression") == ["t1 = a"]


def test_assignment_writes_directly_into_variable():
    assert tac("int x = 2; int y = x * 3 + 1; print(y);") == [
        "x = 2", "t1 = x * 3", "y = t1 + 1", "print y", "halt"]


def test_default_initialisation():
    assert tac("int a; float b; bool c; print(a, b, c);")[:3] == ["a = 0", "b = 0.0", "c = false"]


def test_while_translation():
    assert tac("int i = 0; while (i < 3) { i = i + 1; }") == [
        "i = 0", "L1:", "t1 = i < 3", "ifFalse t1 goto L2", "i = i + 1", "goto L1", "L2:",
        "halt"]


def test_if_else_translation():
    assert tac("int x = 1; if (x > 0) { print(1); } else { print(2); }") == [
        "x = 1", "t1 = x > 0", "ifFalse t1 goto L1", "print 1", "goto L2", "L1:", "print 2",
        "L2:", "halt"]


def test_for_with_break_and_continue():
    code = tac("for (int i = 0; i < 9; i++) { if (i == 2) continue; if (i == 5) break; }")
    assert code[:3] == ["i = 0", "L1:", "t1 = i < 9"]
    assert "goto L2" in code  # continue → update label
    assert "goto L3" in code  # break → loop exit
    assert code[-5:] == ["L2:", "i = i + 1", "goto L1", "L3:", "halt"]


def test_short_circuit_and():
    code = tac("int x = 1; bool b = x != 0 && 10 / x > 1; print(b);")
    assert code[1:6] == ["t1 = x != 0", "ifFalse t1 goto L1", "t3 = 10 / x", "t1 = t3 > 1", "L1:"]


def test_function_translation():
    code = tac("int sq(int n) { return n * n; } print(sq(3));")
    assert code == ["param 3", "t1 = call sq, 1", "print t1", "halt", "func sq(n):",
                    "t2 = n * n", "return t2", "endfunc sq"]


def test_int_to_float_conversion_is_explicit():
    code = tac("int a = 3; float f = a; print(f);")
    assert "f = (float) a" in code


def test_instructions_carry_source_lines():
    result = run("int x = 1;\nprint(x);")
    lines = [i["line"] for i in result["phases"]["ir"]["tac"]]
    assert lines[:2] == [1, 2]


def test_quadruples():
    result = run("int x = 2; int y = x + 1; print(y);")
    quads = [i["quad"] for i in result["phases"]["ir"]["tac"]]
    assert quads[1] == {"op": "+", "arg1": "x", "arg2": "1", "result": "y"}


def test_cfg_for_while_loop():
    result = run("int i = 0; while (i < 3) { i = i + 1; } print(i);")
    main = result["phases"]["cfg"]["functions"][0]
    assert len(main["blocks"]) == 4
    assert main["loops"] == 1
    back = [e for e in main["edges"] if e["back"]]
    assert back == [{"from": "B3", "to": "B2", "kind": "jump", "back": True}]
    assert main["mermaid"].startswith("flowchart TD")


def test_cfg_per_function():
    result = run("int f(int n) { if (n > 0) { return 1; } return 0; } print(f(1));")
    names = [f["name"] for f in result["phases"]["cfg"]["functions"]]
    assert names == ["main", "f"]
    branch = [e for e in result["phases"]["cfg"]["functions"][1]["edges"] if e["kind"] in
              ("true", "false")]
    assert len(branch) == 2


def test_user_names_never_collide_with_temporaries():
    assert run("int t1 = 5; int L1 = 2; print(t1 + L1);")["phases"]["execution"]["output"] == ["7"]
