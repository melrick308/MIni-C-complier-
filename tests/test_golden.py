"""Every sample program in examples/ is a golden test: valid ones must print their .out file,
error samples must produce exactly the expected diagnostics."""

import json
import pathlib

import pytest

from compiler import compile_source
from tests.helpers import codes

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROGRAMS = sorted((ROOT / "examples" / "programs").glob("*.mc"))
VALID = [p for p in PROGRAMS if p.with_suffix(".out").exists()]

EXPECTED_ERRORS = {
    "19_infinite_loop": [("E_RT_STEP_LIMIT", 5)],
    "20_error_syntax": [("E_SYN_MISSING_SEMICOLON", 4), ("E_SYN_MISSING_SEMICOLON", 6),
                        ("E_SYN_EXPECTED", 7)],
    "21_error_semantic": [("E_SEM_LOSSY_ASSIGN", 6), ("E_SEM_CONDITION_NOT_BOOL", 7),
                          ("E_SEM_UNDECLARED", 8), ("E_SEM_INVALID_OPERANDS", 10)],
    "22_error_runtime": [("E_RT_DIV_ZERO", 7)],
    "23_error_lexical": [("E_LEX_INVALID_CHAR", 5)],
}


def test_every_sample_is_covered():
    assert {p.stem for p in PROGRAMS} == {p.stem for p in VALID} | set(EXPECTED_ERRORS)


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
@pytest.mark.parametrize("optimize", [False, True], ids=["plain", "optimized"])
def test_valid_program_output(path, optimize):
    result = compile_source(path.read_text(encoding="utf-8"), optimize=optimize)
    assert result["success"], result["diagnostics"]
    expected = path.with_suffix(".out").read_text(encoding="utf-8").splitlines()
    assert result["phases"]["execution"]["output"] == expected


@pytest.mark.parametrize("name", sorted(EXPECTED_ERRORS))
def test_error_program_diagnostics(name):
    source = (ROOT / "examples" / "programs" / f"{name}.mc").read_text(encoding="utf-8")
    result = compile_source(source)
    assert not result["success"]
    assert [(c, line) for c, line, _ in codes(result)] == EXPECTED_ERRORS[name]


@pytest.mark.parametrize("path", PROGRAMS, ids=lambda p: p.stem)
def test_results_are_json_serialisable(path):
    json.dumps(compile_source(path.read_text(encoding="utf-8"), optimize=True))


def test_expression_examples_behave_as_labelled():
    examples = json.loads((ROOT / "examples" / "expressions.json").read_text(encoding="utf-8"))
    for ex in examples:
        result = compile_source(ex["expression"], "expression", variables=ex["variables"])
        category = ex["category"]
        if category == "valid":
            assert result["success"], ex
        elif category == "runtime":
            assert result["evaluation"]["status"] == "error", ex
        else:
            assert result["failed_phase"] == category, ex
