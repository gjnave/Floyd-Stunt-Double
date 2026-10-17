# Floyd Stunt Double handoff

## Product and layout

Follow `D:\apps2review\GGF-APP-BUILD-GUIDE.md` and the root GGF branding guide before changing the UI or release. `INSTALL.bat` sits beside `Floyd-Stunt-Double/`; the customer ZIP contains only `INSTALL.bat`, `RUN.bat`, `UPDATE.bat`, `disclaimer.md`, and `about.nfo`. Do not package app source, models, caches, environments, jobs, or outputs. Never delete files without the owner's explicit permission.

The existing **Create** tab is the MiniMax H3 character/body-swap flow. The additive **Head Swap + Video** tab previews a frame of an uploaded video, automatically transfers the one visible head when possible, and retains optional painting to choose a specific head. The edited still guides the existing H3 video generator. Painting composites only selected pixels over the original still, but video generation can still change details; do not promise pixel-identical clothing across all frames.

## Models and runtimes

The standard installer prepares the app runtime without model weights. Settings downloads and verifies each selected model pack into this app; never point it at an installed copy of Floyd Headliner or another app. The six MiniMax H3 model files are managed by `Floyd-Stunt-Double/model_manager.py`; the five Head Swap files and pinned Headliner source revision are defined in `Floyd-Stunt-Double/headliner_addon.py`. The base app uses uv-managed Python 3.12 and CUDA 13 PyTorch 2.11. The isolated Head Swap worker uses uv-managed Python 3.11 and CUDA 13 PyTorch 2.10. `INSTALL.bat models-video` and `INSTALL.bat models-head` handle the two optional downloads. Together they need roughly 55 GB for weights plus runtime, downloads, and working space. Preserve partial downloads on failure.

`pipeline.py` owns the single active-generation guard, cancellation, video plan, and the one-shot Headliner worker protocol. `headliner_addon.py` owns source/model verification, mask extraction, head transfer, and compositing. `app.py` owns both tab flows and the optional model-download guide. `update_source.py` fetches current app source from Codeberg first, GitHub second. An update must not silently install an optional model pack.

## Verification

From this folder, use `cmd.exe /d /c "set GGF_UNATTENDED=1&& INSTALL.bat"` to exercise the real installer. Run `Floyd-Stunt-Double\.venv\Scripts\python.exe -m unittest discover -s tests -v`. `tests/smoke_guided.py --video <file> --head <image> --head-box x1,y1,x2,y2 --seconds 1` performs a real frame-to-video smoke; it requires the downloaded models and an NVIDIA GPU. A completed test on 2026-10-16 produced `Floyd-Stunt-Double/outputs/Floyd-Stunt-Double-Head-20261016-190401-0870c68f.png` and `Floyd-Stunt-Double/outputs/Floyd-Stunt-Double-20261016-190401-36f37248.mp4` without touching the existing Create tab.

For publishing, push individual source files to Codeberg `Cognibuild/Floyd-Stunt-Double` (primary) and GitHub `gjnave/Floyd-Stunt-Double`; verify both archives contain `headliner_addon.py` and `headliner-requirements.txt`. Then rebuild the installer-only ZIP under the stable name `Floyd-Stunt-Double-Installer.zip`, preserving the prior ZIP first, and back up the source/installer to Drive. Do not maintain a source ZIP inside either Git repository. Record new remote commits and Drive IDs here after publication.

## 2026-10-16 release snapshot

The guided flow source is published on Codeberg (latest browser commit `5a12c00431a3bac1eee8c2619d89d06feb0093ca`) and GitHub (Git commit `386f243`, before this handoff-only note). Codeberg Git HTTPS credentials still return HTTP 403; browser upload worked. Both repository archives were checked by `update_source.py --check`, which selected Codeberg and reported `Changed: none`. The installer-only ZIP is 3,716 bytes and contains exactly the five files listed above; its prior version is preserved locally as `Floyd-Stunt-Double-Installer-before-headswap-20261016.zip`.

