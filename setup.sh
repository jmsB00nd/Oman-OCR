#!/bin/bash
# Setup script for Arabic OCR System

set -e

echo "=================================================="
echo "   Arabic Document Processor - Automated Setup"
echo "=================================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python 3.10 or higher."
    exit 1
fi

# Check if Poppler is available (required for pdf2image)
if ! command -v pdftoppm &> /dev/null; then
    echo "WARNING: 'poppler-utils' is not installed on your system."
    echo "PDF processing will fail locally."
    echo "Ubuntu/Debian: sudo apt-get install poppler-utils"
    echo "Mac: brew install poppler"
    echo ""
    read -p "Press enter to continue anyway or Ctrl+C to abort..."
fi

# Install Python dependencies for model download
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r scripts/requirements.txt

# Download models
echo ""
echo "Downloading models (this may take a while)..."
python3 scripts/download_models.py

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file..."
    cp .env.example .env
fi

# Create data directories
echo ""
echo "Creating data directories..."
mkdir -p data/uploads

echo ""
echo "=================================================="
echo "   Setup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Start the services:"
echo "     docker-compose up -d"
echo ""
echo "  2. Access the application:"
echo "     http://localhost:8080"
echo ""