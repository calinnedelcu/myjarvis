@echo off
:: Wait a few seconds for audio/GPU drivers to be ready after login
timeout /t 10 /nobreak >nul

cd /d "C:\Projects\jarvis"
"C:\Users\Calin\AppData\Local\Programs\Python\Python314\python.exe" main.py
