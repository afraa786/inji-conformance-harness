#!/usr/bin/env python3
"""Drive OIDF plans. Exit 0: expected; 1: test failure; 2: configuration/API failure."""
from __future__ import annotations
import argparse
import io
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit, urlunsplit, quote
import zipfile
import requests

try:
    from .render_plans import render_plan, read_env
    from .common import RunnerError, HandoffFailure
except ImportError:
    from render_plans import render_plan, read_env
    from common import RunnerError, HandoffFailure

FAILURES = {"FAILED", "INTERRUPTED"}
STATUSES = {"PASSED", "FAILED", "WARNING", "SKIPPED", "INTERRUPTED", "REVIEW", "EXPECTED_FAILURE", "EXPECTED_SKIP"}


def write_results(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_report(path, output):
    report = Path(path).with_name("report-" + output["component"] + ".md")
    lines = ["# " + output["component"].capitalize() + " conformance", "",
             "Runner exit: " + str(output["exitCode"]), "", "| Module | Status | Seconds |", "| --- | --- | --- |"]
    if output.get("selectedModules"):
        lines[3:3] = ["Diagnostic subset: " + str(len(output["modules"])) + "/" +
                      str(output["planModuleCount"]) + " planned modules; not a complete plan run.", ""]
    for module in output["modules"]:
        lines.append("| " + module["name"].replace("|", "\\|") + " | " + module["status"] + " | " + str(module.get("duration", 0)) + " |")
    if output["errors"]:
        lines += ["", "Infrastructure errors:", ""] + ["- " + message for message in output["errors"]]
    lines += ["", "REVIEW/SKIPPED do not establish conformance. See JSON and private evidence logs for details."]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_expected_failures(path):
    if not path:
        return {}
    try:
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            raise ValueError()
        result = {}
        for entry in entries:
            if not isinstance(entry, dict) or any(not isinstance(entry.get(k), str) or not entry[k].strip()
                                                  for k in ("module", "reason")):
                raise ValueError()
            if entry["module"] in result:
                raise ValueError()
            result[entry["module"]] = entry["reason"]
        return result
    except (OSError, ValueError, TypeError) as error:
        raise RunnerError("Expected-failures must contain unique module/reason objects") from error


class SuiteAPI:
    """Keep suite bearer token and TLS bypass on the configured suite origin only."""
    def __init__(self, base_url, deadline):
        self.base = base_url.rstrip("/")
        parsed = urlsplit(self.base)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
            raise RunnerError("Invalid suite URL")
        self.origin = (parsed.scheme, parsed.netloc)
        public = urlsplit(os.environ.get("SUITE_PUBLIC_URL", "https://localhost.emobix.co.uk:8443"))
        self.public_origin = (public.scheme, public.netloc)
        self.deadline = deadline
        self.session = requests.Session()
        # Local self-signed suite only: .env.example exposes this development flag.
        # All Inji requests use separate sessions with normal TLS verification.
        flag = os.environ.get("OIDC_SUITE_INSECURE", "false").lower()
        if flag not in {"true", "false"}:
            raise RunnerError("OIDC_SUITE_INSECURE must be true or false")
        self.session.verify = flag != "true"
        # conformance.py sends this even for a bodyless create-from-plan POST.
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        if os.environ.get("OIDC_SUITE_TOKEN"):
            self.session.headers["Authorization"] = "Bearer " + os.environ["OIDC_SUITE_TOKEN"]

    def local_url(self, path):
        parsed = urlsplit(path)
        if parsed.netloc:
            if (parsed.scheme, parsed.netloc) not in {self.origin, self.public_origin}:
                raise RunnerError("Refusing suite credentials/TLS bypass for another origin")
            return self.base + urlunsplit(("", "", parsed.path, parsed.query, ""))
        if not path.startswith("/") or path.startswith("//"):
            raise RunnerError("Invalid suite endpoint")
        return self.base + path

    def request(self, method, path, *, expected=200, decode=True, retry_safe=None, **kwargs):
        url = self.local_url(path)
        for attempt in range(3):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise RunnerError("Global/module API deadline exceeded")
            try:
                response = self.session.request(method, url, timeout=min(30, remaining),
                                                allow_redirects=False, **kwargs)
                if response.status_code != expected:
                    raise RunnerError(f"Suite {method} returned HTTP {response.status_code}")
                if not decode:
                    return response
                value = response.json()
                if not isinstance(value, (dict, list)):
                    raise RunnerError("Suite returned an invalid JSON structure")
                return value
            except requests.exceptions.SSLError as error:
                raise RunnerError("Suite TLS validation failed; check CA or OIDC_SUITE_INSECURE") from error
            except (requests.ConnectionError, requests.Timeout) as error:
                if retry_safe is False or method.upper() not in {"GET", "HEAD", "OPTIONS"}:
                    raise RunnerError("Suite action response lost; outcome unknown, not retried to avoid duplicate execution") from error
                if attempt == 2:
                    raise RunnerError("Suite connection failed after 3 attempts") from error
                time.sleep(min(2 ** attempt, max(0, self.deadline - time.monotonic())))
            except (ValueError, requests.RequestException) as error:
                raise RunnerError("Invalid suite response/request") from error


def module_name(module):
    name = module if isinstance(module, str) else module.get("testModule") if isinstance(module, dict) else None
    if not isinstance(name, str) or not name:
        raise RunnerError("Suite module is missing testModule")
    return name


def result_status(info):
    if info.get("status") == "INTERRUPTED":
        return "INTERRUPTED", "Suite interrupted this module"
    raw = info.get("result")
    if isinstance(raw, dict):
        raw = raw.get("result", raw.get("status"))
    status = str(raw).upper()
    status = {"PASS": "PASSED", "FAILURE": "FAILED", "FAIL": "FAILED", "SKIP": "SKIPPED"}.get(status, status)
    if status not in STATUSES - {"EXPECTED_FAILURE", "EXPECTED_SKIP"}:
        return "FAILED", "Suite did not provide a recognized terminal result"
    return status, "Suite terminal result: " + status


def apply_expected_outcome(name, status, detail, expected):
    if name in expected:
        if status in FAILURES:
            return "EXPECTED_FAILURE", "Expected failure: " + expected[name]
        if status == "SKIPPED":
            return "EXPECTED_SKIP", expected[name]
        if status == "PASSED":
            detail += "; unexpectedly passing, remove from expected-failures list"
    return status, detail


def run_module(api, plan_id, module, handoff, args, output_dir):
    name, start = module_name(module), time.monotonic()
    global_deadline = api.deadline
    api.deadline = min(global_deadline, start + args.module_timeout_seconds)
    record = dict(name=name, status="FAILED", detail="Module did not complete", logUrl="", duration=0,
                  variant=module.get("variant", {}) if isinstance(module, dict) else {})
    rid, context, failure, timed_out = None, {"moduleName": name}, None, False
    last_state = "CREATED"
    try:
        params = {"test": name, "plan": plan_id}
        if record["variant"]:
            params["variant"] = json.dumps(record["variant"])
        created = api.request("POST", "/api/runner", params=params, expected=201)
        runner_id = created.get("id") if isinstance(created, dict) else None
        if not isinstance(runner_id, str) or not runner_id:
            raise RunnerError("Suite did not return a runner ID")
        rid = quote(runner_id, safe="")
        record["testId"] = runner_id
        record["logUrl"] = api.base + "/log-detail.html?log=" + rid
        waiting_since, last_state, started = None, "CREATED", False
        handoff.deadline = api.deadline
        while True:
            if time.monotonic() >= api.deadline:
                record["detail"] = "Module/global timeout; last state: " + str(last_state)
                timed_out = True
                break
            info = api.request("GET", "/api/info/" + rid)
            if not isinstance(info, dict) or not isinstance(info.get("status"), str):
                raise RunnerError("Suite returned invalid module status")
            last_state = info.get("status")
            # Configuration happens asynchronously; CONFIGURED may arrive on a later poll.
            if last_state == "CONFIGURED" and not started:
                api.request("POST", "/api/runner/" + rid)
                started = True
            if last_state in {"FINISHED", "INTERRUPTED"}:
                record["status"], record["detail"] = result_status(info)
                handoff.finish(context, name)
                break
            if last_state == "WAITING":
                waiting_since = waiting_since if waiting_since is not None else time.monotonic()
                if time.monotonic() - waiting_since >= args.waiting_timeout_seconds:
                    record["detail"] = ("WAITING timeout: suite requires screenshot review; actual Verify result is saved"
                                        if context.get("pendingEvidence") and context.get("verification") else
                                        "WAITING timeout: browser/wallet action was not completed")
                    timed_out = True
                    break
                # /api/info is persisted; live browser/exposed values come from /api/runner.
                live = api.request("GET", "/api/runner/" + rid)
                if not isinstance(live, dict):
                    raise RunnerError("Suite returned invalid live runner information")
                browser = live.get("browser", {})
                if not isinstance(browser, dict):
                    raise RunnerError("Suite returned invalid browser interaction state")
                context["pendingEvidence"] = bool(browser.get("uploadsRequired", 0))
                if handoff.drive(api, live, context):
                    waiting_since = time.monotonic()
            else:
                waiting_since = None
                context.pop("offer_sent", None)
            time.sleep(min(args.poll_interval, max(0, api.deadline - time.monotonic())))
    except HandoffFailure as error:
        record["status"], record["detail"] = "FAILED", str(error)
        timed_out = last_state not in {"FINISHED", "INTERRUPTED"}
    except RunnerError as error:
        failure = error
        record.update(status="FAILED", detail=str(error), infrastructureError=True)
        timed_out = last_state not in {"FINISHED", "INTERRUPTED"}
    finally:
        api.deadline = global_deadline
        record["duration"] = round(time.monotonic() - start, 3)
    if context.get("verifyOutcome"):
        record["verifyOutcome"] = context["verifyOutcome"]
        record["pendingEvidence"] = context.get("pendingEvidence", False)
    if context.get("verification") and rid:
        write_results(output_dir / (rid + "-verify-result.json"), context["verification"])
    try:
        if rid:
            if timed_out:
                # Stop abandoned tests before reusing the same alias for another module.
                api.request("DELETE", "/api/runner/" + rid)
            evidence = api.request("GET", "/api/log/" + rid)
            write_results(output_dir / (rid + "-log.json"), evidence)
    except RunnerError as error:
        failure = failure or error
        record["infrastructureError"] = True
    if failure:
        failure.record = record
        raise failure
    return record


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=("certify", "verify"), required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--suite-url", help="Defaults to SUITE_URL or https://localhost:8443")
    parser.add_argument("--plan", help="Rendered JSON; otherwise render from environment")
    parser.add_argument("--expected-failures")
    parser.add_argument("--module", action="append", help="Run only this exact module name; repeatable diagnostic subset")
    parser.add_argument("--timeout-minutes", type=float, default=60)
    parser.add_argument("--module-timeout-seconds", type=float, default=600)
    parser.add_argument("--waiting-timeout-seconds", type=float, default=120)
    parser.add_argument("--poll-interval", type=float, default=3)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    from datetime import datetime, timezone
    import uuid
    output = dict(component=args.component, planId=None, modules=[], summary={}, errors=[],
                  runId=str(uuid.uuid4()), startedAt=datetime.now(timezone.utc).isoformat())
    api, exit_code = None, 2
    try:
        read_env()
        args.suite_url = args.suite_url or os.environ.get("SUITE_URL", "https://localhost:8443")
        if any(not math.isfinite(v) or v <= 0 for v in (args.timeout_minutes, args.module_timeout_seconds,
                                                       args.waiting_timeout_seconds, args.poll_interval)):
            raise RunnerError("Timeouts/poll interval must be positive finite numbers")
        plan = (json.loads(Path(args.plan).read_text(encoding="utf-8")) if args.plan else
                render_plan(args.component, args.target, args.suite_url))
        if (not isinstance(plan, dict) or not isinstance(plan.get("planName"), str) or not plan["planName"]
                or not isinstance(plan.get("variant"), dict) or not isinstance(plan.get("config"), dict)):
            raise RunnerError("Rendered plan requires variant/config objects")
        if "{{" in json.dumps(plan):
            raise RunnerError("Unresolved plan placeholders")
        expected = load_expected_failures(args.expected_failures)
        try:
            from .handoff_certify import CertifyHandoff
            from .handoff_verify import VerifyHandoff
        except ImportError:
            from handoff_certify import CertifyHandoff
            from handoff_verify import VerifyHandoff
        handoff = (CertifyHandoff if args.component == "certify" else VerifyHandoff)(args.target, plan)
        api = SuiteAPI(args.suite_url, time.monotonic() + args.timeout_minutes * 60)
        created = api.request("POST", "/api/plan", expected=201,
                              params={"planName": plan["planName"], "variant": json.dumps(plan["variant"])},
                              json=plan["config"])
        plan_id = created.get("id") if isinstance(created, dict) else None
        if not isinstance(plan_id, str) or not plan_id:
            raise RunnerError("Suite did not return a plan ID")
        output["planId"] = plan_id
        plan_info = api.request("GET", "/api/plan/" + quote(plan_id, safe=""))
        if not isinstance(plan_info, dict):
            raise RunnerError("Suite returned invalid plan information")
        modules = plan_info.get("modules", created.get("modules"))
        if not isinstance(modules, list) or not modules:
            raise RunnerError("Suite plan has no modules")
        output["planModuleCount"] = len(modules)
        output["selectedModules"] = args.module
        if args.module:
            requested = set(args.module)
            if requested - {module_name(module) for module in modules}:
                raise RunnerError("Requested diagnostic module is not in the suite plan")
            modules = [module for module in modules if module_name(module) in requested]
        evidence_dir = Path(args.out).parent / (args.component + "-evidence") / quote(plan_id, safe="")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        output["evidenceDirectory"] = str(evidence_dir)
        for module in modules:
            try:
                record = run_module(api, plan_id, module, handoff, args, evidence_dir)
            except RunnerError as error:
                output["modules"].append(getattr(error, "record", dict(
                    name=module_name(module), status="FAILED", detail=str(error),
                    logUrl="", duration=0, infrastructureError=True)))
                raise
            record["status"], record["detail"] = apply_expected_outcome(record["name"], record["status"], record["detail"], expected)
            output["modules"].append(record)
            print(f"{args.component}: {record['name']}: {record['status']}", flush=True)
        exported = api.request("GET", "/api/plan/export/" + quote(plan_id, safe=""), decode=False,
                               headers={"Accept": "application/zip"})
        try:
            with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                if not archive.namelist() or archive.testzip():
                    raise ValueError()
        except (zipfile.BadZipFile, ValueError) as error:
            raise RunnerError("Suite export was not a valid ZIP") from error
        (evidence_dir / "plan-export.zip").write_bytes(exported.content)
        exit_code = int(any(m["status"] in FAILURES for m in output["modules"]))
    except (RunnerError, OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, RunnerError) else "Invalid or missing configuration/results"
        output["errors"].append(message)
        print("Conformance error: " + message, file=sys.stderr)
        exit_code = 2
    finally:
        output["finishedAt"] = datetime.now(timezone.utc).isoformat()
        if api:
            api.session.close()
        output["summary"] = {s.lower(): sum(m["status"] == s for m in output["modules"]) for s in sorted(STATUSES)}
        output["exitCode"] = exit_code
        try:
            write_results(args.out, output)
            write_report(args.out, output)
        except OSError:
            print("Could not write results", file=sys.stderr)
            exit_code = 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
