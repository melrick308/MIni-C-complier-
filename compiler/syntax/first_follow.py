"""FIRST / FOLLOW sets and the LL(1) parse table, computed by the textbook fixed-point method."""

from __future__ import annotations

from dataclasses import dataclass, field

EPSILON = "ε"
END = "EOF"


@dataclass
class GrammarFacts:
    first: dict[str, set[str]]
    follow: dict[str, set[str]]
    table: dict[tuple[str, str], list[list[str]]] = field(default_factory=dict)
    conflicts: dict[tuple[str, str], list[list[str]]] = field(default_factory=dict)

    def first_of(self, symbols: list[str]) -> set[str]:
        return first_of_sequence(symbols, self.first)


def first_of_sequence(symbols: list[str], first: dict[str, set[str]]) -> set[str]:
    result: set[str] = set()
    for sym in symbols:
        sym_first = first[sym] if sym in first else {sym}
        result |= sym_first - {EPSILON}
        if EPSILON not in sym_first:
            return result
    result.add(EPSILON)
    return result


def compute_facts(grammar: dict[str, list[list[str]]], start: str) -> GrammarFacts:
    first: dict[str, set[str]] = {nt: set() for nt in grammar}
    changed = True
    while changed:
        changed = False
        for nt, alternatives in grammar.items():
            for alt in alternatives:
                add = first_of_sequence(alt, first)
                if not add <= first[nt]:
                    first[nt] |= add
                    changed = True

    follow: dict[str, set[str]] = {nt: set() for nt in grammar}
    follow[start].add(END)
    changed = True
    while changed:
        changed = False
        for nt, alternatives in grammar.items():
            for alt in alternatives:
                for i, sym in enumerate(alt):
                    if sym not in grammar:
                        continue
                    rest = first_of_sequence(alt[i + 1:], first)
                    add = rest - {EPSILON}
                    if EPSILON in rest:
                        add |= follow[nt]
                    if not add <= follow[sym]:
                        follow[sym] |= add
                        changed = True

    table: dict[tuple[str, str], list[list[str]]] = {}
    for nt, alternatives in grammar.items():
        for alt in alternatives:
            alt_first = first_of_sequence(alt, first)
            targets = alt_first - {EPSILON}
            if EPSILON in alt_first:
                targets |= follow[nt]
            for terminal in targets:
                table.setdefault((nt, terminal), []).append(alt)
    conflicts = {key: prods for key, prods in table.items() if len(prods) > 1}
    return GrammarFacts(first, follow, table, conflicts)
