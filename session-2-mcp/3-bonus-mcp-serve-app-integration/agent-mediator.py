# agent_mediator.py LangGraph agent that uses MCP for chest X-ray diagnosis
# Uses the official MCP Python SDK (SSE transport) to call the SciLifeLab Serve SHAMSUL Gradio app (https://shamsul.serve.scilifelab.se/) server
#
# Run:  python agent_mediator.py --image example.jpg --study-id "CheXpert-v1.0/valid/patient64664/study1/view1_frontal.jpg"
#
# Requires: shamsul_mcp_server.py running on port 8503

import argparse
import asyncio
import json
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END

from mcp import ClientSession
from mcp.client.sse import sse_client

load_dotenv(override=True)

# -- Configuration -------------------------------------------------------------

MCP_SSE_URL = 'http://localhost:8503/sse'


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], 'Conversation messages']
    image_path: Annotated[str, 'Local path to the X-ray image']
    study_id: Annotated[str, 'Exact CheXpert study path required by SHAMSUL app']
    analysis: Annotated[dict, 'Objective data from the SHAMSUL tool']


# LLM with tool binding (same model as Session 2)
llm = ChatOpenAI(model='gpt-4o', temperature=0)

TOOL_SCHEMA = {
    'name': 'analyze_xray',
    'description': (
        'Analyse a chest X-ray image for thoracic pathologies. '
        'Returns prediction probabilities and interpretability heatmaps. '
        'MUST be called before making any diagnostic statement.'
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'image_path': {'type': 'string', 'description': 'Path to the X-ray'},
            'study_id': {'type': 'string', 'description': 'Study identifier'}
        },
        'required': ['image_path']
    }
}

llm_with_tools = llm.bind_tools([TOOL_SCHEMA])


# -- MCP helper using the official SDK -----------------------------------------

