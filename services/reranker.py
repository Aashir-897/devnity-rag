"""Reranker stub — currently a pass-through.
Ready for future integration with ONNX-based cross-encoders (e.g. BGE-Reranker)."""


def rerank(query: str, passages: list[dict]) -> list[dict]:
    """Stub: returns passages unchanged. Swap with real reranker when available."""
    return passages
