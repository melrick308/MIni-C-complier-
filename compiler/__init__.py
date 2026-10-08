"""MiniC Compiler Explorer: an educational recursive descent compiler."""

from .pipeline import PROGRAM, compile_source

__all__ = ["compile_source", "PROGRAM"]
