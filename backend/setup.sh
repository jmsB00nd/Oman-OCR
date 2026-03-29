#!/bin/bash
# Setup script for Arabic OCR System (Backend)

set -e

# Automatically move to the directory where this script is located
cd "$(dirname "$0")"

echo "=================================================="
echo "   Arabic Document Processor - Backend Setup"
echo "=================================================="
echo ""

# Check if Python is available 
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python 3.10 or higher."
    exit 1
fi

# Install Python dependencies for model download 
echo "Installing dependencies..."
python3 -m pip install -q --upgrade pip
# Ensure huggingface-hub is explicitly available for the download script
python3 -m pip install -q -r scripts/requirements.txt 

# Download models 
echo ""
echo "Downloading models (this may take a while)..."
python3 scripts/download_models.py 

# Create .env if it doesn't exist 
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    if [ -f .env.example ]; then
        cp .env.example .env 
    else
        # If no template exists, we create one with the necessary HF_TOKEN field
        touch .env
        echo "HF_TOKEN=" >> .env
        echo "WARNING: .env.example not found. Created .env with HF_TOKEN placeholder."
    fi
fi

# Create data directories 
echo ""
echo "Creating data directories..."
mkdir -p data/uploads 

echo ""
echo "=================================================="
echo "   Backend Setup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. If you haven't yet, add your Hugging Face token to the .env file."
echo "  2. Go to the project root directory:"
echo "     cd .."
echo ""
echo "  3. Start all services:"
echo "     docker-compose up -d"
echo ""