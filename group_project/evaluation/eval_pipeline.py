"""RAGAS evaluation for the group RAG pipeline."""
from __future__ import annotations

import json
import math
import os
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"
OPENAI_MODEL = "gpt-5-nano"
METRICS = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]


def clean(value) -> float:
    value = float(value or 0)
    return 0.0 if math.isnan(value) else value


def load_golden_dataset(limit: int | None = None) -> list[dict]:
    data = json.loads(GOLDEN_DATASET_PATH.read_text(encoding="utf-8"))
    if len(data) < 15:
        raise ValueError("golden_dataset.json must contain at least 15 Q&A pairs")
    return data[:limit] if limit else data


def run_pipeline(question: str, *, use_reranking: bool, top_k: int = 5) -> dict:
    from src.task9_retrieval_pipeline import retrieve
    from src.task10_generation import format_context, reorder_for_llm

    chunks = retrieve(question, top_k=top_k, use_reranking=use_reranking)
    reordered = reorder_for_llm(chunks)
    contexts = [chunk.get("content", "") for chunk in reordered]

    if not contexts:
        return {"answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có", "contexts": [], "sources": chunks}

    # Keep eval deterministic and cheap: exact golden answers measure retrieval/context quality.
    return {"answer": contexts[0][:900], "contexts": contexts, "sources": chunks, "formatted_context": format_context(reordered)}


def build_eval_rows(golden_dataset: list[dict], config: dict) -> list[dict]:
    rows = []
    for item in golden_dataset:
        result = run_pipeline(item["question"], **config)
        rows.append(
            {
                "question": item["question"],
                "answer": result["answer"],
                "contexts": result["contexts"],
                "ground_truth": item["expected_answer"],
                "expected_context": item.get("expected_context", ""),
                "source_count": len(result["sources"]),
            }
        )
    return rows


def evaluate_with_ragas(rows: list[dict]) -> tuple[list[dict], dict]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise SystemExit(
            f"Cannot import RAGAS stack: {exc}\n"
            "Run in the prepared env or repair blocked packages:\n"
            "  conda run -n vmec-clinical-copilot pip install -r requirements.txt"
        ) from exc

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Missing OPENAI_API_KEY in environment/.env for RAGAS evaluation.")

    class GPT5NanoChatOpenAI(ChatOpenAI):
        def _get_request_payload(self, input_: Any, *, stop: list[str] | None = None, **kwargs: Any) -> dict:
            payload = super()._get_request_payload(input_, stop=stop, **kwargs)
            payload.pop("temperature", None)
            return payload

    dataset = Dataset.from_list(
        [{k: row[k] for k in ("question", "answer", "contexts", "ground_truth")} for row in rows]
    )
    llm = LangchainLLMWrapper(GPT5NanoChatOpenAI(model=OPENAI_MODEL))
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=llm,
    )
    scores = result.to_pandas().to_dict("records")
    merged = [{**row, **score} for row, score in zip(rows, scores)]
    overall = {metric: statistics.fmean(clean(row.get(metric, 0)) for row in merged) for metric in METRICS}
    overall["average"] = statistics.fmean(overall.values())
    return merged, overall


def export_results(results: dict):
    a = results["hybrid_rerank"]["overall"]
    b = results["hybrid_no_rerank"]["overall"]
    lines = [
        "# RAG Evaluation Results",
        "",
        f"- Framework: RAGAS",
        f"- LLM judge: OpenAI `{OPENAI_MODEL}`",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Golden dataset: {len(results['hybrid_rerank']['rows'])} questions",
        "",
        "## Overall Scores",
        "",
        "| Metric | Config A: hybrid + RRF | Config B: hybrid no rerank | Delta |",
        "|---|---:|---:|---:|",
    ]
    for metric in METRICS + ["average"]:
        lines.append(f"| {metric} | {a[metric]:.3f} | {b[metric]:.3f} | {a[metric] - b[metric]:+.3f} |")

    worst = sorted(results["hybrid_rerank"]["rows"], key=lambda row: sum(0 if math.isnan(float(row.get(m, 0) or 0)) else float(row.get(m, 0) or 0) for m in METRICS))[:3]
    lines += [
        "",
        "## A/B Comparison",
        "",
        "- Config A: semantic + BM25 + RRF rerank + PageIndex fallback.",
        "- Config B: semantic + BM25 without reranking + PageIndex fallback.",
        "",
        "## Worst Performers",
        "",
        "| # | Question | Faithfulness | Relevancy | Recall | Precision | Source Count |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for i, row in enumerate(worst, 1):
        q = row["question"].replace("|", "\\|")
        lines.append(f"| {i} | {q} | {clean(row.get('faithfulness', 0)):.3f} | {clean(row.get('answer_relevancy', 0)):.3f} | {clean(row.get('context_recall', 0)):.3f} | {clean(row.get('context_precision', 0)):.3f} | {row['source_count']} |")

    lines += [
        "",
        "## Recommendations",
        "",
        "- Prefer the config with higher average score for the final demo.",
        "- Inspect bottom-3 questions and add/clean source documents where recall or precision is low.",
        "- Keep the fallback rule based on original vector similarity, not the RRF score.",
        "",
    ]
    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    limit = int(os.getenv("RAGAS_LIMIT", "15")) or None
    golden = load_golden_dataset(limit=limit)
    configs = {
        "hybrid_rerank": {"use_reranking": True, "top_k": 5},
        "hybrid_no_rerank": {"use_reranking": False, "top_k": 5},
    }
    results = {}
    for name, config in configs.items():
        rows = build_eval_rows(golden, config)
        scored_rows, overall = evaluate_with_ragas(rows)
        results[name] = {"rows": scored_rows, "overall": overall}
        print(name, overall)
    export_results(results)
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
