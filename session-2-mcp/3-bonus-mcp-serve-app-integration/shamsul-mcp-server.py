# shamsul_mcp_server.py — MCP Server wrapping the SciLifeLab Serve SHAMSUL Gradio app (https://shamsul.serve.scilifelab.se/)
# Uses the official MCP Python SDK (FastMCP) with SSE transport
#
# Run:  python shamsul_mcp_server.py
# URL:  http://localhost:8503/sse
#
# SHAMSUL Gradio outputs (4 elements):
#   result[0] — Gallery: 5 images per pathology [GT, LIME, SHAP, Grad-CAM, LRP]
#   result[1] — DataFrame "Original Classes": annotated ground-truth labels
#   result[2] — DataFrame "Predictions": Predicted Class, Confidence, Decision
#   result[3] — DataFrame "IoU Results per Method": class × method IoU scores

import json, os, re, shutil, time
from mcp.server.fastmcp import FastMCP

# -- Server instance -----------------------------------------------------------

mcp = FastMCP(
    "SciLifeLab Serve SHAMSUL Chest X-ray MCP Server",
    host="0.0.0.0",
    port=8503
)

# -- Guardrails ----------------------------------------------------------------

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
MAX_IMAGE_SIZE_MB = 20
MAX_CALLS = 50
call_count = 0
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
GRADIO_URL = 'https://shamsul.serve.scilifelab.se/'


def validate_image(image_path: str):
    '''Validate image before sending to Gradio. Returns (True, '') or (False, msg).'''
    if not image_path or not image_path.strip():
        return False, 'image_path cannot be empty'
    if not os.path.isfile(image_path):
        return False, f'File not found: {image_path}'
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f'Unsupported format {ext}. Use: {", ".join(ALLOWED_EXTENSIONS)}'
    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        return False, f'File too large ({size_mb:.1f} MB). Max: {MAX_IMAGE_SIZE_MB} MB'
    return True, ''


def check_rate_limit():
    global call_count
    call_count += 1
    if call_count > MAX_CALLS:
        raise ValueError(f'Rate limit exceeded ({MAX_CALLS} calls). Restart the server.')


# -- Helpers for parsing Gradio responses --------------------------------------

def caption_to_filename(caption: str, index: int) -> str:
    '''
    Convert a SHAMSUL gallery caption to a clean filename.

    Captions follow these patterns:
      "Ground Truth Image, Class: Support Devices"
      "Interpretability Prediction Image, Class: Support Devices, Interpretability Method: LIME"

    Returns e.g. "GT_Support_Devices.png" or "LIME_Support_Devices.png"
    '''
    if not caption:
        return f'image_{index}.png'

    class_match = re.search(r'Class:\s*(.+?)(?:,|$)', caption)
    class_name = class_match.group(1).strip().replace(' ', '_') if class_match else f'unknown_{index}'

    method_match = re.search(r'Interpretability Method:\s*(.+)', caption)
    if method_match:
        method = method_match.group(1).strip().replace('-', '')
        return f'{method}_{class_name}.png'
    elif 'Ground Truth' in caption:
        return f'GT_{class_name}.png'
    else:
        return f'image_{index}_{class_name}.png'


def extract_gallery_image_path(item) -> str | None:
    if isinstance(item, dict):
        img = item.get('image', item)
        if isinstance(img, dict):
            return img.get('path') or img.get('url')
        elif isinstance(img, str):
            return img
        return item.get('path')
    elif isinstance(item, (list, tuple)) and len(item) > 0:
        return item[0] if isinstance(item[0], str) else None
    elif isinstance(item, str):
        return item
    return None


def extract_gallery_caption(item) -> str:
    if isinstance(item, dict):
        return item.get('caption') or item.get('label') or ''
    elif isinstance(item, (list, tuple)) and len(item) > 1:
        return str(item[1]) if item[1] else ''
    return ''


def parse_dataframe(df_data) -> list[dict]:
    '''
    Parse a Gradio dataframe output into a list of dicts.
    Handles: pandas DataFrame, dict with headers+data, nested value dict, list of lists.
    '''
    rows = []

    if df_data is None:
        return rows

    # Handle pandas DataFrame
    if hasattr(df_data, 'iterrows'):
        headers = list(df_data.columns)
        for _, row in df_data.iterrows():
            rows.append(dict(zip(headers, row.values.tolist())))
        return rows

    if isinstance(df_data, dict):
        inner = df_data
        if 'value' in df_data and isinstance(df_data['value'], dict):
            inner = df_data['value']

        headers = inner.get('headers', [])
        data = inner.get('data', inner.get('rows', []))

        for row in data:
            if isinstance(row, (list, tuple)):
                if headers:
                    rows.append(dict(zip(headers, row)))
                else:
                    rows.append({f'col_{i}': v for i, v in enumerate(row)})
        return rows

    if isinstance(df_data, list):
        for row in df_data:
            if isinstance(row, dict):
                rows.append(row)
            elif isinstance(row, (list, tuple)):
                rows.append({f'col_{i}': v for i, v in enumerate(row)})
        return rows

    if isinstance(df_data, str):
        try:
            return parse_dataframe(json.loads(df_data))
        except (json.JSONDecodeError, ValueError):
            pass

    print(f'  [PARSE] WARNING: unrecognised dataframe format: {type(df_data).__name__}')
    return rows


# -- Gradio bridge -------------------------------------------------------------

