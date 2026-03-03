# Bonus: MCP Python SDK: Drug Discovery Implementation

## From Scratch to Production: The Same Server in Half the Code

---

## What This Is

In `1-mcp-from-scratch/` you built an MCP server by hand: constructing every JSON-RPC 2.0 message, routing methods through `if/elif` chains, and assembling error responses as raw dicts. That was deliberate — understanding the protocol from the ground up is the foundation of Session 2.

This bonus section re-implements everything you built using the **official MCP Python SDK** (`FastMCP`). The tools are the same, the data is the same, the behaviour is the same, but the SDK handles the protocol plumbing for you. Comparing the two approaches shows you what production MCP development looks like and how much boilerplate disappears when you move from learning to building.

> **No fill-in-the-blank tasks.** Everything here is complete and runnable. Read, run, compare.

---

## How It Connects to `1-mcp-from-scratch/`

| `1-mcp-from-scratch/` concept | How it appears here |
|---|---|
| MCP Server (Part 3) | `sdk_basic_server.py`: same `get_drug_info` tool, now via `@mcp.tool()` |
| MCP Client (Part 3) | `sdk_basic_client.py`: async SDK client replacing the `requests`-based one |
| Resources (Part 2.1) | `@mcp.resource("drug://drugs")` replaces the manual `resources/read` handler |
| Elicitation (Part 5.1, Gap 4) | Aspirin disambiguation in `sdk_advanced_server.py` |
| Sampling (Part 5.1, Gap 5) | Hypothesis prompt + optional OpenAI completion in `sdk_advanced_client.py` |
| Guardrails (Part 5.2, Gaps 6–8) | Blocked compounds, SMILES validation, rate limiting, same logic, cleaner code |
| Streaming | `sdk_advanced_server.py` reports progress step by step via `ctx.report_progress()` |
| Session 1 tools | `resolve_smiles`, `get_properties`, `lit_search`: all re-exposed via the SDK |

---

## Directory Structure

```
2-bonus-mcp-sdk-implementation/
├── README.md                    ← This file
├── drug_db.json                 ← Same drug dataset as 1-mcp-from-scratch/
├── sdk_basic_server.py          ← Resources + get_drug_info via @mcp.resource / @mcp.tool
├── sdk_basic_client.py          ← Async SDK client: list resources, read records, call tools
├── sdk_advanced_server.py       ← All Session 1 tools + elicitation, sampling, streaming, guardrails
└── sdk_advanced_client.py       ← Full demo: elicitation flow, sampling with OpenAI, streaming progress
```

---

## Prerequisites

You need the Session 2 virtual environment (the same one used for `1-mcp-from-scratch/`).

The advanced client calls OpenAI for the sampling demo. Your `.env` file should contain:

```
OPENAI_API_KEY="sk-your-key-here"
```

The start script writes this automatically if you passed the key via `docker run -e`. Otherwise, edit the `.env` file in this directory.

---

## Quick Start

### Basic server + client

```bash
# Terminal 1
python sdk_basic_server.py        # → http://localhost:8501/mcp

# Terminal 2
python sdk_basic_client.py
```

**Expected output from the client:**

```
Basic session initialised.

1. Resources:
   drug://drugs — Drug Discovery Database

2. Reading drug://drugs:
   Found 8 compounds: ASPIRIN, IBUPROFEN, ERLOTINIB, ...

3. get_drug_info(ERLOTINIB):
   Erlotinib (Tarceva)
   Indication: Non-small cell lung cancer (NSCLC), pancreatic cancer
   Mechanism: Selective reversible inhibitor of EGFR tyrosine kinase...
   Lipinski compliant: True
```

### Advanced server + client

```bash
# Terminal 1 (stop the basic server first)
python sdk_advanced_server.py     # → http://localhost:8501/mcp

# Terminal 2
python sdk_advanced_client.py
```

**Expected output includes:**

```
1. resolve_smiles(ERLOTINIB)
   {"drug_id": "ERLOTINIB", "smiles": "C#Cc1cccc(Nc2ncnc3cc(OCCO)c(OCCO)cc23)c1", ...}

2. get_properties(erlotinib SMILES)
   {"smiles": "C#Cc1cccc...", "properties": {"Molecular_Weight": 393.44, ...}, ...}

3. find_drug(aspirin)  [elicitation]
   Server asks for clarification: Multiple matches for 'aspirin'...
   Auto-selecting: ASPIRIN

4. get_drug_hypothesis(IMATINIB)  [sampling]
   Prompt (first 160 chars): Based on the following drug profile, propose a novel...
   LLM hypothesis: ...

5. stream_drug_analysis(DASATINIB)  [streaming + progress]
   ...

6. Guardrail — blocked compound (heroin)
   Correctly blocked: ...

7. Guardrail — empty SMILES
   Correctly rejected: ...

8. lit_search — EGFR inhibitors
   5 result(s):
   ...
```

