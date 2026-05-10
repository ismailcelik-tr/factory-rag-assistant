"""Pure-Python metric functions for RAG evaluation.

No I/O, no external dependencies — fully unit-testable in isolation.
All functions operate on plain Python values (lists, dicts, floats).
"""

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 for zero-magnitude vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def hit_at_k(retrieved_basenames: list[str], expected_sources: list[str]) -> bool:
    """True if any expected source appears in the retrieved basenames."""
    if not expected_sources:
        return False
    expected_set = set(expected_sources)
    return any(name in expected_set for name in retrieved_basenames)


def reciprocal_rank(retrieved_basenames: list[str], expected_sources: list[str]) -> float:
    """1/rank of the first hit (1-indexed). Returns 0.0 if no hit."""
    if not expected_sources:
        return 0.0
    expected_set = set(expected_sources)
    for rank, name in enumerate(retrieved_basenames, start=1):
        if name in expected_set:
            return 1.0 / rank
    return 0.0


def precision_at_k(retrieved_basenames: list[str], expected_sources: list[str]) -> float:
    """Fraction of retrieved results that match an expected source."""
    if not retrieved_basenames:
        return 0.0
    expected_set = set(expected_sources)
    hits = sum(1 for name in retrieved_basenames if name in expected_set)
    return hits / len(retrieved_basenames)


def citation_accuracy(
    citation_source_files: list[str],
    expected_sources: list[str],
) -> float:
    """Fraction of expected_sources found in citation_source_files. 0.0 if expected is empty."""
    if not expected_sources:
        return 0.0
    cited_set = set(citation_source_files)
    hits = sum(1 for src in expected_sources if src in cited_set)
    return hits / len(expected_sources)


def aggregate_retrieval_metrics(question_results: list[dict]) -> dict[str, float]:
    """Average retrieval metrics over evaluated questions only.

    Expects each dict to have: status, hit (bool), reciprocal_rank (float), precision (float).
    Returns zeros for all metrics if no questions were evaluated.
    """
    evaluated = [q for q in question_results if q.get("status") == "evaluated"]
    if not evaluated:
        return {"hit_rate_at_k": 0.0, "mrr": 0.0, "precision_at_k": 0.0}
    n = len(evaluated)
    return {
        "hit_rate_at_k": sum(1 for q in evaluated if q.get("hit")) / n,
        "mrr": sum(q.get("reciprocal_rank", 0.0) for q in evaluated) / n,
        "precision_at_k": sum(q.get("precision", 0.0) for q in evaluated) / n,
    }


def aggregate_answer_metrics(question_results: list[dict]) -> dict[str, float]:
    """Average answer metrics over evaluated questions only.

    Expects each dict to have: status, citation_accuracy (float), semantic_similarity (float).
    Returns zeros if no questions were evaluated.
    """
    evaluated = [q for q in question_results if q.get("status") == "evaluated"]
    if not evaluated:
        return {"citation_accuracy": 0.0, "semantic_similarity_mean": 0.0}
    n = len(evaluated)
    return {
        "citation_accuracy": sum(q.get("citation_accuracy", 0.0) for q in evaluated) / n,
        "semantic_similarity_mean": sum(
            q.get("semantic_similarity", 0.0) for q in evaluated
        ) / n,
    }
