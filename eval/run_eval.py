"""
Agent quality evaluation harness.

Runs all 15 test cases through the live LangGraph agent, scores each
response with an LLM-as-judge, and logs aggregate metrics to MLflow.
Results populate the Staff Dashboard Tab 4.

Usage:
    python eval/run_eval.py
"""

import os
import sys
import time
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import mlflow
from langchain_core.messages import HumanMessage, AIMessage

from agent.llm import fast_llm
from db.client import get_patient_by_name, get_medical_records
from eval.test_cases import TEST_CASES, TEST_PATIENT

JUDGE_PROMPT = """You are an impartial evaluator for a healthcare AI assistant.

Test case: {description}
User input: {input}
Expected behavior: {reference}
Agent response: {response}
Tools that fired: {tools_fired}
Expected tools: {expected_tools}

Score each dimension from 0.0 to 1.0:
- correctness: Did the agent do the right thing and produce a useful response?
- relevance: Was the response on-topic and appropriate for the request?
- tool_accuracy: Did the correct tools fire? (1.0 = all expected tools fired, 0.0 = none did, partial credit for partial matches)

Respond in this exact format with no other text:
correctness: <score>
relevance: <score>
tool_accuracy: <score>"""


def build_patient_context(patient: dict) -> str:
    records = get_medical_records(patient["id"])
    lines = [
        f"Patient: {patient['name']}, Age: {patient['age']}, Gender: {patient['gender']}",
        f"Blood Type: {patient['blood_type']}",
        f"Condition: {patient['medical_condition']}",
        f"Medication: {patient['medication']}",
        f"Test Results: {patient['test_results']}",
    ]
    if records:
        lines.append("Records on file: " + str(len(records)))
    return "\n".join(lines)


def run_case(graph, thread_id: str, patient: dict, case: dict) -> dict:
    patient_context = build_patient_context(patient)
    state = {
        "messages": [HumanMessage(content=case["input"])],
        "patient_id": patient["id"],
        "patient_name": patient["name"],
        "patient_context": patient_context,
        "plan": None,
    }

    start = time.time()
    result = graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
    latency = round(time.time() - start, 2)

    # Extract final AI response
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    response_text = ai_messages[-1].content if ai_messages else ""

    # Extract tools that fired (from tool call messages)
    tools_fired = []
    for m in result["messages"]:
        if hasattr(m, "tool_calls") and m.tool_calls:
            for tc in m.tool_calls:
                tools_fired.append(tc["name"])

    return {
        "response": response_text,
        "tools_fired": tools_fired,
        "latency": latency,
    }


def judge_response(case: dict, response: str, tools_fired: list[str]) -> dict[str, float]:
    prompt = JUDGE_PROMPT.format(
        description=case["description"],
        input=case["input"],
        reference=case["reference"],
        response=response[:1500],
        tools_fired=tools_fired,
        expected_tools=case["expected_tools"],
    )
    result = fast_llm.invoke([HumanMessage(content=prompt)])
    scores = {"correctness": 0.0, "relevance": 0.0, "tool_accuracy": 0.0}
    for line in result.content.strip().splitlines():
        for key in scores:
            if line.startswith(key + ":"):
                try:
                    scores[key] = float(line.split(":")[1].strip())
                except ValueError:
                    pass
    return scores


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 72)
    print(f"{'ID':<16} {'Correct':>8} {'Relevant':>9} {'Tools':>7} {'Latency':>9}")
    print("-" * 72)
    for r in results:
        s = r["scores"]
        print(
            f"{r['id']:<16} {s['correctness']:>8.2f} {s['relevance']:>9.2f} "
            f"{s['tool_accuracy']:>7.2f} {r['latency']:>8.2f}s"
        )
    print("=" * 72)

    avg_correctness = sum(r["scores"]["correctness"] for r in results) / len(results)
    avg_relevance = sum(r["scores"]["relevance"] for r in results) / len(results)
    avg_tool_accuracy = sum(r["scores"]["tool_accuracy"] for r in results) / len(results)
    avg_latency = sum(r["latency"] for r in results) / len(results)

    print(f"\n{'AVERAGES':<16} {avg_correctness:>8.2f} {avg_relevance:>9.2f} {avg_tool_accuracy:>7.2f} {avg_latency:>8.2f}s")
    print(f"\nBooking success: {sum(1 for r in results if 'book_appointment' in r['tools_fired'] and 'book_appointment' in r['expected_tools'])}"
          f"/{sum(1 for r in results if 'book_appointment' in r['expected_tools'])} booking cases passed")


