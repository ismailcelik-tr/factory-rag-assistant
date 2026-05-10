"""Compare two evaluation result files and flag regressions.

Usage:
    python evals/compare_runs.py evals/results/baseline.json evals/results/new_run.json

Exit code 0 = no regressions. Exit code 1 = one or more regressions detected.
This exit code convention enables CI gating.
"""

import json
import sys
from pathlib import Path

_REGRESSION_THRESHOLD = 0.05  # strictly greater than this drop triggers a regression

_METRIC_LABELS = {
    "hit_rate_at_k": "Hit Rate @ k",
    "mrr": "MRR",
    "precision_at_k": "Precision @ k",
    "citation_accuracy": "Citation Accuracy",
    "semantic_similarity_mean": "Semantic Similarity",
}


def load_result(path: str) -> dict:
    """Load a result JSON file. Raises FileNotFoundError or json.JSONDecodeError on failure."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Result file not found: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def compare_summaries(
    baseline: dict,
    new_run: dict,
    regression_threshold: float = _REGRESSION_THRESHOLD,
) -> list[dict]:
    """Compare metric values present in both summaries.

    Returns a list of comparison rows, one per shared metric:
      {metric, baseline_value, new_value, delta, regression}

    regression = True when delta < -regression_threshold (strictly greater drop).
    Metrics only in baseline or only in new_run are ignored.
    """
    rows = []
    for metric in baseline:
        if metric not in new_run:
            continue
        if not isinstance(baseline[metric], (int, float)):
            continue
        if not isinstance(new_run[metric], (int, float)):
            continue
        b_val = float(baseline[metric])
        n_val = float(new_run[metric])
        delta = n_val - b_val
        rows.append(
            {
                "metric": metric,
                "baseline": b_val,
                "new": n_val,
                "delta": delta,
                "regression": delta < -regression_threshold,
            }
        )
    return rows


def format_comparison_table(
    rows: list[dict],
    baseline_path: str = "",
    new_run_path: str = "",
) -> str:
    """Format comparison rows as a printable table string."""
    header = (
        f"Comparing: {Path(baseline_path).name} → {Path(new_run_path).name}\n\n"
        f"{'Metric':<26} {'Baseline':>10} {'New':>10} {'Delta':>10}  Status\n"
        + "─" * 65
    )
    lines = [header]
    for row in rows:
        label = _METRIC_LABELS.get(row["metric"], row["metric"])
        delta_str = f"{row['delta']:+.3f}"
        status = "REGRESSION" if row["regression"] else "OK"
        lines.append(
            f"{label:<26} {row['baseline']:>10.3f} {row['new']:>10.3f} {delta_str:>10}  {status}"
        )

    n_regressions = sum(1 for r in rows if r["regression"])
    lines.append("")
    if n_regressions:
        lines.append(f"Result: {n_regressions} REGRESSION(S) DETECTED")
    else:
        lines.append("Result: no regressions")

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python compare_runs.py <baseline.json> <new_run.json>", file=sys.stderr)
        sys.exit(2)

    baseline_path, new_run_path = sys.argv[1], sys.argv[2]

    baseline_result = load_result(baseline_path)
    new_run_result = load_result(new_run_path)

    baseline_summary = baseline_result.get("summary", baseline_result)
    new_run_summary = new_run_result.get("summary", new_run_result)

    rows = compare_summaries(baseline_summary, new_run_summary)
    print(format_comparison_table(rows, baseline_path, new_run_path))

    if any(r["regression"] for r in rows):
        sys.exit(1)


if __name__ == "__main__":
    main()
