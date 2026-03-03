# Developing AI Agents in Life Sciences

## Hands-on Session 2: AI Agent Collaboration with the Model Context Protocol (MCP)

> **SciLifeLab Data Centre** · Stockholm · 2026-03-05

---

## What you will build

In this session you expose the drug discovery tools from Session 1 over the **Model Context Protocol (MCP)**, a standardised layer that lets any AI application discover and call your tools dynamically. You will build an MCP server from scratch, add guardrails and security, and connect your LangGraph agent to it.

The workshop has three parts:

| Directory | What's inside | Type |
|---|---|---|
| `1-mcp-from-scratch/` | Main workshop notebook with 11 fill-in-the-blank gaps | **Core session** |
| `2-bonus-mcp-sdk-implementation/` | Same server re-implemented with the official MCP Python SDK | Optional bonus |
| `3-bonus-mcp-serve-app-integration/` | Wrapping a deployed SciLifeLab Serve ML model as an MCP server | Optional bonus |

Each directory has its own README with detailed instructions.

---

## Getting started

You need an **OpenAI API key**. Have it ready before you start.

### Option 1: Pull from Docker Hub (recommended)

Everything is pre-installed. One command to start:

```bash
docker run -p 7860:7860 -e OPENAI_API_KEY="sk-..." mahbub1969/scilifelab-mcp-workshop:v1
```

Then open **http://localhost:7860** in your browser and navigate to `1-mcp-from-scratch/mcp_workshop.ipynb`.

### Option 2: Build the image locally

```bash
# From the session-2-mcp/ directory
docker build -t scilifelab-mcp-workshop:v1 .
docker run -p 7860:7860 -e OPENAI_API_KEY="sk-..." scilifelab-mcp-workshop:v1
```

Then open **http://localhost:7860** as above.

### Option 3: Deploy on SciLifeLab Serve (after the workshop)

> This option is for **after the workshop**, if you want to revisit the material or share it with colleagues without installing Docker locally. During the session, use Option 1 or 2.

If you are affiliated with a Swedish research institution, you can deploy this as a persistent app on [SciLifeLab Serve](https://serve.scilifelab.se/). Create a **Custom app**, set the image to `mahbub1969/scilifelab-mcp-workshop:v1`, port `7860`, and provide your API key in the `.env` file after.

For questions about Serve deployment, contact the SciLifeLab Serve team at **serve@scilifelab.se**.

---

## Running locally without Docker (not supported during the workshop)

> ⚠️ **During the workshop we will only support the Docker-based setup above.** The local option is provided for your own reference after the session. We will not troubleshoot local environment issues during workshop time due to time constraints.

If you prefer to run without Docker:

```bash
# From the session-2-mcp/ directory
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Add your API key
echo 'OPENAI_API_KEY="sk-..."' > 1-mcp-from-scratch/.env
echo 'OPENAI_API_KEY="sk-..."' > 2-bonus-mcp-sdk-implementation/.env
echo 'OPENAI_API_KEY="sk-..."' > 3-bonus-mcp-serve-app-integration/.env

# Open the notebook
cd 1-mcp-from-scratch/
jupyter lab
```

You will need Python 3.10+ and all packages listed in `requirements.txt`. RDKit is optional — the workshop falls back to pre-computed properties if it is not available.

---

## Directory structure

```
session-2-mcp/
├── README.md                              ← This file
├── Dockerfile
├── requirements.txt
├── start-script.sh
├── jupyter_lab_config.py
│
├── 1-mcp-from-scratch/                    ← Main workshop (start here)
│   ├── README.md
│   ├── mcp_workshop.ipynb                 ← Your main notebook
│   ├── mcp_workshop_answers.ipynb         ← Reference answers
│   ├── drug_db.json
│   ├── images/
│   └── ...
│
├── 2-bonus-mcp-sdk-implementation/        ← SDK bonus (optional)
│   ├── README.md
│   ├── sdk_basic_server.py
│   ├── sdk_advanced_server.py
│   └── ...
│
└── 3-bonus-mcp-serve-app-integration/     ← Serve app bonus (optional)
    ├── README.md
    ├── shamsul-mcp-server.py
    ├── agent-mediator.py
    └── ...
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Docker: `port is already allocated` | Stop any process using port 7860, or use `-p 8888:7860` and open port 8888 instead |
| Jupyter shows but no notebooks appear | Navigate into `1-mcp-from-scratch/` in the Jupyter file browser |
| OpenAI 401 / authentication error | Check that you passed `-e OPENAI_API_KEY="sk-..."` when starting the container |
| `Address already in use` on 8501/8502 | Another server is running on that port — stop it first (see the notebook README) |

For other issues, see the README inside each subdirectory.