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

from flask import Flask, request, jsonify, render_template, send_file
import ollama
import json
import csv
import os
import base64
import requests
from io import StringIO
from datetime import datetime
import logging
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

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

def extract_and_format_csv(image_data, columns, instructions, ollama_client, model=None):
    """Single-step OCR and CSV formatting - Extract and format data in one call"""
    logger.info("=== Single-step OCR and CSV formatting ===")
    
    # Determine if we're in auto-detect or specify mode
    column_list = [col.strip() for col in columns.split(',') if col.strip()] if columns.strip() else []
    auto_detect_mode = len(column_list) == 0
    
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

@app.route('/')
def index():
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
def extract():
    try:
        logger.info("=== Starting single-step extraction request ===")
        data = request.json
        image_data = data.get('image')
        columns = data.get('columns', '')
        instructions = data.get('instructions', '')
        # Always use environment variable host (frontend doesn't specify host)
        custom_host = OLLAMA_HOST
        # Use selected model or fall back to environment variable
        selected_model = data.get('model', OLLAMA_MODEL)
        
        logger.info(f"Request parameters - Columns: '{columns}', Instructions: '{instructions}', Host: '{custom_host}', Model: '{selected_model}'")
        logger.info(f"Image data length: {len(image_data) if image_data else 'None'}")
        
        # Remove data URL prefix if present
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
            logger.info("Removed data URL prefix from image data")
        
        # Configure Ollama client
        ollama_client = create_ollama_client(custom_host)
        logger.info(f"Using Ollama host: {custom_host}")

        # Single-step OCR and CSV formatting
        logger.info("Starting single-step OCR and CSV formatting")
        formatted_data = extract_and_format_csv(image_data, columns, instructions, ollama_client, selected_model)
        
        logger.info("Single-step extraction completed successfully")
        return jsonify(formatted_data)
            
    except Exception as e:
        logger.error(f"Unexpected error in extract endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/save', methods=['POST'])
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
                fieldnames = rows[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # Write header if file is new
                if not file_exists or os.path.getsize(csv_file) == 0:
                    writer.writeheader()
                
                # Write all rows
                for row in rows:
                    writer.writerow(row)
        
        logger.info(f"Successfully saved {len(rows)} rows to CSV")
        return jsonify({'message': f'Saved {len(rows)} rows to CSV'})
        
    except Exception as e:
        logger.error(f"Error in save endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/download')
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