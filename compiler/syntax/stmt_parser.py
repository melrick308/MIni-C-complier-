"""Statement, declaration and function parsing functions (MiniC profile)."""

from __future__ import annotations

from ..common.source import Span
from ..lexer.tokens import Token, TokenType
from .ast import (
    Assign,
    Block,
    Break,
    Call,
    CallStmt,
    Continue,
    DoWhile,
    For,
    FuncDecl,
    If,
    Literal,
    Node,
    Param,
    Print,
    Program,
    Return,
    StringLit,
    Var,
    VarDecl,
    While,
)
from .grammar import terminal_types
from .parser_base import ParseError, quote

T = TokenType

TYPE_TOKENS = {T.INT: "int", T.FLOAT: "float", T.BOOL: "bool"}
ASSIGN_OPS = {T.ASSIGN: "=", T.PLUS_ASSIGN: "+=", T.MINUS_ASSIGN: "-=", T.STAR_ASSIGN: "*=",
              T.SLASH_ASSIGN: "/=", T.INCREMENT: "++", T.DECREMENT: "--"}
EXPRESSION_START = {T.NUMBER, T.STRING, T.LEFT_PAREN, T.MINUS, T.NOT, T.TRUE, T.FALSE}


class StatementMixin:
    # ------------------------------------------------------------------ program
    def parse_program(self) -> Program:
        root = self.enter("Program", ["TopList", "EOF"])
        items: list[Node] = []
        opened = []
        while self.la.type is not T.EOF:
            opened.append(self.enter("TopList", ["TopItem", "TopList"]))
            item = self.guarded(self.TopItem)
            if item is not None:
                items.append(item)
        self.epsilon("TopList", "'$' ∈ FOLLOW(TopList) → TopList → ε")
        for node in reversed(opened):
            self.exit(node)
        eof = self.match(T.EOF)
        self.exit(root)
        if self.errors:
            self.tracer.record(0, "Program", "reject", eof, None, None,
                               f"End of input reached with {len(self.errors)} syntax error(s)")
        else:
            self.tracer.record(0, "Program", "accept", eof, None, None,
                               "End of input reached → program accepted")
        span = None
        for item in items:
            span = item.span if span is None else span.merge(item.span)
        return Program(items, span=span or eof.span)

    def TopItem(self) -> Node | None:
        la = self.la
        if la.type in TYPE_TOKENS:
            node = self.enter("TopItem", ["Type", "IDENTIFIER", "DeclTail"])
            type_name, type_tok = self.Type()
            name = self.expect(T.IDENTIFIER)
            if self.la.type is T.LEFT_PAREN:
                tail = self.enter("DeclTail", ["FuncTail"])
                result: Node = self.FuncTail(type_name, name, type_tok)
            else:
                tail = self.enter("DeclTail", ["VarInit", "SEMICOLON"])
                init = self.VarInit()
                self.expect_semicolon()
                result = VarDecl(name.lexeme, type_name, init, name.span,
                                 span=self.span_from(type_tok))
            self.exit(tail)
            self.exit(node)
            return result
        if la.type is T.VOID:
            node = self.enter("TopItem", ["void", "IDENTIFIER", "FuncTail"])
            void_tok = self.match(T.VOID)
            name = self.expect(T.IDENTIFIER)
            if self.la.type is not T.LEFT_PAREN:
                raise self.error("E_SYN_EXPECTED",
                                 f"Expected '(' after function name '{name.lexeme}'",
                                 expected=[T.LEFT_PAREN],
                                 hint="'void' can only be used as a function return type.")
            result = self.FuncTail("void", name, void_tok)
            self.exit(node)
            return result
        node = self.enter("TopItem", ["NonDeclStmt"])
        result = self.NonDeclStmt()
        self.exit(node)
        return result

    def Type(self) -> tuple[str, Token]:
        la = self.la
        if la.type not in TYPE_TOKENS:
            raise self.error("E_SYN_EXPECTED",
                             f"Expected a type (int, float or bool) but found {la.describe()}",
                             expected=set(TYPE_TOKENS))
        node = self.enter("Type", [la.type.value])
        tok = self.match(la.type)
        self.exit(node)
        return TYPE_TOKENS[tok.type], tok

    # ---------------------------------------------------------------- functions
    def FuncTail(self, return_type: str, name: Token, start: Token) -> FuncDecl:
        node = self.enter("FuncTail", ["LEFT_PAREN", "Params", "RIGHT_PAREN", "Block"])
        self.match(T.LEFT_PAREN)
        params = self.Params()
        self.expect(T.RIGHT_PAREN)
        if self.la.type is not T.LEFT_BRACE:
            raise self.error("E_SYN_EXPECTED",
                             f"Expected '{{' to start the body of function '{name.lexeme}'",
                             expected=[T.LEFT_BRACE])
        body = self.Block()
        self.exit(node)
        return FuncDecl(name.lexeme, return_type, params, body, name.span,
                        span=start.span.merge(body.span))

    def Params(self) -> list[Param]:
        if self.la.type is T.RIGHT_PAREN:
            self.epsilon("Params", "')' ∈ FOLLOW(Params) → Params → ε (no parameters)")
            return []
        node = self.enter("Params", ["Param", "ParamList"])
        params = [self.Param()]
        opened = []
        while self.la.type is T.COMMA:
            opened.append(self.enter("ParamList", ["COMMA", "Param", "ParamList"]))
            self.match(T.COMMA)
            params.append(self.Param())
        self.epsilon("ParamList", f"{quote(self.la)} is not ',' → ParamList → ε")
        for n in reversed(opened):
            self.exit(n)
        self.exit(node)
        return params

    def Param(self) -> Param:
        if self.la.type not in TYPE_TOKENS:
            raise self.error(
                "E_SYN_EXPECTED",
                f"Expected a parameter type (int, float or bool) but found {self.la.describe()}",
                expected=set(TYPE_TOKENS))
        node = self.enter("Param", ["Type", "IDENTIFIER"])
        type_name, type_tok = self.Type()
        name = self.expect(T.IDENTIFIER)
        self.exit(node)
        return Param(name.lexeme, type_name, span=type_tok.span.merge(name.span))

    # ------------------------------------------------------------------- blocks
    def Block(self) -> Block:
        node = self.enter("Block", ["LEFT_BRACE", "StmtList", "RIGHT_BRACE"])
        open_tok = self.match(T.LEFT_BRACE)
        self.push_nesting(open_tok)
        self.block_depth += 1
        stmts = self.StmtList()
        if self.la.type is not T.RIGHT_BRACE:
            raise self.error("E_SYN_MISSING_RBRACE", "Missing '}' to close the block",
                             expected=[T.RIGHT_BRACE],
                             hint=f"The '{{' at line {open_tok.line} is never closed.",
                             related=(open_tok.span, "'{' opened here"))
        close = self.match(T.RIGHT_BRACE)
        self.block_depth -= 1
        self.nesting -= 1
        self.exit(node)
        return Block(stmts, span=open_tok.span.merge(close.span))

    def StmtList(self) -> list[Node]:
        stmts: list[Node] = []
        opened = []
        while self.la.type not in (T.RIGHT_BRACE, T.EOF):
            opened.append(self.enter("StmtList", ["Stmt", "StmtList"]))
            stmt = self.guarded(self.Stmt)
            if stmt is not None:
                stmts.append(stmt)
        self.epsilon("StmtList", f"{quote(self.la)} ends the statement list → StmtList → ε")
        for node in reversed(opened):
            self.exit(node)
        return stmts

    def Stmt(self) -> Node | None:
        la = self.la
        if la.type in TYPE_TOKENS:
            node = self.enter("Stmt", ["VarDecl"])
            result = self.VarDecl()
            self.exit(node)
            return result
        if la.type is T.VOID:
            raise self.error("E_SYN_NESTED_FUNCTION",
                             "Functions can only be declared at the top level, not inside a block")
        node = self.enter("Stmt", ["NonDeclStmt"])
        result = self.NonDeclStmt()
        self.exit(node)
        return result

    def body(self) -> Node:
        """A statement used as the body of if/while/for; an empty statement becomes {}."""
        start = self.la
        stmt = self.Stmt()
        return stmt if stmt is not None else Block([], span=start.span)

    def VarDecl(self) -> VarDecl:
        node = self.enter("VarDecl", ["Type", "IDENTIFIER", "VarInit", "SEMICOLON"])
        type_name, type_tok = self.Type()
        name = self.expect(T.IDENTIFIER)
        if self.la.type is T.LEFT_PAREN:
            raise self.error("E_SYN_NESTED_FUNCTION",
                             f"Function '{name.lexeme}' must be declared at the top level, "
                             "not inside a block", span=name.span)
        init = self.VarInit()
        self.expect_semicolon()
        self.exit(node)
        return VarDecl(name.lexeme, type_name, init, name.span, span=self.span_from(type_tok))

    def VarInit(self) -> Node | None:
        if self.la.type is T.ASSIGN:
            node = self.enter("VarInit", ["ASSIGN", "Expr"])
            self.match(T.ASSIGN)
            value = self.Expr()
            self.exit(node)
            return value
        self.epsilon("VarInit", f"{quote(self.la)} is not '=' → VarInit → ε (no initializer)")
        return None

    # ---------------------------------------------------------------- statements
    def NonDeclStmt(self) -> Node | None:
        la = self.la
        dispatch = {
            T.LEFT_BRACE: ("Block", self.Block), T.IF: ("IfStmt", self.IfStmt),
            T.WHILE: ("WhileStmt", self.WhileStmt), T.DO: ("DoStmt", self.DoStmt),
            T.FOR: ("ForStmt", self.ForStmt), T.RETURN: ("ReturnStmt", self.ReturnStmt),
            T.BREAK: ("BreakStmt", self.BreakStmt), T.CONTINUE: ("ContinueStmt", self.ContinueStmt),
            T.PRINT: ("PrintStmt", self.PrintStmt), T.IDENTIFIER: ("IdStmt", self.IdStmt),
        }
        if la.type is T.SEMICOLON:
            node = self.enter("NonDeclStmt", ["SEMICOLON"])
            self.match(T.SEMICOLON)
            self.exit(node)
            return None
        if la.type in dispatch:
            symbol, parse_fn = dispatch[la.type]
            node = self.enter("NonDeclStmt", [symbol])
            result = parse_fn()
            self.exit(node)
            return result
        expected = terminal_types(self.facts.first["Stmt"])
        if la.type is T.ELSE:
            raise self.error("E_SYN_ELSE_WITHOUT_IF", "'else' without a matching 'if'",
                             hint="Check for a stray ';' after the if-body or a missing '{'.")
        if la.type is T.EOF:
            raise self.error("E_SYN_UNEXPECTED_EOF", "Unexpected end of input: expected a statement",
                             expected=expected)
        if la.type is T.RIGHT_BRACE:
            raise self.error("E_SYN_UNEXPECTED_TOKEN", "Unmatched '}' — no block is open",
                             hint="Remove the extra '}' or add the missing '{'.")
        hint = None
        if la.type in EXPRESSION_START:
            hint = ("An expression on its own is not a statement — assign it to a variable or "
                    "print it.")
        return_error = self.error("E_SYN_EXPECTED_STATEMENT",
                                  f"Expected a statement but found {la.describe()}",
                                  expected=expected, hint=hint)
        raise return_error

    def IfStmt(self) -> If:
        node = self.enter("IfStmt", ["if", "LEFT_PAREN", "Expr", "RIGHT_PAREN", "Stmt", "ElsePart"])
        kw = self.match(T.IF)
        self.expect(T.LEFT_PAREN)
        cond = self.Expr()
        self.expect(T.RIGHT_PAREN)
        then = self.body()
        else_ = None
        if self.la.type is T.ELSE:
            part = self.enter("ElsePart", ["else", "Stmt"])
            self.match(T.ELSE)
            else_ = self.body()
            self.exit(part)
        else:
            self.epsilon("ElsePart", f"{quote(self.la)} is not 'else' → ElsePart → ε")
        self.exit(node)
        return If(cond, then, else_, span=self.span_from(kw))

    def WhileStmt(self) -> While:
        node = self.enter("WhileStmt", ["while", "LEFT_PAREN", "Expr", "RIGHT_PAREN", "Stmt"])
        kw = self.match(T.WHILE)
        self.expect(T.LEFT_PAREN)
        cond = self.Expr()
        self.expect(T.RIGHT_PAREN)
        body = self.body()
        self.exit(node)
        return While(cond, body, span=self.span_from(kw))

    def DoStmt(self) -> DoWhile:
        node = self.enter("DoStmt", ["do", "Stmt", "while", "LEFT_PAREN", "Expr", "RIGHT_PAREN",
                                     "SEMICOLON"])
        kw = self.match(T.DO)
        body = self.body()
        self.expect(T.WHILE)
        self.expect(T.LEFT_PAREN)
        cond = self.Expr()
        self.expect(T.RIGHT_PAREN)
        self.expect_semicolon()
        self.exit(node)
        return DoWhile(body, cond, span=self.span_from(kw))

    def ForStmt(self) -> For:
        node = self.enter("ForStmt", ["for", "LEFT_PAREN", "ForInit", "SEMICOLON", "ForCond",
                                      "SEMICOLON", "ForUpdate", "RIGHT_PAREN", "Stmt"])
        kw = self.match(T.FOR)
        self.expect(T.LEFT_PAREN)
        init = self.ForInit()
        self.expect(T.SEMICOLON)
        cond = self.ForCond()
        self.expect(T.SEMICOLON)
        update = self.ForUpdate()
        self.expect(T.RIGHT_PAREN)
        body = self.body()
        self.exit(node)
        return For(init, cond, update, body, span=self.span_from(kw))

    def ForInit(self) -> Node | None:
        la = self.la
        if la.type in TYPE_TOKENS:
            node = self.enter("ForInit", ["Type", "IDENTIFIER", "ASSIGN", "Expr"])
            type_name, type_tok = self.Type()
            name = self.expect(T.IDENTIFIER)
            self.expect(T.ASSIGN)
            value = self.Expr()
            self.exit(node)
            return VarDecl(name.lexeme, type_name, value, name.span, span=self.span_from(type_tok))
        if la.type is T.IDENTIFIER:
            node = self.enter("ForInit", ["IDENTIFIER", "AssignTail"])
            name = self.match(T.IDENTIFIER)
            result = self.AssignTail(name)
            self.exit(node)
            return result
        if la.type is T.SEMICOLON:
            self.epsilon("ForInit", "';' → ForInit → ε (no initializer)")
            return None
        raise self.error("E_SYN_UNEXPECTED_TOKEN",
                         f"Expected a declaration, an assignment or ';' in the for-loop "
                         f"initializer but found {la.describe()}",
                         expected=terminal_types(self.facts.first["ForInit"]) | {T.SEMICOLON})

    def ForCond(self) -> Node | None:
        if self.la.type is T.SEMICOLON:
            self.epsilon("ForCond", "';' → ForCond → ε (empty condition means true)")
            return None
        node = self.enter("ForCond", ["Expr"])
        cond = self.Expr()
        self.exit(node)
        return cond

    def ForUpdate(self) -> Node | None:
        la = self.la
        if la.type is T.RIGHT_PAREN:
            self.epsilon("ForUpdate", "')' → ForUpdate → ε (no update)")
            return None
        if la.type is T.IDENTIFIER:
            node = self.enter("ForUpdate", ["IDENTIFIER", "AssignTail"])
            name = self.match(T.IDENTIFIER)
            result = self.AssignTail(name)
            self.exit(node)
            return result
        raise self.error("E_SYN_UNEXPECTED_TOKEN",
                         f"Expected an assignment (e.g. i++) or ')' in the for-loop update but "
                         f"found {la.describe()}", expected={T.IDENTIFIER, T.RIGHT_PAREN})

    def ReturnStmt(self) -> Return:
        node = self.enter("ReturnStmt", ["return", "ReturnVal", "SEMICOLON"])
        kw = self.match(T.RETURN)
        value = None
        if self.la.type is T.SEMICOLON:
            self.epsilon("ReturnVal", "';' → ReturnVal → ε (return without a value)")
        else:
            rv = self.enter("ReturnVal", ["Expr"])
            value = self.Expr()
            self.exit(rv)
        self.expect_semicolon()
        self.exit(node)
        return Return(value, span=self.span_from(kw))

    def BreakStmt(self) -> Break:
        node = self.enter("BreakStmt", ["break", "SEMICOLON"])
        kw = self.match(T.BREAK)
        self.expect_semicolon()
        self.exit(node)
        return Break(span=self.span_from(kw))

    def ContinueStmt(self) -> Continue:
        node = self.enter("ContinueStmt", ["continue", "SEMICOLON"])
        kw = self.match(T.CONTINUE)
        self.expect_semicolon()
        self.exit(node)
        return Continue(span=self.span_from(kw))

    def PrintStmt(self) -> Print:
        node = self.enter("PrintStmt", ["print", "LEFT_PAREN", "PrintArgs", "RIGHT_PAREN",
                                        "SEMICOLON"])
        kw = self.match(T.PRINT)
        self.expect(T.LEFT_PAREN)
        args = self.PrintArgs()
        self.expect(T.RIGHT_PAREN)
        self.expect_semicolon()
        self.exit(node)
        return Print(args, span=self.span_from(kw))

    def PrintArgs(self) -> list[Node]:
        if self.la.type is T.RIGHT_PAREN:
            self.epsilon("PrintArgs", "')' → PrintArgs → ε (prints an empty line)")
            return []
        node = self.enter("PrintArgs", ["PrintArg", "PrintArgList"])
        args = [self.PrintArg()]
        opened = []
        while self.la.type is T.COMMA:
            opened.append(self.enter("PrintArgList", ["COMMA", "PrintArg", "PrintArgList"]))
            self.match(T.COMMA)
            args.append(self.PrintArg())
        self.epsilon("PrintArgList", f"{quote(self.la)} is not ',' → PrintArgList → ε")
        for n in reversed(opened):
            self.exit(n)
        self.exit(node)
        return args

    def PrintArg(self) -> Node:
        if self.la.type is T.STRING:
            node = self.enter("PrintArg", ["STRING"])
            tok = self.match(T.STRING)
            self.exit(node)
            return StringLit(tok.value, tok.lexeme, span=tok.span)
        node = self.enter("PrintArg", ["Expr"])
        value = self.Expr()
        self.exit(node)
        return value

    def IdStmt(self) -> Node:
        node = self.enter("IdStmt", ["IDENTIFIER", "IdTail", "SEMICOLON"])
        name = self.match(T.IDENTIFIER)
        la = self.la
        if la.type is T.LEFT_PAREN:
            tail = self.enter("IdTail", ["LEFT_PAREN", "Args", "RIGHT_PAREN"])
            self.match(T.LEFT_PAREN)
            args = self.Args()
            close = self.expect(T.RIGHT_PAREN)
            self.exit(tail)
            call = Call(name.lexeme, args, span=name.span.merge(close.span))
            result: Node = CallStmt(call)
        elif la.type in ASSIGN_OPS:
            tail = self.enter("IdTail", ["AssignTail"])
            result = self.AssignTail(name)
            self.exit(tail)
        else:
            hint = None
            if la.type is T.IDENTIFIER:
                hint = f"'{name.lexeme}' is not a type. MiniC types are int, float and bool."
            elif la.type is T.EQUAL:
                hint = "Use '=' to assign; '==' compares two values."
            raise self.error(
                "E_SYN_UNEXPECTED_TOKEN",
                f"Expected '=', '(' or an assignment operator after '{name.lexeme}' but found "
                f"{la.describe()}", expected=set(ASSIGN_OPS) | {T.LEFT_PAREN}, hint=hint)
        self.expect_semicolon()
        self.exit(node)
        result.span = self.span_from(name)
        return result

    def AssignTail(self, name: Token) -> Assign:
        la = self.la
        if la.type not in ASSIGN_OPS:
            raise self.error("E_SYN_EXPECTED",
                             f"Expected an assignment operator after '{name.lexeme}' but found "
                             f"{la.describe()}", expected=set(ASSIGN_OPS))
        op = ASSIGN_OPS[la.type]
        target = Var(name.lexeme, span=name.span)
        if la.type in (T.INCREMENT, T.DECREMENT):
            node = self.enter("AssignTail", [la.type.value])
            tok = self.match(la.type)
            self.exit(node)
            one = Literal(1, "1", span=tok.span)
            value = self.make_binary(op[0], target, one, tok)
        else:
            node = self.enter("AssignTail", [la.type.value, "Expr"])
            tok = self.match(la.type)
            rhs = self.Expr()
            self.exit(node)
            value = rhs if op == "=" else self.make_binary(op[0], target, rhs, tok)
        return Assign(name.lexeme, value, op, name.span, span=self.span_from(name))

    # ------------------------------------------------------------------ helpers
    def expect_semicolon(self) -> Token | None:
        """Match ';'. If missing, report it and pretend it was there (phrase-level recovery)."""
        if self.la.type is T.SEMICOLON:
            return self.match(T.SEMICOLON)
        diag = self._missing_semicolon()
        if diag.code != "E_SYN_MISSING_SEMICOLON":
            raise ParseError(diag)
        self.report(diag)
        prev = self.prev
        node = self._node("error", "error", lexeme="missing ;",
                          span=Span(prev.span.end, prev.span.end))
        node.step = self.tracer.record(len(self.stack), self._function(), "recover", self.la, None,
                                       node.id,
                                       "Phrase-level recovery: assume the missing ';' and continue")
        return None

