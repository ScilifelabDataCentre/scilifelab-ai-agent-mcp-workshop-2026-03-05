#!/bin/bash
set -e

REPO_DIR=/home/workshop/app/repo

# Subdirectories that need .env access
SUBDIRS=(
    "$REPO_DIR/1-mcp-from-scratch"
    "$REPO_DIR/2-bonus-mcp-sdk-implementation"
    "$REPO_DIR/3-bonus-mcp-serve-app-integration"
)

# Write .env from environment variable if provided
if [ -n "$OPENAI_API_KEY" ]; then
    ENV_CONTENT="OPENAI_API_KEY=\"$OPENAI_API_KEY\""
    echo "✓ OPENAI_API_KEY provided"
else
    ENV_CONTENT="OPENAI_API_KEY=\"sk-REPLACE-ME-with-your-real-key\""
    echo "⚠  No OPENAI_API_KEY set. Parts 5.3 and 6 require it."
    echo "   Edit the .env file in any subdirectory to add your key."
fi

# Write to repo root
echo "$ENV_CONTENT" > "$REPO_DIR/.env"
echo "  .env written to $REPO_DIR/"

# Write to each subdirectory so scripts run from there can find it
for dir in "${SUBDIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "$ENV_CONTENT" > "$dir/.env"
        echo "  .env written to $dir/"
    else
        echo "⚠  Directory not found, skipping: $dir"
    fi
done

echo ""
echo "============================================================"
echo "  Developing AI Agents in Life Sciences, Hands-on Session 2:"
echo "  AI agent collaboration with the Model Context Protocol (MCP)"
echo "  2026-03-05"
echo "  Open: http://localhost:7860"
echo "  Then open: 1-mcp-from-scratch/mcp_workshop.ipynb"
echo "============================================================"
echo ""

python3 -m jupyter lab \
    --ip=0.0.0.0 \
    --port=7860 \
    --no-browser \
    --NotebookApp.token='' \
    --NotebookApp.password='' \
    --notebook-dir="$REPO_DIR"