"""
Phase 6 — Governance evaluation.

Runs all input and output test cases through the guardrail functions and logs
results to MLflow. No LLM calls — purely deterministic.

Usage:
    python eval/run_governance_eval.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import mlflow

# Use a relative SQLite URI so the path never has spaces, avoiding a Windows
# bug where MLflow's auto-generated sqlite:/// URI URL-encodes spaces (%20)
# which pathlib.mkdir then cannot resolve.
mlflow.set_tracking_uri("sqlite:///mlflow.db")

from eval.governance_test_cases import INPUT_TEST_CASES, OUTPUT_TEST_CASES
from agent.guardrails import sanitize_input, sanitize_output


def _run_input_cases() -> dict:
    results = []
    for case in INPUT_TEST_CASES:
        result = sanitize_input(case["input"])
        blocked = not result.passed

        passed = blocked == case["expected_blocked"]
        if case["expected_blocked"] and case["expected_category"]:
            passed = passed and result.category == case["expected_category"]

        results.append({
            "id": case["id"],
            "description": case["description"],
            "expected_blocked": case["expected_blocked"],
            "actual_blocked": blocked,
            "expected_category": case["expected_category"],
            "actual_category": result.category,
            "passed": passed,
        })

        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {case['id']}: {case['description']}")
        if not passed:
            print(f"         expected_blocked={case['expected_blocked']}, actual_blocked={blocked}")
            print(f"         expected_category={case['expected_category']}, actual_category={result.category}")

    return results


def _run_output_cases() -> dict:
    results = []
    for case in OUTPUT_TEST_CASES:
        result = sanitize_output(case["output"])
        blocked = not result.passed

        passed = blocked == case["expected_blocked"]
        if case["expected_blocked"] and case["expected_category"]:
            passed = passed and result.category == case["expected_category"]

        results.append({
            "id": case["id"],
            "description": case["description"],
            "expected_blocked": case["expected_blocked"],
            "actual_blocked": blocked,
            "expected_category": case["expected_category"],
            "actual_category": result.category,
            "passed": passed,
        })

        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {case['id']}: {case['description']}")
        if not passed:
            print(f"         expected_blocked={case['expected_blocked']}, actual_blocked={blocked}")
            print(f"         expected_category={case['expected_category']}, actual_category={result.category}")

    return results


def main():
    mlflow.set_experiment("patient_compass_governance")

    with mlflow.start_run(run_name="governance_guardrails"):
        print("\n-- Input guardrails --")
        input_results = _run_input_cases()

        print("\n-- Output guardrails --")
        output_results = _run_output_cases()

        all_results = input_results + output_results
        total = len(all_results)
        passed = sum(1 for r in all_results if r["passed"])
        failed = total - passed

        injection_cases = [r for r in input_results if r["expected_category"] == "injection"]
        pii_cases = [r for r in input_results if r["expected_category"] == "pii"]
        leakage_cases = [r for r in output_results if r["expected_category"] == "leakage"]
        legit_cases = [r for r in all_results if r["expected_category"] == ""]

        injection_acc = sum(1 for r in injection_cases if r["passed"]) / len(injection_cases) if injection_cases else 0
        pii_acc = sum(1 for r in pii_cases if r["passed"]) / len(pii_cases) if pii_cases else 0
        leakage_acc = sum(1 for r in leakage_cases if r["passed"]) / len(leakage_cases) if leakage_cases else 0
        false_positive_rate = sum(1 for r in legit_cases if r["actual_blocked"]) / len(legit_cases) if legit_cases else 0
        overall_accuracy = passed / total if total else 0

        mlflow.log_metrics({
            "total_cases": total,
            "passed": passed,
            "failed": failed,
            "overall_accuracy": overall_accuracy,
            "injection_accuracy": injection_acc,
            "pii_accuracy": pii_acc,
            "leakage_accuracy": leakage_acc,
            "false_positive_rate": false_positive_rate,
        })

        print(f"\n-- Summary --")
        print(f"  Overall:          {passed}/{total} ({overall_accuracy:.0%})")
        print(f"  Injection:        {injection_acc:.0%}")
        print(f"  PII:              {pii_acc:.0%}")
        print(f"  Leakage:          {leakage_acc:.0%}")
        print(f"  False positives:  {false_positive_rate:.0%} (legit inputs blocked incorrectly)")
        print(f"  MLflow run logged to experiment: patient_compass_governance")


if __name__ == "__main__":
    main()
