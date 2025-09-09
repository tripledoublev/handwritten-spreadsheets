from flask import Flask, request, jsonify, send_file, send_from_directory
import ollama
import json
import csv
import os
import base64
import requests
from io import StringIO
from datetime import datetime

app = Flask(__name__)

# Default Ollama configuration
OLLAMA_HOST = 'http://localhost:11434'

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/ollama-status')
def ollama_status():
    try:
        # Check if custom host is provided
        custom_host = request.args.get('host', OLLAMA_HOST)
        
        # Try to connect to Ollama
        response = requests.get(f'{custom_host}', timeout=5)
        
        if response.status_code == 200:
            return jsonify({
                'status': 'running',
                'host': custom_host,
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

@app.route('/extract', methods=['POST'])
def extract():
    try:
        data = request.json
        image_data = data.get('image')
        columns = data.get('columns', '')
        instructions = data.get('instructions', '')
        custom_host = data.get('ollama_host', OLLAMA_HOST)
        
        # Remove data URL prefix if present
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        # Build strict prompt
        column_list = [col.strip() for col in columns.split(',') if col.strip()]
        
        prompt = f"""Extract data from this handwritten spreadsheet image and return ONLY a JSON object.

Required columns: {', '.join(column_list)}
{f"Additional instructions: {instructions}" if instructions else ""}

Return format: {{"data": [{{"column1": "value1", "column2": "value2", ...}}]}}

IMPORTANT: 
- Return ONLY valid JSON, no explanation
- Use exact column names provided
- Extract all visible rows
- If a cell is unclear, use empty string ""
- Ensure JSON is properly formatted"""

        # Configure Ollama client with custom host if provided
        if custom_host != OLLAMA_HOST:
            ollama_client = ollama.Client(host=custom_host)
        else:
            ollama_client = ollama

        # Call Ollama with vision model
        response = ollama_client.chat(
            model='llama3.2-vision',
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [image_data]
            }]
        )
        
        # Parse response
        content = response['message']['content'].strip()
        
        # Try to extract JSON from response
        try:
            # Find JSON in response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                parsed_data = json.loads(json_str)
                return jsonify(parsed_data)
            else:
                # Try parsing entire response as JSON
                parsed_data = json.loads(content)
                return jsonify(parsed_data)
        except json.JSONDecodeError:
            return jsonify({'error': 'Failed to parse JSON from model response', 'raw_response': content}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save', methods=['POST'])
def save():
    try:
        data = request.json
        rows = data.get('data', [])
        
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
        
        return jsonify({'message': f'Saved {len(rows)} rows to CSV'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download')
def download():
    csv_file = 'data/results.csv'
    if os.path.exists(csv_file):
        return send_file(csv_file, as_attachment=True, download_name='results.csv')
    else:
        return jsonify({'error': 'No CSV file found'}), 404

if __name__ == '__main__':
    app.run(debug=True)