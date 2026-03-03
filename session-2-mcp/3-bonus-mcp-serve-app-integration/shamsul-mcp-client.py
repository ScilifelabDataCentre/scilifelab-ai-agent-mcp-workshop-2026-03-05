# shamsul_mcp_client.py — Standalone MCP client for the SciLifeLab Serve SHAMSUL Gradio app (https://shamsul.serve.scilifelab.se/) server
# Uses the official MCP Python SDK with SSE transport
#
# Run:  python shamsul_mcp_client.py --image example.jpg --study-id "CheXpert-v1.0/valid/patient64664/study1/view1_frontal.jpg"

import argparse
import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.sse import sse_client


async def run(image_path: str, study_id: str, server_url: str):
    print('=== SHAMSUL MCP Client (SDK) ===\n')

    # 1. Connect via SSE
    print('1. Connecting to MCP server...')
    async with sse_client(server_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f'   Connected to: {server_url}\n')

            # 2. Discover tools
            print('2. Discovering tools...')
            tools_result = await session.list_tools()
            for t in tools_result.tools:
                print(f'   {t.name}: {t.description[:70]}...\n')

            # 3. Call analyze_xray
            print('3. Calling analyze_xray...')
            print(f'   Sending image: {os.path.basename(image_path)}')
            print(f'   Study ID: {study_id}')
            print('   (This may take 30-60s on first call while the model loads)\n')

            result = await session.call_tool('analyze_xray', {
                'image_path': image_path,
                'study_id': study_id
            })

            # 4. Parse and display results
            # The tool returns a single text content block with JSON
            raw_text = result.content[0].text
            data = json.loads(raw_text)

            if data.get('status') != 'success':
                print(f'   Analysis failed: {data.get("message", data)}')
                return

            print('4. Results:')

            # Original annotated classes
            classes = data.get('original_classes', [])
            if classes:
                print('\n   Ground-Truth Annotated Classes:')
                for cls in classes:
                    print(f'     • {cls}')

            # Predictions (from result[2] of Gradio output)
            print('\n   Model Predictions:')
            for p in data.get('pathology_probabilities', []):
                name = p['pathology']
                conf = p['probability'] * 100
                decision = p.get('decision', '')
                bar = '█' * int(conf / 5) + '░' * (20 - int(conf / 5))
                marker = ' ✓' if decision == 'Correct' else ' ✗'
                print(f'     {name:30s} {conf:5.1f}%  {bar}  {decision}{marker}')

            # IoU results
            iou = data.get('iou_results', [])
            if iou:
                print('\n   Interpretability IoU Scores:')
                for entry in iou:
                    print(f'     {entry["class"]:25s}  {entry["method"]:10s}  IoU: {entry["iou"]:.2f}')

            # Saved images (with proper names from gallery captions)
            images = data.get('segmentation_image_details', [])
            if images:
                print(f'\n   Segmentation images saved ({len(images)} total):')
                for img in images:
                    fname = os.path.basename(img['path'])
                    caption = img.get('caption', '')
                    print(f'     {fname:45s}  {caption[:60]}')
            else:
                print('\n   (No segmentation images returned)')

            print('\nDone.')


def main():
    parser = argparse.ArgumentParser(description='SHAMSUL APP MCP Client (SDK)')
    parser.add_argument('--image', required=True, help='Path to chest X-ray image')
    parser.add_argument('--study-id', required=True,
                        help='Exact CheXpert study path '
                             '(e.g. CheXpert-v1.0/valid/patient64664/study1/view1_frontal.jpg)')
    parser.add_argument('--server', default='http://localhost:8503/sse',
                        help='MCP server SSE URL')
    args = parser.parse_args()

    image_path = os.path.abspath(args.image)
    if not os.path.isfile(image_path):
        print(f'ERROR: Image not found: {image_path}')
        return

    asyncio.run(run(image_path, args.study_id, args.server))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        if 'Connect' in type(e).__name__ or 'refused' in str(e).lower():
            print('ERROR: Could not connect to server.')
            print('Make sure shamsul_mcp_server.py is running: python shamsul_mcp_server.py')
        else:
            raise
