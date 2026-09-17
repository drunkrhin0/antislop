#!/usr/bin/env bash

set -euo pipefail

VERSION="$(python3 -c 'import json; print(json.load(open("rules.json"))["version"])')"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

NOTES_FILE="docs/release-notes-${VERSION}.md"
STANDALONE="${WORK_DIR}/antislop-${VERSION}.zip"
PLUGIN="${WORK_DIR}/antislop-plugin-${VERSION}.zip"
KIRO="${WORK_DIR}/antislop-kiro-${VERSION}.zip"
RELEASE_JSON="${WORK_DIR}/release.json"

if [ ! -f "${NOTES_FILE}" ]; then
  echo "Missing release notes: ${NOTES_FILE}" >&2
  exit 1
fi

(cd skills && zip -q -r "${STANDALONE}" antislop/)
(cd powers/antislop && zip -q -r "${KIRO}" .)
bash scripts/build-plugin-archive.sh "${WORK_DIR}"
python3 scripts/build-release-json.py \
  "antislop-v${VERSION}" "${VERSION}" "${NOTES_FILE}" > "${RELEASE_JSON}"

for required in \
    "${STANDALONE}" \
    "${PLUGIN}" \
    "${PLUGIN}.sha256" \
    "${KIRO}" \
    "${RELEASE_JSON}"; do
  if [ ! -s "${required}" ]; then
    echo "Missing or empty release output: ${required}" >&2
    exit 1
  fi
done

for entry in antislop/SKILL.md antislop/references/vocabulary.md; do
  unzip -Z1 "${STANDALONE}" | grep -Fx "${entry}" > /dev/null
done

for entry in POWER.md steering/audit-mode.md steering/vocabulary.md; do
  unzip -Z1 "${KIRO}" | grep -Fx "${entry}" > /dev/null
done

python3 -c '
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
notes = Path(sys.argv[2]).read_text(encoding="utf-8")
version = sys.argv[3]
assert payload["tag_name"] == "antislop-v" + version
assert payload["name"] == "antislop v" + version
assert payload["body"] == notes
assert payload["draft"] is False
assert payload["prerelease"] is False
' "${RELEASE_JSON}" "${NOTES_FILE}" "${VERSION}"

printf 'Release E2E passed for %s\n' "${VERSION}"
printf 'Assets:\n'
find "${WORK_DIR}" -maxdepth 1 -type f -name '*.zip' -printf '  %f\n' | LC_ALL=C sort
