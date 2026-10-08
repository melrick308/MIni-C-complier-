"""Robustness: no input may crash the pipeline."""

import json
import random

import pytest

from compiler import compile_source

ALPHABET = list("ab12 .+-*/%()<>=!&|{};,\"\n") + [
    "if", "else", "while", "for", "do", "int", "float", "bool", "void", "return", "break",
    "continue", "print", "true", "false", " x ", " y ", "==", "&&", "||", "++",
]


@pytest.mark.parametrize("seed", range(400))
def test_random_programs_never_crash(seed):
    rng = random.Random(seed)
    source = "".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 80)))
    result = compile_source(source, optimize=True)
    json.dumps(result)


@pytest.mark.parametrize("seed", range(200))
def test_random_expressions_never_crash(seed):
    rng = random.Random(seed)
    source = "".join(rng.choice(list("ab12 .+-*/()@")) for _ in range(rng.randint(0, 30)))
    result = compile_source(source, "expression", variables={"a": 1, "b": 0})
    json.dumps(result)


@pytest.mark.parametrize("source", [
    "{" * 150 + "}" * 150,
    "int x = " + "(" * 150 + "1" + ")" * 150 + ";",
    "int x = " + "-" * 150 + "1;",
    "print(" + "9" * 400 + ");",
    "x" * 20_000,
    "\n" * 500,
    "<img src=x onerror=alert(1)>",
    'print("<script>alert(1)</script>");',
])
def test_hostile_inputs(source):
    result = compile_source(source)
    json.dumps(result)
    assert result["failed_phase"] is not None or result["phases"]["execution"]["status"] in (
        "ok", "error")


def test_input_limit():
    result = compile_source("x" * 20_000)
    assert result["diagnostics"][0]["code"] == "E_INPUT_TOO_LONG"
    expr = compile_source("1+" * 300 + "1", "expression")
    assert expr["diagnostics"][0]["code"] == "E_INPUT_TOO_LONG"
