"""
Handwritten Spreadsheet OCR Application

Environment Variables:
- OLLAMA_HOST: Ollama server URL (default: http://localhost:11434)
- OLLAMA_USERNAME: Basic auth username (optional)
- OLLAMA_PASSWORD: Basic auth password (optional)
- OLLAMA_MODEL: Model to use for OCR processing (default: llama3.2-vision)

Create a .env file in the project root with these variables to configure
external Ollama endpoints with authentication.
"""

from flask import Flask, request, jsonify, render_template, send_file, Response, session, redirect, url_for
from functools import wraps
import ollama
import json
import csv
import os
import base64
import requests
from io import StringIO
from datetime import datetime
import logging
from collections import OrderedDict
from dotenv import load_dotenv

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Load environment variables from .env file
load_dotenv()

# Secret key for session management (set in .env)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())

# Password from environment variable
APP_PASSWORD = os.getenv('APP_PASSWORD', 'change-me-in-production')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ollama configuration from environment variables
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_USERNAME = os.getenv('OLLAMA_USERNAME', '')
OLLAMA_PASSWORD = os.getenv('OLLAMA_PASSWORD', '')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5vl:7b')

# Authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def create_ollama_client(host=None):
    """Create an Ollama client with optional basic auth"""
    client_host = host or OLLAMA_HOST
    
    # Prepare headers for authentication
    headers = {}
    
    # Use basic auth if username/password provided
    if OLLAMA_USERNAME and OLLAMA_PASSWORD:
        auth_string = f"{OLLAMA_USERNAME}:{OLLAMA_PASSWORD}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        headers['Authorization'] = f'Basic {auth_b64}'
        logger.info(f"Created Ollama client with basic auth for host: {client_host}")
    else:
        logger.info(f"Created Ollama client without auth for host: {client_host}")
    
    # Create client with custom host and headers
    if headers:
        client = ollama.Client(host=client_host, headers=headers)
    else:
        client = ollama.Client(host=client_host)
    
    return client