def main():
    print(f"Patient Compass Coordinator — Eval Run ({date.today()})")
    print(f"Test patient: {TEST_PATIENT}")
    print(f"Cases: {len(TEST_CASES)}\n")

    patient = get_patient_by_name(TEST_PATIENT)
    if not patient:
        print(f"ERROR: Test patient '{TEST_PATIENT}' not found in database.")
        print("Update TEST_PATIENT in eval/test_cases.py to a name that exists.")
        sys.exit(1)

    print(f"Loaded patient: {patient['name']} (id: {patient['id'][:8]}...)\n")

    mlflow.set_experiment("patient-compass-eval")

    with mlflow.start_run(run_name=f"eval-{date.today()}"):
        from agent.graph import build_graph
        graph = build_graph()
        results = []

        for i, case in enumerate(TEST_CASES, 1):
            print(f"[{i:02d}/{len(TEST_CASES)}] {case['id']}: {case['description']}")
            thread_id = f"eval-{case['id']}"

            try:
                outcome = run_case(graph, thread_id, patient, case)
                scores = judge_response(case, outcome["response"], outcome["tools_fired"])

                results.append({
                    "id": case["id"],
                    "scores": scores,
                    "latency": outcome["latency"],
                    "tools_fired": outcome["tools_fired"],
                    "expected_tools": case["expected_tools"],
                })

                status = "PASS" if scores["correctness"] >= 0.7 else "FAIL"
                print(f"       {status} | correct={scores['correctness']:.2f} "
                      f"relevant={scores['relevance']:.2f} tools={scores['tool_accuracy']:.2f} "
                      f"latency={outcome['latency']}s")
                print(f"       tools fired: {outcome['tools_fired']}")

            except Exception as e:
                print(f"       ERROR: {e}")
                results.append({
                    "id": case["id"],
                    "scores": {"correctness": 0.0, "relevance": 0.0, "tool_accuracy": 0.0},
                    "latency": 0.0,
                    "tools_fired": [],
                    "expected_tools": case["expected_tools"],
                })

        # Aggregate metrics
        avg_correctness = sum(r["scores"]["correctness"] for r in results) / len(results)
        avg_relevance = sum(r["scores"]["relevance"] for r in results) / len(results)
        avg_tool_accuracy = sum(r["scores"]["tool_accuracy"] for r in results) / len(results)
        avg_latency = sum(r["latency"] for r in results) / len(results)

        booking_cases = [r for r in results if "book_appointment" in r["expected_tools"]]
        booking_success = sum(
            1 for r in booking_cases if "book_appointment" in r["tools_fired"]
        )
        booking_success_rate = booking_success / len(booking_cases) if booking_cases else 0.0

        # Per-tool call counts across all cases
        all_tools_fired = [t for r in results for t in r["tools_fired"]]
        tool_counts = Counter(all_tools_fired)

        quality_metrics = {
            "avg_correctness": avg_correctness,
            "avg_relevance": avg_relevance,
            "avg_tool_accuracy": avg_tool_accuracy,
            "avg_latency_s": avg_latency,
            "booking_success_rate": booking_success_rate,
            "cases_run": len(results),
        }
        tool_metrics = {f"tool_count_{name}": count for name, count in tool_counts.items()}

        mlflow.log_metrics({**quality_metrics, **tool_metrics})

        print_summary(results)
        print(f"\nMLflow run logged. View in dashboard Tab 4 or run: mlflow ui")


if __name__ == "__main__":
    main()
