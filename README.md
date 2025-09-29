# Handwritten Spreadsheet to CSV

Convert handwritten spreadsheet images to structured CSV data using AI vision models.

## What it does?

- **Image Upload**: Support for various image formats (PNG, JPG, etc.)
- **AI-Powered Extraction**: Uses Ollama vision models for accurate text recognition
- **Model Selection**: Choose from available Ollama models for optimal performance
- **Confidence Scoring**: Get confidence scores for each extracted cell to identify uncertain data
- **Auto-Detect Headers**: Automatically detect column headers from the image
- **Custom Column Mapping**: Define your own spreadsheet headers when needed
- **Optional Instructions**: Provide additional context for better extraction
- **Live Preview**: See extracted data with confidence highlighting before saving
- **CSV Export**: Save and download results as CSV files
- **Ollama Integration**: Built-in status checking and custom endpoint configuration

## Quick Start

### Prerequisites

1. **Python 3.7+** (for local setup)
2. **Docker & Docker Compose** (for Docker setup)
3. **Ollama** with a vision model
   - [Download Ollama](https://ollama.com/download)
   - Install a vision model: `ollama pull qwen2.5vl:7b` (recommended) or `ollama pull llama3.2-vision`

## Setup Options

### Option 1: Local Development Setup

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

### Option 2: Docker Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/tripledoublev/handwritten-spreadsheets.git
   cd handwritten-spreadsheets
   ```

2. **Configure environment** (optional)
   ```bash
   cp env.example .env
   # Edit .env file to customize Ollama settings if needed
   ```

3. **Start the application**
   ```bash
   docker compose up --build -d
   ```

4. **Download the vision model** (first time only)
   ```bash
   # This downloads the llama3.2-vision model (~7.8 GB)
   docker exec -it handwritten-spreadsheets-app-1 ollama pull llama3.2-vision
   ```

5. **Open your browser** to `http://127.0.0.1:5000`

6. **Stop the application**
   ```bash
   docker compose down
   ```

#### Docker Benefits
- **Isolated Environment**: No need to install Python dependencies locally
- **Consistent Setup**: Same environment across different machines
- **Easy Cleanup**: Remove containers to clean up completely
- **Production Ready**: Same setup used in production deployments

## Usage

1. **Check Ollama Status**: The app will automatically detect if Ollama is running
2. **Select Model**: Choose from available Ollama models (defaults to qwen2.5vl:7b)
3. **Upload Image**: Select a photo of your handwritten spreadsheet
4. **Define Headers** (optional): Enter column names separated by commas (e.g., "name,email,phone,notes")
   - **Auto-detect mode**: Leave empty to automatically detect headers from the image
   - **Specify mode**: Enter column names to force specific headers
5. **Set Confidence Threshold**: Adjust the threshold for highlighting uncertain data (default: 0.7)
6. **Add Instructions** (optional): Provide specific guidance for extraction
7. **Extract Data**: Click "Extract Data" to process the image
8. **Preview Results**: Review the extracted data with confidence scores and highlighting
9. **Save to CSV**: Click "Save Rows to CSV" to append data to your CSV file
10. **Download**: Use "Download CSV" to get your complete dataset

## Configuration

### Environment Variables

Create a `.env` file in the project root to configure external Ollama endpoints:

```bash
# Ollama server configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_USERNAME=your_username
OLLAMA_PASSWORD=your_password
OLLAMA_MODEL=qwen2.5vl:7b
```

### Custom Ollama Endpoint

If Ollama is running on a different host/port:
1. The status indicator will show "offline" for localhost:11434
2. Click to reveal the custom endpoint configuration
3. Enter your Ollama URL (e.g., `http://192.168.1.123:11434`)
4. Click "Test Connection" to verify

### Model Selection

- **Default Model**: The app uses `qwen2.5vl:7b` by default (configurable via `OLLAMA_MODEL`)
- **Model Dropdown**: Select from available models in the web interface
- **Model Information**: Each model shows its size and current status
- **Performance**: Different models may have varying accuracy and speed

### File Structure

```
handwritten-spreadsheets/
├── app.py                 # Flask backend
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker container configuration
├── docker-compose.yaml   # Docker Compose configuration
├── env.example           # Environment variables template
├── templates/
│   └── index.html        # Web interface
├── data/
│   └── results.csv       # Output CSV file (auto-created)
├── archive/
│   └── photo-to-csv.py   # Original script
└── ollama/               # Ollama model files (Docker setup)
```

## API Endpoints

- `GET /` - Serve web interface
- `GET /ollama-status` - Check Ollama connectivity
- `GET /ollama-models` - Get list of available Ollama models
- `POST /extract` - Process image and extract data with confidence scores
- `POST /save` - Save extracted data to CSV
- `GET /download` - Download current CSV file

## Tips for Best Results

- **Image Quality**: Use high-resolution, well-lit photos
- **Clear Handwriting**: Ensure text is legible
- **Consistent Format**: Maintain regular spacing and alignment
- **Column Headers**: Be specific with column names for better mapping
- **Additional Instructions**: Mention any special formatting or context
- **Model Selection**: Try different models to find the best performance for your handwriting style
- **Confidence Scores**: Review highlighted cells (low confidence) and verify accuracy
- **Confidence Threshold**: Adjust the threshold (0.7 default) to highlight more or fewer uncertain cells
- **Auto-detect vs Specify**: Use auto-detect for well-structured tables, specify headers for complex layouts

## Troubleshooting

### Ollama Connection Issues
- Ensure Ollama is installed and running (`ollama serve`)
- Check if a vision model is available (`ollama list`)
- Verify firewall settings if using remote Ollama instance
- Check environment variables in `.env` file for custom endpoints

### Extraction Problems
- Try providing more specific column headers
- Add instructions about handwriting style or format
- Ensure image is clear and well-lit
- Check that all text is visible in the uploaded image
- Try different models for better accuracy
- Review confidence scores to identify problematic areas
- Use auto-detect mode for well-structured tables

### CSV Output Issues
- Check the `data/` directory for the results.csv file
- Ensure write permissions in the project directory

### Docker Issues
- **Container won't start**: Check Docker is running and ports 5000 is available
- **Model download fails**: Ensure sufficient disk space (~8GB for llama3.2-vision)
- **Permission errors**: On Linux, you may need to run `sudo docker compose up`
- **Port conflicts**: Change the port mapping in docker-compose.yaml if 5000 is in use
- **Environment variables**: Ensure .env file exists and has correct Ollama settings
- **Container logs**: Use `docker compose logs` to debug issues

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