"""Differential testing: the optimizer must never change what a program does, and the
pure-arithmetic subset must agree with Python's own arithmetic."""

import random

import pytest

from compiler import compile_source

OPS = ["+", "-", "*", "/", "%"]
RELS = ["<", "<=", ">", ">=", "==", "!="]


class ProgramGenerator:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.loop_vars = 0

    def expr(self, names, depth=0):
        r = self.rng
        if depth > 2 or r.random() < 0.35:
            return r.choice(names) if r.random() < 0.6 else str(r.randint(0, 9))
        if r.random() < 0.1:
            return f"-({self.expr(names, depth + 1)})"
        return f"({self.expr(names, depth + 1)} {r.choice(OPS)} {self.expr(names, depth + 1)})"

    def cond(self, names):
        c = f"{self.expr(names)} {self.rng.choice(RELS)} {self.expr(names)}"
        if self.rng.random() < 0.3:
            c = f"({c}) {self.rng.choice(['&&', '||'])} ({self.expr(names)} != 0)"
        return c

    def stmt(self, names, depth=0):
        r = self.rng
        kind = r.random()
        target = r.choice(names)
        if depth > 2 or kind < 0.35:
            return f"{target} = {self.expr(names)};"
        if kind < 0.45:
            return f"{target} {r.choice(['+=', '-=', '*='])} {self.expr(names)};"
        if kind < 0.6:
            return f"print({self.expr(names)});"
        if kind < 0.8:
            return (f"if ({self.cond(names)}) {{ {self.stmt(names, depth + 1)} }} "
                    f"else {{ {self.stmt(names, depth + 1)} }}")
        self.loop_vars += 1
        v = f"i{self.loop_vars}"
        body = self.stmt(names + [v], depth + 1)
        extra = " if (a > 50) { break; }" if r.random() < 0.3 else ""
        return f"for (int {v} = 0; {v} < {r.randint(1, 4)}; {v}++) {{ {body}{extra} }}"

    def program(self):
        names = ["a", "b", "c"]
        lines = [f"int {n} = {self.rng.randint(-5, 9)};" for n in names]
        lines += [self.stmt(names) for _ in range(self.rng.randint(3, 8))]
        lines.append("print(a, b, c);")
        return "\n".join(lines)


def behaviour(result):
    ex = result["phases"]["execution"]
    diag = [d["code"] for d in result["diagnostics"] if d["severity"] == "error"]
    return ex.get("output"), diag


@pytest.mark.parametrize("seed", range(150))
def test_optimizer_preserves_behaviour(seed):
    source = ProgramGenerator(seed).program()
    plain = compile_source(source)
    assert plain["failed_phase"] is None, (source, plain["diagnostics"])
    optimized = compile_source(source, optimize=True)
    assert behaviour(plain) == behaviour(optimized), source


def _c_div(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


@pytest.mark.parametrize("seed", range(100))
def test_expression_mode_matches_python(seed):
    rng = random.Random(seed)

    def gen(depth=0):
        if depth > 3 or rng.random() < 0.3:
            return str(rng.randint(1, 9))
        return f"({gen(depth + 1)} {rng.choice('+-*/')} {gen(depth + 1)})"

    expr = gen()
    result = compile_source(expr, "expression")
    try:
        expected = eval(expr)  # test oracle only: never applied to user input
    except ZeroDivisionError:
        assert result["evaluation"]["status"] == "error"
        return
    assert abs(float(result["evaluation"]["value"]) - expected) <= 1e-6 * max(1, abs(expected))
