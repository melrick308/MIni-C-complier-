"""Both grammars as data. Terminals are TokenType values; everything else is a non-terminal.

The parser functions mirror these productions one-to-one, and FIRST/FOLLOW sets used
for prediction and error messages are computed from this data (see first_follow.py).
"""

from __future__ import annotations

from functools import cache

from ..lexer.tokens import GRAMMAR_SYMBOL, TokenType
from .first_follow import EPSILON, GrammarFacts, compute_facts

EXPRESSION = "expression"
MINIC = "minic"

Grammar = dict[str, list[list[str]]]

# Original grammar from the problem statement (with id split into id | num).
EXPRESSION_GRAMMAR: Grammar = {
    "E": [["T", "E'"]],
    "E'": [["PLUS", "T", "E'"], ["MINUS", "T", "E'"], []],
    "T": [["F", "T'"]],
    "T'": [["MULTIPLY", "F", "T'"], ["DIVIDE", "F", "T'"], []],
    "F": [["LEFT_PAREN", "E", "RIGHT_PAREN"], ["IDENTIFIER"], ["NUMBER"]],
}

MINIC_GRAMMAR: Grammar = {
    "Program": [["TopList", "EOF"]],
    "TopList": [["TopItem", "TopList"], []],
    "TopItem": [["Type", "IDENTIFIER", "DeclTail"], ["void", "IDENTIFIER", "FuncTail"],
                ["NonDeclStmt"]],
    "DeclTail": [["FuncTail"], ["VarInit", "SEMICOLON"]],
    "FuncTail": [["LEFT_PAREN", "Params", "RIGHT_PAREN", "Block"]],
    "Params": [["Param", "ParamList"], []],
    "ParamList": [["COMMA", "Param", "ParamList"], []],
    "Param": [["Type", "IDENTIFIER"]],
    "Type": [["int"], ["float"], ["bool"]],
    "Block": [["LEFT_BRACE", "StmtList", "RIGHT_BRACE"]],
    "StmtList": [["Stmt", "StmtList"], []],
    "Stmt": [["VarDecl"], ["NonDeclStmt"]],
    "VarDecl": [["Type", "IDENTIFIER", "VarInit", "SEMICOLON"]],
    "VarInit": [["ASSIGN", "Expr"], []],
    "NonDeclStmt": [["Block"], ["IfStmt"], ["WhileStmt"], ["DoStmt"], ["ForStmt"],
                    ["ReturnStmt"], ["BreakStmt"], ["ContinueStmt"], ["PrintStmt"],
                    ["IdStmt"], ["SEMICOLON"]],
    "IfStmt": [["if", "LEFT_PAREN", "Expr", "RIGHT_PAREN", "Stmt", "ElsePart"]],
    "ElsePart": [["else", "Stmt"], []],
    "WhileStmt": [["while", "LEFT_PAREN", "Expr", "RIGHT_PAREN", "Stmt"]],
    "DoStmt": [["do", "Stmt", "while", "LEFT_PAREN", "Expr", "RIGHT_PAREN", "SEMICOLON"]],
    "ForStmt": [["for", "LEFT_PAREN", "ForInit", "SEMICOLON", "ForCond", "SEMICOLON",
                 "ForUpdate", "RIGHT_PAREN", "Stmt"]],
    "ForInit": [["Type", "IDENTIFIER", "ASSIGN", "Expr"], ["IDENTIFIER", "AssignTail"], []],
    "ForCond": [["Expr"], []],
    "ForUpdate": [["IDENTIFIER", "AssignTail"], []],
    "ReturnStmt": [["return", "ReturnVal", "SEMICOLON"]],
    "ReturnVal": [["Expr"], []],
    "BreakStmt": [["break", "SEMICOLON"]],
    "ContinueStmt": [["continue", "SEMICOLON"]],
    "PrintStmt": [["print", "LEFT_PAREN", "PrintArgs", "RIGHT_PAREN", "SEMICOLON"]],
    "PrintArgs": [["PrintArg", "PrintArgList"], []],
    "PrintArgList": [["COMMA", "PrintArg", "PrintArgList"], []],
    "PrintArg": [["STRING"], ["Expr"]],
    "IdStmt": [["IDENTIFIER", "IdTail", "SEMICOLON"]],
    "IdTail": [["AssignTail"], ["LEFT_PAREN", "Args", "RIGHT_PAREN"]],
    "AssignTail": [["ASSIGN", "Expr"], ["PLUS_ASSIGN", "Expr"], ["MINUS_ASSIGN", "Expr"],
                   ["STAR_ASSIGN", "Expr"], ["SLASH_ASSIGN", "Expr"], ["INCREMENT"],
                   ["DECREMENT"]],
    "Args": [["Expr", "ArgList"], []],
    "ArgList": [["COMMA", "Expr", "ArgList"], []],
    "Expr": [["Or"]],
    "Or": [["And", "Or'"]],
    "Or'": [["OR", "And", "Or'"], []],
    "And": [["Eq", "And'"]],
    "And'": [["AND", "Eq", "And'"], []],
    "Eq": [["Rel", "Eq'"]],
    "Eq'": [["EQUAL", "Rel"], ["NOT_EQUAL", "Rel"], []],
    "Rel": [["E", "Rel'"]],
    "Rel'": [["LESS", "E"], ["LESS_EQUAL", "E"], ["GREATER", "E"], ["GREATER_EQUAL", "E"], []],
    "E": [["T", "E'"]],
    "E'": [["PLUS", "T", "E'"], ["MINUS", "T", "E'"], []],
    "T": [["U", "T'"]],
    "T'": [["MULTIPLY", "U", "T'"], ["DIVIDE", "U", "T'"], ["MODULO", "U", "T'"], []],
    "U": [["MINUS", "U"], ["NOT", "U"], ["F"]],
    "F": [["LEFT_PAREN", "Expr", "RIGHT_PAREN"], ["NUMBER"], ["true"], ["false"],
          ["IDENTIFIER", "CallSuffix"]],
    "CallSuffix": [["LEFT_PAREN", "Args", "RIGHT_PAREN"], []],
}

