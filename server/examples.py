"""Sample programs (examples/programs/*.mc) and expressions (examples/expressions.json)."""

from __future__ import annotations

import json
import pathlib
from functools import cache

ROOT = pathlib.Path(__file__).resolve().parent.parent / "examples"
CATEGORY_ORDER = ["basics", "conditions", "loops", "functions", "scopes", "types", "optimizer",
                  "runtime", "errors"]


def _header(source: str) -> dict:
    meta = {}
    for line in source.splitlines():
        if not line.startswith("//"):
            break
        key, _, value = line[2:].strip().partition(":")
        if value:
            meta[key.strip()] = value.strip()
    return meta


@cache
def program_examples() -> list[dict]:
    items = []
    for path in sorted((ROOT / "programs").glob("*.mc")):
        source = path.read_text(encoding="utf-8")
        meta = _header(source)
        expected = path.with_suffix(".out")
        items.append({
            "id": path.stem,
            "title": meta.get("title", path.stem),
            "description": meta.get("description", ""),
            "category": meta.get("category", "basics"),
            "source": source,
            "expected_output": expected.read_text(encoding="utf-8") if expected.exists() else None,
        })
    items.sort(key=lambda e: (CATEGORY_ORDER.index(e["category"])
                              if e["category"] in CATEGORY_ORDER else 99, e["id"]))
    return items


@cache
def expression_examples() -> list[dict]:
    data = json.loads((ROOT / "expressions.json").read_text(encoding="utf-8"))
    return [{"id": f"expr{i + 1}", **item} for i, item in enumerate(data)]
