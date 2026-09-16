#!/bin/bash
# Reduce a full Keycloak realm export to a minimal declarative config by diffing
# against Keycloak's bundled reference realm and dropping fields that match its
# defaults. Note: this is NOT a full generated-ID scrub — the top-level realm
# 'id' (a random UUID) and 'keycloakVersion' are always retained, since they
# never match the reference baseline. Downstream diffs (e.g. the drift check)
# must ignore these two fields.
#
#   ./scripts/keycloak/normalize.sh <input-realm-json> <output-dir>
#
# Note: normalize ignores `users` and `components` by design (see
# docs/NORMALIZE.md upstream). Users are authored by hand; components in this
# realm are all Keycloak defaults (generated keys, client-registration
# policies) and are intentionally dropped.
set -euo pipefail

CONFIG_CLI_IMAGE="${KEYCLOAK_CONFIG_CLI_IMAGE:-adorsys/keycloak-config-cli:6.5.1-26.1.0}"

# This pinned image bundles a reference/default realm only for the Keycloak
# version baked into its own tag, so normalization.fallback-version must
# always name that same Keycloak version (see docs/NORMALIZE.md upstream) —
# any mismatch means normalize silently diffs against the wrong defaults and
# produces a subtly wrong baseline with no error. Rather than track that
# version in a second, independently-overridable variable, derive it from
# CONFIG_CLI_IMAGE's own tag, which has the form <cli-version>-<kc-version>
# (e.g. "6.5.1-26.1.0").
IMAGE_TAG="${CONFIG_CLI_IMAGE##*:}"
if [[ ! "$IMAGE_TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+-([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "error: cannot derive Keycloak baseline version from image tag '${IMAGE_TAG}'" >&2
  echo "       (CONFIG_CLI_IMAGE=${CONFIG_CLI_IMAGE})" >&2
  echo "       expected format <cli-version>-<kc-version>, e.g. 6.5.1-26.1.0" >&2
  exit 2
fi
DERIVED_FALLBACK_VERSION="${BASH_REMATCH[1]}"

# KEYCLOAK_CONFIG_CLI_FALLBACK_VERSION remains an explicit escape hatch, but
# if set it must agree with what the image tag implies. Disagreement would
# otherwise be exactly the silent-wrong-baseline failure mode this derivation
# exists to prevent, so fail loudly instead of picking one value quietly.
if [[ -n "${KEYCLOAK_CONFIG_CLI_FALLBACK_VERSION:-}" ]]; then
  if [[ "$KEYCLOAK_CONFIG_CLI_FALLBACK_VERSION" != "$DERIVED_FALLBACK_VERSION" ]]; then
    echo "error: KEYCLOAK_CONFIG_CLI_FALLBACK_VERSION='${KEYCLOAK_CONFIG_CLI_FALLBACK_VERSION}' disagrees with" >&2
    echo "       the Keycloak version implied by CONFIG_CLI_IMAGE's tag ('${DERIVED_FALLBACK_VERSION}')." >&2
    echo "       Set KEYCLOAK_CONFIG_CLI_IMAGE to a matching tag, or unset the override." >&2
    exit 2
  fi
fi
NORMALIZATION_FALLBACK_VERSION="$DERIVED_FALLBACK_VERSION"

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <input-realm-json> <output-dir>" >&2
  exit 2
fi

if [[ ! -f "$1" ]]; then
  echo "error: input realm file not found: $1" >&2
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
