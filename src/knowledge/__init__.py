"""Bounded local knowledge ingestion and grounded answer service."""

from .local_rag import LocalRAGError, run_ingest_and_answer

__all__ = ["LocalRAGError", "run_ingest_and_answer"]
