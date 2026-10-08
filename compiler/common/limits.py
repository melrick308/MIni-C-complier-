"""Every resource limit in one place (see docs/decisions.md)."""

MAX_SOURCE_CHARS = 10_000
MAX_SOURCE_LINES = 400
MAX_EXPRESSION_CHARS = 500
MAX_VARIABLES = 50

MAX_NESTING = 100  # parentheses + blocks + unary operators
MAX_EXPR_DEPTH = 200  # operators stacked in one expression tree
MAX_SYNTAX_ERRORS = 20
MAX_PARSE_TRACE = 20_000

MAX_EXEC_STEPS = 100_000
MAX_EXEC_TRACE = 20_000
MAX_EXEC_SECONDS = 2.0
MAX_OUTPUT_LINES = 1_000
MAX_CALL_DEPTH = 200
