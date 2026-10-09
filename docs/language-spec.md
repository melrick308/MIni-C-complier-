# MiniC language specification

## Lexical structure

| Element | Rule |
|---|---|
| Identifiers | `[A-Za-z_][A-Za-z0-9_]*`, case-sensitive |
| Integers | `[0-9]+` |
| Floats | `[0-9]+\.[0-9]+` (`3.` and `.5` are errors) |
| Strings | `"…"` with escapes `\n \t \" \\`; allowed **only** as `print` arguments |
| Keywords | `int float bool void if else while do for return break continue print true false` |
| Operators | `+ - * / % < <= > >= == != && \|\| ! = += -= *= /= ++ --` |
| Delimiters | `( ) { } , ;` |
| Comments | `// to end of line` and `/* block */` |

The lexer uses maximal munch: the longest operator wins, so `<=` is one token and `a--b` is `a -- b`.

## Grammar

See [grammar.md](grammar.md) for the full LL(1) grammar.

## Programs

A program is a sequence of global variable declarations, function definitions and statements.
Execution starts with the first top-level statement (script style, so no `main` is needed).
Functions are top-level only. They can be called before they are defined, because they are hoisted.

```c
int square(int x) { return x * x; }
for (int i = 1; i <= 3; i++) {
    print(i, "squared is", square(i));
}
```

## Types

| Type | Values | Default |
|---|---|---|
| `int` | arbitrary-precision integers | `0` |
| `float` | 64-bit floating point | `0.0` |
| `bool` | `true`, `false` | `false` |
| `void` | function return type only | – |

Type rules:

| Expression | Rule |
|---|---|
| `a + b`, `a - b`, `a * b`, `a / b` | numeric operands; the result is `float` if either operand is `float`, otherwise `int` |
| `a % b` | `int` operands only |
| `int / int` | truncates toward zero, as in C (`-7 / 2 == -3`) |
| `< <= > >=` | numeric operands → `bool` |
| `== !=` | both numeric or both `bool` → `bool` |
| `&& \|\| !` | `bool` operands → `bool` (short-circuit) |
| unary `-` | numeric |
| conditions of `if/while/for/do` | must be `bool` (stricter than C on purpose) |
| assignment, initialisation, arguments, `return` | same type, or `int` → `float` widening; `float` → `int` is an error |

## Statements

```
int x = 1;            float f;               bool done = false;
x = x + 1;            x += 2;   x++;   x--;   (compound forms are desugared: x += 2 ⇒ x = x + 2)
if (c) S  [else S]    while (c) S            do S while (c);
for (init; cond; update) S                  (each part optional; empty cond = true)
break;  continue;     return [expr];         print(a, "text", b);
f(args);              { ... }                ;
```

`print` separates its arguments with a single space and ends the line. Floats always show a
decimal point (`7.0`). Booleans print as `true` and `false`.

## Scopes

Scopes are global, function, block and for-loop. A name must be declared before use. Redeclaring a name in the same scope is an
error. Inner scopes may shadow outer ones; the IR renames shadowed variables (`x`, `x_2`).

## Runtime limits

| Limit | Value |
|---|---|
| Instructions executed | 100,000 |
| Wall time | 2 seconds |
| Nested calls | 200 |
| Printed lines | 1,000 |
| Source size | 10,000 characters / 400 lines (Expression mode: 500 characters) |
| Nesting (parentheses + blocks + unary) | 100 |
| Operators stacked in one expression tree | 200 |

## Expression mode

Expression mode accepts one arithmetic expression using the original grammar:
`+ - * / ( )`, identifiers and numbers. There is no unary minus.

Variable values come from the Variables panel. Division is true division (`7 / 2 = 3.5`), as in
the original problem statement.
