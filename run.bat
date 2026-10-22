@echo off
title ShiftDrop
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment tidak ditemukan.
    echo Harap jalankan 'python -m venv .venv' dan 'pip install -r requirements.txt' terlebih dahulu.
    pause
    exit /b
)

echo Memulai ShiftDrop di background...
echo Cek icon 'S' oranye di System Tray Windows (pojok kanan bawah dekat jam).
start "" ".venv\Scripts\pythonw.exe" main.py
exit

