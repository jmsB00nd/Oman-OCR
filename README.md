# Arabic OCR System

A high-performance Arabic Optical Character Recognition (OCR) system that extracts and corrects text from document images using GPU-accelerated AI models.

## Overview

This system combines two specialized AI models in a microservices architecture:
- **Vision Model**: Extracts raw Arabic text from images
- **Text Model**: Corrects OCR errors and improves text quality

The application provides a web-based interface for batch processing document images with real-time progress tracking.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Network                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   Vision    │    │    Text     │    │     App Core        │ │
│  │   Engine    │    │   Engine    │    │  (Streamlit + API)  │ │
│  │  (vLLM)     │    │  (vLLM)     │    │                     │ │
│  │  Port 8000  │    │  Port 8001  │    │  Host: 8080 → 8501  │ │
│  │  GPU: 40%   │    │  GPU: 30%   │    │     CPU Only        │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Batch Processing**: Upload multiple images simultaneously
- **Async Queue**: Non-blocking UI with background job processing
- **Real-time Status**: Track job progress with live updates
- **Error Correction**: Two-stage pipeline for accurate text extraction
- **GPU Optimized**: Efficient VRAM allocation for concurrent model inference
- **Docker Ready**: Full containerization with Docker Compose
- **Auto-Setup**: Automatic model downloading with default models

## Default Models

