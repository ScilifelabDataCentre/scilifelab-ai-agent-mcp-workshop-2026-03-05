# ═══════════════════════════════════════════════════════════════════════════════
# sdk_advanced_server.py
# ═══════════════════════════════════════════════════════════════════════════════
# Official MCP Python SDK version of advanced_server.py.
# Exposes all Session 1 tools + elicitation, sampling, streaming, guardrails.
#
# Run:  python sdk_advanced_server.py
# URL:  http://localhost:8501/mcp

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Tuple

import requests as http_requests
from mcp.server.fastmcp import FastMCP, Context

HERE    = Path(__file__).parent
DB_PATH = HERE / "drug_db.json"
DB: dict[str, dict[str, Any]] = json.loads(DB_PATH.read_text(encoding="utf-8"))

# RDKit (optional) ─────────────────────────────────────────────────────────────
try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

# In-memory store for sampling callbacks ──────────────────────────────────────
_pending_callbacks: dict[str, dict] = {}

# Guardrails ───────────────────────────────────────────────────────────────────
BLOCKED_COMPOUNDS = {"fentanyl", "methamphetamine", "heroin", "cocaine", "ketamine"}
MAX_CALLS_PER_TOOL = 1000
_call_counts: dict[str, int] = {}

def _check_rate_limit(tool_name: str) -> None:
    _call_counts.setdefault(tool_name, 0)
    _call_counts[tool_name] += 1
    if _call_counts[tool_name] > MAX_CALLS_PER_TOOL:
        raise ValueError(f"Rate limit exceeded for tool '{tool_name}'")

def _validate_smiles(smiles: str) -> tuple[bool, str]:
    if not smiles.strip():
        return False, "SMILES cannot be empty"
    if len(smiles) > 500:
        return False, "SMILES too long (max 500 chars)"
    if any(c in smiles for c in [" ", "\t", "\n", "<", ">"]):
        return False, "SMILES contains invalid characters"
    return True, ""

# ── FastMCP app ───────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="Drug Discovery MCP Server (Official SDK) — Advanced",
    instructions=(
        "Advanced drug discovery MCP server. Supports tool resolution, "
        "property calculation, literature search, elicitation, sampling, "
        "and streaming analysis. Input validation and rate limiting are active."
    ),
)

# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("dataset://drugs")
def dataset_overview() -> str:
    overview = {
        "id": "drugs", "count": len(DB),
        "ids": sorted(DB.keys()),
        "description": "Curated drug dataset used for the MCP workshop",
    }
    return json.dumps(overview, indent=2)


@mcp.resource("drug://{drug_id}")
def get_drug_record(drug_id: str) -> Tuple[bytes, str]:
    rec = DB.get(drug_id.upper())
    payload = {"id": drug_id.upper(), **(rec or {"error": f"Unknown: {drug_id}"})}
    return json.dumps(payload, indent=2).encode(), "application/json"


# ── Tools: basic ──────────────────────────────────────────────────────────────

@mcp.tool()
def get_drug_info(drug_id: str) -> str:
    """Return name, indication, mechanism, and Lipinski compliance for a drug."""
    _check_rate_limit("get_drug_info")
    if drug_id.lower() in BLOCKED_COMPOUNDS:
        raise ValueError(f"Compound '{drug_id}' is not available on this server.")
    rec = DB.get(drug_id.upper())
    if not rec:
        raise ValueError(f"Unknown drug_id: {drug_id!r}")
    return (
        rec["name"]
        + "\nIndication: "         + rec["indication"]
        + "\nMechanism: "          + rec["mechanism"]
        + "\nLipinski compliant: " + str(rec.get("lipinski_compliant"))
    )


