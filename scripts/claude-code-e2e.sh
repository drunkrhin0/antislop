#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/claude-code-e2e.sh --revision <40-char-commit> [options]

Options:
  --repo <path>       Antislop checkout to test (default: current directory)
  --receipt <path>    Write a bounded receipt at this path
  --config-dir <path> Use an existing authenticated Claude config directory
  --live              Run three opt-in Claude Code probes
  -h, --help          Show this help

The live mode requires CLAUDE_E2E_ALLOW_LIVE=1. Each live probe is bounded
by CLAUDE_E2E_TIMEOUT_SECONDS, which defaults to 180 and may be 1..900.
Live mode can consume provider quota and never writes provider output.
USAGE
}

repo_dir="$(pwd)"
expected_revision=""
receipt=""
auth_config_dir=""
live=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      repo_dir="$2"
      shift 2
      ;;
    --revision)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      expected_revision="$2"
      shift 2
      ;;
    --receipt)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      receipt="$2"
      shift 2
      ;;
    --config-dir)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      auth_config_dir="$2"
      shift 2
      ;;
    --live)
      live=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$expected_revision" ]] || {
  echo "error: --revision is required" >&2
  exit 2
}
[[ "$expected_revision" =~ ^[0-9a-f]{40}$ ]] || {
  echo "error: --revision must be a 40-character lowercase commit SHA" >&2
  exit 2
}
[[ -d "$repo_dir" ]] || {
  echo "error: checkout does not exist: $repo_dir" >&2
  exit 2
}
[[ -z "$auth_config_dir" || -d "$auth_config_dir" ]] || {
  echo "error: config directory does not exist: $auth_config_dir" >&2
  exit 2
}

actual_revision="$(git -C "$repo_dir" rev-parse HEAD 2>/dev/null || true)"
[[ "$actual_revision" == "$expected_revision" ]] || {
  echo "error: checkout HEAD is $actual_revision, expected $expected_revision" >&2
  exit 2
}
[[ -z "$(git -C "$repo_dir" status --porcelain)" ]] || {
  echo "error: checkout has uncommitted changes" >&2
  exit 2
}
[[ -f "$repo_dir/.claude-plugin/plugin.json" ]] || {
  echo "error: .claude-plugin/plugin.json is missing" >&2
  exit 2
}
[[ -f "$repo_dir/.claude-plugin/marketplace.json" ]] || {
  echo "error: .claude-plugin/marketplace.json is missing" >&2
  exit 2
}

tmp_dir="$(mktemp -d)"
summary_file="$tmp_dir/summary"
trap 'rm -rf "$tmp_dir"' EXIT

record() {
  printf '%s=%s\n' "$1" "$2" >> "$summary_file"
}

write_receipt() {
  [[ -n "$receipt" ]] || return 0
  mkdir -p "$(dirname -- "$receipt")"
  {
    echo "# Claude Code E2E driver receipt"
    echo
    cat "$summary_file"
  } > "$receipt"
}

blocked() {
  record "status" "blocked"
  record "reason" "$1"
  write_receipt
  cat "$summary_file"
  exit 2
}

failed() {
  record "status" "failed"
  record "reason" "$1"
  write_receipt
  cat "$summary_file"
  exit 1
}

record "run_date_utc" "$(date -u +%F)"
record "antislop_revision" "$expected_revision"
record "checkout" "$repo_dir"
record "tested_surface" "Claude Code plugin-dir"

if ! command -v claude >/dev/null 2>&1; then
  blocked "claude executable is not on PATH"
fi
cli_version="$(claude --version 2>/dev/null | head -n 1 | tr '\r\n' ' ' || true)"
[[ -n "$cli_version" ]] || blocked "claude --version returned no version"
record "claude_code_version" "$cli_version"

if ! (
  cd "$repo_dir"
  python3 -c 'import json, pathlib; [json.loads(pathlib.Path(p).read_text()) for p in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json")]'
); then
  failed "Claude plugin or marketplace manifest is not valid JSON"
fi
record "manifest_validation" "pass"

if ! (
  cd "$repo_dir"
  python3 validate.py --skills-dir skills --expect-version-from rules.json >/dev/null
  bash check.sh >/dev/null
  python3 -m unittest discover -s tests -v >/dev/null
); then
  failed "repository validation or tests failed"
fi
record "repository_verification" "pass"

if (( live == 0 )); then
  record "live_prompts" "not_requested"
  record "status" "preflight_pass"
  write_receipt
  cat "$summary_file"
  exit 0
fi

[[ "${CLAUDE_E2E_ALLOW_LIVE:-}" == "1" ]] || {
  blocked "--live requires CLAUDE_E2E_ALLOW_LIVE=1"
}
probe_timeout_seconds="${CLAUDE_E2E_TIMEOUT_SECONDS:-180}"
if ! [[ "$probe_timeout_seconds" =~ ^[0-9]+$ ]] ||
   (( probe_timeout_seconds < 1 || probe_timeout_seconds > 900 )); then
  failed "CLAUDE_E2E_TIMEOUT_SECONDS must be an integer from 1 to 900"
fi
record "live_attempts" "3"
record "probe_timeout_seconds" "$probe_timeout_seconds"
if [[ -n "$auth_config_dir" ]]; then
  record "profile_mode" "authenticated_config_dir"
else
  record "profile_mode" "temporary_config_dir"
fi

run_with_timeout() {
  if command -v timeout >/dev/null 2>&1; then
    timeout --signal=TERM "${probe_timeout_seconds}s" "$@"
    return $?
  fi

  python3 - "$probe_timeout_seconds" "$@" <<'PY'
import subprocess
import sys

seconds = int(sys.argv[1])
process = subprocess.Popen(sys.argv[2:])
try:
    process.communicate(timeout=seconds)
except subprocess.TimeoutExpired:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    sys.exit(124)
sys.exit(process.returncode)
PY
}

run_probe() {
  local label="$1"
  local prompt="$2"
  local profile
  local output_file
  if [[ -n "$auth_config_dir" ]]; then
    profile="$auth_config_dir"
  else
    profile="$(mktemp -d "$tmp_dir/profile.XXXXXX")"
  fi
  output_file="$tmp_dir/$label.output"
  if (
    cd "$repo_dir"
    unset CLAUDECODE
    CLAUDE_CONFIG_DIR="$profile" \
      run_with_timeout \
      claude --plugin-dir "$repo_dir" -p "$prompt" >"$output_file" 2>&1
  ); then
    record "$label" "completed_manual_review_required"
  else
    if grep -Eiq 'not logged in|please run /login|authentication|unauthorized' "$output_file"; then
      record "$label" "blocked_not_logged_in"
    else
      record "$label" "blocked_command_failed"
    fi
    rm -f "$output_file"
    return 1
  fi
  rm -f "$output_file"
}

probe_failures=0
run_probe "writing_probe" \
  "Rewrite this exact sentence as plain technical prose. Preserve every fact and return only the rewrite: Parser rejects bad date -> exit 2, no write." ||
  probe_failures=$((probe_failures + 1))
run_probe "audit_probe" \
  "Audit this exact text for AI-writing patterns. Return only a 0-100 score, violations with severity, and short excerpts: It is important to note that the parser rejects bad dates." ||
  probe_failures=$((probe_failures + 1))
run_probe "unrelated_probe" \
  "What is 2 + 2? Reply with only the number." ||
  probe_failures=$((probe_failures + 1))

if (( probe_failures > 0 )); then
  blocked "one or more Claude Code probes were blocked or failed"
fi
record "status" "completed_manual_review_required"
write_receipt
cat "$summary_file"
