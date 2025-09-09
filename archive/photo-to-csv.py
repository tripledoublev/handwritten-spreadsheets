"""
This is the original PoC that I used to extract the data from the image.


Usage instructions:

1. Install Ollama: https://ollama.com/download

2. Pull the vision model:
   ollama pull llama3.2-vision

3. Install Python requirements:
   pip install ollama pandas

4. Replace 'test.jpeg' with the path to your own image(s).

5. Edit the PROMPT variable below to describe the data format you need.
   For example, you might want {"first_name": "...", "last_name": "...", "email": "..."} 
   or add/remove fields depending on your form.

This script will:
- Send the image to the llama3.2-vision model running locally via Ollama.
- Extract structured fields as JSON.
- Save the results into results.csv for easy spreadsheet use.
"""

import ollama
import json
import pandas as pd

# >>> customize this prompt for your data format <<<
PROMPT = '''
Extract the handwritten email, phone, and name from this photo. 
Return ONLY valid JSON in this exact format:
{"name": "extracted_name", "email": "extracted_email", "phone": "extracted_phone", "notes": "any_additional_notes"}.
Do not include any other text or explanation.
'''

# call ollama
response = ollama.chat(
    model='llama3.2-vision',
    messages=[{
        'role': 'user',
        'content': PROMPT,
        'images': ['test.jpeg']  # change this path to your own image
    }]
)

# parse response
content = response['message']['content']
try:
    data = json.loads(content)
except json.JSONDecodeError:
    print("⚠️ model did not return valid JSON, raw output:", content)
    exit(1)

print("✅ extracted:", data)

# save to CSV
df = pd.DataFrame([data])
df.to_csv("results.csv", index=False)
print("💾 saved to results.csv")
