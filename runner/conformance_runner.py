#!/usr/bin/env python3
"""Run OpenID conformance plan modules and write normalized results."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


DEFAULT_SUITE_URL = "https://localhost:8443"
POLL_INTERVAL_SECONDS = 3
REQUEST_TIMEOUT_SECONDS = 30
EXPECTED_STATUSES = {
    "PASSED",
    "FAILED",
    "SKIPPED",
    "WARNING",
    "EXPECTED_FAILURE",
    "EXPECTED_SKIP",
}


class RunnerError(Exception):
    """An actionable configuration or conformance API error."""


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an OpenID Foundation conformance plan."
    )
    parser.add_argument("--component", choices=("certify", "verify"), required=True)
    parser.add_argument("--target", required=True, help="Base URL of the Inji service")
    parser.add_argument("--out", required=True, help="Path for the results JSON")
    parser.add_argument("--suite-url", default=DEFAULT_SUITE_URL)
    parser.add_argument("--expected-failures", help="JSON list of expected module outcomes")
    parser.add_argument("--timeout-minutes", type=float, default=60)
    return parser.parse_args()


def load_plan(component: str, target: str, suite_url: str) -> dict[str, Any]:
    template_path = Path("configs") / f"{'issuer' if component == 'certify' else 'verifier'}-plan.json.tpl"
    if not template_path.is_file():
        raise RunnerError(f"Plan template not found: {template_path}")

    try:
        template_text = template_path.read_text(encoding="utf-8")
        rendered = template_text.replace("{{TARGET}}", target).replace(
            "{{SUITE_URL}}", suite_url
        )
        plan = json.loads(rendered)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RunnerError(f"Could not load plan template: {template_path}") from error

    if not isinstance(plan, dict):
        raise RunnerError("Plan template must contain a JSON object")
    for key in ("planName", "variant"):
        if not isinstance(plan.get(key), str) or not plan[key]:
            raise RunnerError(f"Plan template is missing a non-empty {key}")
    if "config" not in plan:
        raise RunnerError("Plan template is missing config")
    if not isinstance(plan["config"], dict):
        raise RunnerError("Plan template config must be a JSON object")
    if "_comment" in plan:
        del plan["_comment"]
    if "{{TARGET}}" in json.dumps(plan) or "{{SUITE_URL}}" in json.dumps(plan):
        raise RunnerError("Plan template contains an unresolved URL placeholder")
    return plan


def load_expected_failures(path: str | None) -> dict[str, str]:
    if path is None:
        return {}
    try:
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RunnerError(f"Could not load expected-failures file: {path}") from error
    if not isinstance(entries, list):
        raise RunnerError("Expected-failures file must contain a JSON list")

    expected: dict[str, str] = {}
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("module"), str)
            or not isinstance(entry.get("reason"), str)
        ):
            raise RunnerError(
                "Each expected-failures entry must have string module and reason fields"
            )
        expected[entry["module"]] = entry["reason"]
    return expected


def suite_url(base_url: str, endpoint: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))


def get_json(session: requests.Session, url: str) -> Any:
    last_error: requests.RequestException | None = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.Timeout) as error:
            last_error = error
            if attempt < 2:
                time.sleep(attempt + 1)
        except requests.HTTPError as error:
            raise RunnerError(f"Conformance API GET returned HTTP {error.response.status_code}") from error
        except ValueError as error:
            raise RunnerError("Conformance API returned invalid JSON") from error
    raise RunnerError("Could not connect to the conformance API after 3 attempts") from last_error


def post_json(session: requests.Session, url: str, payload: dict[str, Any]) -> Any:
    try:
        response = session.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as error:
        raise RunnerError(
            f"Conformance API POST returned HTTP {error.response.status_code}"
        ) from error
    except (requests.ConnectionError, requests.Timeout) as error:
        raise RunnerError("Could not connect to the conformance API") from error
    except ValueError as error:
        raise RunnerError("Conformance API returned invalid JSON") from error


def response_id(response: Any, description: str) -> str:
    if isinstance(response, dict):
        value = response.get("id", response.get("planId"))
        if value is not None and str(value):
            return str(value)
    raise RunnerError(f"Conformance API did not return an ID for {description}")


def plan_modules(response: Any) -> list[Any]:
    if not isinstance(response, dict):
        raise RunnerError("Conformance API returned an invalid plan response")
    modules = response.get("modules")
    if modules is None and isinstance(response.get("plan"), dict):
        modules = response["plan"].get("modules")
    if not isinstance(modules, list):
        raise RunnerError("Conformance API plan response did not include a module list")
    return modules


def module_name(module: Any) -> str:
    if isinstance(module, str) and module:
        return module
    if isinstance(module, dict):
        for key in ("name", "module", "test"):
            value = module.get(key)
            if isinstance(value, str) and value:
                return value
    raise RunnerError("Conformance API returned a module without a name")


def result_status(result: Any, terminal_status: str) -> tuple[str, str]:
    if isinstance(result, dict):
        nested_result = result.get("result")
        if isinstance(nested_result, dict):
            result = nested_result

        raw_status = result.get("status") or result.get("outcome") or result.get("result")
        detail = result.get("detail") or result.get("message") or result.get("description")
        if isinstance(raw_status, str):
            normalized = raw_status.strip().upper().replace(" ", "_")
            aliases = {
                "PASS": "PASSED",
                "SUCCESS": "PASSED",
                "FAIL": "FAILED",
                "ERROR": "FAILED",
                "SKIP": "SKIPPED",
            }
            status = aliases.get(normalized, normalized)
            if status in EXPECTED_STATUSES:
                return status, str(detail or "")
        if terminal_status == "INTERRUPTED":
            return "FAILED", str(detail or "Runner was interrupted")
        return "FAILED", str(detail or "Conformance module did not report a recognized result")
    if terminal_status == "INTERRUPTED":
        return "FAILED", "Runner was interrupted"
    return "FAILED", "Conformance API returned an invalid module result"


def run_module(
    session: requests.Session,
    base_url: str,
    plan_id: str,
    name: str,
    deadline: float,
) -> tuple[str, str]:
    runner_response = post_json(
        session,
        suite_url(base_url, "/api/runner"),
        {"plan": plan_id, "module": name},
    )
    runner_id = response_id(runner_response, f"runner for {name}")
    log(f"Started module {name}")

    while True:
        if time.monotonic() >= deadline:
            raise RunnerError(f"Timed out waiting for module {name}")
        info = get_json(session, suite_url(base_url, f"/api/info/{runner_id}"))
        if not isinstance(info, dict) or not isinstance(info.get("status"), str):
            raise RunnerError(f"Conformance API returned invalid status for module {name}")
        state = info["status"].upper()
        if state in ("FINISHED", "INTERRUPTED"):
            break
        time.sleep(min(POLL_INTERVAL_SECONDS, max(0, deadline - time.monotonic())))

    result = info.get("result")
    if result is None:
        result = get_json(session, suite_url(base_url, f"/api/results/{runner_id}"))
    status, detail = result_status(result, state)
    log(f"Completed module {name}: {status}")
    return status, detail


def apply_expected_outcome(
    name: str, status: str, detail: str, expected: dict[str, str]
) -> tuple[str, str]:
    if name not in expected:
        return status, detail
    reason = expected[name]
    if status == "FAILED":
        return "EXPECTED_FAILURE", reason
    if status == "SKIPPED":
        return "EXPECTED_SKIP", reason
    return status, detail


def write_results(path: str, results: dict[str, Any]) -> None:
    output_path = Path(path)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as error:
        raise RunnerError(f"Could not write results file: {path}") from error


def main() -> int:
    args = parse_args()
    if args.timeout_minutes <= 0:
        log("Configuration error: --timeout-minutes must be greater than zero")
        return 2

    try:
        plan = load_plan(args.component, args.target, args.suite_url)
        expected = load_expected_failures(args.expected_failures)
    except RunnerError as error:
        log(f"Configuration error: {error}")
        return 2

    base_url = args.suite_url.rstrip("/")
    session = requests.Session()
    session.verify = False
    session.headers.update({"Accept": "application/json"})

    try:
        plan_response = post_json(
            session,
            suite_url(base_url, "/api/plan"),
            {
                "planName": plan["planName"],
                "variant": plan["variant"],
                "config": plan["config"],
            },
        )
        plan_id = response_id(plan_response, "plan")
        modules = plan_modules(plan_response)
        log(f"Created conformance plan {plan_id} with {len(modules)} modules")

        deadline = time.monotonic() + args.timeout_minutes * 60
        module_results: list[dict[str, str]] = []
        for module in modules:
            name = module_name(module)
            status, detail = run_module(
                session, base_url, plan_id, name, deadline
            )
            status, detail = apply_expected_outcome(name, status, detail, expected)
            module_results.append({"name": name, "status": status, "detail": detail})

        summary = {
            "passed": sum(item["status"] == "PASSED" for item in module_results),
            "failed": sum(item["status"] == "FAILED" for item in module_results),
            "skipped": sum(
                item["status"] in ("SKIPPED", "EXPECTED_SKIP") for item in module_results
            ),
            "warning": sum(item["status"] == "WARNING" for item in module_results),
        }
        output = {
            "component": args.component,
            "planId": plan_id,
            "summary": summary,
            "modules": module_results,
        }
        write_results(args.out, output)
    except RunnerError as error:
        log(f"Conformance run error: {error}")
        return 2
    finally:
        session.close()

    log(
        "Summary: "
        f"passed={summary['passed']} failed={summary['failed']} "
        f"skipped={summary['skipped']} warning={summary['warning']}"
    )
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
