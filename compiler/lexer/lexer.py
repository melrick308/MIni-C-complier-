"""Hand-written scanner. Produces tokens with 1-based line:col spans."""

from __future__ import annotations

from ..common.diagnostics import ERROR, LEXICAL, Diagnostic
from ..common.source import SourceFile
from .tokens import KEYWORDS, OPERATORS, Token, TokenType


class Lexer:
    def __init__(self, source: SourceFile):
        self.source = source
        self.text = source.text
        self.i = 0
        self.tokens: list[Token] = []

    def tokenize(self) -> tuple[list[Token], Diagnostic | None]:
        """Scan the whole input. Stops at the first lexical error.

        Returns the tokens scanned so far (always ending with EOF) and the error, if any.
        """
        error = None
        try:
            while True:
                self._skip_trivia()
                if self.i >= len(self.text):
                    break
                self._scan_token()
        except _LexFailure as failure:
            error = failure.diagnostic
        eof_at = len(self.text) if error is None else self.i
        self._add(TokenType.EOF, "$", eof_at, eof_at)
        return self.tokens, error

    # ------------------------------------------------------------------ helpers
    def _add(self, tt: TokenType, lexeme: str, start: int, end: int, value=None) -> None:
        self.tokens.append(Token(tt, lexeme, self.source.span(start, end), len(self.tokens), value))

    def _fail(self, code: str, message: str, start: int, end: int, found: str, hint=None):
        raise _LexFailure(
            Diagnostic(ERROR, LEXICAL, code, message, self.source.span(start, end),
                       found=found, hint=hint)
        )

    def _peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.text[j] if j < len(self.text) else ""

    def _skip_trivia(self) -> None:
        text = self.text
        while self.i < len(text):
            ch = text[self.i]
            if ch in " \t\r\n\f\v":
                self.i += 1
            elif text.startswith("//", self.i):
                end = text.find("\n", self.i)
                self.i = len(text) if end == -1 else end
            elif text.startswith("/*", self.i):
                end = text.find("*/", self.i + 2)
                if end == -1:
                    self._fail("E_LEX_UNTERMINATED_COMMENT", "Unterminated comment: missing '*/'",
                               self.i, self.i + 2, "/*",
                               hint="Close the block comment with */.")
                self.i = end + 2
            else:
                return

    def _scan_token(self) -> None:
        ch = self.text[self.i]
        if ch.isascii() and (ch.isalpha() or ch == "_"):
            self._scan_word()
        elif ch.isascii() and ch.isdigit():
            self._scan_number()
        elif ch == '"':
            self._scan_string()
        else:
            for text, tt in OPERATORS:
                if self.text.startswith(text, self.i):
                    self._add(tt, text, self.i, self.i + len(text))
                    self.i += len(text)
                    return
            self._invalid_char(ch)

    def _scan_word(self) -> None:
        start = self.i
        while self.i < len(self.text) and (self.text[self.i].isascii()
                                           and (self.text[self.i].isalnum() or self.text[self.i] == "_")):
            self.i += 1
        word = self.text[start:self.i]
        tt = KEYWORDS.get(word, TokenType.IDENTIFIER)
        value = {"true": True, "false": False}.get(word)
        self._add(tt, word, start, self.i, value)

    def _scan_number(self) -> None:
        start = self.i
        while self._peek().isascii() and self._peek().isdigit():
            self.i += 1
        if self._peek() == ".":
            if self._peek(1).isascii() and self._peek(1).isdigit():
                self.i += 1
                while self._peek().isascii() and self._peek().isdigit():
                    self.i += 1
                lexeme = self.text[start:self.i]
                self._add(TokenType.NUMBER, lexeme, start, self.i, float(lexeme))
                return
            self._fail("E_LEX_MALFORMED_NUMBER",
                       f"Malformed number '{self.text[start:self.i + 1]}'",
                       start, self.i + 1, self.text[start:self.i + 1],
                       hint="A decimal point must be followed by digits, e.g. 3.0")
        lexeme = self.text[start:self.i]
        self._add(TokenType.NUMBER, lexeme, start, self.i, int(lexeme))

    def _scan_string(self) -> None:
        start = self.i
        self.i += 1
        chars = []
        escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
        while True:
            ch = self._peek()
            if ch == "" or ch == "\n":
                self._fail("E_LEX_UNTERMINATED_STRING", "Unterminated string literal",
                           start, self.i, self.text[start:self.i],
                           hint='Close the string with a double quote (").')
            if ch == '"':
                self.i += 1
                break
            if ch == "\\" and self._peek(1) in escapes:
                chars.append(escapes[self._peek(1)])
                self.i += 2
                continue
            chars.append(ch)
            self.i += 1
        self._add(TokenType.STRING, self.text[start:self.i], start, self.i, "".join(chars))

    def _invalid_char(self, ch: str) -> None:
        hint = None
        if ch == "." and self._peek(1).isdigit():
            hint = "Numbers must start with a digit, e.g. 0.5"
        elif ch == "&":
            hint = "Logical AND is written '&&'."
        elif ch == "|":
            hint = "Logical OR is written '||'."
        elif ch == "'":
            hint = 'Strings use double quotes, e.g. "hello".'
        elif ch in "[]":
            hint = "Arrays are not supported."
        elif ch == "^":
            hint = "There is no power operator; use repeated multiplication."
        self._fail("E_LEX_INVALID_CHAR", f"Invalid character '{ch}'", self.i, self.i + 1, ch, hint)


class _LexFailure(Exception):
    def __init__(self, diagnostic: Diagnostic):
        self.diagnostic = diagnostic


def tokenize(text: str) -> tuple[list[Token], Diagnostic | None]:
    return Lexer(SourceFile(text)).tokenize()
