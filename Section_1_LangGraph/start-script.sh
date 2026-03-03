#!/bin/bash
set -e

# Write .env from environment variable if provided
if [ -n "$OPENAI_API_KEY" ]; then
    echo "OPENAI_API_KEY=\"$OPENAI_API_KEY\"" > /home/workshop/app/.env
    echo "✓ OPENAI_API_KEY written to .env"
else
    echo "⚠  No OPENAI_API_KEY set."
fi

echo ""
echo "============================================================"
echo "  SciLifeLab MCP Workshop — Session 1"
echo "  Open: http://localhost:8888"
echo "============================================================"
echo ""

python -m jupyter lab \
    --ip=0.0.0.0 \
    --port=8888 \
    --no-browser \
    --NotebookApp.token='' \
    --NotebookApp.password='' \
    --notebook-dir=/home/workshop/app