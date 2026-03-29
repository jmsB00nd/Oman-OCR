#!/bin/bash
# Setup script for Arabic OCR System (Backend)
# This script should now reside in the /backend/ folder

set -e

# Automatically move to the directory where this script is located
# This ensures paths like 'scripts/' work even if called from the root
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
python3 -m pip install -q -r scripts/requirements.txt 

# Download models 
echo ""
echo "Downloading models (this may take a while)..."
python3 scripts/download_models.py 

# Create .env if it doesn't exist 
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    # Assuming .env.example was also moved to the backend folder
    if [ -f .env.example ]; then
        cp .env.example .env 
    else
        touch .env
        echo "WARNING: .env.example not found. Created an empty .env file."
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
echo "  1. Go to the project root directory:"
echo "     cd .."
echo ""
echo "  2. Start all services (Backend + Next.js):"
echo "     docker-compose up -d"
echo ""
echo "  3. Access the Next.js UI:"
echo "     http://localhost:3000"
echo ""