GRAMMARS = {EXPRESSION: EXPRESSION_GRAMMAR, MINIC: MINIC_GRAMMAR}
START = {EXPRESSION: "E", MINIC: "Program"}

# Conflicts that are expected and resolved by a documented rule.
RESOLVED_CONFLICTS = {
    MINIC: {("ElsePart", "else"): "Dangling else: 'else' always binds to the nearest 'if'."},
    EXPRESSION: {},
}

# Non-terminal -> parser method name.
FUNCTION_NAMES = {
    "E'": "EPrime", "T'": "TPrime", "Or'": "OrPrime", "And'": "AndPrime",
    "Eq'": "EqPrime", "Rel'": "RelPrime",
}


def function_name(nonterminal: str) -> str:
    return FUNCTION_NAMES.get(nonterminal, nonterminal) + "()"


def symbol_text(symbol: str, grammar: Grammar) -> str:
    if symbol in grammar:
        return symbol
    return GRAMMAR_SYMBOL[TokenType(symbol)]


def production_text(lhs: str, rhs: list[str], grammar: Grammar) -> str:
    body = " ".join(symbol_text(s, grammar) for s in rhs) if rhs else EPSILON
    return f"{lhs} → {body}"


@cache
def facts(profile: str) -> GrammarFacts:
    return compute_facts(GRAMMARS[profile], START[profile])


def terminal_types(symbols) -> set[TokenType]:
    return {TokenType(s) for s in symbols if s != EPSILON}


def grammar_info(profile: str) -> dict:
    """JSON-serialisable description for the Grammar panel."""
    grammar = GRAMMARS[profile]
    f = facts(profile)

    def show(symbols):
        out = [symbol_text(s, grammar) if s != EPSILON else EPSILON for s in symbols]
        order = {s: i for i, s in enumerate(TokenType)}
        return sorted(out, key=lambda s: (s == EPSILON, order.get(_tt(s), 999), s))

    rows = []
    for nt, alternatives in grammar.items():
        rows.append({
            "nonterminal": nt,
            "function": function_name(nt),
            "productions": [production_text(nt, alt, grammar) for alt in alternatives],
            "first": show(f.first[nt]),
            "follow": show(f.follow[nt]),
        })
    table = []
    for (nt, terminal), prods in sorted(f.table.items()):
        table.append({
            "nonterminal": nt,
            "terminal": symbol_text(terminal, grammar),
            "productions": [production_text(nt, p, grammar) for p in prods],
        })
    conflicts = []
    for (nt, terminal), prods in f.conflicts.items():
        conflicts.append({
            "nonterminal": nt,
            "terminal": symbol_text(terminal, grammar),
            "productions": [production_text(nt, p, grammar) for p in prods],
            "resolution": RESOLVED_CONFLICTS[profile].get((nt, terminal)),
        })
    return {
        "profile": profile,
        "start": START[profile],
        "nonterminals": rows,
        "table": table,
        "conflicts": conflicts,
        "is_ll1": all(c["resolution"] for c in conflicts),
    }


def _tt(text: str):
    for tt, sym in GRAMMAR_SYMBOL.items():
        if sym == text:
            return tt
    return None
