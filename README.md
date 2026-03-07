# Arabic Document Processor

A high-performance Arabic Optical Character Recognition (OCR) system that extracts and corrects text from document images using GPU-accelerated AI models.

## Overview

This system combines two specialized AI models in a microservices architecture:
- **Vision Model**: Extracts raw Arabic text from images
- **Text Model**: Corrects OCR errors and improves text quality

The application provides a web-based interface for batch processing document images with real-time progress tracking.


## Supplementary Documents
Here are the supplementary documentation of this application:
- Development roadmap, and technical discussions [Roadmap.md](docs/Arabic%20Document%20Processor.md)
  - > Discussion regarding `Why we call this application MVP`, technical architectural design, and future works are included in this document.
- Installation guide [INSTALLATION.md](docs/INSTALLATION.md)
- Tests [e2e_tests.md](docs/Arabic_Document_Processor_e2e_Evaluation_Report.md)
  - There are various categories of documents that are aimed to be ingested by this application, among of which are `Tax Declaration`, `Financial Results Summary`, `Commercial Lease Contract`, `Tax Exemption Certificate`, etc. We have cherrypicked a handful of those documents, and reported relevant metrics.



## Demo
![Demo GIF](demo/UI_demo.gif)

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
- **Text Model**: [google/gemma-3-4b-it](https://huggingface.co/google/gemma-3-4b-it) - Efficient 2B parameter text correction model

You can replace these with your own models by placing them in `models/vision/` and `models/text/` directories.

## Installation

For full installation instructions, see [INSTALLATION.md](docs/INSTALLATION.md).

## Project Structure

```
oman-ocr/
├── src/
│   ├── main.py              # Streamlit application & worker
│   ├── database.py          # SQLite job queue operations
│   └── requirements.txt     # Python dependencies
├── scripts/
│   ├── download_models.py   # Automatic model downloader
│   ├── Dockerfile.downloader # Model downloader container
│   └── requirements.txt     # Script dependencies
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_database.py     # Database tests
│   ├── test_pipeline.py     # OCR pipeline tests
│   └── test_worker.py       # Worker tests
├── data/
│   ├── jobs.db              # SQLite database
│   └── uploads/             # Uploaded images
├── models/
│   ├── vision/              # Vision model weights (auto-downloaded)
│   └── text/                # Text model weights (auto-downloaded)
├── .env                     # Environment configuration
├── .env.example             # Environment template
├── Dockerfile               # App container definition
├── docker-compose.yml       # Service orchestration
├── setup.sh                 # Automated setup (Linux/Mac)
├── setup.bat                # Automated setup (Windows)
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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributor

- Mohammad Sadegh Vaezi (Lead)
- Arash Saleh Ahmadi
- Maryam Asad Samani
- Hossein Mohammadi
