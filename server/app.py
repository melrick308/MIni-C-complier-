"""FastAPI application: the compiler API plus the static web UI on the same origin.

Run with:  uvicorn server.app:app --reload
"""

from __future__ import annotations

import pathlib

from fastapi import FastAPI, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from compiler import compile_source
from compiler.common import limits
from compiler.common.diagnostics import CATALOG
from compiler.syntax.grammar import EXPRESSION, MINIC, grammar_info

from .examples import expression_examples, program_examples
from .schemas import CompileRequest

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="MiniC Compiler Explorer",
    version="1.0.0",
    description="Educational recursive descent compiler: every phase, visualised.",
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/compile")
def compile_endpoint(request: CompileRequest) -> dict:
    """Run the whole pipeline. Compile errors are results (HTTP 200), not HTTP failures."""
    return compile_source(
        request.source,
        request.mode,
        optimize=request.options.optimize,
        run=request.options.run,
        variables=request.variables,
    )


@app.get("/api/examples")
def examples() -> dict:
    return {"programs": program_examples(), "expressions": expression_examples()}


@app.get("/api/grammar")
def grammar(profile: str = Query(MINIC, pattern=f"^({MINIC}|{EXPRESSION})$")) -> dict:
    return grammar_info(profile)


@app.get("/api/info")
def info() -> dict:
    return {
        "errors": CATALOG,
        "limits": {name.lower(): getattr(limits, name) for name in dir(limits)
                   if name.isupper()},
    }


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