@mcp.tool()
def resolve_smiles(drug_id: str) -> str:
    """Resolve a drug name or ID to its SMILES string (database first, PubChem fallback)."""
    _check_rate_limit("resolve_smiles")
    uid = drug_id.upper()
    if uid in DB:
        entry = DB[uid]
        smiles = entry.get("smiles_rdkit") or entry.get("smiles")
        return json.dumps({"drug_id": uid, "smiles": smiles, "source": "drug_db"})
    try:
        url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
               f"{drug_id}/property/IsomericSMILES/JSON")
        smiles = (http_requests.get(url, timeout=10)
                  .json()["PropertyTable"]["Properties"][0]["IsomericSMILES"])
        return json.dumps({"drug_id": drug_id, "smiles": smiles, "source": "pubchem"})
    except Exception as e:
        raise ValueError(f"Could not resolve SMILES for '{drug_id}': {e}")


@mcp.tool()
def get_properties(smiles: str) -> str:
    """
    Calculate Lipinski / physicochemical properties from a SMILES string.
    Uses pre-computed values from the database when available; falls back to RDKit.
    """
    _check_rate_limit("get_properties")
    ok, err = _validate_smiles(smiles)
    if not ok:
        raise ValueError(err)

    # Pre-computed lookup
    for did, entry in DB.items():
        if smiles in (entry.get("smiles"), entry.get("smiles_rdkit"), entry.get("smiles_pubchem")):
            props = entry.get("pre_computed_properties", {})
            if props:
                return json.dumps({
                    "smiles": smiles, "drug_id": did,
                    "properties": props,
                    "lipinski_compliant":  entry.get("lipinski_compliant"),
                    "lipinski_violations": entry.get("lipinski_violations", 0),
                    "source": "pre_computed",
                })

    # Live RDKit
    if RDKIT_AVAILABLE:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("RDKit could not parse this SMILES string")
        props = {
            "Molecular_Weight":  round(Descriptors.MolWt(mol), 2),
            "LogP":              round(Descriptors.MolLogP(mol), 2),
            "HBD":               rdMolDescriptors.CalcNumHBD(mol),
            "HBA":               rdMolDescriptors.CalcNumHBA(mol),
            "TPSA":              round(Descriptors.TPSA(mol), 1),
            "Rotatable_Bonds":   rdMolDescriptors.CalcNumRotatableBonds(mol),
            "Aromatic_Rings":    rdMolDescriptors.CalcNumAromaticRings(mol),
        }
        v = sum([props["Molecular_Weight"] > 500, props["LogP"] > 5,
                 props["HBD"] > 5, props["HBA"] > 10])
        return json.dumps({"smiles": smiles, "properties": props,
                           "lipinski_compliant": v == 0,
                           "lipinski_violations": v, "source": "rdkit"})
    raise ValueError("No pre-computed properties found and RDKit is unavailable.")


@mcp.tool()
def lit_search(query: str, max_results: int = 5) -> str:
    """Semantic search across PubMed via the LitSense API."""
    _check_rate_limit("lit_search")
    try:
        url  = "https://www.ncbi.nlm.nih.gov/research/litsense-api/api/"
        raw  = http_requests.get(url, params={"query": query, "rerank": "true"}, timeout=15).json()
        hits = (raw[:max_results] if isinstance(raw, list) else [])
        return json.dumps({
            "query":   query,
            "results": [{'title': h.get('text', 'N/A'), 'pmid': h.get('pmid', 'N/A'), 'annotations': h.get('annotations', 'N/A')} for h in hits],
            "count":   len(hits),
        })
    except Exception as e:
        raise ValueError(f"LitSense search failed: {e}")


# ── Tools: elicitation ────────────────────────────────────────────────────────

