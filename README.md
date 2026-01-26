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

## Requirements

### Hardware
- NVIDIA GPU with at least 16GB VRAM (RTX 3090/4090/5090 recommended)
- 16GB+ System RAM
- 50GB+ Storage for models

### Software
- Docker & Docker Compose
- NVIDIA Container Toolkit
- CUDA 12.0+

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/oman-ocr.git
cd oman-ocr
```

### 2. Prepare Models

Download your vision and text models and place them in the appropriate directories:

```bash
mkdir -p models/vision models/text
# Place your AWQ-quantized vision model in models/vision/
# Place your AWQ-quantized text model in models/text/
```

### 3. Configure Environment

Copy the example environment file and adjust as needed:

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

### 4. Launch Services

```bash
docker-compose up -d
```

### 5. Access the Application

Open your browser and navigate to: `http://localhost:8080`

## Project Structure

```
oman-ocr/
├── src/
│   ├── main.py              # Streamlit application & worker
│   ├── database.py          # SQLite job queue operations
│   └── requirements.txt     # Python dependencies
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_database.py     # Database tests
│   ├── test_pipeline.py     # OCR pipeline tests
│   └── test_worker.py       # Worker tests
├── data/
│   ├── jobs.db              # SQLite database
│   └── uploads/             # Uploaded images
├── models/
│   ├── vision/              # Vision model weights
│   └── text/                # Text model weights
├── .env                     # Environment configuration
├── .env.example             # Environment template
├── Dockerfile               # App container definition
├── docker-compose.yml       # Service orchestration
├── requirements-dev.txt     # Development dependencies
├── pytest.ini               # Pytest configuration
├── IMPLEMENTATION_PLAN.md   # Technical documentation
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
  command: --gpu-memory-utilization 0.4  # 40% VRAM

text-engine:
  command: --gpu-memory-utilization 0.3  # 30% VRAM
```

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

**GPU not detected**
```bash
# Verify NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

**Out of VRAM**
- Reduce `gpu-memory-utilization` values in `docker-compose.yml`
- Use smaller quantized models (AWQ 4-bit recommended)

**Connection refused errors**
- Ensure all services are running: `docker-compose ps`
- Check service logs: `docker-compose logs -f`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm) - High-performance LLM inference
- [Streamlit](https://streamlit.io/) - Web application framework
