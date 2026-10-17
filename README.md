# Floyd Stunt Double

A local Windows app for replacing one character in a video while following the original performance. The PC runs MiniMax H3; a phone can control the app through Settings while the PC stays on.

## Install

Clone or download this repository, then double-click `INSTALL.bat` beside the `Floyd-Stunt-Double` folder. The installer sets up a private Python environment, downloads the inference runtime and all six required model/adaptor files, and verifies the model hashes. It does not require a preinstalled Python or a separate ComfyUI server. Allow roughly 36 GB for weights plus runtime and working space. On completion, double-click `RUN.bat`.

Requires Windows 64-bit and an NVIDIA CUDA GPU with a current driver. The tested machine has 24 GB VRAM; lower-memory cards may need more offloading and run more slowly or fail on demanding clips.

The member-download ZIP contains only `INSTALL.bat`, `RUN.bat`, `UPDATE.bat`, `about.nfo`, and `disclaimer.md`; it fetches this repository and the models during installation. Model files are never bundled in the ZIP or committed to this repository.

See [`Floyd-Stunt-Double/README.md`](Floyd-Stunt-Double/README.md) for the workflow and source/model attributions. Use only media you have the rights and consent to edit.
