# Floyd Stunt Double

Replace one character in a source video while following the original performance. Upload a video, a character image, describe which person changes, preview the start frame, then generate. The PC runs MiniMax H3 locally; Settings can create a temporary link for phone control.

## Windows installation

Download the small installer package and double-click `INSTALL.bat`. It keeps the app in the adjacent `Floyd-Stunt-Double` folder, provisions private Python 3.12 through uv, installs CUDA PyTorch and runtime dependencies, then downloads and verifies every required model file. No model weights are packaged in the ZIP. Use `RUN.bat` after setup completes.

The default install uses the H3 Ref2VA quantized weights, the H3 Character Swap V1.5 LoRA, and the matching eight-step Turbo LoRA. Model download is about 36 GB, with extra working disk space needed. The package includes the owner's disclaimer and about files. Use media you have the rights and permission to edit.

## Using it

1. Add the source video and a reference picture of the new character.
2. Preview the chosen starting frame and describe which person in the video changes.
3. Generate. The default is eight seconds; set Length to `0` for the rest of the video. Long clips run as consecutive eight-second parts and may show joins.
4. Watch or download the finished file in `outputs`.

Local access needs no login. In Settings, choose a phone access mode and restart the app. A blank remote password allows anyone with the link to use it. A password affects phone access only; the local page stays password-free.

This is character replacement, so face, hair and clothing can change. The model may drift on cuts or complicated movement. Preview a short clip before processing a long one.

## Sources

- Inference runtime: `Koongrizzly/MiniMax_H3_Standalone_app` at `fc86444383a8888de8036356a5febd5141010c41` (downloaded during installation)
- Quantized H3 model components: `koongrizzly/MiniMax_H3_int4_W4A8_ConvRot_Pruned` at `483eee468874f1fd12dd2159666b7a72f0504cbc`
- Character adapter: `akatz-ai/MiniMax-H3-Character-Swap-LoRA` V1.5 at `d06323b7c8e70e97cdab48b78a1e05f786c8cba9`
- Fast adapter: `lightx2v/Minimax-h3-Turbo` at `a29e57d195f80ead07c89f89e55ecf2911e893c5`

The weights are obtained directly from their model repositories. Their own terms apply. GGF does not package those weights.
