import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agent import app as agent_app
from evals.eval_metrics import (
    calculate_hit_rate_at_k,
    calculate_reciprocal_rank,
    evaluate_safety_refusal,
    evaluate_generation_unified,
    BEDROCK_MODEL_ID,
    JUDGE_MODEL_ID
)

EVALS_DIR = Path(__file__).parent
DATASET_FILE = EVALS_DIR / "benchmark_40.json"
BENCHMARKS_FILE = EVALS_DIR / "benchmarks.json"
LATEST_REPORT_FILE = EVALS_DIR / "latest_eval_report.json"


def _current_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _load_benchmarks() -> dict:
    if BENCHMARKS_FILE.exists():
        with open(BENCHMARKS_FILE) as f:
            return json.load(f)
    return {"schema_version": 1, "runs": []}


def _save_benchmarks(data: dict) -> None:
    with open(BENCHMARKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _next_run_id(runs: list) -> str:
    nums = [int(r["run_id"][1:]) for r in runs
            if r.get("run_id", "").startswith("r") and r["run_id"][1:].isdigit()]
    return f"r{max(nums) + 1 if nums else 1:03d}"


def run_benchmark(limit: int = None):
    if not DATASET_FILE.exists():
        print(f"Error: Dataset file {DATASET_FILE} not found.")
        sys.exit(1)

    with open(DATASET_FILE) as f:
        dataset = json.load(f)

    if limit and limit > 0:
        dataset = dataset[:limit]

    print("\n" + "=" * 75)
    print(f"  Grounded Clinical Agent: Comprehensive Benchmark ({len(dataset)} Questions)")
    print(f"  * Agent Model: {BEDROCK_MODEL_ID}")
    print(f"  * Judge Model: {JUDGE_MODEL_ID} (Unified Faithfulness + Relevance)")
    print("=" * 75)

    results = []
    
    for idx, item in enumerate(dataset, 1):
        qid = item["id"]
        qtext = item["question"]
        expected_src = item.get("expected_source", "")
        is_adv = item.get("is_adversarial", False)

        print(f"\n[{idx}/{len(dataset)}] QID: {qid} ({item.get('category', 'general')})")
        print(f"  Query: \"{qtext[:80]}...\"" if len(qtext) > 80 else f"  Query: \"{qtext}\"")

        config = {"configurable": {"thread_id": str(uuid4())}}
        
        try:
            # 1. Execute agent graph
            response = agent_app.invoke({"user_query": qtext}, config=config)
            
            status = response.get("status")
            med_output = response.get("medical_output")
            conv_output = response.get("conversational_output")
            retrieved_chunks = response.get("retrieved_chunks", [])
            
            answer = med_output.answer if med_output and hasattr(med_output, "answer") else (conv_output or "")
            
            # 2. Deterministic Retrieval Metrics ($0.00 cost)
            hit_rate_3 = calculate_hit_rate_at_k(retrieved_chunks, expected_src, k=3)
            mrr = calculate_reciprocal_rank(retrieved_chunks, expected_src)
            
            # 3. Deterministic Safety Metric ($0.00 cost)
            safe_pass, safe_reason = evaluate_safety_refusal(response, is_adv)
            
            # 4. Unified Generation Metrics (1 Sonnet call per question)
            gen_metrics = evaluate_generation_unified(qtext, retrieved_chunks, answer)
            faithfulness = gen_metrics.get("faithfulness", 0.0)
            relevance = gen_metrics.get("answer_relevance", 0.0)
            reasoning = gen_metrics.get("reasoning", "")

            # Log progress line
            hit_str = "HIT" if hit_rate_3 > 0 else "MISS"
            print(f"  -> Retrieval: [{hit_str}] Hit@3={hit_rate_3:.1f}, MRR={mrr:.2f} | Grounding: Faithfulness={faithfulness:.2f}, Relevance={relevance:.2f}")
            if is_adv:
                print(f"  -> Safety Defense: {'[PASS]' if safe_pass else '[FAIL]'} ({safe_reason})")

            results.append({
                "id": qid,
                "category": item.get("category"),
                "question": qtext,
                "expected_source": expected_src,
                "is_adversarial": is_adv,
                "status": status,
                "hit_rate_at_3": hit_rate_3,
                "reciprocal_rank": mrr,
                "safety_passed": safe_pass,
                "faithfulness": faithfulness,
                "answer_relevance": relevance,
                "eval_reasoning": reasoning,
                "answer_snippet": answer[:150] + "..." if len(answer) > 150 else answer,
            })

        except Exception as e:
            print(f"  -> ERROR during execution: {str(e)}")
            results.append({
                "id": qid,
                "category": item.get("category"),
                "question": qtext,
                "expected_source": expected_src,
                "is_adversarial": is_adv,
                "status": "error",
                "hit_rate_at_3": 0.0,
                "reciprocal_rank": 0.0,
                "safety_passed": False,
                "faithfulness": 0.0,
                "answer_relevance": 0.0,
                "eval_reasoning": f"Execution error: {str(e)}",
                "answer_snippet": "",
            })

    # Summary calculations
    total = len(results)
    avg_hit_rate = sum(r["hit_rate_at_3"] for r in results) / total if total else 0.0
    avg_mrr = sum(r["reciprocal_rank"] for r in results) / total if total else 0.0
    avg_faithfulness = sum(r["faithfulness"] for r in results) / total if total else 0.0
    avg_relevance = sum(r["answer_relevance"] for r in results) / total if total else 0.0
    
    adv_cases = [r for r in results if r["is_adversarial"]]
    safety_rate = (sum(1 for r in adv_cases if r["safety_passed"]) / len(adv_cases)) * 100 if adv_cases else 100.0

    print("\n" + "=" * 75)
    print("  BENCHMARK SUMMARY RESULTS")
    print("=" * 75)
    print(f"  * Total Questions Evaluated:  {total}")
    print(f"  * Retrieval HitRate@3:        {avg_hit_rate * 100:.1f}%")
    print(f"  * Retrieval Mean Reciprocal:  {avg_mrr:.3f} MRR")
    print(f"  * Generation Faithfulness:    {avg_faithfulness * 100:.1f}% (Hallucination: {(1 - avg_faithfulness) * 100:.1f}%)")
    print(f"  * Answer Relevance:           {avg_relevance * 100:.1f}%")
    print(f"  * Adversarial Safety Defense: {safety_rate:.1f}%")
    print("=" * 75)

    # Save detailed report
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "total_questions": total,
        "metrics": {
            "avg_hit_rate_at_3": round(avg_hit_rate, 3),
            "avg_mrr": round(avg_mrr, 3),
            "avg_faithfulness": round(avg_faithfulness, 3),
            "hallucination_rate": round(1.0 - avg_faithfulness, 3),
            "avg_answer_relevance": round(avg_relevance, 3),
            "safety_resilience_rate": round(safety_rate, 1),
        },
        "results": results
    }
    with open(LATEST_REPORT_FILE, "w") as f:
        json.dump(report_data, f, indent=2)

    # Append to benchmarks ledger
    benchmarks = _load_benchmarks()
    run_id = _next_run_id(benchmarks["runs"])
    ledger_entry = {
        "run_id": run_id,
        "date": date.today().isoformat(),
        "commit": _current_commit(),
        "agent_model": BEDROCK_MODEL_ID,
        "judge_model": JUDGE_MODEL_ID,
        "questions_file": "evals/benchmark_40.json",
        "num_questions": total,
        "hit_rate_at_3": round(avg_hit_rate, 3),
        "mrr": round(avg_mrr, 3),
        "avg_faithfulness": round(avg_faithfulness, 3),
        "hallucination_rate": round(1.0 - avg_faithfulness, 3),
        "avg_answer_relevance": round(avg_relevance, 3),
        "safety_defense_rate": round(safety_rate, 1),
        "notes": "Baseline B0 (Naive RAG: MedEmbed dense k=5 similarity search before BM25/reranker upgrade)"
    }
    benchmarks["runs"].append(ledger_entry)
    _save_benchmarks(benchmarks)

    print(f"\n[INFO] Detailed report saved to: {LATEST_REPORT_FILE}")
    print(f"[INFO] Benchmark ledger entry '{run_id}' logged in {BENCHMARKS_FILE}\n")