def try_extract_json(content):
    """Try to extract valid JSON from content"""
    import json
    import re
    
    # First try: look for JSON in markdown code blocks
    json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(json_pattern, content, re.DOTALL)
    
    for json_str in matches:
        try:
            return json.loads(json_str.strip())
        except json.JSONDecodeError:
            continue
    
    # Second try: find JSON object by looking for { and }
    start = content.find('{')
    if start != -1:
        end = content.rfind('}')
        if end > start:
            json_str = content[start:end+1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
    
    # Third try: parse entire content as JSON
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass
    
    return None

def reorder_columns(data_rows, confidence_rows, desired_order):
    """
    Reorder columns in data and confidence arrays to match specified order.
    
    Args:
        data_rows: List of dicts with extracted data
        confidence_rows: List of dicts with confidence scores
        desired_order: List of column names in desired order
    
    Returns:
        Tuple of (reordered_data_rows, reordered_confidence_rows)
    """
    if not data_rows or not desired_order:
        return data_rows, confidence_rows
    
    # Normalize desired order to lowercase for case-insensitive matching
    desired_order_lower = [col.lower().strip() for col in desired_order]
    
    # Build mapping from extracted columns to desired order
    extracted_columns = list(data_rows[0].keys())
    
    # Create mapping: for each desired column, find matching extracted column
    column_mapping = {}
    for desired_col in desired_order_lower:
        # Try exact match first
        if desired_col in [col.lower().strip() for col in extracted_columns]:
            # Find the original case version
            for extracted_col in extracted_columns:
                if extracted_col.lower().strip() == desired_col:
                    column_mapping[desired_col] = extracted_col
                    break
        else:
            # Try partial/fuzzy matching (e.g., "support for association" matches "Support for Tenant Association")
            # Check if desired column is a substring of any extracted column
            found = False
            for extracted_col in extracted_columns:
                extracted_col_lower = extracted_col.lower().strip()
                # Check if desired_col is contained in extracted_col or vice versa
                if desired_col in extracted_col_lower or extracted_col_lower in desired_col:
                    column_mapping[desired_col] = extracted_col
                    found = True
                    logger.info(f"Fuzzy matched '{desired_col}' to '{extracted_col}'")
                    break
            
            if not found:
                # No match found, will use empty string
                logger.warning(f"No match found for desired column: '{desired_col}'")
                column_mapping[desired_col] = None
    
    # Find any unmapped columns
    mapped_extracted_cols = set(column_mapping.values())
    unmapped_cols = [col for col in extracted_columns if col not in mapped_extracted_cols]
    
    # Create mapping from lowercase to original case from desired_order
    desired_order_original = {}
    for i, col in enumerate(desired_order):
        desired_order_original[col.lower().strip()] = col
    
    # Reorder data rows
    reordered_data = []
    reordered_confidence = []
    
    for i, row in enumerate(data_rows):
        new_row = OrderedDict()
        new_confidence_row = OrderedDict()
        
        # Add columns in desired order (use original case from desired_order)
        for desired_col_lower in desired_order_lower:
            desired_col_original = desired_order_original[desired_col_lower]
            extracted_col = column_mapping.get(desired_col_lower)
            if extracted_col and extracted_col in row:
                new_row[desired_col_original] = row[extracted_col]
            else:
                new_row[desired_col_original] = ""
            
            # Same for confidence
            if confidence_rows and i < len(confidence_rows):
                if extracted_col and extracted_col in confidence_rows[i]:
                    new_confidence_row[desired_col_original] = confidence_rows[i][extracted_col]
                else:
                    new_confidence_row[desired_col_original] = 0.0
        
        # Add any unmapped columns at the end
        for unmapped_col in unmapped_cols:
            new_row[unmapped_col] = row[unmapped_col]
            if confidence_rows and i < len(confidence_rows):
                new_confidence_row[unmapped_col] = confidence_rows[i].get(unmapped_col, 0.0)
        
        reordered_data.append(new_row)
        reordered_confidence.append(new_confidence_row)
    
    logger.info(f"Reordered columns to match specified order: {desired_order}")
    
    # Debug: Log the first row's keys to verify order
    if reordered_data:
        logger.info(f"First row keys after reordering: {list(reordered_data[0].keys())}")
    
    return reordered_data, reordered_confidence

def extract_and_format_csv(image_data, columns, instructions, ollama_client, model=None):
    """Single-step OCR and CSV formatting - Extract and format data in one call"""
    logger.info("=== Single-step OCR and CSV formatting ===")
    
    # We always use auto-detect mode now - let LLM find all columns
    # Column specification is only used for reordering at the end
    column_list = []  # Empty - always auto-detect
    auto_detect_mode = True
    
    if auto_detect_mode:
        logger.info("Using auto-detect mode - will detect headers from image")
        extraction_prompt = f"""Perform Optical Character Recognition (OCR) on this handwritten spreadsheet image and convert it directly to CSV format.

Your task is to:
1. Read and extract ALL text content from the image
2. Identify table structure, rows, and columns
3. Detect the header row and use those as column names
4. Return properly formatted CSV data with confidence scores

{f"Additional instructions: {instructions}" if instructions else ""}

Return ONLY valid JSON in this format (use the actual headers detected from the image):
{{"data": [
    {{"header1": "value1", "header2": "value2", "header3": "value3", "header4": "value4"}},
    {{"header1": "value5", "header2": "value6", "header3": "value7", "header4": "value8"}}
], "confidence": [
    {{"header1": 0.95, "header2": 0.87, "header3": 0.92, "header4": 0.78}},
    {{"header1": 0.89, "header2": 0.93, "header3": 0.85, "header4": 0.91}}
]}}

Rules:
- Extract text accurately from the handwritten content
- Use the actual column headers found in the image
- Clean and format the data appropriately
- Provide confidence scores (0.0-1.0) for each cell based on text clarity and legibility
- Higher scores (0.8+) for clear, well-formed text
- Lower scores (0.5-0.7) for unclear, smudged, or ambiguous text
- Very low scores (0.0-0.4) for illegible or missing text
- Return ONLY the JSON object, no explanations"""
    else:
        logger.info(f"Using specify mode - forcing headers: {', '.join(column_list)}")
        extraction_prompt = f"""Perform Optical Character Recognition (OCR) on this handwritten spreadsheet image and convert it directly to CSV format.

Your task is to:
1. Read and extract ALL text content from the image
2. Identify table structure, rows, and columns
3. Map the extracted data to the specified column names
4. Return properly formatted CSV data with confidence scores

Required columns: {', '.join(column_list)}
{f"Additional instructions: {instructions}" if instructions else ""}

Return ONLY valid JSON in this format:
{{"data": [
    {{"{column_list[0]}": "value1", "{column_list[1]}": "value2", "{column_list[2]}": "value3", "{column_list[3]}": "value4"}},
    {{"{column_list[0]}": "value5", "{column_list[1]}": "value6", "{column_list[2]}": "value7", "{column_list[3]}": "value8"}}
], "confidence": [
    {{"{column_list[0]}": 0.95, "{column_list[1]}": 0.87, "{column_list[2]}": 0.92, "{column_list[3]}": 0.78}},
    {{"{column_list[0]}": 0.89, "{column_list[1]}": 0.93, "{column_list[2]}": 0.85, "{column_list[3]}": 0.91}}
]}}

Rules:
- Extract text accurately from the handwritten content
- Map values to the specified column names exactly
- Clean and format the data appropriately
- Ensure all required columns are present
- Provide confidence scores (0.0-1.0) for each cell based on text clarity and legibility
- Higher scores (0.8+) for clear, well-formed text
- Lower scores (0.5-0.7) for unclear, smudged, or ambiguous text
- Very low scores (0.0-0.4) for illegible or missing text
- Return ONLY the JSON object, no explanations"""
    
    # Use provided model or fall back to environment variable
    model_to_use = model or OLLAMA_MODEL
    
    logger.info(f"Calling single-step extraction with model: {model_to_use}")
    response = ollama_client.chat(
        model=model_to_use,
        messages=[{
            'role': 'user',
            'content': extraction_prompt,
            'images': [image_data]
        }]
    )
    
    content = response['message']['content'].strip()
    logger.info(f"Single-step extraction response: {content}")
    
    # Extract JSON from response
    formatted_data = try_extract_json(content)
    if not formatted_data:
        logger.warning("Failed to parse extraction JSON, attempting correction...")
        
        if auto_detect_mode:
            correction_prompt = f"""The previous extraction response was not valid JSON. Please fix it.

Previous response:
{content}

Return ONLY valid JSON in this format (use the actual headers detected from the image):
{{"data": [
    {{"header1": "value1", "header2": "value2", "header3": "value3", "header4": "value4"}},
    {{"header1": "value5", "header2": "value6", "header3": "value7", "header4": "value8"}}
], "confidence": [
    {{"header1": 0.95, "header2": 0.87, "header3": 0.92, "header4": 0.78}},
    {{"header1": 0.89, "header2": 0.93, "header3": 0.85, "header4": 0.91}}
]}}"""
        else:
            correction_prompt = f"""The previous extraction response was not valid JSON. Please fix it.

Required columns: {', '.join(column_list)}

Previous response:
{content}

Return ONLY valid JSON in this format:
{{"data": [
    {{"{column_list[0]}": "value1", "{column_list[1]}": "value2", "{column_list[2]}": "value3", "{column_list[3]}": "value4"}},
    {{"{column_list[0]}": "value5", "{column_list[1]}": "value6", "{column_list[2]}": "value7", "{column_list[3]}": "value8"}}
], "confidence": [
    {{"{column_list[0]}": 0.95, "{column_list[1]}": 0.87, "{column_list[2]}": 0.92, "{column_list[3]}": 0.78}},
    {{"{column_list[0]}": 0.89, "{column_list[1]}": 0.93, "{column_list[2]}": 0.85, "{column_list[3]}": 0.91}}
]}}"""
        
        correction_response = ollama_client.chat(
            model=model_to_use,
            messages=[{
                'role': 'user',
                'content': correction_prompt
            }]
        )
        
        corrected_content = correction_response['message']['content'].strip()
        formatted_data = try_extract_json(corrected_content)
    
    if formatted_data:
        logger.info(f"Successfully extracted and formatted CSV data: {formatted_data}")
        return formatted_data
    else:
        raise Exception("Failed to extract and format data from image")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        password = data.get('password', '')
        
        if password == APP_PASSWORD:
            session['authenticated'] = True
            logger.info("User authenticated successfully")
            return jsonify({'success': True})
        else:
            logger.warning("Failed authentication attempt")
            return jsonify({'success': False, 'error': 'Invalid password'}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    logger.info("User logged out")
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html', ollama_host=OLLAMA_HOST)

@app.route('/ollama-status')
def ollama_status():
    try:
        # Check if custom host is provided
        custom_host = request.args.get('host', OLLAMA_HOST)
        
        # Prepare headers for authentication
        headers = {}
        if OLLAMA_USERNAME and OLLAMA_PASSWORD:
            auth_string = f"{OLLAMA_USERNAME}:{OLLAMA_PASSWORD}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            headers['Authorization'] = f'Basic {auth_b64}'
        
        # Try to connect to Ollama
        response = requests.get(f'{custom_host}', timeout=5, headers=headers)
        
        if response.status_code == 200:
            return jsonify({
                'status': 'running',
                'host': custom_host,
                'current_model': OLLAMA_MODEL,
                'message': 'Ollama is running'
            })
        else:
            return jsonify({
                'status': 'error',
                'host': custom_host,
                'message': f'Ollama returned status code {response.status_code}'
            })
            
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'offline',
            'host': custom_host,
            'message': 'Cannot connect to Ollama'
        })
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'timeout',
            'host': custom_host,
            'message': 'Connection to Ollama timed out'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'host': custom_host,
            'message': str(e)
        })