Drive folder ID: `1tgFBqgkPEzUanQ7DJQ5ZFbVbr0n9dEaB`. Stable source backup ID: `1M11xxLcHIO3Ln3mRcEy3P4rwq_mYT7qA`; stable installer ZIP ID: `10ZjGdOXt70L_j_VHBdHSNMinGTEloqNQ`. Both were updated in place and their sizes read back as 34,469 and 3,716 bytes respectively. Existing Drive links remain the same. The installed models are excluded from all source and installer archives.
## Phone output recovery and repeat Head Swap

Finished MP4 files are written to `Floyd-Stunt-Double/outputs` before the UI receives its final update. A phone page can disconnect during a long generation, leaving a valid MP4 on disk but an empty player. Both tabs now expose **Show latest saved video on this PC**, which loads the newest saved MP4; the status includes its filename. This is explicit so a fresh session does not silently display another user's output.

The Head Swap editor can occasionally fail Gradio preprocessing while uploading its PNG canvas from a phone (`OSError: unrecognized data stream contents`). A successful swap now saves a mask PNG alongside the edited still. **Try another head with same selection** reruns the swap from that saved mask and original preview frame, bypassing the editor upload. A head-reference change preserves the preview and mask but disables video generation until the swap succeeds again. The editor-preprocessing failure handler re-enables the swap button and gives a recovery instruction.

## Optional model packs and automatic Head Swap

`INSTALL.bat` now prepares the app runtime without model weights. The running app opens Settings automatically if Video Swap models are absent. Settings invokes the same CMD installer with `models-video` or `models-head`, verifies the chosen pack, and shows progress through a background job. Video Swap is 36.2 GB of model weights; Head Swap adds 19.0 GB and its separate Python 3.11 runtime. The two removal actions require an explicit second click and target only exact app-owned model paths and their cached download links; they do not remove outputs or another app's models. No model sharing is implemented.

The guided tab now has an automatic, unpainted one-person head swap matching Headliner's simple path. Painted selection remains in an optional accordion for multiple people or tighter pixel preservation. A browser-side low-volume two-tone chime fires when video generation or a head swap completes, subject to browser audio restrictions. `model_packs.py` and `tests/test_optional_models.py` are source files; `update_source.py` lists the former.

The root `INSTALL.bat` accepts a downloaded repository by its app entry point, not by optional feature files. It creates the UV-managed runtime and installs dependencies; model packs are requested from Settings. Do not add a version-specific source-file gate to the installer. Mirror the complete source revision to Codeberg and GitHub before distributing an installer ZIP.

## Liz model-download guide

When Video Swap weights are absent, Settings opens with a skippable two-step Liz card before the model buttons. Step 1 says the user must first download Video Swap models to the **PC**; phone access controls the PC and does not run/download weights on the phone. Step 2 explains full-character Video Swap versus optional Head Swap for closer facial likeness and an attempt to retain the source body/clothes. Next, Skip, Done, and Replay are wired; if Video Swap weights are installed initially, the card is collapsed but Replay remains available. The static Liz poster is `Floyd-Stunt-Double/assets/liz-guide.png`.

Speaking Liz clips were rendered on 2026-10-16 using the restored official LTX 2.5 distilled image-to-video pipeline and `D:\liz\ltx25\liz_medium_512.png`. They are `assets/liz-stunt-welcome.mp4` and `assets/liz-stunt-choices.mp4`, both 512x512, 24 fps, about 10 seconds, with AAC speech. The local ASR check recovered the intended setup instructions; the poster remains the fallback if either clip is absent. The six gated weights are in `D:\liz\ltx25\models\ltx-2.5`; the restored source checkout at `D:\apps2review\ltx25\New folder\LTX-2` links to those weights. Its `sft_loader.py` has a local `backend="pread"` change to avoid the Windows invalid-storage failure on large safetensors. No model weights belong in this Git repository or installer ZIP. Restart the app to pick up the new clips; do not interrupt a user generation just to activate them.
