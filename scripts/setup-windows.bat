@echo off
echo === SocialControl AI setup (Windows) ===
where python >nul 2>nul || (echo Python nahi mila. https://www.python.org/downloads/ se install karo, "Add to PATH" tick karna & pause & exit /b 1)
where node >nul 2>nul || (echo Node.js nahi mila. https://nodejs.org se LTS install karo & pause & exit /b 1)
where ffmpeg >nul 2>nul || (echo ffmpeg install kar raha hoon... & winget install -e --id Gyan.FFmpeg)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
call npm install
if not exist .env copy .env.example .env
echo.
echo Setup done! Ab chalao:  scripts\start-windows.bat
pause