> ⚠️ Both basic and advanced servers use port **8501**. Stop one before starting the other. Also stop any `basic_server.py` or `advanced_server.py` from `1-mcp-from-scratch/` if they are using the same port.

---

## File Descriptions

### `sdk_basic_server.py`

The same basic server from Part 3, re-implemented with `FastMCP`. Exposes one resource (`drug://drugs`) and one tool (`get_drug_info`).

**What changes:** no `@app.route`, no `handle_mcp` function, no `jsonify({"jsonrpc": "2.0", ...})`. Tools are plain Python functions with a `@mcp.tool()` decorator. Resources use `@mcp.resource("drug://drugs")`. The SDK generates `inputSchema` from type hints and builds all JSON-RPC responses automatically.

### `sdk_basic_client.py`

An async client using the official `ClientSession` and `streamablehttp_client` transport. Replaces the synchronous `requests`-based `MCPClient` class from Part 3.

### `sdk_advanced_server.py`

The full advanced server from Part 5, re-implemented with the SDK. Exposes all six tools (`get_drug_info`, `resolve_smiles`, `get_properties`, `lit_search`, `find_drug`, `get_drug_hypothesis`) plus a streaming tool (`stream_drug_analysis`) and all three guardrail layers (blocked compounds, SMILES validation, rate limiting).

### `sdk_advanced_client.py`

A comprehensive demo client that exercises every feature: resolves SMILES, calculates properties, triggers elicitation (aspirin disambiguation), requests a sampling prompt and optionally completes it with OpenAI, runs a streaming analysis with progress reporting, tests both guardrails, and performs a literature search.

---

## SDK vs Scratch: What Changes?

Open your `1-mcp-from-scratch/basic_server.py` and this directory's `sdk_basic_server.py` side by side. Here is what you will notice:

| Aspect | Your scratch server (Flask) | SDK server (FastMCP) |
|---|---|---|
| Protocol handling | You build every JSON-RPC dict by hand | Automatic — SDK handles it |
| Tool registration | `elif tool_name == '...'` dispatch chain | `@mcp.tool()` decorator |
| Resource registration | `elif method == 'resources/read'` | `@mcp.resource("uri://{param}")` |
| Error responses | `{"code": -32602, "message": ...}` | `raise ValueError(...)` |
| Input validation | Manual `arguments.get(...)` | Type hints + automatic validation |
| Transport | Raw HTTP via Flask routes | `mcp.streamable_http_app()` + uvicorn |
| Progress reporting | Not available | `await ctx.report_progress(...)` |
| Lines of code (basic) | ~110 lines | ~40 lines |

**What to look for:**

1. **No `@app.route` or `handle_mcp` function** — the SDK routes methods automatically
2. **No `jsonify({"jsonrpc": "2.0", ...})` anywhere** — the SDK builds responses for you
3. **Tools are just Python functions** with a decorator — the SDK generates the `inputSchema` from type hints
4. **Errors are just exceptions** — `raise ValueError("Drug not found")` becomes a proper JSON-RPC error

---

## Advanced Features Demonstrated

### Elicitation (disambiguation)
When a user searches for "aspirin", the `find_drug` tool returns multiple candidate IDs with descriptions so the user (or LLM) can clarify which one they want. This is the same pattern as Gap 4 in Part 5.1.

### Sampling (server → LLM)
The `get_drug_hypothesis` tool returns a structured prompt containing the drug's profile. The client passes this prompt to OpenAI to generate a research hypothesis. This is the same pattern as Gap 5 in Part 5.1, but here the full round-trip (server → client → LLM → callback) is demonstrated end to end.

### Streaming with progress
The `stream_drug_analysis` tool performs a multi-step analysis and reports progress at each stage via `ctx.report_progress()`. The client sees intermediate updates as the analysis runs — useful for long-running operations like docking simulations or large batch analyses.

### Guardrails
The same safety logic from Part 5.2: blocked compounds (Gap 7), SMILES validation (Gap 6), and rate limiting (Gap 8) — implemented with cleaner code since the SDK handles error formatting.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'mcp'`:** Make sure you are using the Session 2 virtual environment where `mcp>=1.0` is installed (check `requirements.txt`).

**`Address already in use` on port 8501:** Stop any other server using that port. Run `lsof -i :8501` (Linux/macOS) or `netstat -ano | findstr 8501` (Windows) to find and kill the process.

**Sampling demo shows `(Set OPENAI_API_KEY to see the LLM complete the hypothesis)`:** Edit `.env` in this directory to add your key, or re-run the Docker container with `-e OPENAI_API_KEY="sk-..."`.

---

## Further Reading

- [Official MCP documentation](https://modelcontextprotocol.io/)
- [MCP Python SDK on GitHub](https://github.com/modelcontextprotocol/python-sdk)
- [Hugging Face MCP course](https://huggingface.co/learn/mcp-course/en/unit1/introduction)