@mcp.tool()
def find_drug(drug_name: str) -> str:
    """
    Find a drug by name. Returns disambiguation options (elicitation) when
    multiple matches exist, or a list of matching IDs otherwise.
    """
    _check_rate_limit("find_drug")
    dn = drug_name.lower()

    if dn == "aspirin":
        return json.dumps({
            "result_type": "elicitation",
            "message":     "Multiple matches for 'aspirin'. Please specify:",
            "choices": [
                {"label": "Aspirin / Acetylsalicylic acid",   "value": "ASPIRIN"},
                {"label": "Aspirin-C / Effervescent variant",  "value": "ASPIRIN_C"},
            ],
        }, indent=2)

    matches = [
        {"id": did, "name": info["name"]}
        for did, info in DB.items()
        if dn in info["name"].lower()
    ]
    if matches:
        return json.dumps({"result_type": "matches", "matches": matches}, indent=2)
    raise ValueError(f"No drugs found matching '{drug_name}'")


# ── Tools: sampling ───────────────────────────────────────────────────────────

@mcp.tool()
def get_drug_hypothesis(drug_id: str) -> str:
    """
    Return a research hypothesis prompt for a given drug (sampling pattern).
    The client should pass the returned text to their LLM to generate a
    novel hypothesis.
    """
    _check_rate_limit("get_drug_hypothesis")
    rec = DB.get(drug_id.upper())
    if not rec:
        raise ValueError(f"Unknown drug_id: {drug_id!r}")

    token = str(uuid.uuid4())
    _pending_callbacks[token] = {"drug_id": drug_id.upper()}

    prompt = (
        "Based on the following drug profile, propose a novel research\n"
        "hypothesis that could lead to a new therapeutic application\n"
        "or mechanistic insight. Be specific and scientifically grounded.\n\n"
        "Drug: "        + rec["name"]        + "\n"
        "Indication: "  + rec["indication"]  + "\n"
        "Mechanism: "   + rec["mechanism"]   + "\n\n"
        "Research hypothesis:"
    )
    return json.dumps({
        "result_type":    "sampling",
        "prompt":         prompt,
        "callback_token": token,
    }, indent=2)


@mcp.tool()
def submit_hypothesis_result(callback_token: str, llm_result: str) -> str:
    """Submit the LLM-generated hypothesis back to the server."""
    if callback_token not in _pending_callbacks:
        raise ValueError("Invalid or expired callback token.")
    info = _pending_callbacks.pop(callback_token)
    return json.dumps({
        "result_type": "sampling_complete",
        "drug_id":     info["drug_id"],
        "hypothesis":  llm_result,
        "status":      "success",
    }, indent=2)


# ── Tools: streaming ──────────────────────────────────────────────────────────

@mcp.tool()
async def stream_drug_analysis(drug_id: str, ctx: Context) -> str:
    """
    Stream a step-by-step analysis log for a drug, reporting progress via
    MCP notifications so the client sees each step in real time.
    """
    _check_rate_limit("stream_drug_analysis")
    rec = DB.get(drug_id.upper())
    if not rec:
        raise ValueError(f"Unknown drug_id: {drug_id!r}")

    steps = [
        f"Loading record for {rec['name']}...",
        f"Indication: {rec['indication']}",
        f"Mechanism: {rec['mechanism']}",
        "Evaluating Lipinski compliance...",
        f"  MW       = {rec.get('pre_computed_properties', {}).get('Molecular_Weight', 'N/A')} Da",
        f"  LogP     = {rec.get('pre_computed_properties', {}).get('LogP', 'N/A')}",
        f"  HBD/HBA  = {rec.get('pre_computed_properties', {}).get('HBD', 'N/A')} / {rec.get('pre_computed_properties', {}).get('HBA', 'N/A')}",
        f"  TPSA     = {rec.get('pre_computed_properties', {}).get('TPSA', 'N/A')} Å²",
        f"Lipinski compliant: {rec.get('lipinski_compliant')}",
        "Analysis complete.",
    ]

    for i, step in enumerate(steps, 1):
        await ctx.report_progress(progress=i, total=len(steps), message=step)
        await ctx.info(f"[{i}/{len(steps)}] {step}")
        await asyncio.sleep(0.3)

    return "\n".join(steps)


# ── Entry point ───────────────────────────────────────────────────────────────

app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