def call_shamsul(image_path: str, study_id: str) -> dict:
    '''
    Send an X-ray image to the SHAMSUL Gradio app and parse all 4 outputs.
    '''
    from gradio_client import Client, handle_file

    client = Client(GRADIO_URL)
    result = client.predict(
        image=handle_file(image_path),
        image_name=study_id,
        api_name='/predict'
    )

    print(f'  [SHAMSUL] Result has {len(result)} elements')
    for i, item in enumerate(result):
        t = type(item).__name__
        extra = ''
        if isinstance(item, dict):
            extra = f', keys={list(item.keys())}'
        elif isinstance(item, list):
            extra = f', len={len(item)}'
        print(f'  [SHAMSUL]   result[{i}]: {t}{extra}')

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── result[0]: Gallery images ─────────────────────────────────────────
    saved_images = []
    gallery_data = result[0] if isinstance(result, (list, tuple)) and len(result) > 0 else []
    if not isinstance(gallery_data, list):
        gallery_data = []

    for i, item in enumerate(gallery_data):
        src = extract_gallery_image_path(item)
        caption = extract_gallery_caption(item)
        if src and os.path.isfile(src):
            filename = caption_to_filename(caption, i)
            dst = os.path.join(OUTPUT_DIR, filename)
            shutil.copy(src, dst)
            saved_images.append({'path': dst, 'caption': caption})

    print(f'  [GALLERY] Saved {len(saved_images)} images')

    # ── result[1]: Original Classes ───────────────────────────────────────
    original_classes_data = result[1] if len(result) > 1 else None
    original_classes = parse_dataframe(original_classes_data)
    original_class_labels = []
    for row in original_classes:
        label = row.get('Annotated Class Labels') or row.get('col_0', '')
        if label:
            original_class_labels.append(str(label))

    print(f'  [CLASSES] {original_class_labels}')

    # ── result[2]: Predictions ────────────────────────────────────────────
    predictions_data = result[2] if len(result) > 2 else None
    predictions_rows = parse_dataframe(predictions_data)
    pathology_probabilities = []
    for row in predictions_rows:
        pathology = row.get('Predicted Class') or row.get('col_0', '')
        confidence = row.get('Confidence') or row.get('col_1', 0)
        decision = row.get('Decision') or row.get('col_2', '')
        try:
            pathology_probabilities.append({
                'pathology': str(pathology),
                'probability': float(confidence),
                'decision': str(decision)
            })
        except (ValueError, TypeError) as e:
            print(f'  [PRED] Skipping row {row}: {e}')

    print(f'  [PRED] {len(pathology_probabilities)} predictions')

    # ── result[3]: IoU Results ────────────────────────────────────────────
    iou_data = result[3] if len(result) > 3 else None
    iou_rows = parse_dataframe(iou_data)
    iou_results = []
    for row in iou_rows:
        cls = row.get('Class') or row.get('col_0', '')
        method = row.get('Interpretability Method') or row.get('col_1', '')
        iou_val = row.get('IoU') or row.get('col_2', 0)
        try:
            iou_results.append({
                'class': str(cls),
                'method': str(method),
                'iou': float(iou_val)
            })
        except (ValueError, TypeError):
            pass

    print(f'  [IoU] {len(iou_results)} entries')

    return {
        'status': 'success',
        'study_id': study_id,
        'original_classes': original_class_labels,
        'pathology_probabilities': pathology_probabilities,
        'iou_results': iou_results,
        'segmentation_image_paths': [img['path'] for img in saved_images],
        'segmentation_image_details': saved_images,
        'segmentation_count': len(saved_images)
    }


# -- MCP Tool ------------------------------------------------------------------

@mcp.tool()
def analyze_xray(image_path: str, study_id: str = "unknown_study") -> str:
    """Analyse a chest X-ray image for thoracic pathologies using the SHAMSUL
    model (YOLOv8-based segmentation hosted on SciLifeLab Serve).

    Returns disease probabilities, ground-truth annotations, IoU scores per
    interpretability method, and paths to heatmap overlay images
    (Grad-CAM, LIME, SHAP, LRP).

    Args:
        image_path: Local file path to a frontal chest X-ray (JPEG or PNG).
        study_id: Exact CheXpert study path as listed in val_labels.csv
                  (e.g. CheXpert-v1.0/valid/patient64664/study1/view1_frontal.jpg).
    """
    # Rate limit
    check_rate_limit()

    # Validate image
    valid, err = validate_image(image_path)
    if not valid:
        return json.dumps({'status': 'error', 'message': err})

    # Call SHAMSUL
    try:
        print(f'  [SHAMSUL] Analysing {os.path.basename(image_path)} '
              f'(study: {study_id})...')
        t0 = time.time()
        result = call_shamsul(image_path, study_id)
        dt = time.time() - t0
        print(f'  [SHAMSUL] Done in {dt:.1f}s — '
              f'{len(result["pathology_probabilities"])} predictions, '
              f'{result["segmentation_count"]} overlays')
        return json.dumps(result, indent=2)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({'status': 'error',
                           'message': f'SHAMSUL analysis failed: {str(e)}'})


# -- Entry point ---------------------------------------------------------------

if __name__ == '__main__':
    print('SHAMSUL Chest X-ray MCP Server (FastMCP + SSE)')
    print(f'Endpoint: http://localhost:8503/sse')
    print(f'Backend:  {GRADIO_URL}')
    print(f'Output:   {OUTPUT_DIR}/')
    mcp.run(transport="sse")
