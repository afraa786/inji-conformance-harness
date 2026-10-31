"""Record a clean browser viewport showing real local validation subprocesses.

Requires the already-installed Playwright browser/recorder and imageio-ffmpeg.
No chat/desktop windows are captured. Raw suite evidence is retained separately;
only redacted subprocess output and public reports enter the recording.
"""
from datetime import datetime, timezone
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.capture_diagnostics import redact
from runner.render_plans import read_env

EVIDENCE = ROOT / "artifacts/demo/evidence"
STATE = dict(stage="Project and architecture", command="", lines=[], outcomes=[], summary={}, busy=False)
LOCK = threading.Lock()
LEDGER = EVIDENCE / "demo-commands.json"

PAGE = r'''<!doctype html><html><head><meta charset="utf-8"><title>Inji Conformance Validation</title>
<style>body{margin:0;background:#101923;color:#e4edf6;font:16px Segoe UI,Arial}header{padding:22px 32px;background:#182b3a}h1{margin:0 0 8px;font-size:27px}small{color:#afd0e4}.grid{display:grid;grid-template-columns:1fr 310px;gap:20px;padding:22px 32px}h2{font-size:21px;margin:0 0 12px}#terminal{background:#060c12;border:1px solid #37546a;padding:16px;white-space:pre-wrap;overflow:auto;height:410px;font:14px Consolas,monospace;line-height:1.5}#command{color:#7dd9c6;font:14px Consolas;overflow-wrap:anywhere;margin-bottom:10px}aside{line-height:1.65}li{margin-bottom:8px}#outcomes{font:14px Consolas}#summary{white-space:pre-wrap;font:14px Consolas}iframe{display:none;width:100%;height:575px;background:white;border:0}footer{padding:0 32px;color:#b4c7d7;font-size:14px}</style></head>
<body><header><h1>Inji Conformance Harness — real validation</h1><small>Python REST driver → OpenID suite → Certify / Verify · Java TestNG → Extent · Local alpha releases</small></header>
<div class="grid"><main><h2 id="stage"></h2><div id="command"></div><pre id="terminal"></pre><iframe id="report"></iframe></main><aside>
<b>Architecture</b><p>CA-verified HTTPS gateway<br>Certify → PostgreSQL<br>Verify → PostgreSQL<br>OpenID suite → MongoDB</p>
<b>Project files</b><p>docker-compose.yml<br>runner/conformance_runner.py<br>runner/handoff_certify.py<br>runner/handoff_verify.py<br>testrig-bridge/<br>.github/workflows/</p>
<b>Actual command outcomes</b><div id="outcomes"></div><pre id="summary"></pre></aside></div>
<footer>Recorded browser viewport only. Output is from actual subprocesses. Nonzero conformance exits remain failures. Unit tests, WARNING and SKIPPED are not conformance passes.</footer>
<script>async function poll(){let s=await(await fetch('/state')).json();document.getElementById('stage').textContent=s.stage;document.getElementById('command').textContent=s.command;let t=document.getElementById('terminal');t.textContent=s.lines.slice(-20).join('\n');t.scrollTop=t.scrollHeight;document.getElementById('outcomes').textContent=s.outcomes.map(x=>x.name+': exit '+x.exitCode).join(' | ');document.getElementById('summary').textContent=JSON.stringify(s.summary,null,2)}setInterval(poll,400);poll();
function report(path){document.getElementById('terminal').style.display='none';let f=document.getElementById('report');f.style.display='block';f.src=path}</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == "/":
            payload, content_type = PAGE.encode(), "text/html; charset=utf-8"
        elif self.path == "/state":
            with LOCK:
                payload = json.dumps(STATE).encode()
            content_type = "application/json"
        elif self.path.startswith("/reports/"):
            path = (EVIDENCE / self.path[len("/reports/"):].split("?")[0]).resolve()
            if EVIDENCE.resolve() not in path.parents or path.suffix not in {".html", ".css", ".js", ".png", ".gif"} or not path.is_file():
                self.send_error(404)
                return
            import mimetypes
            payload, content_type = path.read_bytes(), mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run(name, command, env):
    with LOCK:
        STATE.update(stage=name, command=subprocess.list2cmdline(command), lines=[], busy=True)
    started = datetime.now(timezone.utc).isoformat()
    with (EVIDENCE / (name + ".log")).open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in process.stdout:
            safe = redact(line).rstrip()
            log.write(safe + "\n")
            log.flush()
            with LOCK:
                STATE["lines"].append(safe)
        code = process.wait()
    outcome = dict(name=name, command=command, exitCode=code, startedAt=started,
                   finishedAt=datetime.now(timezone.utc).isoformat())
    with LOCK:
        STATE["outcomes"].append(outcome)
        STATE["lines"].append("ACTUAL PROCESS EXIT: " + str(code))
        STATE["busy"] = False
    LEDGER.write_text(json.dumps(STATE["outcomes"], indent=2) + "\n")
    print(name + ": exit " + str(code), flush=True)
    return code


def main():
    global LEDGER
    from playwright.sync_api import sync_playwright
    import imageio_ffmpeg
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-only", action="store_true")
    parser.add_argument("--video-output", default="artifacts/demo/inji-conformance-working-demo.mp4")
    parser.add_argument("--report-suffix", default="-testng-recovery")
    parser.add_argument("--build-directory", default="local/final-validation/bridge-target-v2")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ledger", default="demo-commands.json")
    args = parser.parse_args()
    LEDGER = EVIDENCE / args.ledger
    read_env()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    video_path = ROOT / args.video_output
    if video_path.exists():
        raise ValueError("Preserve existing demo; choose a new output before rerunning")
    if args.reports_only:
        STATE["stage"] = "Java reporting recovery — first attempts retained"
        STATE["outcomes"] = json.loads((EVIDENCE / "demo-commands.json").read_text())
        previous = json.loads((EVIDENCE / "combined/results-combined.json").read_text())
        STATE["summary"] = {"combined": previous["summary"]}
    env = dict(os.environ, DOCKER_CONTEXT="desktop-linux", COMPOSE_PROJECT_NAME="inji-final-validation",
               COMPOSE_FILE=str(ROOT / "docker-compose.yml") + os.pathsep + str(ROOT / "docker-compose.validation.yml"),
               COMPOSE_PATH_SEPARATOR=os.pathsep, WAITING_TIMEOUT_SECONDS="10",
               PYTHONPATH=str(ROOT / ".local-deps"), PYTHON=sys.executable)
    bash = "C:/Program Files/Git/bin/bash.exe"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, executable_path="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
        context = browser.new_context(viewport=dict(width=1440, height=900),
                                      record_video_dir=str(ROOT / "artifacts/demo/recording"),
                                      record_video_size=dict(width=1440, height=900))
        page = context.new_page()
        page.goto("http://127.0.0.1:" + str(args.port))
        video = page.video
        page.wait_for_timeout(7000)

        def execute(name, command):
            worker = threading.Thread(target=run, args=(name, command, env))
            worker.start()
            while worker.is_alive():
                page.wait_for_timeout(500)
            worker.join()
            page.wait_for_timeout(2500)

        if args.reports_only:
            inspection = (
                "from pathlib import Path; "
                "print('ACTUAL PROJECT FILES'); "
                "[print(str(p)) for p in sorted(Path('runner').glob('*.py'))]; "
                "print('ACTUAL COMPOSE SERVICE / IMAGE CONFIGURATION'); "
                "[print(line) for line in Path('docker-compose.yml').read_text().splitlines() "
                "if line.startswith('  ') and (line.strip().endswith(':') and len(line)-len(line.lstrip())==2 "
                "or line.strip().startswith('image:'))]; "
                "print('Derived Certify override:'); "
                "print(Path('docker-compose.validation.yml').read_text()); "
                "print('Status comparison is a regression benchmark, not a performance benchmark.')")
            execute("project-inspection" + args.report_suffix, [sys.executable, "-c", inspection])
        if not args.reports_only:
            execute("deployment-health", ["docker", "compose", "up", "-d", "--no-recreate", "--pull", "never", "--wait", "--wait-timeout", "120"])
            execute("docker-services", ["docker", "compose", "ps", "-a"])
            execute("gateway-metadata", [sys.executable, "tools/final_validation_probe.py", "--out", "artifacts/demo/evidence/endpoint-probes-recorded.json"])
        for component in (() if args.reports_only else ("certify", "verify", "combined")):
            args = ["--combined"] if component == "combined" else ["--component", component]
            execute(component, [bash, "run-full-stack-conformance.sh"] + args + ["--no-up"])
            snapshot = EVIDENCE / component
            snapshot.mkdir(exist_ok=True)
            for path in (ROOT / "results").glob("*.*"):
                if path.suffix in {".json", ".md", ".txt"}:
                    shutil.copy2(path, snapshot / path.name)
            for result in snapshot.glob("results-*.json"):
                data = json.loads(result.read_text())
                if component != "combined" and data["component"] != component:
                    continue
                with LOCK:
                    STATE["summary"][data["component"]] = data.get("summary", {})
        for component in ("certify", "verify"):
            package = "injicertify" if component == "certify" else "injiverify"
            report_name = component + (args.report_suffix if args.reports_only else "-testng")
            reports = EVIDENCE / report_name
            command = ["mvn.cmd", "-q", "-o", "-f", "testrig-bridge/pom.xml",
                       "-Dmaven.repo.local=" + str(ROOT / "local/m2"), "test",
                       "-Dconformance.buildDirectory=" + str(ROOT / args.build_directory),
                       "-Dtest=io.inji.testrig.apirig." + package + ".testscripts.OpenIDConformanceTest",
                       "-Dconformance.root=" + str(ROOT), "-Denv.endpoint=" + ("https://certify.test:8446" if component == "certify" else "https://verify.test:8447/v1/verify"),
                       "-Dconformance.results=" + str(reports / ("results-" + component + ".json")),
                       "-Dconformance.reportsDirectory=" + str(reports), "-Dconformance.waitingTimeoutSeconds=10"]
            execute(report_name, command)
        if args.reports_only:
            previous = sorted((ROOT / "results/previous").glob("*/results-combined.json"))
            if previous:
                execute("benchmark-status-comparison" + args.report_suffix,
                        [sys.executable, "runner/diff_results.py", str(previous[-1]), "results/results-combined.json"])
            execute("evidence-index" + args.report_suffix, [sys.executable, "-c",
                    "from pathlib import Path; [print(str(p)) for p in Path('artifacts/demo/evidence').glob('*testng*/*') if p.is_file()]"])
        for component in ("certify", "verify"):
            with LOCK:
                STATE["stage"] = component.capitalize() + " — actual Extent report"
                STATE["command"] = "Generated by the real TestNG listener from actual module outcomes"
            suffix = args.report_suffix if args.reports_only else "-testng"
            page.evaluate("report", "/reports/" + component + suffix + "/conformance-extent.html")
            page.wait_for_timeout(10000)
            page.evaluate("window.scrollTo(0,180)")
            page.wait_for_timeout(4000)
        page.reload()
        with LOCK:
            STATE.update(stage="Final status — deployed, conformance remains failing", command="See raw evidence and final-validation-report.md",
                         lines=["Metadata fallback: verified through real gateway with CA validation.",
                                "Native AS: conventional authorization_endpoint absent; IAR is a different protocol.",
                                "Verify: actual backend responses saved; suite failures/review remain visible.",
                                "CI: latest remote run failed pulling the pinned suite image.",
                                "Benchmark: status regression comparison; no performance benchmark.",
                                "No test result was fabricated or weakened."])
        page.wait_for_timeout(12000)
        context.close()
        source_video = video.path()
        browser.close()
    server.shutdown()
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-n", "-i", str(source_video),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(video_path)], check=True,
                   stdout=subprocess.DEVNULL, stderr=(EVIDENCE / "video-conversion.log").open("w"))
    print("Saved actual browser recording: " + str(video_path), flush=True)


if __name__ == "__main__":
    main()
