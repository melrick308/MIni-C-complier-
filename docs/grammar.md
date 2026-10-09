# Grammar and parser design

The grammar is stored as **data** in `compiler/syntax/grammar.py`. From that data,
`first_follow.py` computes the FIRST and FOLLOW sets and the LL(1) parse table with the standard
fixed-point algorithms. The parser uses those sets for its decisions and its error messages.
`tests/unit/test_first_follow.py` proves that there are no table conflicts other than the dangling else, which is documented below.

## Expression grammar (original problem statement)

```
E  → T E'
E' → + T E' | - T E' | ε
T  → F T'
T' → * F T' | / F T' | ε
F  → ( E ) | id | num
```

| | FIRST | FOLLOW |
|---|---|---|
| E | `( id num` | `) $` |
| E' | `+ - ε` | `) $` |
| T | `( id num` | `+ - ) $` |
| T' | `* / ε` | `+ - ) $` |
| F | `( id num` | `* / + - ) $` |

## MiniC grammar

```
Program    → TopList $
TopList    → TopItem TopList | ε
TopItem    → Type id DeclTail | void id FuncTail | NonDeclStmt
DeclTail   → FuncTail | VarInit ;                     (left-factored: function vs global variable)
FuncTail   → ( Params ) Block
Params     → Param ParamList | ε          ParamList → , Param ParamList | ε
Param      → Type id                      Type      → int | float | bool
Block      → { StmtList }                 StmtList  → Stmt StmtList | ε
Stmt       → VarDecl | NonDeclStmt
VarDecl    → Type id VarInit ;            VarInit   → = Expr | ε
NonDeclStmt→ Block | IfStmt | WhileStmt | DoStmt | ForStmt | ReturnStmt
           | BreakStmt | ContinueStmt | PrintStmt | IdStmt | ;
IfStmt     → if ( Expr ) Stmt ElsePart    ElsePart  → else Stmt | ε
WhileStmt  → while ( Expr ) Stmt
DoStmt     → do Stmt while ( Expr ) ;
ForStmt    → for ( ForInit ; ForCond ; ForUpdate ) Stmt
ForInit    → Type id = Expr | id AssignTail | ε
ForCond    → Expr | ε                     ForUpdate → id AssignTail | ε
ReturnStmt → return ReturnVal ;           ReturnVal → Expr | ε
BreakStmt  → break ;                      ContinueStmt → continue ;
PrintStmt  → print ( PrintArgs ) ;
PrintArgs  → PrintArg PrintArgList | ε    PrintArgList → , PrintArg PrintArgList | ε
PrintArg   → str | Expr
IdStmt     → id IdTail ;                  (left-factored: assignment vs call)
IdTail     → AssignTail | ( Args )
AssignTail → = Expr | += Expr | -= Expr | *= Expr | /= Expr | ++ | --
Args       → Expr ArgList | ε             ArgList   → , Expr ArgList | ε

Expr → Or
Or   → And Or'      Or'  → || And Or' | ε
And  → Eq And'      And' → && Eq And' | ε
Eq   → Rel Eq'      Eq'  → == Rel | != Rel | ε           (non-associative)
Rel  → E Rel'       Rel' → < E | <= E | > E | >= E | ε   (non-associative)
E    → T E'         E'   → + T E' | - T E' | ε
T    → U T'         T'   → * U T' | / U T' | % U T' | ε
U    → - U | ! U | F
F    → ( Expr ) | num | true | false | id CallSuffix
CallSuffix → ( Args ) | ε
```

The Grammar tab in the UI shows every non-terminal with its parser function, FIRST and FOLLOW sets,
and the complete LL(1) table.

## Why the grammar looks like this

**Precedence comes from levels.** Each precedence level is one non-terminal. Lower levels bind tighter:
`||` < `&&` < `== !=` < `< <= > >=` < `+ -` < `* / %` < unary < primary.
`a + b * c` therefore parses as `a + (b * c)`, because `*` is handled deeper, in `T`.

**Left recursion was removed.** `E → E + T` would make `E()` call itself before consuming a token,
which is infinite recursion. It is rewritten as `E → T E'`, `E' → + T E' | ε`.

**Left factoring.** Both an assignment and a call start with `id`, and both a function and a global
variable start with `Type id`. The common prefix is factored out (`IdStmt → id IdTail`,
`TopItem → Type id DeclTail`), so a single lookahead token decides.

**Non-associative comparisons.** `Eq'` and `Rel'` have no recursive alternative, so `a < b < c` is
rejected with `E_SYN_CHAINED_COMPARISON`.

**Dangling else.** `ElsePart → else Stmt | ε` puts `else` in both FIRST and FOLLOW of
`ElsePart`, which is the only LL(1) conflict. It is resolved the standard way: the parser always
takes `else` when it sees it, so `else` binds to the nearest `if`.

## Associativity with a right-recursive grammar

`E' → - T E'` is right-recursive. If the AST simply copied the parse tree shape, `10 - 4 - 3`
would become `10 - (4 - 3) = 9`. Instead, each `X'` function receives the AST built so far as an
**inherited attribute** and folds each new operand onto it from the left (an L-attributed
syntax-directed definition):

```python
def _chain(self, prime, ops, operand_fn, operand_symbol, left):
    while self.la.type in ops:            # E' → op T E'
        tok = self.la
        self.match(tok.type)
        right = operand_fn()
        left = Binary(ops[tok.type], left, right)   # fold onto the inherited left operand
    self.prime_epsilon(prime)             # E' → ε when the lookahead ∈ FOLLOW(E')
    return left
```

The result is `((10 - 4) - 3) = 3`. The loop still builds the nested `E'` nodes of the parse tree,
so the trace matches the grammar exactly.

## Prediction and errors

- A prime function applies ε only if the lookahead is in its FOLLOW set. In Expression mode any other token is
  an error, and its *expected* list is FIRST ∪ FOLLOW. For `a b` that gives "Missing operator before 'b'; expected '+', '-', '*', '/', ')', end of input".
- In Program mode a token that cannot continue an expression is left for the enclosing rule to report.
  That lets a missing `;` be reported at the end of the previous line, not at the next statement.
- **Phrase-level recovery:** a missing `;` is reported and assumed, so parsing continues normally.
- **Panic-mode recovery:** for other errors the parser skips tokens until a synchronising token (`;` is consumed,
  or it stops at `}`, `{` or a statement keyword), then continues with the next statement. Only one error is
  reported per token, and parsing stops after 20 errors.
