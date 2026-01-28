@echo off
REM Setup script for Arabic OCR System (Windows)

echo ==================================================
echo    Arabic OCR System - Automated Setup
echo ==================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed.
    echo Please install Python 3.10 or higher.
    exit /b 1
)

REM Install Python dependencies for model download
echo Installing dependencies...
python -m pip install -q --upgrade pip
python -m pip install -q -r scripts\requirements.txt

REM Download models
echo.
echo Downloading models (this may take a while)...
python scripts\download_models.py

if errorlevel 1 (
    echo.
    echo ERROR: Model download failed.
    exit /b 1
)

REM Create .env if it doesn't exist
if not exist .env (
    echo.
    echo Creating .env file...
    copy .env.example .env
)

REM Create data directories
echo.
echo Creating data directories...
if not exist data\uploads mkdir data\uploads

echo.
echo ==================================================
echo    Setup Complete!
echo ==================================================
echo.
echo Next steps:
echo   1. Start the services:
echo      docker-compose up -d
echo.
echo   2. Access the application:
echo      http://localhost:8080
echo.
pause
