@echo off
cd /d "%~dp0"

echo [1/2] Starting backend on port 8000 ...
start "Research-Backend" cmd /k "python -m uvicorn api.routes:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] Starting frontend on port 8501 ...
start "Research-Frontend" cmd /k "python -m streamlit run ui\app.py --server.headless true --server.port 8501"

echo.
echo ============================================
echo  Started! Open:  http://127.0.0.1:8501
echo  In the sidebar, enter your API Key
echo  (the API_AUTH_TOKEN value in .env).
echo ============================================
echo.
pause
