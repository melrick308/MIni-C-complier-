# Three Address Code (IR) specification

Each instruction has at most one operator. Temporaries are `t1, t2, …` and labels are `L1, L2, …`.
Both restart at 1 for every compilation. Every instruction records the source span and the AST node it came from.

| Op | Text form | Quadruple (op, arg1, arg2, result) |
|---|---|---|
| assign | `x = a` | `(=, a, , x)` |
| binop | `t1 = a + b` (also `- * / % < <= > >= == !=`) | `(+, a, b, t1)` |
| unop | `t1 = minus a`, `t1 = not a`, `t1 = (float) a` | `(minus, a, , t1)` |
| label | `L1:` | `(label, , , L1)` |
| goto | `goto L1` | `(goto, , , L1)` |
| iffalse | `ifFalse t1 goto L2` | `(ifFalse, t1, , L2)` |
| iftrue | `if t1 goto L2` | `(if, t1, , L2)` |
| param | `param a` | `(param, a, , )` |
| call | `t3 = call f, 2` (or `call f, 2` for void) | `(call, f, 2, t3)` |
| return | `return t1` / `return` | `(return, t1, , )` |
| print | `print "x =", x` | `(print, "x =", x, , )` |
| func / endfunc | `func f(a, b):` … `endfunc f` | `(func, f, 2, )` |
| halt | `halt` | `(halt, , , )` |

Layout: the top-level statements come first and end with `halt`, followed by each function between `func` and `endfunc`.

## Translation schemes

```
x = a + b * c        t1 = b * c
                     x = a + t1                (the last temporary is written straight into x)

if (c) S1 else S2    t = c
                     ifFalse t goto Lelse
                     S1
                     goto Lend
                   Lelse:
                     S2
                   Lend:

while (c) S        Lstart:
                     t = c
                     ifFalse t goto Lend
                     S                          (continue → goto Lstart, break → goto Lend)
                     goto Lstart
                   Lend:

do S while (c);    Lstart:
                     S                          (continue → goto Lcont)
                   Lcont:
                     t = c
                     if t goto Lstart
                   Lend:

for (I; C; U) S      I
                   Lstart:
                     t = C ; ifFalse t goto Lend
                     S                          (continue → goto Lcont, break → goto Lend)
                   Lcont:
                     U
                     goto Lstart
                   Lend:

a && b               t = a                      (a || b uses: if t goto L)
                     ifFalse t goto L
                     t = b
                   L:

f(a, b)              param a
                     param b
                     t = call f, 2
```

Conversions: wherever an `int` value flows into a `float` (an initialiser, assignment, argument or return),
the generator inserts `t = (float) x`, or converts the constant directly.

Uninitialised declarations emit an explicit default (`x = 0`, `f = 0.0`, `b = false`).

## Virtual machine

- Labels are resolved to indices before execution.
- Globals live in one table. Each call pushes a frame holding the parameters, locals and temporaries, the return address and the result target.
- Integer `/` and `%` truncate toward zero. Expression mode uses true division.
- Every executed instruction records `{step, pc, func, frame, depth, line, text, writes[], event?, output?}`. The debugger rebuilds any past state by replaying this list, which is how stepping backwards works.
