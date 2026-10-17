# Floyd Stunt Double

Replace one character in a source video while following the original performance. The original **Create** tab remains available. The **Head Swap + Video** tab first transfers a head to one video frame with Floyd Headliner's image workflow, then uses that edited frame to guide the video swap. The PC runs the models locally; Settings can create a temporary link for phone control.

## Windows installation

Download the small installer package and double-click `INSTALL.bat`. It keeps the app in the adjacent `Floyd-Stunt-Double` folder, provisions private Python through uv, and prepares the app runtime **without downloading model weights**. Use `RUN.bat` after setup completes. If models are missing, Settings opens with a friendly install choice. Select Video Swap first (about 36.2 GB); optionally add Head Swap + Video later (about 19.0 GB of weights plus a separate private Python 3.11 runtime). Settings verifies each download and offers a separately confirmed removal action for each app-owned pack. No model weights are packaged in the ZIP.

Liz's two-step video guide in Settings explains the model choice and can be skipped or replayed. Video Swap changes the overall character; optional Head Swap first edits a selected frame for closer facial likeness while aiming to retain the original body and clothing. Both model packs download to the PC, even when you control the app from a phone. The two short Liz clips are app assets, not model weights.

The Video Swap choice downloads H3 Ref2VA weights and the H3 Character Swap V1.5 and Turbo LoRAs. The optional Head Swap choice downloads this app's own Qwen Image 2.1, BFS Head Swap, and Viggle Turbo files. Both choices together total about 55 GB of model weights, with extra working disk space needed. The app never relies on a separately installed Floyd Headliner or copies its models. The package includes the owner's disclaimer and about files. Use media you have the rights and permission to edit.

## Using it

1. Add the source video and a reference picture of the new character. Loading a video resets Start to zero and presets Length to that video's full duration; edit either value freely afterward.
2. Preview the chosen starting frame and describe which person in the video changes.
3. Press **Turbo preview** to check a short, smaller video first, or **Generate** for the selected output quality and full chosen length. Turbo preview defaults to three seconds; change its length under More control, or set it to `0` to preview the entire selected interval. Both workflows use the same app-owned models. Length defaults to the full uploaded clip, but you can enter any shorter duration or set it to `0` for the rest of the video from Start. Long clips run as consecutive eight-second parts and may show joins.
4. Watch or download the finished file in `outputs`.

Local access needs no login. In Settings, choose a phone access mode and restart the app. A blank remote password allows anyone with the link to use it. A password affects phone access only; the local page stays password-free.

In **Head Swap + Video**, upload the source video and head reference, preview the selected frame, then press **Swap the visible head automatically** when there is one clear person. Check the edited still and generate the video. The automatic path follows Headliner's unpainted image workflow; it may change other details in the still. For several people or when you need to preserve unpainted pixels exactly, expand **Choose a specific head by painting**, paint the full target head including hair, and press **Swap using painted area**. To try a different head reference, upload it and press **Try another head with same selection**; the app reuses the saved selection without making the phone upload the painted canvas again. The video model uses the still as a guide, so it can still reinterpret clothes or facial details on motion or cuts. Preview a short clip before processing a long one.

Turbo preview also works after the head-swapped frame is ready. It forces the fast eight-step adapter and aims for about half the width and height of the selected full output, subject to the model's 256-pixel minimum per side. Preview MP4s are labeled `PREVIEW` in `outputs`; full Generate never inherits the preview length or smaller dimensions.

Finished MP4 files are kept under `Floyd-Stunt-Double/outputs`. If a phone browser disconnects or refreshes before it shows the finished result, press **Show latest saved video on this PC** under the player to load the newest saved MP4 without regenerating. The button can show a result from either tab or another session on the same PC; check the filename in the status line.

A short, quiet two-tone chime plays when a video or head swap finishes if the browser allows sound after the Generate/Swap click. Phone browsers may suppress audio when the page is closed or asleep.

## Sources

- Inference runtime: `Koongrizzly/MiniMax_H3_Standalone_app` at `fc86444383a8888de8036356a5febd5141010c41` (downloaded during installation)
- Quantized H3 model components: `koongrizzly/MiniMax_H3_int4_W4A8_ConvRot_Pruned` at `483eee468874f1fd12dd2159666b7a72f0504cbc`
- Character adapter: `akatz-ai/MiniMax-H3-Character-Swap-LoRA` V1.5 at `d06323b7c8e70e97cdab48b78a1e05f786c8cba9`
- Fast adapter: `lightx2v/Minimax-h3-Turbo` at `a29e57d195f80ead07c89f89e55ecf2911e893c5`
- Head-transfer inference core: `Cognibuild/Floyd-Headliner` at `24b9cfdc0f72d06372eb90b105575991436be643` (GPLv3 Comfy core modules are downloaded with their license; no ComfyUI server)
- Head-transfer weights: `Comfy-Org/Qwen-Image-2.1`, `Comfy-Org/Qwen3-VL`, `Alissonerdx/BFS-Best-Face-Swap`, and `Viggle/Qwen-Image-2.1-viggle-turbo` at the pinned revisions in `headliner_addon.py`

The weights are obtained directly from their model repositories. Their own terms apply. GGF does not package those weights.
