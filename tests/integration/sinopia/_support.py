from __future__ import annotations

import json
import secrets
import string
from typing import Any

# The RDF type every Sinopia Resource Template node carries. The Blue Core API
# stores Resource Templates as "Profiles" and identifies the template node by
# this type when minting/re-homing its URI (see bluecore_api profiles route).
RESOURCE_TEMPLATE_TYPE = "http://sinopia.io/vocabulary/ResourceTemplate"
SINOPIA = "http://sinopia.io/vocabulary/"


# ========================================================================
# Generate a distinctive, letters-only token for search/round-trip asserts.
# ------------------------------------------------------------------------
def interop_nonce() -> str:
    return "interopprobe" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))


# ========================================================================
# Build a compacted Sinopia Resource Template JSON-LD document.
#
# Carries its own @context so the API's JSON-LD loader expands the sinopia
# prefixes rather than falling back to the Blue Core default context. The
# nonce lands in the label + resource id so the profile is searchable.
# ------------------------------------------------------------------------
def build_resource_template_jsonld(nonce: str) -> dict[str, Any]:
    resource_id = f"test:RT:bluecore:Interop:{nonce}"
    return {
        "@context": {
            "sinopia": SINOPIA,
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
        "@id": f"http://localhost:3000/resource/{resource_id}",
        "@type": "sinopia:ResourceTemplate",
        "rdfs:label": f"Blue Core Sinopia interop probe {nonce}",
        "sinopia:hasResourceId": resource_id,
        "sinopia:hasClass": {"@id": "http://id.loc.gov/ontologies/bibframe/Work"},
    }


# ========================================================================
# Build an expanded (context-free, full-URI) Resource Template JSON-LD list.
#
# Mirrors the shape the remote /api/search/profile returns and that the
# load-templates flow POSTs back, so tests cover the real interop payload.
# ------------------------------------------------------------------------
def build_expanded_resource_template_jsonld(nonce: str) -> list[dict[str, Any]]:
    resource_id = f"test:RT:bluecore:Interop:{nonce}"
    return [
        {
            "@id": f"http://localhost:3000/resource/{resource_id}",
            "@type": [RESOURCE_TEMPLATE_TYPE],
            "http://www.w3.org/2000/01/rdf-schema#label": [
                {"@value": f"Blue Core Sinopia interop probe {nonce}"}
            ],
            "http://sinopia.io/vocabulary/hasResourceId": [{"@value": resource_id}],
            "http://sinopia.io/vocabulary/hasClass": [
                {"@id": "http://id.loc.gov/ontologies/bibframe/Work"}
            ],
        }
    ]


# ========================================================================
# Wrap JSON-LD into the ProfileCreateSchema body ({"data": "<json string>"}).
# ------------------------------------------------------------------------
def profile_create_body(jsonld: dict[str, Any] | list[Any]) -> dict[str, str]:
    return {"data": json.dumps(jsonld)}


# ========================================================================
# Normalize profile data (list of nodes or single node) to an iterable.
# ------------------------------------------------------------------------
def _nodes(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [node for node in data if isinstance(node, dict)]
    if isinstance(data, dict):
        return [data]
    return []


# ========================================================================
# Return the node typed sinopia:ResourceTemplate, or None if absent.
# ------------------------------------------------------------------------
def find_resource_template_node(data: Any) -> dict[str, Any] | None:
    for node in _nodes(data):
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if RESOURCE_TEMPLATE_TYPE in types:
            return node
    return None
