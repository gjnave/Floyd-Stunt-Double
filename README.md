# Floyd Stunt Double

A local Windows app for replacing one character in a video while following the original performance. The original Create tab uses MiniMax H3; the Head Swap + Video tab first transfers a head to a video frame with app-local Headliner models. A phone can control the app through Settings while the PC stays on.

## Install

Clone or download this repository, then double-click `INSTALL.bat` beside the `Floyd-Stunt-Double` folder. The installer sets up private Python and the app runtime, but does not download model weights. Double-click `RUN.bat`; if Video Swap models are absent, the app opens Settings with a clear installation choice. The Video Swap pack is about 36.2 GB. Head Swap + Video adds about 19.0 GB in model weights and its separate runtime; both packs are downloaded and verified only when selected in Settings. There is no need for preinstalled Python, a separate Headliner app, or a ComfyUI server. Allow extra disk space for runtimes and working files.

Requires Windows 64-bit and an NVIDIA CUDA GPU with a current driver. The tested machine has 24 GB VRAM; lower-memory cards may need more offloading and run more slowly or fail on demanding clips.

The member-download ZIP contains only `INSTALL.bat`, `RUN.bat`, `UPDATE.bat`, `about.nfo`, and `disclaimer.md`; it fetches this repository and the models during installation. Model files are never bundled in the ZIP or committed to this repository.

See [`Floyd-Stunt-Double/README.md`](Floyd-Stunt-Double/README.md) for the workflow and source/model attributions. Use only media you have the rights and consent to edit.