@app.route('/ollama-models')
def ollama_models():
    """Get list of available models from Ollama"""
    try:
        # Check if custom host is provided
        custom_host = request.args.get('host', OLLAMA_HOST)
        
        # Prepare headers for authentication
        headers = {}
        if OLLAMA_USERNAME and OLLAMA_PASSWORD:
            auth_string = f"{OLLAMA_USERNAME}:{OLLAMA_PASSWORD}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            headers['Authorization'] = f'Basic {auth_b64}'
        
        # Get list of models
        response = requests.get(f'{custom_host}/api/tags', timeout=10, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            models = []
            for model in data.get('models', []):
                model_info = {
                    'name': model.get('name', ''),
                    'size': model.get('size', 0),
                    'modified_at': model.get('modified_at', ''),
                    'family': model.get('family', ''),
                    'format': model.get('format', ''),
                    'families': model.get('families', []),
                    'parameter_size': model.get('parameter_size', ''),
                    'quantization_level': model.get('quantization_level', '')
                }
                models.append(model_info)
            
            return jsonify({
                'status': 'success',
                'host': custom_host,
                'current_model': OLLAMA_MODEL,
                'models': models,
                'count': len(models)
            })
        else:
            return jsonify({
                'status': 'error',
                'host': custom_host,
                'message': f'Ollama returned status code {response.status_code}'
            })
            
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'offline',
            'host': custom_host,
            'message': 'Cannot connect to Ollama'
        })
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'timeout',
            'host': custom_host,
            'message': 'Connection to Ollama timed out'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'host': custom_host,
            'message': str(e)
        })

