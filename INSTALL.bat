@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Floyd Stunt Double Setup
if exist "disclaimer.md" type "disclaimer.md"
if not defined GGF_UNATTENDED pause
if exist "about.nfo" type "about.nfo"

set "APP=%~dp0Floyd-Stunt-Double"
set "CACHE=%~dp0installer-cache"
if not exist "%CACHE%" mkdir "%CACHE%"
if not exist "%APP%\app.py" call :fetch_source
if errorlevel 1 goto failed
if not exist "%APP%\app.py" goto failed

if not exist "%APP%\runtime\uv.exe" (
  if not exist "%APP%\runtime" mkdir "%APP%\runtime"
  curl.exe --fail --location --retry 3 --output "%CACHE%\uv-0.12.13.zip" "https://github.com/astral-sh/uv/releases/download/0.12.13/uv-x86_64-pc-windows-msvc.zip"
  if errorlevel 1 goto failed
  certutil -hashfile "%CACHE%\uv-0.12.13.zip" SHA256 | findstr /i /c:"a86c9dc7bad9b03f388583b7187c05fe9951c2e0d392217e8fd43d97787f6ec2" >nul
  if errorlevel 1 goto failed
  tar.exe -xf "%CACHE%\uv-0.12.13.zip" -C "%APP%\runtime" uv.exe
  if errorlevel 1 goto failed
)
set "UV_PYTHON_INSTALL_DIR=%APP%\runtime\python"
set "UV_PYTHON_DOWNLOADS=automatic"
set "VIRTUAL_ENV="
if not exist "%APP%\.venv\Scripts\python.exe" (
  "%APP%\runtime\uv.exe" venv --managed-python --python 3.12 "%APP%\.venv"
  if errorlevel 1 goto failed
)
set "PY=%APP%\.venv\Scripts\python.exe"
"%PY%" "%APP%\engine_manager.py"
if errorlevel 1 goto failed
"%APP%\runtime\uv.exe" pip install --python "%PY%" --index-url https://download.pytorch.org/whl/cu130 torch==2.11.0+cu130 torchvision==0.26.0+cu130 torchaudio==2.11.0+cu130
if errorlevel 1 goto failed
"%PY%" -c "import torch; assert torch.cuda.is_available(), 'NVIDIA CUDA GPU or compatible driver not available'"
if errorlevel 1 goto failed
"%APP%\runtime\uv.exe" pip install --python "%PY%" -r "%APP%\engine\presets\requirements-runtime.txt" "gradio==6.29.0" "huggingface_hub>=0.35,<2" "imageio-ffmpeg>=0.6,<1" "torchcodec==0.11.1"
if errorlevel 1 goto failed
"%PY%" "%APP%\model_manager.py"
if errorlevel 1 goto failed
"%PY%" "%APP%\model_manager.py" --verify-only
if errorlevel 1 goto failed
echo Setup complete. Double-click RUN.bat.
if not defined GGF_UNATTENDED pause
exit /b 0

:fetch_source
set "SOURCE_URL=https://codeberg.org/Cognibuild/Floyd-Stunt-Double/archive/main.zip"
call :download_source
if not errorlevel 1 exit /b 0
echo Codeberg unavailable. Trying GitHub...
set "SOURCE_URL=https://github.com/gjnave/Floyd-Stunt-Double/archive/refs/heads/main.zip"
call :download_source
exit /b %ERRORLEVEL%

:download_source
set "STAGE=%CACHE%\source-%RANDOM%-%RANDOM%"
mkdir "%STAGE%"
curl.exe --fail --location --retry 2 --output "%STAGE%\source.zip" "%SOURCE_URL%"
if errorlevel 1 exit /b 1
tar.exe -tf "%STAGE%\source.zip" | findstr /r /c:"\.\./" /c:"^/" /c:"^\\" >nul
if not errorlevel 1 exit /b 1
tar.exe -xf "%STAGE%\source.zip" -C "%STAGE%"
if errorlevel 1 exit /b 1
for /d %%D in ("%STAGE%\*") do if exist "%%D\Floyd-Stunt-Double\app.py" if exist "%%D\Floyd-Stunt-Double\pipeline.py" if exist "%%D\Floyd-Stunt-Double\model_manager.py" (
  if not exist "%APP%" mkdir "%APP%"
  xcopy "%%D\Floyd-Stunt-Double\*" "%APP%\" /E /I /Y >nul
  if errorlevel 1 exit /b 1
  exit /b 0
)
exit /b 1

:failed
echo Setup stopped. Existing files and partial downloads are preserved.
if not defined GGF_UNATTENDED pause
exit /b 1
