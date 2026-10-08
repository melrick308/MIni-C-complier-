from compiler.syntax.first_follow import compute_facts
from compiler.syntax.grammar import EXPRESSION, MINIC, facts, grammar_info


def test_expression_first_follow_matches_textbook():
    f = facts(EXPRESSION)
    assert f.first["E"] == {"LEFT_PAREN", "IDENTIFIER", "NUMBER"}
    assert f.first["E'"] == {"PLUS", "MINUS", "ε"}
    assert f.first["T'"] == {"MULTIPLY", "DIVIDE", "ε"}
    assert f.follow["E"] == {"RIGHT_PAREN", "EOF"}
    assert f.follow["E'"] == {"RIGHT_PAREN", "EOF"}
    assert f.follow["T"] == {"PLUS", "MINUS", "RIGHT_PAREN", "EOF"}
    assert f.follow["T'"] == {"PLUS", "MINUS", "RIGHT_PAREN", "EOF"}
    assert f.follow["F"] == {"MULTIPLY", "DIVIDE", "PLUS", "MINUS", "RIGHT_PAREN", "EOF"}


def test_expression_grammar_is_ll1():
    assert facts(EXPRESSION).conflicts == {}


def test_minic_grammar_is_ll1_except_dangling_else():
    conflicts = facts(MINIC).conflicts
    assert set(conflicts) == {("ElsePart", "else")}
    assert grammar_info(MINIC)["is_ll1"] is True


def test_left_recursive_grammar_is_detected_as_not_ll1():
    left_recursive = {"E": [["E", "PLUS", "T"], ["T"]], "T": [["IDENTIFIER"]]}
    assert compute_facts(left_recursive, "E").conflicts


def test_grammar_info_is_serialisable():
    import json

    info = grammar_info(MINIC)
    json.dumps(info)
    names = {row["nonterminal"] for row in info["nonterminals"]}
    assert {"Program", "IfStmt", "E'", "CallSuffix"} <= names
    e_prime = next(r for r in info["nonterminals"] if r["nonterminal"] == "E'")
    assert e_prime["function"] == "EPrime()"
    assert "E' → + T E'" in e_prime["productions"]
