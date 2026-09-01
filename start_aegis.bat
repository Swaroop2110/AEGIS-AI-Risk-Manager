@echo off
echo =========================================
echo  AEGIS -- Fraud War Room Dashboard
echo  Razorpay AI Buildathon 2026
echo =========================================
echo.
echo Starting AEGIS backend on http://localhost:8000 ...
echo Starting React dashboard on http://localhost:5173 ...
echo.
echo Open http://localhost:5173 in your browser.
echo.

start "AEGIS Backend" cmd /k "cd /d %~dp0backend && python main.py"
timeout /t 3 /nobreak > nul
start "AEGIS Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
