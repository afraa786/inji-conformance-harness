#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

usage() {
  echo 'Usage: ./run-full-stack-conformance.sh (--component certify|verify | --combined) [--no-up] [--down] [--expected-failures-dir DIR]'
}
die() { echo "Error: $*" >&2; exit 2; }
mode='' no_up=0 down=0 expected_dir=runner
while (($#)); do
  case "$1" in
    --component)
      [[ $# -ge 2 && -z "$mode" ]] || die 'provide exactly one component or --combined'
      [[ "$2" == certify || "$2" == verify ]] || die 'component must be certify or verify'
      mode=$2; shift 2 ;;
    --combined) [[ -z "$mode" ]] || die 'choose only one mode'; mode=combined; shift ;;
    --no-up) no_up=1; shift ;;
    --down) down=1; shift ;;
    --expected-failures-dir)
      [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || die 'missing expected-failures directory'
      expected_dir=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; die "unknown argument: $1" ;;
  esac
done
[[ -n "$mode" ]] || { usage >&2; die 'select a component or --combined'; }
python_bin=${PYTHON:-python}
command -v "$python_bin" >/dev/null || die 'Python is required (or set PYTHON)'
command -v docker >/dev/null || die 'Docker Compose v2 is required'
docker compose version >/dev/null
components=("$mode")
[[ "$mode" != combined ]] || components=(certify verify)
services=(postgres mongodb server httpd "${components[@]}")
timeout=${HEALTH_TIMEOUT_SECONDS:-600}
[[ "$timeout" =~ ^[1-9][0-9]*$ ]] || die 'HEALTH_TIMEOUT_SECONDS must be a positive integer'

setting() {
  "$python_bin" -c 'import os,sys; from runner.render_plans import read_env; read_env(); print(os.environ.get(sys.argv[1], sys.argv[2]))' "$1" "$2"
}
suite_url=$(setting SUITE_URL https://localhost:8443)
# Render with the shared typed renderer; never print private plan configuration.
for component in "${components[@]}"; do
  target=$(setting CERTIFY_TARGET https://certify.test:8446)
  [[ "$component" != verify ]] || target=$(setting VERIFY_TARGET https://verify.test:8447/v1/verify)
  "$python_bin" runner/render_plans.py --component "$component" --target "$target" \
    --suite-url "$suite_url" --out "results/rendered/$component-plan.json"
  "$python_bin" - "$component" "$expected_dir" <<'PY'
import sys
from pathlib import Path
from runner.conformance_runner import load_expected_failures
component, directory = sys.argv[1:]
try:
    load_expected_failures(str(Path(directory) / ('expected-failures-' + component + '.json')))
except Exception as error:
    print('Configuration error: ' + str(error), file=sys.stderr)
    sys.exit(2)
PY
done
if (( ! no_up )); then
  db_init_dir=$(setting DB_INIT_DIR ./local/db-init)
  [[ -d "$db_init_dir" ]] || die 'prepare DB_INIT_DIR; see README'
  if [[ "$mode" != verify ]]; then
    certify_config_dir=$(setting CERTIFY_CONFIG_DIR ./local/certify-config)
    [[ -f "$certify_config_dir/certify-default.properties" ]] || die 'prepare CERTIFY_CONFIG_DIR; see README'
  fi
fi

cleanup() {
  code=$?
  trap - EXIT
  "$python_bin" runner/capture_diagnostics.py "$code" || true
  if ((down)); then
    if ! docker compose down --remove-orphans; then
      echo 'Error: Compose teardown failed' >&2
      ((code != 0)) || code=2
    fi
  fi
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
docker compose config --quiet
if ((! no_up)); then
  "$python_bin" runner/stack_control.py "${services[@]}"
fi
deadline=$((SECONDS + timeout))
for service in "${services[@]}"; do
  while :; do
    id=$(docker compose ps -a -q "$service")
    [[ -n "$id" ]] || die "service $service is missing; remove --no-up to start it"
    state=$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$id")
    [[ "$state" != 'running healthy' ]] || break
    case "$state" in
      *unhealthy*|exited*|dead*|*missing) die "service $service is $state" ;;
    esac
    ((SECONDS < deadline)) || die "health timeout waiting for $service"
    sleep 3
  done
done

mkdir -p results
previous_dir=$("$python_bin" runner/archive_results.py "$mode")
if [[ "$mode" == combined ]]; then
  "$python_bin" -c 'from pathlib import Path; [(p.unlink() if p.exists() else None) for p in (Path("results/results-combined.json"), Path("results/report-combined.md"))]'
fi
codes=()
for component in "${components[@]}"; do
  target=$(setting CERTIFY_TARGET https://certify.test:8446)
  [[ "$component" != verify ]] || target=$(setting VERIFY_TARGET https://verify.test:8447/v1/verify)
  out="results/results-$component.json"
  # Only discard this run's output so old results cannot mask an API failure.
  "$python_bin" -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.unlink() if p.exists() else None' "$out"
  code=0
  "$python_bin" runner/conformance_runner.py --component "$component" --target "$target" \
    --suite-url "$suite_url" --out "$out" --plan "results/rendered/$component-plan.json" \
    --waiting-timeout-seconds "${WAITING_TIMEOUT_SECONDS:-120}" \
    --expected-failures "$expected_dir/expected-failures-$component.json" || code=$?
  if ((code == 0)); then
    "$python_bin" - "$out" <<'PY' || code=2
import sys
from runner.diff_results import load_modules
try:
    modules = load_modules(sys.argv[1])
    if not modules or set(modules.values()) & {'FAILED', 'INTERRUPTED'}:
        raise ValueError('no modules or unexpected failures')
except (OSError, ValueError, TypeError) as error:
    print('Invalid run output: ' + str(error), file=sys.stderr)
    sys.exit(2)
PY
  fi
  codes+=("$code")
  if [[ -n "$previous_dir" && -f "$previous_dir/results-$component.json" && -f "$out" ]]; then
    diff_code=0
    "$python_bin" runner/diff_results.py "$previous_dir/results-$component.json" "$out" > "results/diff-$component.txt" || diff_code=$?
    if ((diff_code != 0 && code == 0)); then
      code=$diff_code
      codes[${#codes[@]}-1]=$code
    fi
  fi
  echo "$component: runner exit=$code, results=$out"
done
if [[ "$mode" == combined ]]; then
  "$python_bin" runner/merge_results.py "${codes[@]}"
else
  exit "${codes[0]}"
fi
