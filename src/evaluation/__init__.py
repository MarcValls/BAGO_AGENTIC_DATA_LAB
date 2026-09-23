"""Deterministic local evaluation contracts for BAGO traces."""

from .local_evals import EvaluationCheck, EvaluationReport, EvaluationStatus, LocalTraceEvaluator

__all__ = [
    "EvaluationCheck",
    "EvaluationReport",
    "EvaluationStatus",
    "LocalTraceEvaluator",
]
