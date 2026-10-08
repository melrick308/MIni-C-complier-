from compiler import compile_source
from compiler.lexer.lexer import tokenize
from compiler.syntax.parser import parse


def parse_expr(src: str):
    tokens, err = tokenize(src)
    assert err is None, err
    return parse(tokens, "expression")


def parse_prog(src: str):
    tokens, err = tokenize(src)
    assert err is None, err
    return parse(tokens, "minic")


def run(src: str, **kwargs) -> dict:
    return compile_source(src, **kwargs)


def output(src: str, **kwargs) -> list[str]:
    result = compile_source(src, **kwargs)
    assert result["success"], result["diagnostics"]
    return result["phases"]["execution"]["output"]


def codes(result: dict, severity: str = "error") -> list[tuple[str, int, int]]:
    return [(d["code"], d["line"], d["col"]) for d in result["diagnostics"]
            if d["severity"] == severity]
