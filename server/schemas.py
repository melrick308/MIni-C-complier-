"""Request validation for the HTTP API."""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from compiler.common import limits

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CompileOptions(BaseModel):
    optimize: bool = False
    run: bool = True


class CompileRequest(BaseModel):
    mode: Literal["program", "expression"] = "program"
    source: str = Field(max_length=limits.MAX_SOURCE_CHARS)
    options: CompileOptions = CompileOptions()
    variables: dict[str, int | float] = Field(default_factory=dict)

    @field_validator("variables")
    @classmethod
    def check_variables(cls, value: dict) -> dict:
        if len(value) > limits.MAX_VARIABLES:
            raise ValueError(f"at most {limits.MAX_VARIABLES} variables are allowed")
        for name, number in value.items():
            if not IDENTIFIER.match(name):
                raise ValueError(f"'{name}' is not a valid identifier")
            if isinstance(number, float) and not math.isfinite(number):
                raise ValueError(f"value of '{name}' must be a finite number")
        return value
