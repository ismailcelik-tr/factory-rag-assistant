"""Evaluation harness for factory-rag-assistant.

Usage:
    python evals/run_evals.py --dataset evals/datasets/smoke_test.jsonl --mode retrieval
    python evals/run_evals.py --dataset evals/datasets/full_suite.jsonl --mode full --tag baseline
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from metrics import (  # noqa: E402
    aggregate_answer_metrics,
    aggregate_retrieval_metrics,
    citation_accuracy,
    cosine_similarity,
    hit_at_k,
    precision_at_k,
    reciprocal_rank,
)

from app.config import settings  # noqa: E402
from app.retrieval.retriever import retrieve  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = {"id", "question", "role", "expected_sources", "reference_answer"}


def check_ollama_or_exit() -> None:
    """Exit with a clear message if Ollama is not reachable."""
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        if r.status_code != 200:
            raise httpx.ConnectError("non-200 status")
    except Exception:
        print(
            f"ERROR: Ollama is not reachable at {settings.ollama_base_url}.\n"
            "       Start Ollama with: ollama serve",
            file=sys.stderr,
        )
        sys.exit(1)


def load_dataset(path: str) -> list[dict]:
    """Load and validate a JSONL dataset. Raises ValueError on malformed records."""
    records = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            missing = _REQUIRED_FIELDS - record.keys()
            if missing:
                raise ValueError(
                    f"Record at line {lineno} is missing required fields: {missing}"
                )
            records.append(record)
    return records


def evaluate_question(record: dict, mode: str, top_k: int) -> dict:
    """Run retrieval and/or answer evaluation for one question record.

    Returns a per-question result dict. In 'full' mode the same retrieved
    chunks are reused for answer evaluation — retrieve() is called only once.
    """
    result: dict = {
        "id": record["id"],
        "question": record["question"],
        "role": record["role"],
        "status": "skipped",
    }

    expected = record.get("expected_sources", [])
    reference = record.get("reference_answer", "")

    # --- Retrieval ---
    if mode in ("retrieval", "full"):
        if not expected:
            result["retrieval_skipped_reason"] = "expected_sources is empty"
            chunks = retrieve(record["question"], top_k=top_k)
        else:
            chunks = retrieve(record["question"], top_k=top_k)
            basenames = [Path(c["source_file"]).name for c in chunks]
            result["retrieved_sources"] = basenames
            result["hit"] = hit_at_k(basenames, expected)
            result["reciprocal_rank"] = reciprocal_rank(basenames, expected)
            result["precision"] = precision_at_k(basenames, expected)
            result["status"] = "evaluated"
    else:
        chunks = retrieve(record["question"], top_k=top_k)

    # --- Answer ---
    if mode in ("answer", "full"):
        if reference.startswith("PLACEHOLDER"):
            result["answer_skipped_reason"] = "reference_answer is a placeholder"
            if result["status"] != "evaluated":
                result["status"] = "skipped"
        else:
            # Lazy imports — avoid triggering OllamaEmbeddings at module level
            from app.embeddings.embedder import embed_texts
            from app.llm.ollama_provider import OllamaProvider
            from app.llm.parser import extract_citations
            from app.prompts.assembler import build_system_prompt, build_user_message

            system_prompt = build_system_prompt(record["role"])
            user_message = build_user_message(record["question"], chunks)
            answer = OllamaProvider().generate(system_prompt, user_message)
            citations = extract_citations(answer)
            cited_names = [c.source_file for c in citations]

            ref_vec = embed_texts([reference])[0]
            ans_vec = embed_texts([answer])[0]
            sim = cosine_similarity(ref_vec, ans_vec)

            result["answer"] = answer
            result["citations"] = [c.model_dump() for c in citations]
            result["citation_accuracy"] = citation_accuracy(cited_names, expected)
            result["semantic_similarity"] = sim
            result["status"] = "evaluated"

    return result


def build_run_id(tag: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{ts}-{tag}"


def build_summary(per_question: list[dict], mode: str) -> dict:
    total = len(per_question)
    evaluated = sum(1 for q in per_question if q.get("status") == "evaluated")
    skipped = total - evaluated

    summary: dict = {
        "total_questions": total,
        "evaluated": evaluated,
        "skipped": skipped,
    }

    if mode in ("retrieval", "full"):
        summary.update(aggregate_retrieval_metrics(per_question))
    if mode in ("answer", "full"):
        summary.update(aggregate_answer_metrics(per_question))

    return summary


def write_markdown(result: dict, path: Path) -> None:
    """Write a human-readable Markdown summary."""
    mode = result["mode"]
    summary = result["summary"]

    lines = [
        f"## Run: {result['run_id']}",
        "",
        f"Dataset: `{result['dataset']}`  |  Mode: `{mode}`"
        f"  |  Top-k: `{result['config']['top_k']}`",
        "",
        "### Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ]

    metric_labels = {
        "hit_rate_at_k": "Hit Rate @ k",
        "mrr": "MRR",
        "precision_at_k": "Precision @ k",
        "citation_accuracy": "Citation Accuracy",
        "semantic_similarity_mean": "Semantic Similarity (mean)",
    }
    for key, label in metric_labels.items():
        if key in summary:
            lines.append(f"| {label} | {summary[key]:.3f} |")
    lines.append(
        f"| Evaluated | {summary['evaluated']} / {summary['total_questions']} |"
    )
    lines.append(f"| Skipped | {summary['skipped']} |")

    lines += ["", "### Per-Question Results", ""]

    # Build header based on mode
    headers = ["ID", "Question", "Status"]
    if mode in ("retrieval", "full"):
        headers += ["Hit", "RR", "Prec"]
    if mode in ("answer", "full"):
        headers += ["CitAcc", "SimScore"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for q in result["per_question"]:
        q_short = (q["question"][:40] + "…") if len(q["question"]) > 40 else q["question"]
        row = [q["id"], q_short, q.get("status", "-")]
        if mode in ("retrieval", "full"):
            row.append("yes" if q.get("hit") else "-")
            is_eval = q.get("status") == "evaluated"
            row.append(f"{q.get('reciprocal_rank', 0.0):.2f}" if is_eval else "-")
            row.append(f"{q.get('precision', 0.0):.2f}" if is_eval else "-")
        if mode in ("answer", "full"):
            row.append(
                f"{q.get('citation_accuracy', 0.0):.2f}" if "citation_accuracy" in q else "-"
            )
            row.append(
                f"{q.get('semantic_similarity', 0.0):.2f}" if "semantic_similarity" in q else "-"
            )
        lines.append("| " + " | ".join(row) + " |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline.")
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--mode", required=True, choices=["retrieval", "answer", "full"])
    parser.add_argument("--top-k", type=int, default=settings.top_k)
    parser.add_argument("--tag", default="run")
    parser.add_argument("--output-dir", default="evals/results/")
    args = parser.parse_args()

    if args.mode in ("answer", "full"):
        check_ollama_or_exit()

    logger.info("Loading dataset: %s", args.dataset)
    records = load_dataset(args.dataset)
    logger.info("Loaded %d record(s).", len(records))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = build_run_id(args.tag)
    per_question = []

    for i, record in enumerate(records, start=1):
        logger.info("[%d/%d] Evaluating %s …", i, len(records), record["id"])
        q_result = evaluate_question(record, mode=args.mode, top_k=args.top_k)
        per_question.append(q_result)
        logger.info("  → status=%s", q_result.get("status"))

    summary = build_summary(per_question, args.mode)

    result = {
        "run_id": run_id,
        "dataset": args.dataset,
        "mode": args.mode,
        "config": {
            "top_k": args.top_k,
            "embedding_model": settings.embedding_model,
            "llm": settings.llm_model,
        },
        "summary": summary,
        "per_question": per_question,
    }

    safe_id = run_id.replace(":", "-")
    json_path = output_dir / f"{safe_id}.json"
    md_path = output_dir / f"{safe_id}.md"

    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(result, md_path)

    logger.info("Results written to %s", json_path)

    # Print summary
    print(f"\nRun: {run_id}")
    print(f"Dataset: {args.dataset}  |  Mode: {args.mode}  |  Top-k: {args.top_k}")
    evaluated = summary["evaluated"]
    total = summary["total_questions"]
    skipped = summary["skipped"]
    print(f"Evaluated: {evaluated}/{total}  |  Skipped: {skipped}")
    summary_keys = (
        "hit_rate_at_k", "mrr", "precision_at_k", "citation_accuracy", "semantic_similarity_mean"
    )
    for key in summary_keys:
        if key in summary:
            print(f"  {key}: {summary[key]:.3f}")


if __name__ == "__main__":
    main()
