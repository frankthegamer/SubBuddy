# SubBuddy - Local Environment Setup Script
# Run this once after unzipping the project folder.
# Prerequisites: Python 3.10+, MySQL Server running locally

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  SubBuddy - Local Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# -------------------------------------------------------
# 1. Check Python is available
# -------------------------------------------------------
Write-Host "`n[1/4] Checking Python installation..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found. Please install Python 3.10+ and try again." -ForegroundColor Red
    exit 1
}
python --version

# -------------------------------------------------------
# 2. Create virtual environment
# -------------------------------------------------------
Write-Host "`n[2/4] Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

# Temporarily allow script execution for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate venv
.\venv\Scripts\Activate.ps1
Write-Host "Virtual environment activated." -ForegroundColor Green

# -------------------------------------------------------
# 3. Install dependencies
# -------------------------------------------------------
Write-Host "`n[3/4] Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
Write-Host "Dependencies installed." -ForegroundColor Green

# -------------------------------------------------------
# 4. Initialize database
# -------------------------------------------------------
Write-Host "`n[4/4] Setting up database..." -ForegroundColor Yellow
Write-Host "Make sure your .env file is configured before continuing." -ForegroundColor Magenta
Write-Host "(Copy .env.example to .env and fill in your MySQL credentials)`n"

$confirm = Read-Host "Has your .env file been configured? (y/n)"
if ($confirm -ne 'y') {
    Write-Host "`nSetup paused. Configure your .env file and re-run this script." -ForegroundColor Red
    exit 0
}

python app/database/setup.py

# -------------------------------------------------------
# Done
# -------------------------------------------------------
Write-Host "`n================================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To run SubBuddy:"
Write-Host "  1. Activate venv:  .\venv\Scripts\Activate.ps1"
Write-Host "  2. Start server:   python -m uvicorn app.main:app --reload"
Write-Host "  3. Open browser:   http://127.0.0.1:8000"
Write-Host ""
Write-Host "Default admin login:"
Write-Host "  Email:    admin@subbuddy.com"
Write-Host "  Password: admin123"
Write-Host ""
