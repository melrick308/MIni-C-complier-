from tests.helpers import run


def optimized(src):
    result = run(src, optimize=True)
    assert result["success"], result["diagnostics"]
    return [i["text"] for i in result["phases"]["optimize"]["tac"]], result


def test_constant_folding_and_propagation():
    code, result = optimized("int x = 2 * 3 + 4; int y = x * 2; print(y);")
    assert code == ["x = 10", "y = 20", "print 20", "halt"]
    assert result["phases"]["optimize"]["changes"]["constant folding"] >= 2
    assert result["phases"]["execution"]["output"] == ["20"]


def test_algebraic_simplification():
    code, _ = optimized("int a = 5; a = a; int b = a * 1 + 0; print(b);")
    assert "t1 = a * 1" not in code


def test_constant_false_branch_is_removed():
    code, result = optimized('if (1 > 2) { print("never"); } print("done");')
    assert '"never"' not in " ".join(code)
    assert result["phases"]["execution"]["output"] == ["done"]


def test_marks_reference_original_instructions():
    _, result = optimized("int x = 2 * 3; print(x);")
    marks = result["phases"]["optimize"]["marks"]
    assert marks  # at least one original instruction rewritten or removed
    assert set(marks.values()) <= {"removed", "rewritten"}


def test_loop_variables_are_not_propagated_across_labels():
    _, result = optimized("int i = 0; int s = 0; while (i < 4) { s = s + i; i = i + 1; } print(s);")
    assert result["phases"]["execution"]["output"] == ["6"]


def test_calls_invalidate_known_globals():
    src = "int g = 1; void bump() { g = 5; } bump(); print(g);"
    _, result = optimized(src)
    assert result["phases"]["execution"]["output"] == ["5"]


def test_division_by_zero_is_not_folded():
    result = run("print(1 / 0);", optimize=True)
    assert result["diagnostics"][0]["code"] == "E_RT_DIV_ZERO"
