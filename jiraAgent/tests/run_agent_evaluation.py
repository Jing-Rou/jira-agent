from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model.agent import invoke


CASES_PATH = Path(__file__).with_name("agent_eval_cases.json")
REPORT_PATH = Path(__file__).with_name("evaluation_report.json")

WRITE_TOOLS = {
    "create_issue",
    "transition_issue",
    "create_issue_link",
    "jira_add_issue_comment",
}

DRAFT_FIELDS = {
    "type",
    "project_key",
    "summary",
    "description",
    "work_type",
}


def load_cases() -> list[dict[str, Any]]:
    with CASES_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def extract_tool_calls(result: dict) -> list[dict]:
    calls = []

    for event in result.get("agent_trace", []):
        if not isinstance(event, dict):
            continue

        event_type = str(event.get("type", "")).lower()

        if event_type in {"tool_result", "observation"}:
            continue

        name = (
            event.get("tool")
            or event.get("name")
            or event.get("function")
        )
        arguments = event.get("args") or event.get("arguments") or {}

        if name:
            calls.append({
                "name": name,
                "arguments": arguments,
            })

    if not calls and result.get("function"):
        calls.append({
            "name": result["function"],
            "arguments": {},
        })

    return calls


def arguments_match(
    actual: dict,
    expected: dict,
) -> bool:
    return all(
        str(actual.get(key, "")).strip().lower()
        == str(value).strip().lower()
        for key, value in expected.items()
    )


def required_arguments_present(
    actual: dict,
    required: list[str],
) -> bool:
    return all(
        key in actual
        and actual[key] is not None
        and str(actual[key]).strip()
        for key in required
    )


def valid_draft(draft: Any) -> bool:
    if not isinstance(draft, dict):
        return False

    if not DRAFT_FIELDS.issubset(draft):
        return False

    return all(
        isinstance(draft[field], str)
        and draft[field].strip()
        for field in DRAFT_FIELDS
    )


def evaluate_case(
    case: dict,
    result: dict,
) -> dict:
    calls = extract_tool_calls(result)
    expected_tool = case["expected_tool"]

    matching_calls = [
        call for call in calls
        if call["name"] == expected_tool
    ]

    tool_selected = bool(matching_calls)
    actual_arguments = (
        matching_calls[0]["arguments"]
        if matching_calls
        else {}
    )

    argument_match = arguments_match(
        actual_arguments,
        case.get("expected_arguments", {}),
    )

    required_arguments_valid = required_arguments_present(
        actual_arguments,
        case.get("required_arguments", []),
    )

    used_write_tool = any(
        call["name"] in WRITE_TOOLS
        for call in calls
    )

    confirmation_respected = (
        case.get("write_allowed", False)
        or not used_write_tool
    )

    draft_valid = (
        valid_draft(result.get("draft"))
        if case.get("expect_valid_draft")
        else True
    )

    output_valid = bool(result.get("output"))

    checks = {
        "tool_selected": tool_selected,
        "arguments_match": argument_match,
        "required_arguments_present": required_arguments_valid,
        "confirmation_respected": confirmation_respected,
        "draft_valid": draft_valid,
        "output_valid": output_valid,
    }

    return {
        "id": case["id"],
        "input": case["input"],
        "expected_tool": expected_tool,
        "actual_tools": [call["name"] for call in calls],
        "actual_arguments": actual_arguments,
        "checks": checks,
        "passed": all(checks.values()),
        "error": "",
    }


def calculate_rate(
    reports: list[dict],
    check_name: str,
) -> float:
    if not reports:
        return 0.0

    passed = sum(
        report["checks"].get(check_name, False)
        for report in reports
    )
    return passed / len(reports)


def main() -> None:
    cases = load_cases()
    reports = []

    for case in cases:
        print(f"\nRunning: {case['id']}")
        print(f"Input: {case['input']}")

        try:
            result = invoke(
                user_request=case["input"],
                thread_id=f"evaluation-{uuid4()}",
            )
            report = evaluate_case(case, result)

        except Exception as error:
            report = {
                "id": case["id"],
                "input": case["input"],
                "expected_tool": case["expected_tool"],
                "actual_tools": [],
                "actual_arguments": {},
                "checks": {
                    "tool_selected": False,
                    "arguments_match": False,
                    "required_arguments_present": False,
                    "confirmation_respected": True,
                    "draft_valid": False,
                    "output_valid": False,
                },
                "passed": False,
                "error": str(error),
            }

        reports.append(report)

        status = "PASS" if report["passed"] else "FAIL"
        print(f"Result: {status}")
        print(f"Tools: {report['actual_tools']}")

        if report["error"]:
            print(f"Error: {report['error']}")

    summary = {
        "total_cases": len(reports),
        "passed_cases": sum(report["passed"] for report in reports),
        "tool_selection_accuracy": calculate_rate(
            reports,
            "tool_selected",
        ),
        "argument_accuracy": calculate_rate(
            reports,
            "arguments_match",
        ),
        "confirmation_compliance": calculate_rate(
            reports,
            "confirmation_respected",
        ),
        "draft_validity": calculate_rate(
            reports,
            "draft_valid",
        ),
        "output_validity": calculate_rate(
            reports,
            "output_valid",
        ),
    }

    report_data = {
        "summary": summary,
        "cases": reports,
    }

    REPORT_PATH.write_text(
        json.dumps(report_data, indent=2),
        encoding="utf-8",
    )

    print("\nEvaluation summary")
    print(json.dumps(summary, indent=2))
    print(f"\nReport: {REPORT_PATH}")

    deployment_passed = (
        summary["tool_selection_accuracy"] >= 0.95
        and summary["confirmation_compliance"] == 1.0
        and summary["draft_validity"] == 1.0
        and summary["output_validity"] >= 0.95
    )

    if not deployment_passed:
        raise SystemExit(
            "Evaluation failed. Deployment should be blocked."
        )

    print("Evaluation passed. Deployment may continue.")


if __name__ == "__main__":
    main()