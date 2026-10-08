import pathlib

from compiler.cli import main

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_run_program(capsys):
    code = main(["run", str(ROOT / "examples/programs/03_factorial_loop.mc"), "--tac"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Three address code" in out and "5 ! = 120" in out


def test_expression_with_variables(capsys):
    code = main(["expr", "a + b * (c - 2)", "--var", "a=3", "--var", "b=4", "--var", "c=7",
                 "--all"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Result = 23" in out and "t3 = a + t2" in out and "Parsing steps" in out


def test_expression_error_exit_code(capsys):
    assert main(["expr", "a + * b"]) == 1
    out = capsys.readouterr().out
    assert "E_SYN_UNEXPECTED_TOKEN" in out and "^" in out


def test_runtime_error_exit_code(capsys):
    assert main(["run", str(ROOT / "examples/programs/22_error_runtime.mc")]) == 2


def test_json_output(capsys):
    import json

    main(["expr", "1 + 2", "--json"])
    assert json.loads(capsys.readouterr().out)["evaluation"]["value"] == "3"
