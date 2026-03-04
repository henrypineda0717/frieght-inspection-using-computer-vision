@echo off
echo ========================================
echo Clearing Python Cache and Restarting
echo ========================================
echo.

echo [1/3] Stopping any running server...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] Clearing Python cache files...
for /r %%i in (__pycache__) do (
    if exist "%%i" (
        echo Removing: %%i
        rmdir /s /q "%%i"
    )
)

for /r %%i in (*.pyc) do (
    if exist "%%i" (
        echo Removing: %%i
        del /q "%%i"
    )
)

echo [3/3] Starting server...
echo.
echo Server starting on http://localhost:8000
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
