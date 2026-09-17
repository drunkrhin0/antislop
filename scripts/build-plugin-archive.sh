#!/usr/bin/env bash

set -euo pipefail

OUTPUT_DIR="${1:-dist}"
mkdir -p "${OUTPUT_DIR}"
OUTPUT_DIR="$(cd "${OUTPUT_DIR}" && pwd)"
VERSION="$(python3 -c 'import json; print(json.load(open("rules.json"))["version"])')"
PLUGIN_VERSION="$(python3 -c 'import json; print(json.load(open("plugin.json"))["version"])')"

if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid canonical version: ${VERSION}" >&2
  exit 1
fi

if [ "${PLUGIN_VERSION}" != "${VERSION}" ]; then
  echo "plugin.json version ${PLUGIN_VERSION} does not match ${VERSION}" >&2
  exit 1
fi

EXPECTED_SKILLS=$'antislop
generate-slop'
ACTUAL_SKILLS="$(
  find skills -mindepth 2 -maxdepth 2 -name SKILL.md -print \
    | sed -E 's#^skills/([^/]+)/SKILL\.md$#\1#' \
    | LC_ALL=C sort
)"

if [ "${ACTUAL_SKILLS}" != "${EXPECTED_SKILLS}" ]; then
  echo "Portable plugin must contain exactly antislop and generate-slop" >&2
  printf 'Found:\n%s\n' "${ACTUAL_SKILLS}" >&2
  exit 1
fi

ARCHIVE="${OUTPUT_DIR}/antislop-plugin-${VERSION}.zip"
CHECKSUM="${ARCHIVE}.sha256"
STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGING_DIR}"' EXIT

mkdir -p "${STAGING_DIR}/antislop"
cp plugin.json "${STAGING_DIR}/antislop/plugin.json"
cp -R .claude-plugin "${STAGING_DIR}/antislop/.claude-plugin"
cp -R .codex-plugin "${STAGING_DIR}/antislop/.codex-plugin"
cp -R skills "${STAGING_DIR}/antislop/skills"
(
  cd "${STAGING_DIR}"
  zip -q -r "${ARCHIVE}" antislop
)

ARCHIVE_SKILLS="$(
  unzip -Z1 "${ARCHIVE}" \
    | sed -nE 's#^antislop/skills/([^/]+)/SKILL\.md$#\1#p' \
    | LC_ALL=C sort
)"

if [ "${ARCHIVE_SKILLS}" != "${EXPECTED_SKILLS}" ]; then
  echo "Built archive has an unexpected skill roster" >&2
  printf 'Found:\n%s\n' "${ARCHIVE_SKILLS}" >&2
  exit 1
fi

for required_file in antislop/plugin.json antislop/.claude-plugin/plugin.json antislop/.claude-plugin/marketplace.json antislop/.codex-plugin/plugin.json; do
  if ! unzip -Z1 "${ARCHIVE}" | grep -Fx "${required_file}" > /dev/null; then
    echo "Built archive is missing ${required_file}" >&2
    exit 1
  fi
done

DIGEST="$(python3 -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "${ARCHIVE}")"
printf '%s  %s\n' "${DIGEST}" "$(basename "${ARCHIVE}")" > "${CHECKSUM}"

echo "Built ${ARCHIVE}"
echo "SHA-256 ${DIGEST}"
