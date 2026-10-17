# Floyd Stunt Double handoff

## Product and layout

Follow `D:\apps2review\GGF-APP-BUILD-GUIDE.md` and the root GGF branding guide before changing the UI or release. `INSTALL.bat` sits beside `Floyd-Stunt-Double/`; the customer ZIP contains only `INSTALL.bat`, `RUN.bat`, `UPDATE.bat`, `disclaimer.md`, and `about.nfo`. Do not package app source, models, caches, environments, jobs, or outputs. Never delete files without the owner's explicit permission.

The existing **Create** tab is the MiniMax H3 character/body-swap flow. The additive **Head Swap + Video** tab previews a frame of an uploaded video, lets the user paint the target head and hair, transfers the head from an uploaded reference photo with Headliner's pinned inference core, then uses the edited still as the character reference for the existing H3 video generator. Only painted pixels are composited over the original still, so the rest of the frame is preserved at the handoff. Video generation can still change details; do not promise pixel-identical clothing across all frames.

## Models and runtimes

The standard installer must download and verify *all* models into this app. Never point it at an installed copy of Floyd Headliner or another app. The six MiniMax H3 model files are managed by `Floyd-Stunt-Double/model_manager.py`; the five Head Swap files and pinned Headliner source revision are defined in `Floyd-Stunt-Double/headliner_addon.py`. The base app uses uv-managed Python 3.12 and CUDA 13 PyTorch 2.11. The isolated Head Swap worker uses uv-managed Python 3.11 and CUDA 13 PyTorch 2.10. `INSTALL.bat headswap` is only a repair/update branch; the normal `INSTALL.bat` installs both sets. These files are large: budget roughly 55 GB for weights plus runtime, downloads, and working space. Preserve partial downloads on failure.

`pipeline.py` owns the single active-generation guard, cancellation, video plan, and the one-shot Headliner worker protocol. `headliner_addon.py` owns source/model verification, mask extraction, head transfer, and compositing. `app.py` owns both tab flows. `update_source.py` fetches current app source from Codeberg first, GitHub second; after an update, Settings installs missing Head Swap models before restarting.

## Verification

From this folder, use `cmd.exe /d /c "set GGF_UNATTENDED=1&& INSTALL.bat"` to exercise the real installer. Run `Floyd-Stunt-Double\.venv\Scripts\python.exe -m unittest discover -s tests -v`. `tests/smoke_guided.py --video <file> --head <image> --head-box x1,y1,x2,y2 --seconds 1` performs a real frame-to-video smoke; it requires the downloaded models and an NVIDIA GPU. A completed test on 2026-10-16 produced `Floyd-Stunt-Double/outputs/Floyd-Stunt-Double-Head-20261016-190401-0870c68f.png` and `Floyd-Stunt-Double/outputs/Floyd-Stunt-Double-20261016-190401-36f37248.mp4` without touching the existing Create tab.

For publishing, push individual source files to Codeberg `Cognibuild/Floyd-Stunt-Double` (primary) and GitHub `gjnave/Floyd-Stunt-Double`; verify both archives contain `headliner_addon.py` and `headliner-requirements.txt`. Then rebuild the installer-only ZIP under the stable name `Floyd-Stunt-Double-Installer.zip`, preserving the prior ZIP first, and back up the source/installer to Drive. Do not maintain a source ZIP inside either Git repository. Record new remote commits and Drive IDs here after publication.

## 2026-10-16 release snapshot

The guided flow source is published on Codeberg (latest browser commit `5a12c00431a3bac1eee8c2619d89d06feb0093ca`) and GitHub (Git commit `386f243`, before this handoff-only note). Codeberg Git HTTPS credentials still return HTTP 403; browser upload worked. Both repository archives were checked by `update_source.py --check`, which selected Codeberg and reported `Changed: none`. The installer-only ZIP is 3,716 bytes and contains exactly the five files listed above; its prior version is preserved locally as `Floyd-Stunt-Double-Installer-before-headswap-20261016.zip`.

Drive folder ID: `1tgFBqgkPEzUanQ7DJQ5ZFbVbr0n9dEaB`. Stable source backup ID: `1M11xxLcHIO3Ln3mRcEy3P4rwq_mYT7qA`; stable installer ZIP ID: `10ZjGdOXt70L_j_VHBdHSNMinGTEloqNQ`. Both were updated in place and their sizes read back as 34,469 and 3,716 bytes respectively. Existing Drive links remain the same. The installed models are excluded from all source and installer archives.
