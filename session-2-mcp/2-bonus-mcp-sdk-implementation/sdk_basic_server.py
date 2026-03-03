# ═══════════════════════════════════════════════════════════════════════════════
# sdk_basic_server.py
# ═══════════════════════════════════════════════════════════════════════════════
# Official MCP Python SDK version of basic_server.py.
# Exposes:
#   Resources:  dataset://drugs             -> database overview
#               drug://{drug_id}            -> individual drug record
#   Tools:      get_drug_info(drug_id)      -> name, indication, mechanism
#
# Run:  python sdk_basic_server.py
# URL:  http://localhost:8501/mcp

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Tuple

from mcp.server.fastmcp import FastMCP

HERE    = Path(__file__).parent
DB_PATH = HERE / "drug_db.json"
DB: dict[str, dict[str, Any]] = json.loads(DB_PATH.read_text(encoding="utf-8"))

mcp = FastMCP(
    name="Drug Discovery MCP Server (Official SDK) — Basic",
    instructions=(
        "Basic MCP server exposing a curated drug database and a single "
        "lookup tool. Use get_drug_info to retrieve a drug's indication "
        "and mechanism of action by its ID."
    ),
)

# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("dataset://drugs")
def dataset_overview() -> str:
    """High-level overview of the drug database."""
    overview = {
        "id":          "drugs",
        "count":       len(DB),
        "ids":         sorted(DB.keys()),
        "description": "Curated drug dataset used for the MCP workshop",
    }
    return json.dumps(overview, indent=2)


@mcp.resource("drug://{drug_id}")
def get_drug_record(drug_id: str) -> Tuple[bytes, str]:
    """Full database record for a single drug."""
    record = DB.get(drug_id.upper())
    if not record:
        payload = {"error": f"Unknown drug_id: {drug_id}"}
        return json.dumps(payload).encode(), "application/json"
    payload = {"id": drug_id.upper(), **record}
    return json.dumps(payload, indent=2).encode(), "application/json"


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_drug_info(drug_id: str) -> str:
    """
    Return the name, indication, mechanism, and Lipinski compliance
    for a drug given its database ID (e.g. ERLOTINIB, IMATINIB, ASPIRIN).
    """
    rec = DB.get(drug_id.upper())
    if not rec:
        raise ValueError(f"Unknown drug_id: {drug_id!r}. "
                         f"Available: {', '.join(sorted(DB.keys()))}")
    return (
        rec["name"]
        + "\nIndication: "          + rec["indication"]
        + "\nMechanism: "           + rec["mechanism"]
        + "\nLipinski compliant: "  + str(rec.get("lipinski_compliant"))
    )


# ── Entry point ───────────────────────────────────────────────────────────────

app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
