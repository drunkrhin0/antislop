#!/bin/bash
# fix.sh — regenerate-and-reverify auto-fix for Antislop propagation failures
#
# Thin bash wrapper around fix.py, mirroring check.sh's role: check.sh is the
# bash orchestration/report layer over the generate.py / validate.py engines,
# fix.sh is the same layer over fix.py. The fix logic itself lives in Python
# (fix.py) rather than in this script because it reuses validate.py's
# frontmatter/body parsers directly instead of re-parsing YAML/JSON in bash.
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

python3 fix.py "$@"
exit $?
