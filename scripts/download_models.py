"""Automatic model downloader for Arabic Document Processor."""

import os
import sys
from pathlib import Path

try:
    from huggingface_hub import snapshot_download, list_repo_files
except ImportError:
    print("ERROR: huggingface_hub is not installed.")
    print("Please install it with: pip install huggingface-hub")
    sys.exit(1)


# Model configuration
TEXT_MODEL = "datalab-to/chandra-ocr-2"

# Directories
BASE_DIR = Path(__file__).parent.parent
TEXT_DIR = BASE_DIR / "models" / "text"


def get_hf_token() -> str:
    """Retrieve the Hugging Face token from the environment or prompt the user."""
    token = os.getenv("HF_TOKEN", "").strip()
    if token:
        return token

    print("\n" + "=" * 60)
    print("  Hugging Face Token Required (or Recommended)")
    print("=" * 60)
    print()
    print("  Your token is used to download:")
    print("    - datalab-to/chandra-ocr-2 (Open weights, token recommended for rate limits)")
    print()
    print("  Generate / find your token at:")
    print("    https://huggingface.co/settings/tokens")
    print("=" * 60 + "\n")

    token = input("Enter your Hugging Face token (hf_...) or press Enter to skip: ").strip()
    return token


def is_model_downloaded(model_dir: Path) -> bool:
    """Check if a model directory contains the minimum required files."""
    if not model_dir.exists():
        return False
    required_files = ["config.json"]
    return all((model_dir / f).exists() for f in required_files)


def verify_and_repair_model(model_name: str, target_dir: Path, token: str) -> bool:
    """
    Verify every file listed on the Hub exists locally.
    Any missing files are re-downloaded via resume_download so already-present
    files are never re-fetched.
    Returns True if verification passes (or after successful repair).
    """
    print(f"\n  Verifying files for: {model_name} ...")

    try:
        # Pass token if provided, otherwise it might be None/empty string
        expected_files = list(list_repo_files(repo_id=model_name, token=token if token else None))
    except Exception as exc:
        print(f"  WARNING: Could not fetch file list from HF Hub: {exc}")
        print("  Skipping deep verification.")
        return True

    missing = [f for f in expected_files if not (target_dir / f).exists()]

    if not missing:
        print(f"  ✓ All {len(expected_files)} file(s) verified locally")
        return True

    print(f"  ✗ {len(missing)} missing file(s) detected:")
    for path in missing:
        print(f"      - {path}")

    print(f"\n  Re-downloading missing files for {model_name} ...")
    try:
        snapshot_download(
            repo_id=model_name,
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
            token=token if token else None,
        )
        print(f"  ✓ Re-download complete for {model_name}")

        # Final check after repair
        still_missing = [f for f in expected_files if not (target_dir / f).exists()]
        if still_missing:
            print(f"  ✗ {len(still_missing)} file(s) still missing after repair:")
            for path in still_missing:
                print(f"      - {path}")
            return False
        print(f"  ✓ All {len(expected_files)} file(s) verified after repair")
        return True

    except Exception as exc:
        print(f"  ✗ Failed to repair {model_name}: {exc}")
        return False


def download_model(model_name: str, target_dir: Path, token: str) -> None:
    """Download a model from Hugging Face Hub."""
    print(f"\n{'=' * 60}")
    print(f"  Downloading: {model_name}")
    print(f"  Target:      {target_dir}")
    print(f"{'=' * 60}\n")

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_download(
            repo_id=model_name,
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
            token=token if token else None,
        )
        print(f"\n  ✓ Successfully downloaded {model_name}\n")
    except Exception as exc:
        print(f"\n  ✗ Failed to download {model_name}: {exc}\n")
        sys.exit(1)


def main():
    """Check, download, and verify all required models."""
    print("\n" + "=" * 60)
    print("  Arabic Document Processor — Model Setup")
    print("=" * 60 + "\n")

    token = get_hf_token()

    # ── Text model ────────────────────────────────────────────────
    if is_model_downloaded(TEXT_DIR):
        print(f"✓ Text model already present:   {TEXT_DIR}")
    else:
        print("✗ Text model not found — downloading ...")
        download_model(TEXT_MODEL, TEXT_DIR, token)

    verify_and_repair_model(TEXT_MODEL, TEXT_DIR, token)

    print("\n" + "=" * 60)
    print("  Model setup complete!")
    print("=" * 60 + "\n")
    print("Start the services with:")
    print("  docker-compose up -d")
    print()


if __name__ == "__main__":
    main()