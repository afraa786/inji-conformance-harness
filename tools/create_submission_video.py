"""Audit safely and record a narrated, evidence-labelled browser demonstration.

Uses installed Edge, Playwright, Windows SAPI and imageio-ffmpeg. Does not install,
deploy, stop services, edit private configuration, or replace an existing video.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import wave
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.capture_diagnostics import redact
from runner.render_plans import read_env


def safe(value):
    value = redact(value).replace(str(ROOT), '.').replace(ROOT.as_posix(), '.')
    return re.sub(r'C:[\\/]Users[\\/][^\\/\s]+', '[user]', value, flags=re.I)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', default='artifacts/demo/evidence/final-submission-20261102')
    parser.add_argument('--port', type=int, default=8776)
    parser.add_argument('--resume-audit', action='store_true', help='Reuse retained checks after a recording-tool correction; never replace a video')
    args = parser.parse_args()
    output = ROOT / 'artifacts/demo/Final Submission Video.mp4'
    work = ROOT / args.work
    if output.exists() or (work.exists() and not args.resume_audit):
        raise ValueError('Preserve previous outputs: choose an unused work path and retain the existing final video')
    work.mkdir(parents=True, exist_ok=args.resume_audit)
    read_env()
    env = dict(os.environ, PYTHONPATH=str(ROOT / '.local-deps') + os.pathsep + str(ROOT))
    ledger = json.loads((work/'commands.json').read_text()) if args.resume_audit else []

    def execute(name, command, timeout=240):
        if args.resume_audit and any(item['name']==name for item in ledger):
            return next(item['exitCode'] for item in ledger if item['name']==name)
        started = datetime.now(timezone.utc).isoformat()
        try:
            p = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                               encoding='utf-8', errors='replace', timeout=timeout)
            code, text = p.returncode, safe(p.stdout + p.stderr)
        except (OSError, subprocess.TimeoutExpired) as error:
            code, text = None, type(error).__name__ + ': check unavailable or timed out; no success inferred'
        (work / (name + '.log')).write_text(text, encoding='utf-8')
        ledger.append(dict(name=name, command=command, exitCode=code, startedAt=started,
                           finishedAt=datetime.now(timezone.utc).isoformat()))
        (work / 'commands.json').write_text(json.dumps(ledger, indent=2), encoding='utf-8')
        print(name + ': exit ' + str(code), flush=True)
        return code

    execute('git-branch', ['git', 'branch', '--show-current'])
    execute('git-status-before', ['git', 'status', '--short'])
    execute('docker-current', ['docker', '--context', 'desktop-linux', 'info', '--format', '{{.ServerVersion}}'], 25)
    docker_text = (work/'docker-current.log').read_text()
    docker_ok = bool(ledger[-1]['exitCode'] == 0 and re.fullmatch(r'\s*\d+\.\d+\.\d+[^\r\n]*\s*', docker_text))
    if docker_ok:
        execute('docker-services-current', ['docker', '--context', 'desktop-linux', 'ps', '--format', '{{.Names}} {{.Status}}'])
    execute('compose-base', ['docker', '--context', 'desktop-linux', 'compose', '-f', 'docker-compose.yml', 'config', '--quiet'])
    execute('compose-native', ['docker', '--context', 'desktop-linux', 'compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.native-fixes.yml', 'config', '--quiet'])
    execute('bash-syntax', ['C:/Program Files/Git/bin/bash.exe', '-n', 'run-full-stack-conformance.sh'])
    execute('config-validation', [sys.executable, '-c',
            "from runner.benchmarks import load_policy,DEFAULT_CONFIG; from runner.render_plans import read_env,render_plan; "
            "read_env(); load_policy(DEFAULT_CONFIG); "
            "[render_plan(c,t,'https://suite.test:8443') for c,t in [('certify','https://certify.test:8446'),('verify','https://verify.test:8447/v1/verify')]]; "
            "print('Both plan templates render; benchmark policy validates. Private values omitted.')"])
    execute('regression-current', [sys.executable, '-m', 'pytest', 'runner/tests', '-q',
            '--basetemp=local/submission-pytest-' + str(int(time.time())), '--junitxml=' + str(work / 'unit-tests.xml')])
    execute('java-compile-current', ['mvn.cmd', '-q', '-o', '-f', 'testrig-bridge/pom.xml',
            '-Dmaven.repo.local=' + str(ROOT / 'local/m2'),
            '-Dconformance.buildDirectory=' + str(ROOT / ('local/submission-bridge-' + str(int(time.time())))), 'test-compile'])
    execute('git-diff-check', ['git', 'diff', '--check'])
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    private_tracked = [p for p in tracked if p == '.env' or p.startswith(('.local-deps/', 'local/'))]
    required = ['runner/conformance_runner.py', 'runner/handoff_certify.py', 'runner/handoff_verify.py',
                'runner/benchmarks.py', 'runner/merge_results.py', 'configs/issuer-plan.json.tpl',
                'configs/verifier-plan.json.tpl', 'testrig-bridge/pom.xml', 'docs/architecture.md']
    inventory = dict(privatePathsTracked=private_tracked,
                     missingRequiredFiles=[p for p in required if not (ROOT / p).is_file()],
                     pitchFilesInRepository=[p for p in tracked if p.lower().endswith(('.pptx', '.odp', '.key'))],
                     scope='Tracked-path review; not a claim of exhaustive secret detection')
    (work / 'inventory.json').write_text(json.dumps(inventory, indent=2))

    unit = ET.parse(work / 'unit-tests.xml').getroot().find('testsuite')
    ua = unit.attrib
    counts = {k: int(ua[k]) for k in ('tests', 'failures', 'errors', 'skipped')}
    passed = counts['tests'] - counts['failures'] - counts['errors'] - counts['skipped']
    unit_text = '{} passed, {} failed, {} errors, {} skipped'.format(passed, counts['failures'], counts['errors'], counts['skipped'])
    historical = ROOT / 'artifacts/demo/evidence/blocker-resolution'
    runs = {c: json.loads((historical / 'demo' / c / ('results-' + c + '.json')).read_text())
            for c in ('certify', 'verify', 'combined')}
    budget = json.loads((historical / 'benchmark-live-proof/results-verify.json').read_text())
    budget_xml = ET.parse(next((historical / 'benchmark-java-proof').glob('TEST-*.xml'))).getroot().attrib
    facts = dict(regression=counts, regressionPassed=passed, dockerOperational=docker_ok,
                 historicalDate='2026-10-31', historicalRuns={c:d['summary'] for c,d in runs.items()},
                 historicalExits={c:d['exitCode'] for c,d in runs.items()},
                 benchmark=dict(conformanceExitCode=budget['conformanceExitCode'],
                                benchmark=budget['benchmark'], exitCode=budget['exitCode']),
                 benchmarkTestNG={k:budget_xml[k] for k in ('tests','failures','errors','skipped')})
    (work / 'facts.json').write_text(json.dumps(facts, indent=2))
    if docker_ok:
        raise RuntimeError('Docker is operational: reassess live execution before using the blocked-infrastructure recording path')

    def source(path, start=0, limit=70):
        return '\n'.join('{:3}  {}'.format(i+1, line) for i,line in enumerate(
            (ROOT/path).read_text(encoding='utf-8').splitlines()) if start <= i < start+limit)

    views = {
      'intro': {'title':'Inji Conformance Harness', 'label':'MOSIP DEC{}DE · engineering demonstration',
                'kind':'intro', 'content':'Repeatable protocol testing. Traceable evidence. Honest outcomes.'},
      'architecture': {'title':'One harness, two Inji services', 'label':'Actual layout · docs/architecture.md', 'kind':'architecture'},
      'implementation': {'title':'Implementation in the repository', 'label':'Actual source · runner/conformance_runner.py', 'kind':'code',
                         'content':source('runner/conformance_runner.py', 180, 60)},
      'java-source': {'title':'Java bridge and result mapping', 'label':'Actual source · testrig-bridge/verify/OpenIDConformanceTest.java', 'kind':'code',
                      'content': '\n'.join((ROOT/'testrig-bridge/verify/OpenIDConformanceTest.java').read_text().splitlines()[-53:])},
      'docker': {'title':'Current Docker environment', 'label':'CURRENT CHECK · 2026-11-02 · no deployment attempted', 'kind':'terminal',
                 'content':'> docker --context desktop-linux info --format "{{.ServerVersion}}"\n\n' + (work/'docker-current.log').read_text() + '\nLinux engine unavailable. Previous service health is historical evidence.'},
      'execution': {'title':'Certify, Verify and combined execution', 'label':'RETAINED EXECUTION · 2026-10-31 · not a new run', 'kind':'terminal',
                    'content':'\n'.join('> bash run-full-stack-conformance.sh ' + ('--combined' if c=='combined' else '--component '+c) + ' --no-up\n' +
                       (historical/'demo'/(c+'.log')).read_text(encoding='utf-8')[-4500:] + '\n' for c in ('certify','verify','combined'))},
      'certify-report': {'title':'Certify: interruptions stay visible', 'label':'RETAINED REPORT · 2026-10-31 · actual Extent listener output', 'kind':'report', 'report':'certify'},
      'verify-report': {'title':'Verify: five passes, seven evidence failures', 'label':'RETAINED REPORT · 2026-10-31 · actual Extent listener output', 'kind':'report', 'report':'verify'},
      'validation': {'title':'Fresh harness regressions', 'label':'CURRENT CHECK · 2026-11-02 · unit tests are not conformance passes', 'kind':'terminal',
                     'content':'> python -m pytest runner/tests -q --junitxml=<isolated evidence>/unit-tests.xml\n\n' + (work/'regression-current.log').read_text() + '\nSUMMARY: '+unit_text},
      'benchmark': {'title':'A passing module can still breach its budget', 'label':'RETAINED LIVE GATE EVIDENCE · synthetic zero-second limit · 2026-10-31', 'kind':'terminal',
                    'content':json.dumps({'module':budget['modules'][0]['name'],'protocolStatus':budget['modules'][0]['status'],
                                         'conformanceExitCode':budget['conformanceExitCode'],'benchmark':budget['benchmark'],
                                         'processExitCode':budget['exitCode'],'TestNG':facts['benchmarkTestNG']},indent=2) +
                               '\n\n' + '\n'.join(line for line in (historical/'benchmark-java-proof/maven.log').read_text().splitlines() if 'Tests run:' in line)},
      'scope': {'title':'Challenges and next milestones', 'label':'CURRENT ASSESSMENT · docs/external-as-assessment.md', 'kind':'scope'},
      'conclusion': {'title':'Evidence before acceptance', 'label':'A useful prototype · full protocol acceptance remains open', 'kind':'conclusion'}
    }
    narration = [
      ('intro', 'Welcome to the Inji Conformance Harness. This project makes protocol testing repeatable across Inji Certify and Inji Verify, and connects each result to reviewable evidence. Instead of treating a healthy service as proof of compatibility, the harness runs the OpenID Foundation tests and preserves their actual outcomes. This demonstration shows the implementation, current checks, and the integration work that remains.'),
      ('architecture', 'The architecture follows the repository. Java Test N G adapters launch the Python REST runner. The runner creates plans in the OpenID Foundation Conformance Suite, through the HTTPS gateway. The suite exercises Certify for credential issuance and Verify for presentations. Docker Compose supplies the service network, PostgreSQL, and Mongo D B. Results flow into JSON, Markdown, exported evidence, and Test N G with Extent reporting. These are the implemented components; an external authorization server is not yet connected.'),
      ('implementation', 'Here is the actual runner source. It creates and starts modules, polls their state, and reads live handoff information when interaction is required. The component adapters drive the real Certify and Verify interfaces. Timeouts and interrupted modules remain visible. The Java bridge preserves process failures and passes individual module outcomes to the reporting listener. Separate benchmark rows ensure that a performance breach cannot disappear behind a passing protocol result.'),
      ('docker', 'This is the current Docker check. The Linux engine is unreachable because its named pipe is absent. No deployment is claimed. We can inspect the repository and rerun local regressions, but the conformance workflows cannot be executed against these unavailable services. The next screens therefore use clearly labelled retained execution evidence.'),
      ('execution', 'These are the actual commands and retained outputs from October thirty first, not fresh executions. Certify finished with twelve interrupted modules, one warning, and one skip, with zero passes. Verify recorded five passes and seven failures. Combined execution preserved all twenty six outcomes and returned exit code one. The issuer authorization contract and genuine frontend evidence remain blockers. None of these failed workflows is presented as successful conformance.'),
      ('certify-report', 'These are the real Extent reports generated by the Java listener. Certify interruptions appear as failures, while warning and skipped outcomes stay distinct. Verify shows five passes and seven failures awaiting genuine frontend evidence. Test N G XML is retained alongside these reports. A Java adapter handling a warning successfully does not turn that warning into a protocol pass.'),
      ('validation', 'The regression suite was rerun for this submission. The exact current result is: ' + unit_text.replace(',',';') + '. These checks cover the REST contract, result handling, TLS, native status checking, reporting, and benchmark boundaries. They validate harness behavior, not end to end conformance. Next is genuine retained benchmark evidence: the protocol module passed, but a deliberately synthetic zero second budget failed. The runner and Maven both returned failure. Default operational budgets remain unset, so performance acceptance is not claimed.'),
      ('scope', 'The next integration milestone is a real external authorization server. Keycloak is an assessed candidate, and eSignet is an alternative; neither is deployed here. Client registration, callbacks, issuer trust, audience, scope, and credential record mapping must align. Certify also needs resource side D Pop validation, and authorization codes cannot simply be transferred between servers. Verify needs browser owned transactions and genuine screenshots connected to the corresponding suite results, with review where required.'),
      ('conclusion', 'The harness already provides repeatable orchestration, regression coverage, and transparent failure reporting. Its value is a traceable path from protocol execution to evidence. Full acceptance remains open until the missing integrations are implemented and the complete workflows actually pass. Thank you.')
    ]
    scenes = []
    for index, (key, words) in enumerate(narration):
        (work / ('voice-'+str(index)+'.txt')).write_text(words, encoding='utf-8')
        scenes.append(dict(key=key, text=words, textFile=str(work/('voice-'+str(index)+'.txt')),
                           wavFile=str(work/('voice-'+str(index)+'.wav'))))
    (work/'narration.json').write_text(json.dumps(scenes,indent=2),encoding='utf-8')
    ps = work/'narrate-v2.ps1'
    ps.write_text("""param([string]$Manifest)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice('Microsoft Zira Desktop')
