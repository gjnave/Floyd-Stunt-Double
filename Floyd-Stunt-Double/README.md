# Floyd Stunt Double

Replace one character in a source video while following the original performance. The original **Create** tab remains available. The **Head Swap + Video** tab first transfers a head to one video frame with Floyd Headliner's image workflow, then uses that edited frame to guide the video swap. The PC runs the models locally; Settings can create a temporary link for phone control.

## Windows installation

Download the small installer package and double-click `INSTALL.bat`. It keeps the app in the adjacent `Floyd-Stunt-Double` folder, provisions private Python through uv, installs CUDA PyTorch and runtime dependencies, then downloads and verifies every required model file for both tabs. Head Swap runs in a separate private Python 3.11 environment so its dependencies cannot change the original video pipeline. No model weights are packaged in the ZIP. Use `RUN.bat` after setup completes.

The installer downloads H3 Ref2VA weights, the H3 Character Swap V1.5 and Turbo LoRAs, plus Stunt Double's own Qwen Image 2.1, BFS Head Swap, and Viggle Turbo files for the guided tab. Total model download is about 55 GB, with extra working disk space needed. It never relies on a separately installed Floyd Headliner or copies its models. The package includes the owner's disclaimer and about files. Use media you have the rights and permission to edit.

## Using it

1. Add the source video and a reference picture of the new character.
2. Preview the chosen starting frame and describe which person in the video changes.
3. Generate. The default is eight seconds; set Length to `0` for the rest of the video. Long clips run as consecutive eight-second parts and may show joins.
4. Watch or download the finished file in `outputs`.

Local access needs no login. In Settings, choose a phone access mode and restart the app. A blank remote password allows anyone with the link to use it. A password affects phone access only; the local page stays password-free.

In **Head Swap + Video**, upload the source video and head reference, preview the selected frame, paint the full target head including hair, then press **Swap head**. Check the edited still and generate the video. Unpainted pixels in that still are restored from the original frame. The video model uses the still as a guide, so it can still reinterpret clothes or facial details on motion or cuts. Preview a short clip before processing a long one.

## Sources

- Inference runtime: `Koongrizzly/MiniMax_H3_Standalone_app` at `fc86444383a8888de8036356a5febd5141010c41` (downloaded during installation)
- Quantized H3 model components: `koongrizzly/MiniMax_H3_int4_W4A8_ConvRot_Pruned` at `483eee468874f1fd12dd2159666b7a72f0504cbc`
- Character adapter: `akatz-ai/MiniMax-H3-Character-Swap-LoRA` V1.5 at `d06323b7c8e70e97cdab48b78a1e05f786c8cba9`
- Fast adapter: `lightx2v/Minimax-h3-Turbo` at `a29e57d195f80ead07c89f89e55ecf2911e893c5`
- Head-transfer inference core: `Cognibuild/Floyd-Headliner` at `24b9cfdc0f72d06372eb90b105575991436be643` (GPLv3 Comfy core modules are downloaded with their license; no ComfyUI server)
- Head-transfer weights: `Comfy-Org/Qwen-Image-2.1`, `Comfy-Org/Qwen3-VL`, `Alissonerdx/BFS-Best-Face-Swap`, and `Viggle/Qwen-Image-2.1-viggle-turbo` at the pinned revisions in `headliner_addon.py`

The weights are obtained directly from their model repositories. Their own terms apply. GGF does not package those weights.