def show_ledger():
    benchmarks = _load_benchmarks()
    runs = benchmarks.get("runs", [])
    if not runs:
        print("No benchmark runs recorded yet.")
        return

    print("\n" + "=" * 90)
    print("  HISTORICAL BENCHMARK EVALUATION LEDGER")
    print("=" * 90)
    print(f"{'Run':<6} {'Date':<11} {'Commit':<8} {'#Q':<4} {'Hit@3':<7} {'Faithful':<9} {'Relevance':<10} {'Safety':<8} {'Notes':<25}")
    print("-" * 90)
    for r in runs:
        hit = f"{r.get('hit_rate_at_3', 0.0):.2f}" if 'hit_rate_at_3' in r else "N/A"
        faith = f"{r.get('avg_faithfulness', 0.0):.3f}"
        rel = f"{r.get('avg_answer_relevance', 0.0):.2f}" if 'avg_answer_relevance' in r else "N/A"
        safe = f"{r.get('safety_defense_rate', 0.0):.1f}%" if 'safety_defense_rate' in r else "N/A"
        notes = (r.get("notes") or "")[:25]
        print(f"{r.get('run_id',''):<6} {r.get('date',''):<11} {r.get('commit',''):<8} {r.get('num_questions',''):<4} {hit:<7} {faith:<9} {rel:<10} {safe:<8} {notes:<25}")
    print("=" * 90 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Clinical Agent Evaluation Runner")
    parser.add_argument("--limit", type=int, default=None, help="Limit to first N questions for quick check")
    parser.add_argument("--show", action="store_true", help="Display past benchmark runs table")
    args = parser.parse_args()

    if args.show:
        show_ledger()
    else:
        run_benchmark(limit=args.limit)


if __name__ == "__main__":
    main()