$speaker.Rate = 0
$speaker.Volume = 100
$narrationScenes = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($narrationScene in $narrationScenes) {
  $speaker.SetOutputToWaveFile([string]$narrationScene.wavFile)
  $speaker.Speak([IO.File]::ReadAllText([string]$narrationScene.textFile))
  $speaker.SetOutputToNull()
}
$speaker.Dispose()
""",encoding='utf-8')
    execute('offline-narration-v2', ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ps),'-Manifest',str(work/'narration.json')])
    for scene in scenes:
        with wave.open(scene['wavFile'],'rb') as audio:
            scene['duration'] = audio.getnframes()/audio.getframerate() + 0.8
    total = sum(scene['duration'] for scene in scenes) + 1
    if not 120 <= total <= 299:
        raise ValueError('Narration duration outside requested range: ' + str(total))
    print('Narrated recording target: {:.1f}s'.format(total), flush=True)

    summary = '\n'.join('{}: {}'.format(c, ', '.join('{} {}'.format(n,k) for k,n in d['summary'].items() if n)) for c,d in runs.items())
    repo_paths = ['runner/conformance_runner.py','runner/handoff_certify.py','runner/handoff_verify.py',
                  'runner/benchmarks.py','runner/merge_results.py','testrig-bridge/','docker-compose.yml','.github/workflows/']
    page_html = r'''<!doctype html><html><meta charset="utf-8"><title>Inji Submission Demo</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b1424;color:#ecf2fb;font-family:Segoe UI,Arial}header{height:105px;padding:23px 38px;background:#13253d;border-bottom:2px solid #2dd4bf}header small{color:#80d7d0;letter-spacing:3px;font-size:13px}h1{margin:6px 0;font-size:30px}.layout{display:grid;grid-template-columns:1fr 275px;gap:22px;padding:25px 36px}#label{color:#82d7ca;font-size:15px;margin-bottom:15px}#panel{height:580px;overflow:auto;background:#101f34;border:1px solid #304562;border-radius:12px;padding:25px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:17px/1.5 Consolas,monospace;margin:0}iframe{width:100%;height:560px;border:0;background:white}aside{font-size:16px;line-height:1.7;color:#b8c9dd}aside b{color:white}aside pre{font:14px/1.7 Consolas;white-space:pre-wrap}.card{border-left:3px solid #2dd4bf;padding:8px 15px;margin:20px 0}h2{font-size:34px;margin:18px 0}h3{font-size:23px;color:#8ae8dc}p{font-size:22px;line-height:1.6}button{background:#1b3550;border:1px solid #405b79;color:#c5e8f5;border-radius:5px;padding:7px 12px;margin:0 8px 12px 0}footer{padding:0 36px;color:#92aac5;font-size:14px}.node{background:#1b3550;border:1px solid #427593;padding:17px;text-align:center;border-radius:9px;font-size:22px}.row{display:flex;gap:18px;align-items:center;justify-content:center;margin:18px 0}.arrow{color:#2dd4bf;font-size:28px}.muted{color:#afc3d9}.pill{background:#294345;padding:5px 9px;border-radius:4px;font-size:14px;color:#9df5d9}</style>
<header><small>MOSIP DEC{}DE / INJI CONFORMANCE HARNESS</small><h1 id="title"></h1></header>
<div class="layout"><main><div id="label"></div><div id="panel"></div></main><aside><b>Repository walkthrough</b><pre id="files"></pre><div class="card"><b>Current local regression</b><div id="unit"></div></div><div class="card"><b>Retained conformance</b><small>31 October 2026</small><pre id="summary"></pre></div><span class="pill">Acceptance remains open</span></aside></div>
<footer>Actual browser recording · Current checks and retained evidence labelled separately · No secrets or chat captured</footer>
<script>let data;async function init(){data=await(await fetch('/data')).json();document.querySelector('#files').textContent=data.paths.join('\n');document.querySelector('#unit').textContent=data.unit;document.querySelector('#summary').textContent=data.summary}init();
function show(key){let s=data.views[key];document.querySelector('#title').textContent=s.title;document.querySelector('#label').textContent=s.label;let p=document.querySelector('#panel');p.innerHTML='';p.scrollTop=0;if(s.kind==='report'){let f=document.createElement('iframe');f.src='/reports/'+s.report+'/conformance-extent.html';p.style.padding='8px';p.append(f);return}p.style.padding='25px';if(s.kind==='architecture'){p.innerHTML='<h3>Actual Compose services and evidence flow</h3><div class="row"><div class="node">Java TestNG bridge</div><span class="arrow">→</span><div class="node">Python REST runner</div></div><div class="row"><span class="arrow">↓</span><div class="node">HTTPS gateway ↔ OpenID suite</div><span class="arrow">↔</span><div class="node">MongoDB</div></div><div class="row"><div class="node">Inji Certify</div><span class="arrow">↔</span><div class="node">PostgreSQL</div><span class="arrow">↔</span><div class="node">Inji Verify</div></div><div class="row"><div class="node">JSON · Markdown · ZIP evidence</div><span class="arrow">→</span><div class="node">TestNG · Extent</div></div><p class="muted">Suite calls Certify and Verify through the gateway.<br>Docker supplies the private network. External AS not integrated.</p>';return}if(s.kind==='intro'){p.innerHTML='<span class="pill">Protocol testing / integration evidence</span><h2>Inji Conformance Harness</h2><p>Repeatable testing across Certify and Verify.</p><div class="card"><p>Automate execution.<br>Preserve evidence.<br>Report every outcome honestly.</p></div><p class="muted">Implemented prototype; full conformance acceptance remains open.</p>';return}if(s.kind==='scope'){p.innerHTML='<h3>1 / Real external authorization server</h3><p>Keycloak assessed; eSignet alternative.<br>No AS deployment or registered clients.</p><h3>2 / Protocol integration</h3><p>DPoP proof validation, grant coordination,<br>issuer trust and subject-to-record mapping.</p><h3>3 / Genuine Verify UI evidence</h3><p>Browser-owned transactions, real result screenshots,<br>suite association and manual review where required.</p>';return}if(s.kind==='conclusion'){p.innerHTML='<h2>Evidence before acceptance.</h2><p>Repeatable orchestration.<br>Regression-tested harness behavior.<br>Traceable protocol failures and reports.</p><div class="card"><p>Next: complete integrations, then rerun<br>Certify, Verify and combined workflows.</p></div><p class="muted">No end-to-end conformance pass is claimed.</p>';return}let pre=document.createElement('pre');pre.textContent=s.content;p.append(pre)}
function move(fraction){let p=document.querySelector('#panel');p.scrollTo({top:(p.scrollHeight-p.clientHeight)*fraction,behavior:'smooth'})}</script></html>'''
    data = dict(views={k:dict(v, content=safe(v.get('content',''))) for k,v in views.items()},
                paths=repo_paths,unit=unit_text,summary=summary)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path=='/': raw,mime=page_html.encode(),'text/html; charset=utf-8'
            elif self.path=='/data': raw,mime=json.dumps(data).encode(),'application/json'
            elif self.path.startswith('/reports/'):
                rel=self.path[len('/reports/'):].split('?',1)[0]
                component,_,asset=rel.partition('/')
                base=(historical/'demo'/(component+'-testng')).resolve()
                path=(base/asset).resolve()
                if component not in ('certify','verify') or base not in path.parents or path.suffix not in ('.html','.css','.js','.png','.gif') or not path.is_file():
                    self.send_error(404);return
                import mimetypes
                raw=path.read_bytes()
                if path.suffix=='.html': raw=safe(raw.decode('utf-8')).encode('utf-8')
                mime=mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
            else: self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

    from playwright.sync_api import sync_playwright
    import imageio_ffmpeg
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    timeline=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=False,executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
        context=browser.new_context(viewport={'width':1600,'height':900},record_video_dir=str(work/'raw-recording'),record_video_size={'width':1600,'height':900})
        started=time.monotonic()
        page=context.new_page();page.goto('http://127.0.0.1:'+str(args.port));page.wait_for_function('window.data !== undefined || typeof data !== "undefined" && !!data')
        video=page.video
        for index,scene in enumerate(scenes):
            page.evaluate('show',scene['key'])
            offset=time.monotonic()-started
            timeline.append(dict(key=scene['key'],offset=offset,wavFile=scene['wavFile'],duration=scene['duration']))
            print('Recording scene: '+scene['key'],flush=True)
            halfway=scene['duration']/2
            page.wait_for_timeout(halfway*1000)
            if scene['key']=='implementation': page.evaluate('show','java-source')
            elif scene['key']=='certify-report': page.evaluate('show','verify-report')
            elif scene['key']=='validation': page.evaluate('show','benchmark')
            elif scene['key']=='execution': page.evaluate('move',0.65)
            page.wait_for_timeout(max(0,scene['duration']-(time.monotonic()-started-offset))*1000)
        context.close();raw_video=video.path();browser.close()
    server.shutdown()
    (work/'recording-timeline.json').write_text(json.dumps(timeline,indent=2))
    with wave.open(timeline[0]['wavFile'],'rb') as first: params=first.getparams()
    with wave.open(str(work/'voice-over.wav'),'wb') as mixed:
        mixed.setparams(params);written=0
        for entry in timeline:
            target=int(entry['offset']*params.framerate)
            if target>written: mixed.writeframes(b'\0'*(target-written)*params.nchannels*params.sampwidth);written=target
            with wave.open(entry['wavFile'],'rb') as speech:
                if speech.getparams()[:3]!=params[:3]: raise ValueError('Narration format mismatch')
                frames=speech.readframes(speech.getnframes());mixed.writeframes(frames);written+=speech.getnframes()
        mixed.writeframes(b'\0'*int(params.framerate*.8)*params.nchannels*params.sampwidth)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    with (work/'encoding.log').open('w') as log:
        subprocess.run([ffmpeg,'-n','-i',str(raw_video),'-i',str(work/'voice-over.wav'),
                        '-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','20',
                        '-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-af','loudnorm=I=-16:TP=-1.5:LRA=11',
                        '-movflags','+faststart','-shortest',str(output)],check=True,stdout=log,stderr=log)
    reader=imageio_ffmpeg.read_frames(str(output));metadata=next(reader);reader.close()
    decoded=subprocess.run([ffmpeg,'-v','error','-i',str(output),'-f','null','-'],capture_output=True,text=True)
    if decoded.returncode or not 120<=metadata['duration']<=300: raise RuntimeError('Final video validation failed')
    for label,second in [('intro',5),('reports',timeline[5]['offset']+4),('final',metadata['duration']-5)]:
        subprocess.run([ffmpeg,'-v','error','-n','-ss',str(second),'-i',str(output),'-frames:v','1',str(work/('frame-'+label+'.png'))],check=True)
    verification=dict(metadata,bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                      decodeExitCode=decoded.returncode,decodeErrors=decoded.stderr,video=str(output.relative_to(ROOT)),
                      audio='AAC voice-over from installed Microsoft Zira Desktop; synthesized narration disclosed')
    (work/'video-verification.json').write_text(json.dumps(verification,indent=2))
    print('VIDEO COMPLETE: '+str(output.relative_to(ROOT)),flush=True)
    print(json.dumps(verification,indent=2),flush=True)


if __name__=='__main__': main()
