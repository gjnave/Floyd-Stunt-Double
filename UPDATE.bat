@echo off
setlocal
cd /d "%~dp0"
if not exist "Floyd-Stunt-Double\.venv\Scripts\python.exe" (
  echo Run INSTALL.bat first.
  pause
  exit /b 1
)
"Floyd-Stunt-Double\.venv\Scripts\python.exe" "Floyd-Stunt-Double\update_source.py"
if errorlevel 1 (
  echo Update failed. Existing files are preserved or backed up.
  pause
  exit /b 1
)
echo Update complete. Start or restart RUN.bat.
pause
