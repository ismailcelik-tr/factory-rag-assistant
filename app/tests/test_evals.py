"""Unit tests for evals/metrics.py and harness utility functions.

All tests run fully offline — no Ollama, no ChromaDB, no filesystem I/O.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest  # noqa: F401 (used via pytest.raises / pytest.mark)

# Make evals/ importable without installing it as a package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "evals"))

from metrics import (  # noqa: E402
    aggregate_answer_metrics,
    aggregate_retrieval_metrics,
    citation_accuracy,
    cosine_similarity,
    hit_at_k,
    precision_at_k,
    reciprocal_rank,
)

# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_vector_a(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_zero_vector_b(self):
        assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0

    def test_both_zero_vectors(self):
        assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_known_value(self):
        # [3,4] · [4,3] = 24, |[3,4]| = 5, |[4,3]| = 5 → 24/25 = 0.96
        assert cosine_similarity([3.0, 4.0], [4.0, 3.0]) == pytest.approx(0.96)


# ---------------------------------------------------------------------------
# hit_at_k
# ---------------------------------------------------------------------------


class TestHitAtK:
    def test_hit_in_first_position(self):
        assert hit_at_k(["manual.pdf", "spec.pdf"], ["manual.pdf"]) is True

    def test_hit_in_last_position(self):
        assert hit_at_k(["a.pdf", "b.pdf", "c.pdf", "target.pdf"], ["target.pdf"]) is True

    def test_no_hit(self):
        assert hit_at_k(["a.pdf", "b.pdf"], ["missing.pdf"]) is False

    def test_empty_expected_returns_false(self):
        assert hit_at_k(["a.pdf"], []) is False

    def test_empty_retrieved_returns_false(self):
        assert hit_at_k([], ["expected.pdf"]) is False

    def test_multiple_expected_one_match(self):
        assert hit_at_k(["a.pdf"], ["a.pdf", "b.pdf"]) is True

    def test_multiple_expected_no_match(self):
        assert hit_at_k(["c.pdf"], ["a.pdf", "b.pdf"]) is False


# ---------------------------------------------------------------------------
# reciprocal_rank
# ---------------------------------------------------------------------------


class TestReciprocalRank:
    def test_first_result_is_hit(self):
        assert reciprocal_rank(["target.pdf", "other.pdf"], ["target.pdf"]) == pytest.approx(1.0)

    def test_second_result_is_hit(self):
        assert reciprocal_rank(["other.pdf", "target.pdf"], ["target.pdf"]) == pytest.approx(0.5)

    def test_third_result_is_hit(self):
        assert reciprocal_rank(["a.pdf", "b.pdf", "target.pdf"], ["target.pdf"]) == pytest.approx(
            1 / 3
        )

    def test_no_hit_returns_zero(self):
        assert reciprocal_rank(["a.pdf", "b.pdf"], ["target.pdf"]) == 0.0

    def test_empty_expected_returns_zero(self):
        assert reciprocal_rank(["a.pdf"], []) == 0.0

    def test_multiple_expected_first_match_at_rank_2(self):
        assert reciprocal_rank(["a.pdf", "b.pdf", "c.pdf"], ["b.pdf", "z.pdf"]) == pytest.approx(
            0.5
        )


# ---------------------------------------------------------------------------
# precision_at_k
# ---------------------------------------------------------------------------


class TestPrecisionAtK:
    def test_all_match(self):
        assert precision_at_k(["a.pdf", "b.pdf"], ["a.pdf", "b.pdf"]) == pytest.approx(1.0)

    def test_none_match(self):
        assert precision_at_k(["a.pdf", "b.pdf"], ["c.pdf"]) == 0.0

    def test_half_match(self):
        assert precision_at_k(["a.pdf", "b.pdf"], ["a.pdf"]) == pytest.approx(0.5)

    def test_empty_retrieved(self):
        assert precision_at_k([], ["a.pdf"]) == 0.0

    def test_empty_expected(self):
        assert precision_at_k(["a.pdf"], []) == 0.0


# ---------------------------------------------------------------------------
# citation_accuracy
# ---------------------------------------------------------------------------


class TestCitationAccuracy:
    def test_all_expected_cited(self):
        assert citation_accuracy(["a.pdf", "b.pdf"], ["a.pdf", "b.pdf"]) == pytest.approx(1.0)

    def test_none_cited(self):
        assert citation_accuracy(["c.pdf"], ["a.pdf", "b.pdf"]) == 0.0

    def test_partial(self):
        assert citation_accuracy(["a.pdf", "c.pdf"], ["a.pdf", "b.pdf"]) == pytest.approx(0.5)

    def test_empty_expected_returns_zero(self):
        assert citation_accuracy(["a.pdf"], []) == 0.0

    def test_empty_citations(self):
        assert citation_accuracy([], ["a.pdf"]) == 0.0


# ---------------------------------------------------------------------------
# aggregate_retrieval_metrics
# ---------------------------------------------------------------------------


class TestAggregateRetrievalMetrics:
    def test_all_evaluated(self):
        results = [
            {"status": "evaluated", "hit": True, "reciprocal_rank": 1.0, "precision": 0.4},
            {"status": "evaluated", "hit": False, "reciprocal_rank": 0.0, "precision": 0.0},
        ]
        metrics = aggregate_retrieval_metrics(results)
        assert metrics["hit_rate_at_k"] == pytest.approx(0.5)
        assert metrics["mrr"] == pytest.approx(0.5)
        assert metrics["precision_at_k"] == pytest.approx(0.2)

    def test_skipped_questions_excluded(self):
        results = [
            {"status": "evaluated", "hit": True, "reciprocal_rank": 1.0, "precision": 1.0},
            {"status": "skipped", "hit": False, "reciprocal_rank": 0.0, "precision": 0.0},
        ]
        metrics = aggregate_retrieval_metrics(results)
        assert metrics["hit_rate_at_k"] == pytest.approx(1.0)

    def test_all_skipped_returns_zeros(self):
        results = [{"status": "skipped"}, {"status": "skipped"}]
        metrics = aggregate_retrieval_metrics(results)
        assert metrics["hit_rate_at_k"] == 0.0
        assert metrics["mrr"] == 0.0

    def test_empty_input_returns_zeros(self):
        metrics = aggregate_retrieval_metrics([])
        assert metrics["hit_rate_at_k"] == 0.0


# ---------------------------------------------------------------------------
# aggregate_answer_metrics
# ---------------------------------------------------------------------------


class TestAggregateAnswerMetrics:
    def test_all_evaluated(self):
        results = [
            {"status": "evaluated", "citation_accuracy": 1.0, "semantic_similarity": 0.9},
            {"status": "evaluated", "citation_accuracy": 0.5, "semantic_similarity": 0.7},
        ]
        metrics = aggregate_answer_metrics(results)
        assert metrics["citation_accuracy"] == pytest.approx(0.75)
        assert metrics["semantic_similarity_mean"] == pytest.approx(0.8)

    def test_skipped_excluded(self):
        results = [
            {"status": "evaluated", "citation_accuracy": 1.0, "semantic_similarity": 0.8},
            {"status": "skipped"},
        ]
        metrics = aggregate_answer_metrics(results)
        assert metrics["citation_accuracy"] == pytest.approx(1.0)

    def test_all_skipped_returns_zeros(self):
        metrics = aggregate_answer_metrics([{"status": "skipped"}])
        assert metrics["citation_accuracy"] == 0.0


# ---------------------------------------------------------------------------
# compare_summaries (from compare_runs.py)
# ---------------------------------------------------------------------------


class TestCompareSummaries:
    def _import_compare(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "compare_runs",
            Path(__file__).parent.parent.parent / "evals" / "compare_runs.py",
        )
        mod = importlib.util.load_from_spec(spec)  # type: ignore[attr-defined]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    def _load(self):
        evals_dir = Path(__file__).parent.parent.parent / "evals"
        sys.path.insert(0, str(evals_dir))
        import compare_runs

        return compare_runs

    def test_no_regressions(self):
        cr = self._load()
        baseline = {"hit_rate_at_k": 0.80, "mrr": 0.65}
        new_run = {"hit_rate_at_k": 0.82, "mrr": 0.67}
        rows = cr.compare_summaries(baseline, new_run)
        assert all(not r["regression"] for r in rows)

    def test_regression_detected(self):
        cr = self._load()
        baseline = {"hit_rate_at_k": 0.80}
        new_run = {"hit_rate_at_k": 0.65}  # -0.15 > threshold
        rows = cr.compare_summaries(baseline, new_run)
        assert rows[0]["regression"] is True

    def test_exactly_5pp_drop_is_not_regression(self):
        cr = self._load()
        baseline = {"mrr": 0.70}
        new_run = {"mrr": 0.65}  # exactly -0.05, not strictly >0.05
        rows = cr.compare_summaries(baseline, new_run)
        assert rows[0]["regression"] is False

    def test_metric_only_in_baseline_skipped(self):
        cr = self._load()
        baseline = {"hit_rate_at_k": 0.80, "extra_metric": 0.5}
        new_run = {"hit_rate_at_k": 0.85}
        rows = cr.compare_summaries(baseline, new_run)
        metrics = [r["metric"] for r in rows]
        assert "extra_metric" not in metrics


# ---------------------------------------------------------------------------
# load_dataset (from run_evals.py)
# ---------------------------------------------------------------------------


class TestLoadDataset:
    def _load_run_evals(self):
        evals_dir = Path(__file__).parent.parent.parent / "evals"
        sys.path.insert(0, str(evals_dir))
        import run_evals

        return run_evals

    def test_valid_jsonl(self):
        re = self._load_run_evals()
        record = {
            "id": "q001",
            "question": "What is X?",
            "role": "rd_engineer",
            "expected_sources": [],
            "reference_answer": "PLACEHOLDER",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(record) + "\n")
            tmp = f.name
        result = re.load_dataset(tmp)
        assert len(result) == 1
        assert result[0]["id"] == "q001"

    def test_missing_required_field_raises(self):
        re = self._load_run_evals()
        bad_record = {"question": "X?", "role": "rd_engineer"}  # missing id, expected_sources, etc.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(bad_record) + "\n")
            tmp = f.name
        with pytest.raises(ValueError):
            re.load_dataset(tmp)

    def test_empty_file_returns_empty_list(self):
        re = self._load_run_evals()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            tmp = f.name
        assert re.load_dataset(tmp) == []


# ---------------------------------------------------------------------------
# check_ollama_or_exit (from run_evals.py)
# ---------------------------------------------------------------------------


class TestCheckOllamaOrExit:
    def _load_run_evals(self):
        evals_dir = Path(__file__).parent.parent.parent / "evals"
        sys.path.insert(0, str(evals_dir))
        import run_evals

        return run_evals

    def test_reachable_does_not_exit(self):
        re = self._load_run_evals()
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            re.check_ollama_or_exit()  # should not raise

    def test_unreachable_calls_sys_exit(self):
        import httpx

        re = self._load_run_evals()
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(SystemExit):
                re.check_ollama_or_exit()