async def mcp_call(tool_name: str, arguments: dict) -> dict:
    '''Call a tool on the MCP server using the official MCP Python SDK.'''
    async with sse_client(MCP_SSE_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return json.loads(result.content[0].text)


# -- Workflow nodes ------------------------------------------------------------

async def mediator_node(state: AgentState):
    '''
    Node 1: The LLM reads the user query and decides to call analyze_xray.
    '''
    print('[AGENT] Mediator: evaluating query...')
    response = llm_with_tools.invoke(state['messages'])
    return {'messages': state['messages'] + [response]}


async def tool_execution_node(state: AgentState):
    '''
    Node 2: Execute the tool via the MCP server (SSE transport via SDK).
    '''
    last_msg = state['messages'][-1]

    # Extract tool call from LLM response
    if not hasattr(last_msg, 'tool_calls') or not last_msg.tool_calls:
        print('[AGENT] Warning: LLM did not request a tool call. Forcing analysis...')
        tool_args = {'image_path': state['image_path'], 'study_id': state['study_id']}
        tool_call_id = 'forced_call'
    else:
        tc = last_msg.tool_calls[0]
        tool_args = tc['args']
        tool_call_id = tc['id']
        if 'image_path' not in tool_args or not tool_args['image_path']:
            tool_args['image_path'] = state['image_path']
        tool_args['study_id'] = state['study_id']

    print('[AGENT] Tool node: calling analyze_xray via MCP (SDK)...')
    print(f'        Image: {tool_args.get("image_path")}')
    print(f'        Study: {tool_args.get("study_id")}')
    print('        (Waiting for SHAMSUL — this may take a moment)\n')

    data = await mcp_call('analyze_xray', tool_args)

    # Print findings for human review
    print('=' * 60)
    print('  SHAMSUL ANALYSIS — OBJECTIVE FINDINGS')
    print('=' * 60)

    if data.get('status') == 'success':
        classes = data.get('original_classes', [])
        if classes:
            print('\n  Ground-Truth Annotated Classes:')
            for cls in classes:
                print(f'    • {cls}')

        probs = data.get('pathology_probabilities', [])
        if probs:
            print('\n  Model Predictions:')
            for p in probs:
                conf = p['probability'] * 100
                decision = p.get('decision', '')
                marker = ' ✓' if decision == 'Correct' else ' ✗'
                flag = ' ◀ HIGH' if conf > 50 else ''
                print(f'    {p["pathology"]:30s} {conf:5.1f}%  {decision}{marker}{flag}')
        else:
            print('  WARNING: No predictions returned.')

        iou = data.get('iou_results', [])
        if iou:
            print('\n  Interpretability IoU Scores:')
            for entry in iou:
                print(f'    {entry["class"]:25s}  {entry["method"]:10s}  IoU: {entry["iou"]:.2f}')

        images = data.get('segmentation_image_details', [])
        if images:
            print('\n  Saved {len(images)} visualisation images:')
            for img in images[:5]:
                print(f'    {os.path.basename(img["path"]):40s}  {img.get("caption", "")[:60]}')
            if len(images) > 5:
                print(f'    ... and {len(images) - 5} more')
    else:
        print(f'  Error: {data.get("message", "Unknown error")}')

    print('=' * 60 + '\n')

    tool_message = ToolMessage(
        content=json.dumps(data),
        tool_call_id=tool_call_id
    )
    return {
        'messages': state['messages'] + [tool_message],
        'analysis': data
    }


async def diagnosis_node(state: AgentState):
    '''
    Node 3: The LLM synthesises a diagnosis grounded ONLY in the tool data.
    '''
    print('[AGENT] Diagnosis node: synthesising grounded diagnosis...\n')

    analysis = state.get('analysis', {})
    probs = analysis.get('pathology_probabilities', [])
    classes = analysis.get('original_classes', [])
    iou = analysis.get('iou_results', [])

    system = SystemMessage(content=(
        'You are an expert radiologist assistant. Your role is to help doctors '
        'interpret objective findings from a thoracic disease segmentation model. '
        'You must ONLY reference the probability data provided — never invent or '
        'assume findings not present in the data. Highlight any pathology with '
        'probability above 50%. Note that these are model predictions and final '
        'clinical decisions require physician review.'
    ))

    user = HumanMessage(content=(
        f'Original query: {state["messages"][0].content}\n\n'
        f'GROUND-TRUTH ANNOTATED CLASSES:\n{json.dumps(classes, indent=2)}\n\n'
        f'MODEL PREDICTIONS from SHAMSUL:\n{json.dumps(probs, indent=2)}\n\n'
        f'INTERPRETABILITY IoU SCORES:\n{json.dumps(iou, indent=2)}\n\n'
        f'Please provide a structured assessment based on these findings.'
    ))

    diagnosis = llm.invoke([system, user])
    return {'messages': state['messages'] + [diagnosis]}


# -- Compile graph -------------------------------------------------------------

def build_graph():
    '''Build the LangGraph workflow, same pattern as Session 1.'''
    wf = StateGraph(AgentState)
    wf.add_node('mediator', mediator_node)
    wf.add_node('tool', tool_execution_node)
    wf.add_node('diagnosis', diagnosis_node)

    wf.set_entry_point('mediator')
    wf.add_edge('mediator', 'tool')
    wf.add_edge('tool', 'diagnosis')
    wf.add_edge('diagnosis', END)

    return wf.compile()


# -- Entry point ---------------------------------------------------------------

async def run(image_path: str, study_id: str, query: str | None = None):
    if query is None:
        query = (
            'Analyse this frontal chest X-ray. '
            'Does the patient show signs of cardiomegaly or airspace opacity or support devices? '
            'Provide a structured assessment.'
        )

    print(f'[USER QUERY]: {query}')
    print(f'[IMAGE]:       {image_path}')
    print(f'[STUDY ID]:    {study_id}\n')

    # Quick connectivity check via SDK
    try:
        async with sse_client(MCP_SSE_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print(f'[AGENT] Connected to MCP server at {MCP_SSE_URL}\n')
    except Exception as e:
        print(f'ERROR: Cannot connect to MCP server at {MCP_SSE_URL}')
        print(f'       {e}')
        print('Start it first: python gradio_mcp_server.py')
        return

    graph = build_graph()

    async for event in graph.astream({
        'messages': [HumanMessage(content=query)],
        'image_path': os.path.abspath(image_path),
        'study_id': study_id,
        'analysis': {}
    }):
        if 'diagnosis' in event:
            final = event['diagnosis']['messages'][-1].content
            print('─' * 60)
            print('FINAL DIAGNOSIS:')
            print('─' * 60)
            print(final)
            print('─' * 60)


def main():
    parser = argparse.ArgumentParser(description='SHAMSUL LangGraph Agent (MCP SDK)')
    parser.add_argument('--image', required=True, help='Path to chest X-ray')
    parser.add_argument('--study-id', default='unknown_study',
                        help='CheXpert study path '
                             '(e.g. CheXpert-v1.0/valid/patient64664/study1/view1_frontal.jpg)')
    parser.add_argument('--query', default=None, help='Custom query (optional)')
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        print(f'ERROR: Image not found: {args.image}')
        return

    asyncio.run(run(args.image, args.study_id, args.query))


if __name__ == '__main__':
    main()
