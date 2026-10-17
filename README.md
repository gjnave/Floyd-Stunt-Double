![Floyd Stunt Double — Liz model guide](Floyd-Stunt-Double/assets/liz-guide.png)

# Floyd Stunt Double

## A Get Going Fast Application

### [Explore Get Going Fast tools](https://getgoingfast.pro/tools/)

An individual Stunt Double tool page is not published yet. This public repository provides the app source and manual setup route; the guided member installer is separate.

A local Windows app for replacing one character in a video while following the original performance. The original Create tab uses MiniMax H3; the Head Swap + Video tab first transfers a head to a video frame with app-local Headliner models. A phone can control the app through Settings while the PC stays on.

## Manual installation from source

Use Windows 64-bit, a current NVIDIA driver and [uv](https://docs.astral.sh/uv/getting-started/installation/). The tested machine has 24 GB VRAM; smaller GPUs are not guaranteed. Install [Git for Windows](https://git-scm.com/download/win), then open **Command Prompt**:

1. Clone the repository and create a private Python 3.12 environment in the app folder:

   ```bat
   git clone https://codeberg.org/Cognibuild/Floyd-Stunt-Double.git
   cd Floyd-Stunt-Double
   uv venv --managed-python --python 3.12 Floyd-Stunt-Double\.venv
   ```

2. Fetch the pinned app-local MiniMax engine and install its CUDA 13 dependencies:

   ```bat
   Floyd-Stunt-Double\.venv\Scripts\python.exe Floyd-Stunt-Double\engine_manager.py
   uv pip install --python Floyd-Stunt-Double\.venv\Scripts\python.exe --index-url https://download.pytorch.org/whl/cu130 torch==2.11.0+cu130 torchvision==0.26.0+cu130 torchaudio==2.11.0+cu130
   uv pip install --python Floyd-Stunt-Double\.venv\Scripts\python.exe -r Floyd-Stunt-Double\engine\presets\requirements-runtime.txt "gradio==6.29.0" "huggingface_hub>=0.35,<2" "imageio-ffmpeg>=0.6,<1" "torchcodec==0.11.1"
   ```

3. Download and verify the Video Swap model pack (about 36.2 GB):

   ```bat
   Floyd-Stunt-Double\.venv\Scripts\python.exe Floyd-Stunt-Double\model_manager.py
   Floyd-Stunt-Double\.venv\Scripts\python.exe Floyd-Stunt-Double\model_manager.py --verify-only
   ```

4. Optionally add Head Swap + Video for closer facial likeness (about 19 GB more):

   ```bat
   uv venv --managed-python --python 3.11 Floyd-Stunt-Double\engine\headliner\.venv
   uv pip install --python Floyd-Stunt-Double\engine\headliner\.venv\Scripts\python.exe --index-url https://download.pytorch.org/whl/cu130 torch==2.10.0+cu130 torchvision==0.25.0+cu130 torchaudio==2.10.0+cu130
   uv pip install --python Floyd-Stunt-Double\engine\headliner\.venv\Scripts\python.exe -r Floyd-Stunt-Double\headliner-requirements.txt
   Floyd-Stunt-Double\.venv\Scripts\python.exe Floyd-Stunt-Double\headliner_addon.py
   ```

5. Double-click `RUN.bat`, or run `Floyd-Stunt-Double\.venv\Scripts\python.exe Floyd-Stunt-Double\app.py`. The app uses its own models; no separate Headliner or ComfyUI server is required. The guided member installer remains outside this source repository.

Requires Windows 64-bit and an NVIDIA CUDA GPU with a current driver. The tested machine has 24 GB VRAM; lower-memory cards may need more offloading and run more slowly or fail on demanding clips.

The separate member-download ZIP contains the guided CMD installer and supporting files. Model files are never bundled in that ZIP or committed to this source repository.

See [`Floyd-Stunt-Double/README.md`](Floyd-Stunt-Double/README.md) for the workflow and source/model attributions. Use only media you have the rights and consent to edit.
