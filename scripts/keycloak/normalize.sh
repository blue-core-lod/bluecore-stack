#!/bin/bash
# Reduce a full Keycloak realm export to a minimal declarative config by
# stripping Keycloak defaults and generated IDs.
#
#   ./scripts/keycloak/normalize.sh <input-realm-json> <output-dir>
#
# Note: normalize ignores `users` and `components` by design (see
# docs/NORMALIZE.md upstream). Users are authored by hand; components in this
# realm are all Keycloak defaults (generated keys, client-registration
# policies) and are intentionally dropped.
set -euo pipefail

CONFIG_CLI_IMAGE="${KEYCLOAK_CONFIG_CLI_IMAGE:-adorsys/keycloak-config-cli:6.5.1-26.1.0}"

# This pinned image bundles reference/default realms only for the Keycloak
# version baked into its tag (26.1.0). Our exports are produced by the
# 26.1.2 Keycloak used elsewhere in this repo (see compose-keycloak-verify.yaml),
# so normalize otherwise aborts with:
#   "Reference realm for version 26.1.2 does not exist. Aborting!"
# normalization.fallback-version tells it to diff against the closest
# bundled baseline instead. Keep this in sync with CONFIG_CLI_IMAGE's tag.
NORMALIZATION_FALLBACK_VERSION="${KEYCLOAK_CONFIG_CLI_FALLBACK_VERSION:-26.1.0}"

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <input-realm-json> <output-dir>" >&2
  exit 2
fi

INPUT="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT_DIR="$2"

mkdir -p "$OUTPUT_DIR"
OUTPUT_ABS="$(cd "$OUTPUT_DIR" && pwd)"

docker run --rm \
  -v "${INPUT}:/work/in/realm.json:ro" \
  -v "${OUTPUT_ABS}:/work/out" \
  "$CONFIG_CLI_IMAGE" \
  --run.operation=NORMALIZE \
  --normalization.files.input-locations=/work/in/realm.json \
  --normalization.files.output-directory=/work/out \
  --normalization.output-format=YAML \
  --normalization.fallback-version="$NORMALIZATION_FALLBACK_VERSION"

echo "Normalized config written to ${OUTPUT_DIR}"
ls -la "$OUTPUT_DIR"
