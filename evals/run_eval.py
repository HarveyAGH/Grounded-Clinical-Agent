import asyncio
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.faithfulness import check_faithfulness, BEDROCK_MODEL_ID, JUDGE_MODEL_ID

EVALS_DIR = Path(__file__).parent
BENCHMARKS_FILE = EVALS_DIR / "benchmarks.json"


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


def _record_benchmark(results: list) -> str:
    total = len(results)
    avg_faithfulness = sum(r["faithfulness"] for r in results) / total
    run_id = _next_run_id(_load_benchmarks()["runs"])
    row = {
        "run_id": run_id,
        "date": date.today().isoformat(),
        "commit": _current_commit(),
        "agent_model": BEDROCK_MODEL_ID,
        "judge_model": JUDGE_MODEL_ID,
        "questions_file": "evals/adversarial_questions.json",
        "num_questions": total,
        "avg_faithfulness": round(avg_faithfulness, 3),
        "hallucination_rate": round(1 - avg_faithfulness, 3),
        "notes": "",
    }
    benchmarks = _load_benchmarks()
    benchmarks["runs"].append(row)
    _save_benchmarks(benchmarks)
    return run_id


def show_benchmarks() -> None:
    runs = _load_benchmarks()["runs"]
    if not runs:
        print("No benchmark runs recorded yet.")
        return
    header = f"{'Run':<5}{'Date':<11}{'Commit':<8}{'Judge':<28}{'N':<4}{'Faith':<7}{'Halluc':<7}Notes"
    print(header)
    print("-" * len(header))
    for r in runs:
        notes = (r.get("notes") or "")[:60]
        print(f"{r['run_id']:<5}{r['date']:<11}{r['commit']:<8}"
              f"{r['judge_model'][:27]:<28}{r['num_questions']:<4}"
              f"{r['avg_faithfulness']:<7.3f}{r['hallucination_rate'] * 100:5.1f}% {notes}")


async def run_evaluation():
    from src.agent import app

    with open(EVALS_DIR / "adversarial_questions.json") as f:
        test_cases = json.load(f)

    results = []
    for case in test_cases:
        print(f"Testing: {case['id']} - {case['question'][:50]}...")

        final_state = app.invoke({"user_query": case["question"]})
        medical_obj = final_state.get("medical_output")
        if hasattr(medical_obj, "answer"):
            medical_answer = medical_obj.answer
        elif isinstance(medical_obj, str):
            medical_answer = medical_obj
        else:
            medical_answer = ""

        normal_answer = final_state.get("conversational_output") or ""
        routed_to_conversational = final_state.get("status") == "conversational_agent"
        answer = normal_answer if routed_to_conversational else medical_answer
        chunks = final_state.get("retrieved_chunks", [])

        if routed_to_conversational:
            # Out-of-domain query correctly handled by the conversational agent:
            # no medical claims were made, so there is nothing to hallucinate.
            score = 1.0
        elif chunks:
            score = await check_faithfulness(case["question"], chunks, answer) if answer else 0.0
        else:
            score = 0.0

        results.append({
            "id": case["id"],
            "question": case["question"],
            "expected": case["expected_behavior"],
            "faithfulness": score,
            "routed": "conversational" if routed_to_conversational else "medical",
            "output": answer[:200],
        })

    total = len(results)
    avg_faithfulness = sum(r["faithfulness"] for r in results) / total
    hallucination_rate = 1 - avg_faithfulness

    print("\n=== Evaluation Results ===")
    print(f"Total questions: {total}")
    print(f"Average faithfulness: {avg_faithfulness:.3f}")
    print(f"Hallucination rate: {hallucination_rate * 100:.1f}%")

    with open(EVALS_DIR / "eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

    run_id = _record_benchmark(results)
    print(f"Recorded as {run_id} in evals/benchmarks.json")

    return hallucination_rate


if __name__ == "__main__":
    if "--show" in sys.argv:
        show_benchmarks()
    else:
        rate = asyncio.run(run_evaluation())
        print(f"\nFinal hallucination rate: {rate * 100:.1f}%")
