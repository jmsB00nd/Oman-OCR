"""Automatic model downloader for Arabic OCR System."""

import os
import sys
from pathlib import Path

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("ERROR: huggingface_hub is not installed.")
    print("Please install it with: pip install huggingface-hub")
    sys.exit(1)


# Model configuration
VISION_MODEL = "deepseek-ai/DeepSeek-OCR"
TEXT_MODEL = "google/gemma-3-4b-it"  # Using 2B variant for efficiency

# Directories
BASE_DIR = Path(__file__).parent.parent
VISION_DIR = BASE_DIR / "models" / "vision"
TEXT_DIR = BASE_DIR / "models" / "text"


def is_model_downloaded(model_dir: Path) -> bool:
    """Check if a model directory contains valid model files."""
    if not model_dir.exists():
        return False

    # Check for essential model files
    required_files = ["config.json"]
    return all((model_dir / file).exists() for file in required_files)


def download_model(model_name: str, target_dir: Path) -> None:
    """Download a model from Hugging Face Hub."""
    print(f"\n{'='*60}")
    print(f"Downloading: {model_name}")
    print(f"Target directory: {target_dir}")
    print(f"{'='*60}\n")

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_download(
            repo_id=model_name,
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
            token="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"
        )
        print(f"\n✓ Successfully downloaded {model_name}\n")
    except Exception as e:
        print(f"\n✗ Failed to download {model_name}: {e}\n")
        sys.exit(1)


def main():
    """Main function to check and download models."""
    print("\n" + "="*60)
    print("Arabic OCR System - Model Setup")
    print("="*60 + "\n")

    # Check vision model
    if is_model_downloaded(VISION_DIR):
        print(f"✓ Vision model already exists at: {VISION_DIR}")
    else:
        print(f"✗ Vision model not found")
        download_model(VISION_MODEL, VISION_DIR)

    # Check text model
    if is_model_downloaded(TEXT_DIR):
        print(f"✓ Text model already exists at: {TEXT_DIR}")
    else:
        print(f"✗ Text model not found")
        download_model(TEXT_MODEL, TEXT_DIR)

    print("\n" + "="*60)
    print("Model setup complete!")
    print("="*60 + "\n")
    print("You can now start the services with:")
    print("  docker-compose up -d")
    print()


if __name__ == "__main__":
    main()