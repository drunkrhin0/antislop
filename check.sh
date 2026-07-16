#!/bin/bash
# check.sh — combined pass/fail report for Antislop rule propagation
# Runs generate.py --check and validate.py, prints a single report naming
# exactly which check(s) failed and why.
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

generate_failures=0
validate_failures=0
report_lines=()

# ── generate.py --check ──────────────────────────────────────────────
gen_output=$(python3 generate.py --check 2>&1)
gen_exit=$?

if [ "$gen_exit" -eq 0 ]; then
  report_lines+=("PASS  generate.py --check: all artifacts match")
else
  generate_failures=1
  while IFS= read -r line; do
    case "$line" in
      FAILED*|DRIFT*|MISSING*)
        report_lines+=("FAIL  generate.py --check: $line")
        ;;
    esac
  done <<< "$gen_output"
  # If no DRIFT/MISSING/FALED lines were captured, include the raw output
  if ! grep -qE 'FAILED|DRIFT|MISSING' <<< "$gen_output" 2>/dev/null; then
    report_lines+=("FAIL  generate.py --check: exited $gen_exit — $gen_output")
  fi
fi

# ── validate.py ──────────────────────────────────────────────────────
val_output=$(python3 validate.py --skills-dir skills 2>&1)
val_exit=$?

if [ "$val_exit" -eq 0 ]; then
  report_lines+=("PASS  validate.py: all checks passed")
else
  validate_failures=1
  while IFS= read -r line; do
    case "$line" in
      *FAIL*)
        report_lines+=("FAIL  validate.py: $line")
        ;;
    esac
  done <<< "$val_output"
fi

# ── Print report ─────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  Antislop propagation check"
echo "  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "=============================================="
for line in "${report_lines[@]}"; do
  echo "$line"
done
echo ""

if [ "$generate_failures" -ne 0 ] || [ "$validate_failures" -ne 0 ]; then
  echo "Overall: FAILED"
  echo "  generate.py --check: $([ "$generate_failures" -eq 0 ] && echo PASSED || echo FAILED)"
  echo "  validate.py:          $([ "$validate_failures" -eq 0 ] && echo PASSED || echo FAILED)"
  echo "=============================================="
  exit 1
fi

echo "Overall: PASSED"
echo "=============================================="
exit 0
