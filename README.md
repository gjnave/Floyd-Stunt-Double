# Floyd Stunt Double

A local Windows app for replacing one character in a video while following the original performance. The original Create tab uses MiniMax H3; the Head Swap + Video tab first transfers a head to a video frame with app-local Headliner models. A phone can control the app through Settings while the PC stays on.

## Install

Clone or download this repository, then double-click `INSTALL.bat` beside the `Floyd-Stunt-Double` folder. The installer sets up private Python environments, downloads the inference runtimes and all required models for both tabs, and verifies their hashes. It does not require preinstalled Python, a separate Headliner app, or a ComfyUI server. Allow roughly 55 GB for weights plus runtime and working space. On completion, double-click `RUN.bat`.

Requires Windows 64-bit and an NVIDIA CUDA GPU with a current driver. The tested machine has 24 GB VRAM; lower-memory cards may need more offloading and run more slowly or fail on demanding clips.

The member-download ZIP contains only `INSTALL.bat`, `RUN.bat`, `UPDATE.bat`, `about.nfo`, and `disclaimer.md`; it fetches this repository and the models during installation. Model files are never bundled in the ZIP or committed to this repository.

See [`Floyd-Stunt-Double/README.md`](Floyd-Stunt-Double/README.md) for the workflow and source/model attributions. Use only media you have the rights and consent to edit.
