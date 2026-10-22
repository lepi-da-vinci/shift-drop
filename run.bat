@echo off
title ShiftDrop - Radial File Converter & Quick Editor
cd /d "%~dp0"

echo ========================================================
echo              ShiftDrop Windows Utility
echo ========================================================
echo.
echo ShiftDrop sedang aktif!
echo.
echo [Cara Menggunakan]:
echo 1. Periksa ikon 'S' oranye di System Tray (dekat jam Windows).
echo 2. Buka File Explorer, klik & tahan (drag) file gambar atau PDF.
echo 3. Sambil men-drag, tekan tombol 'Shift' pada keyboard.
echo 4. Menu radial akan muncul di bawah kursor mouse.
echo 5. Lepaskan file ke sektor yang diinginkan.
echo.
echo [Catatan]:
echo Biarkan jendela ini tetap terbuka saat menggunakan ShiftDrop.
echo Tutup jendela ini atau tekan Ctrl+C untuk keluar.
echo ========================================================
echo.

".venv\Scripts\python.exe" main.py
pause
