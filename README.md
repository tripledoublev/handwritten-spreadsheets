# Handwritten Spreadsheet to CSV

Convert handwritten spreadsheet images to structured CSV data using AI vision models.

## What it does?

- **Image Upload**: Support for various image formats (PNG, JPG, etc.)
- **AI-Powered Extraction**: Uses Ollama's llama3.2-vision model for accurate text recognition
- **Custom Column Mapping**: Define your own spreadsheet headers
- **Optional Instructions**: Provide additional context for better extraction
- **Live Preview**: See extracted data before saving
- **CSV Export**: Save and download results as CSV files
- **Ollama Integration**: Built-in status checking and custom endpoint configuration

## Quick Start

### Prerequisites

1. **Python 3.7+**
2. **Ollama** with llama3.2-vision model
   - [Download Ollama](https://ollama.com/download)
   - Install vision model: `ollama pull llama3.2-vision`

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/tripledoublev/handwritten-spreadsheets.git
   cd handwritten-spreadsheets
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start Ollama** (if not already running)
   ```bash
   ollama serve
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser** to `http://127.0.0.1:5000`

## Usage

1. **Check Ollama Status**: The app will automatically detect if Ollama is running
2. **Upload Image**: Select a photo of your handwritten spreadsheet
3. **Define Headers**: Enter column names separated by commas (e.g., "name,email,phone,notes")
4. **Add Instructions** (optional): Provide specific guidance for extraction
5. **Extract Data**: Click "Extract Data" to process the image
6. **Preview Results**: Review the extracted data in JSON and table format
7. **Save to CSV**: Click "Save Rows to CSV" to append data to your CSV file
8. **Download**: Use "Download CSV" to get your complete dataset

## Configuration

### Custom Ollama Endpoint

If Ollama is running on a different host/port:
1. The status indicator will show "offline" for localhost:11434
2. Click to reveal the custom endpoint configuration
3. Enter your Ollama URL (e.g., `http://192.168.1.123:11434`)
4. Click "Test Connection" to verify

### File Structure

```
handwritten-spreadsheets/
├── app.py                 # Flask backend
├── requirements.txt       # Python dependencies
├── static/
│   └── index.html        # Web interface
├── data/
│   └── results.csv       # Output CSV file (auto-created)
└── archive/
    └── photo-to-csv.py   # Original script
```

## API Endpoints

- `GET /` - Serve web interface
- `GET /ollama-status` - Check Ollama connectivity
- `POST /extract` - Process image and extract data
- `POST /save` - Save extracted data to CSV
- `GET /download` - Download current CSV file

## Tips for Best Results

- **Image Quality**: Use high-resolution, well-lit photos
- **Clear Handwriting**: Ensure text is legible
- **Consistent Format**: Maintain regular spacing and alignment
- **Column Headers**: Be specific with column names for better mapping
- **Additional Instructions**: Mention any special formatting or context

## Troubleshooting

### Ollama Connection Issues
- Ensure Ollama is installed and running (`ollama serve`)
- Check if llama3.2-vision model is available (`ollama list`)
- Verify firewall settings if using remote Ollama instance

### Extraction Problems
- Try providing more specific column headers
- Add instructions about handwriting style or format
- Ensure image is clear and well-lit
- Check that all text is visible in the uploaded image

### CSV Output Issues
- Check the `data/` directory for the results.csv file
- Ensure write permissions in the project directory

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test it
5. Submit a pull request

## License

This project is open source. Feel free to use and modify as needed.

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- Powered by [Ollama](https://ollama.com/) and [llama3.2-vision](https://ollama.com/library/llama3.2-vision)