@app.route('/extract', methods=['POST'])
@require_auth
def extract():
    """Legacy endpoint for single image - now redirects to extract_multiple for unified logic"""
    try:
        logger.info("=== Starting single image extraction (using unified pipeline) ===")
        data = request.json
        image_data = data.get('image')
        
        # Convert single image to array format and use the unified extract_multiple logic
        data['images'] = [image_data]
        
        # Call the unified extract_multiple function
        return extract_multiple()
            
    except Exception as e:
        logger.error(f"Unexpected error in extract endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/extract-multiple', methods=['POST'])
@require_auth
def extract_multiple():
    try:
        logger.info("=== Starting multiple image extraction request ===")
        data = request.json
        images = data.get('images', [])
        columns = data.get('columns', '')
        instructions = data.get('instructions', '')
        selected_model = data.get('model', OLLAMA_MODEL)
        
        logger.info(f"Processing {len(images)} images - Columns: '{columns}', Instructions: '{instructions}', Model: '{selected_model}'")
        
        if not images or len(images) == 0:
            return jsonify({'error': 'No images provided'}), 400
        
        # Configure Ollama client
        custom_host = OLLAMA_HOST
        ollama_client = create_ollama_client(custom_host)
        
        # Determine column order from columns input
        column_order = [col.strip() for col in columns.split(',') if col.strip()] if columns.strip() else []
        
        # Combined results
        all_data = []
        all_confidence = []
        errors = []
        
        # Process each image sequentially
        for i, image_data in enumerate(images):
            try:
                logger.info(f"Processing image {i + 1} of {len(images)}")
                
                # Remove data URL prefix if present
                processed_image = image_data
                if processed_image.startswith('data:image'):
                    processed_image = processed_image.split(',')[1]
                
                # Extract data from this image
                formatted_data = extract_and_format_csv(processed_image, columns, instructions, ollama_client, selected_model)
                
                # Apply column reordering if column order is specified
                if column_order:
                    reordered_data, reordered_confidence = reorder_columns(
                        formatted_data['data'],
                        formatted_data.get('confidence', []),
                        column_order
                    )
                    # Debug: Check keys after reorder
                    logger.info(f"After reorder, keys are: {list(reordered_data[0].keys()) if reordered_data else 'No data'}")
                    formatted_data['data'] = reordered_data
                    formatted_data['confidence'] = reordered_confidence
                else:
                    # No reordering - log what we got
                    logger.info(f"No reordering, keys are: {list(formatted_data['data'][0].keys()) if formatted_data['data'] else 'No data'}")
                
                # Append to combined results
                # Debug: Check what we're appending
                logger.info(f"Keys in formatted_data before append: {list(formatted_data['data'][0].keys()) if formatted_data['data'] else 'No data'}")
                all_data.extend(formatted_data['data'])
                all_confidence.extend(formatted_data.get('confidence', []))
                
                logger.info(f"Successfully processed image {i + 1} of {len(images)}")
                
            except Exception as e:
                error_msg = f"Error processing image {i + 1}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                continue
        
        # Prepare response
        response = {
            'data': all_data,
            'confidence': all_confidence,
            'total_rows': len(all_data),
            'images_processed': len(images) - len(errors),
            'errors': errors
        }
        
        # Debug: Log the keys of the first row to verify order is preserved
        if all_data:
            logger.info(f"First row keys in final response: {list(all_data[0].keys())}")
        
        logger.info(f"Multiple image extraction completed - {len(all_data)} total rows extracted")
        
        # Use custom JSON encoding to preserve key order
        # Flask's jsonify() may still sort keys even with JSON_SORT_KEYS=False in some versions
        return Response(
            json.dumps(response, ensure_ascii=False),
            mimetype='application/json'
        )
            
    except Exception as e:
        logger.error(f"Unexpected error in extract-multiple endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/save', methods=['POST'])
@require_auth
def save():
    try:
        logger.info("=== Starting save request ===")
        data = request.json
        rows = data.get('data', [])
        logger.info(f"Saving {len(rows)} rows to CSV")
        
        os.makedirs('data', exist_ok=True)
        csv_file = 'data/results.csv'
        
        # Check if file exists to determine if we need headers
        file_exists = os.path.exists(csv_file)
        
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            if rows:
                # Get fieldnames from the first row
                # In Python 3.7+, dict maintains insertion order
                # The rows should already be ordered from the reorder_columns function
                first_row = rows[0]
                fieldnames = list(first_row.keys())
                
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # Write header if file is new
                if not file_exists or os.path.getsize(csv_file) == 0:
                    writer.writeheader()
                
                # Write all rows (order is already preserved by fieldnames specification)
                for row in rows:
                    writer.writerow(row)
        
        logger.info(f"Successfully saved {len(rows)} rows to CSV")
        return jsonify({'message': f'Saved {len(rows)} rows to CSV'})
        
    except Exception as e:
        logger.error(f"Error in save endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/download')
@require_auth
def download():
    logger.info("=== Download request ===")
    csv_file = 'data/results.csv'
    if os.path.exists(csv_file):
        logger.info(f"Sending CSV file: {csv_file}")
        return send_file(csv_file, as_attachment=True, download_name='results.csv')
    else:
        logger.warning(f"CSV file not found: {csv_file}")
        return jsonify({'error': 'No CSV file found'}), 404

if __name__ == '__main__':
    HOST = os.getenv("HOST", "127.0.0.1")
    app.run(debug=True, host=HOST)

# Vercel serverless function handler
app = app