The automated setup downloads these models:
- **Vision Model**: [deepseek-ai/DeepSeek-OCR](https://huggingface.co/deepseek-ai/DeepSeek-OCR) - Specialized OCR vision model
- **Text Model**: [google/gemma-2-2b-it](https://huggingface.co/google/gemma-2-2b-it) - Efficient 2B parameter text correction model

You can replace these with your own models by placing them in `models/vision/` and `models/text/` directories.

## Requirements

### Hardware
- NVIDIA GPU with at least 16GB VRAM (RTX 3090/4090/5090 recommended)
- 16GB+ System RAM
- 50GB+ Storage for models (auto-download requires ~20GB)

### Software
- Docker & Docker Compose
- NVIDIA Container Toolkit
- CUDA 12.0+
- Python 3.10+ (for setup script)

## Quick Start

### Clone the Repository

```bash
git clone https://github.com/hosseinmohammadiibusiness-cyber/Oman-OCR.git
cd oman-ocr
```
### RUN
```bash
cd ~/ocr/Oman-OCR
ls -ld data data/uploads
chown -R 1000:1000 data
chmod -R 755 data
```

### Access Token

Create a Hugging Face access token and store it as an environment variable:

#### Step 1: Create a Hugging Face Token

Go to Hugging Face → Settings → Access Tokens

Click New token

Select Read access

Copy the generated token

#### Step 2: Export the Token as an Environment Variable

macOS / Linux (bash or zsh):

```bash
export HF_TOKEN="your_huggingface_token_here"
```

To make it persistent, add the line above to your ~/.bashrc, ~/.zshrc, or ~/.profile.

Windows (PowerShell):

```bash
setx HF_TOKEN "your_huggingface_token_here"
```

Restart your terminal after running this command.

#### Step 4: Accept the Model License

Visit [gemma](https://huggingface.co/google/gemma-3-4b-it) and accept the repository’s terms and license to enable access.

### Automated Setup (Recommended)

Run the setup script that automatically downloads models and configures the system:

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

This will:
- Install Python dependencies
- Download DeepSeek-OCR (vision model)
- Download Gemma 2B (text model)
- Create necessary directories and configuration

### Launch Services

```bash
docker-compose up -d
```

### Access the Application

Open your browser and navigate to: `http://localhost:8080`

---

## Manual Setup (Alternative)

If you prefer to use your own models:

### Prepare Models

Place your models in the appropriate directories:

```bash
mkdir -p models/vision models/text
# Place your vision model in models/vision/
# Place your text model in models/text/
```

### Configure Environment

```bash
cp .env.example .env
```

The default `.env` configuration:

```env
VISION_URL=http://vision-engine:8000/v1/chat/completions
TEXT_URL=http://text-engine:8001/v1/chat/completions
UPLOAD_DIR=/data/uploads
DB_PATH=/data/jobs.db
```

### Launch Services

```bash
docker-compose up -d
```

## Project Structure

```
oman-ocr/
├── src/
│   ├── main.py               # Streamlit application & worker
│   ├── database.py           # SQLite job queue operations
│   └── requirements.txt      # Python dependencies
├── scripts/
│   ├── download_models.py    # Automatic model downloader
│   ├── Dockerfile.downloader # Model downloader container
│   └── requirements.txt      # Script dependencies
├── tests/
│   ├── conftest.py           # Pytest fixtures
│   ├── test_database.py      # Database tests
│   ├── test_pipeline.py      # OCR pipeline tests
│   └── test_worker.py        # Worker tests
├── data/
│   ├── jobs.db               # SQLite database
│   └── uploads/              # Uploaded images
├── models/
│   ├── vision/               # Vision model weights (auto-downloaded)
│   └── text/                 # Text model weights (auto-downloaded)
├── .env                      # Environment configuration
├── .env.example              # Environment template
├── Dockerfile                # App container definition
├── docker-compose.yml        # Service orchestration
├── setup.sh                  # Automated setup (Linux/Mac)
├── setup.bat                 # Automated setup (Windows)
├── requirements-dev.txt      # Development dependencies
├── pytest.ini                # Pytest configuration
├── IMPLEMENTATION_PLAN.md    # Technical documentation
└── README.md
```

## Usage

### Uploading Documents

1. Navigate to the **Batch Upload** tab
2. Drag and drop image files (PNG, JPG, JPEG, TIFF, BMP)
3. Click **Start Processing**
4. Files are queued for background processing

### Viewing Results

1. Navigate to the **Results & History** tab
2. View real-time job statistics (Pending, Processing, Completed, Failed)
3. Click **Refresh** to update the job list
4. Review both raw OCR output and corrected text

## Configuration

### GPU Memory Allocation

Adjust GPU memory utilization in `docker-compose.yml`:

```yaml
vision-engine:
  command: --gpu-memory-utilization 0.45  # 45% VRAM

text-engine:
  command: --gpu-memory-utilization 0.35  # 35% VRAM
```

**Note**: The default models (DeepSeek-OCR + Gemma 2B) are optimized to fit within 16GB VRAM. If using larger models, adjust these values or use quantized versions.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VISION_URL` | Vision model API endpoint | `http://localhost:8000/v1/chat/completions` |
| `TEXT_URL` | Text model API endpoint | `http://localhost:8001/v1/chat/completions` |
| `UPLOAD_DIR` | Directory for uploaded files | `./data/uploads` |
| `DB_PATH` | SQLite database path | `./data/jobs.db` |

## API Reference

The system uses OpenAI-compatible API endpoints internally:

### Vision Model Request

```json
{
  "model": "vision-model",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "Transcribe the Arabic text in this image."},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]
  }]
}
```

### Text Model Request

```json
{
  "model": "text-model",
  "messages": [{
    "role": "user",
    "content": "Fix any OCR errors in this Arabic text: ..."
  }]
}
```

## Development

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements-dev.txt

# Run locally
cd src
streamlit run main.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_database.py
```

## Troubleshooting

### Common Issues

**Model download fails**
```bash
# Manually download models
python scripts/download_models.py

# Check Hugging Face connectivity
pip install huggingface-hub
huggingface-cli whoami
```

**GPU not detected**
```bash
# Verify NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

**Out of VRAM**
- Reduce `gpu-memory-utilization` values in `docker-compose.yml`
- The default models should fit in 16GB VRAM
- Consider using smaller models or quantized versions

**Connection refused errors**
- Ensure all services are running: `docker-compose ps`
- Check service logs: `docker-compose logs -f vision-engine`
- Wait for models to load (first start takes 2-5 minutes)

**vLLM container crashes**
- Check if models are downloaded: `ls models/vision models/text`
- Verify model compatibility with vLLM
- Check logs: `docker-compose logs vision-engine`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm) - High-performance LLM inference
- [Streamlit](https://streamlit.io/) - Web application framework
