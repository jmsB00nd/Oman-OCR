# Installation

This guide covers everything you need to get the Arabic OCR System up and running — from hardware and software prerequisites through automated or manual setup, to final configuration.

## Table of Contents

- [Prerequisites Checklist](#prerequisites-checklist)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Manual Setup (Alternative)](#manual-setup-alternative)
- [Configuration](#configuration)
- [Developement](#development)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites Checklist

Before proceeding, make sure all of the following are in place:

**Hardware**
- [ ] NVIDIA GPU with 16GB+ VRAM (RTX 3090/4090/5090 recommended)
- [ ] 16GB+ System RAM
- [ ] 50GB+ free disk space (auto-download requires ~20GB for models)

**Software**
- [ ] Docker & Docker Compose installed
- [ ] NVIDIA Container Toolkit installed and configured — see [INSTALL_CUDA_TOOLKIT_FOR_DOCKER](INSTALL_CUDA_TOOLKIT_FOR_DOCKER.md)
- [ ] CUDA 12.0+
- [ ] Python 3.10+ (required for the setup script)
- [ ] Git

---

## Requirements

### Hardware
- NVIDIA GPU with at least 16GB VRAM (RTX 3090/4090/5090 recommended)
- 16GB+ System RAM
- 50GB+ Storage for models (auto-download requires ~20GB)

### Software
- Docker & Docker Compose
- NVIDIA Container Toolkit (Look at [DOCKER_CUDA_TOOLKIT_INSTALLATION](INSTALL_CUDA_TOOLKIT_FOR_DOCKER.md))
- CUDA 12.0+
- Python 3.10+ (for setup script)

---

## Quick Start

This [recorded video](https://mega.nz/file/rcAxmRRb#sX4k5MPo46B7BJ55NzhsTC0b8Lw2FHvYpTAa1BKOkHk) assists you in deploying the model on your local machines.

### 1. Clone the Repository

```bash
git clone https://github.com/hosseinmohammadiibusiness-cyber/Oman-OCR.git
cd Oman-OCR
```

### 2. Automated Setup (Recommended)

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
- Request a `HF-Token` for fetching models
- Download DeepSeek-OCR (vision model)
- Download Gemma 2B (text model)
- Create necessary directories and configuration

### 3. Launch Services

```bash
docker-compose up -d
```

### 4. Access the Application

Open your browser and navigate to: `http://localhost:8080`

---

## Manual Setup (Alternative)

If you prefer to use your own models:

### 1. Prepare Models

Place your models in the appropriate directories:

```bash
mkdir -p models/vision models/text
# Place your vision model in models/vision/
# Place your text model in models/text/
```

### 2. Configure Environment

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

### 3. Launch Services

```bash
docker-compose up -d
```

---

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