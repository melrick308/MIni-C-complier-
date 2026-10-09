import pytest
from fastapi.testclient import TestClient

from server.app import app

client = TestClient(app)


def compile_(payload):
    response = client.post("/api/compile", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_compile_program():
    data = compile_({"source": "int x = 2;\nprint(x * 21);"})
    assert data["success"] is True
    assert data["phases"]["execution"]["output"] == ["42"]
    assert set(data["phases"]) == {"lexical", "syntax", "semantic", "ir", "cfg", "optimize",
                                   "execution"}
    assert data["phases"]["optimize"]["status"] == "skipped"


def test_compile_with_optimizer():
    data = compile_({"source": "int x = 2 * 3; print(x);", "options": {"optimize": True}})
    assert data["phases"]["optimize"]["status"] == "ok"
    assert data["phases"]["execution"]["optimized"] is True


def test_expression_mode():
    data = compile_({"mode": "expression", "source": "a + b * (c - 2)",
                     "variables": {"a": 3, "b": 4, "c": 7}})
    assert data["evaluation"]["value"] == "23"
    assert data["phases"]["syntax"]["ast_infix"] == "(a + (b * (c - 2)))"


@pytest.mark.parametrize("payload, phase", [
    ({"source": "int x = 5 @ 3;"}, "lexical"),
    ({"source": "int x = ;"}, "syntax"),
    ({"source": "x = 1;"}, "semantic"),
    ({"mode": "expression", "source": "a + * b"}, "syntax"),
])
def test_compile_errors_are_results(payload, phase):
    data = compile_(payload)
    assert data["success"] is False and data["failed_phase"] == phase
    assert data["diagnostics"][0]["phase"] == phase


def test_runtime_error():
    data = compile_({"source": "int z = 0; print(1 / z);"})
    assert data["phases"]["execution"]["status"] == "error"
    assert data["diagnostics"][0]["code"] == "E_RT_DIV_ZERO"


@pytest.mark.parametrize("payload", [
    {},
    {"source": "x" * 10_001},
    {"source": "1", "mode": "basic"},
    {"source": "a", "mode": "expression", "variables": {"1bad": 1}},
    {"source": "a", "mode": "expression", "variables": {"a": "ten"}},
    {"source": "a", "mode": "expression", "variables": {f"v{i}": i for i in range(51)}},
])
def test_invalid_requests_are_rejected(payload):
    assert client.post("/api/compile", json=payload).status_code == 422


def test_examples():
    data = client.get("/api/examples").json()
    assert len(data["programs"]) >= 20 and len(data["expressions"]) >= 10
    first = data["programs"][0]
    assert {"id", "title", "description", "category", "source"} <= set(first)


@pytest.mark.parametrize("profile", ["minic", "expression"])
def test_grammar(profile):
    data = client.get(f"/api/grammar?profile={profile}").json()
    assert data["is_ll1"] is True and data["nonterminals"]


def test_grammar_rejects_unknown_profile():
    assert client.get("/api/grammar?profile=python").status_code == 422


def test_info():
    data = client.get("/api/info").json()
    assert "E_SYN_MISSING_SEMICOLON" in data["errors"]
    assert data["limits"]["max_exec_steps"] == 100_000


def test_static_index_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "<html" in response.text.lower()


def test_responses_are_gzipped():
    response = client.post("/api/compile", json={"source": "print(1);"},
                           headers={"Accept-Encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"
