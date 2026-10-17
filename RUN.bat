@echo off
setlocal
cd /d "%~dp0"
if exist "about.nfo" type "about.nfo"
if not exist "Floyd-Stunt-Double\.venv\Scripts\python.exe" (
  echo Run INSTALL.bat first.
  pause
  exit /b 1
)
:launch
"Floyd-Stunt-Double\.venv\Scripts\python.exe" "Floyd-Stunt-Double\app.py"
if %ERRORLEVEL%==75 goto launch
if errorlevel 1 pause
