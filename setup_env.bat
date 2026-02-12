@echo off
echo ========================================
echo   ANK Backend - Environment Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Checking Python version...
python --version
echo.

REM Check if virtual environment already exists
if exist "env\Scripts\activate.bat" (
    echo [WARNING] Virtual environment already exists in 'env' folder.
    echo Do you want to recreate it? (Y/N)
    set /p recreate="> "
    if /i not "%recreate%"=="Y" (
        echo Skipping virtual environment creation...
        goto :activate
    )
    echo Removing existing virtual environment...
    rmdir /s /q env
)

echo [2/5] Creating virtual environment...
python -m venv env
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b 1
)
echo Virtual environment created successfully!
echo.

:activate
echo [3/5] Activating virtual environment...
call env\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)
echo Virtual environment activated!
echo.

echo [4/5] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARNING] Failed to upgrade pip, continuing anyway...
)
echo.

echo [5/5] Installing requirements from requirements.txt...
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found!
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements!
    pause
    exit /b 1
)
echo.

echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Virtual environment is ready in the 'env' folder.
echo.
echo To activate it manually, run:
echo   env\Scripts\activate.bat
echo.
echo To deactivate, run:
echo   deactivate
echo.
pause
