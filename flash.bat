:: filepath: /c:/Users/insilicon/programming/ScienceFair2025/flash.bat
@echo off
setlocal EnableDelayedExpansion

:: Check if esp directory exists
if not exist "esp" (
    echo Error: esp directory not found!
    pause
    exit /b 1
)

:: Use passed PORT or fallback to COM3
if "!PORT!"=="" set PORT=COM3

echo Uploading entire esp directory to ESP32...
ampy --port !PORT! put esp /
if !errorlevel! neq 0 (
    echo Upload failed. Check your connection and port.
    pause
    exit /b 1
)

echo Upload successful!
pause