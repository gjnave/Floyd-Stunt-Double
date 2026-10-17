"""GGF Floyd Stunt Double: simple video character replacement UI."""
from __future__ import annotations

import argparse
import ipaddress
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import gradio as gr
from PIL import Image

from access import MODES, load as load_access, save as save_access, verify as verify_access
from headliner_addon import ready as headliner_ready, swap as swap_head
from pipeline import APP, JobPlan, busy, cancel_active, generate, missing_models, video_info, ffmpeg_path
from update_source import check as check_source, apply as apply_source

CSS = (APP / "ui.css").read_text(encoding="utf-8")
ACTIVE_ACCESS = "local"
ACTIVE_LINK = ""
ACTIVE_LOCAL = ""

CTRL_ENTER = """() => {
  if (window.__ggfStuntShortcut) return;
  window.__ggfStuntShortcut = true;
  document.addEventListener('keydown', event => {
    if (event.key !== 'Enter' || !event.ctrlKey || event.repeat || event.isComposing) return;
    const buttons = document.querySelectorAll('#ggf-generate button, button#ggf-generate, #ggf-guided-generate button, button#ggf-guided-generate');
    const btn = [...buttons].find(item => !item.disabled && item.offsetParent !== null);
    if (!btn) return;
    event.preventDefault(); btn.click();
  });
}"""


def _path(value):
    if isinstance(value, dict):
        return Path(value.get("path") or value.get("name") or "")
    return Path(value) if value else None


def preview_frame(video, start):
    path = _path(video)
    if not path or not path.is_file():
        raise gr.Error("Upload a video first.")
    total, width, height, _ = video_info(path)
    at = max(0.0, float(start or 0))
    if at >= total:
        raise gr.Error(f"Choose a time before {total:.1f} seconds.")
    folder = APP / "previews"
    folder.mkdir(exist_ok=True)
    target = folder / f"frame-{int(time.time() * 1000)}.jpg"
    import subprocess
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(at),
           "-i", str(path), "-frames:v", "1", str(target)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode or not target.is_file():
        raise gr.Error("Could not preview that frame. Try another time.")
    return str(target), f"Frame at {at:.1f}s · source {width} × {height} · {total:.1f}s"


def run_generation(video, character, target, start, duration, megapixels, turbo, preserve_audio, extra):
    path = _path(video)
    image = _path(character)
    try:
        if not path or not image:
            raise ValueError("Upload a source video and character image.")
        plan = JobPlan(path, image, target or "", float(start or 0), float(duration or 0),
                       float(megapixels), extra or "", bool(turbo), bool(preserve_audio))
        for message, result in generate(plan):
            yield message, result, gr.update(interactive=False, value="Generating…")
        yield message, result, gr.update(interactive=True, value="Generate · Ctrl+Enter")
    except Exception as error:
        yield f"Error: {error}", None, gr.update(interactive=True, value="Generate · Ctrl+Enter")


def guided_preview(video, start):
    path, note = preview_frame(video, start)
    with Image.open(path) as source:
        picture = source.convert("RGB")
    picture.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    editor = {"background": picture, "layers": [], "composite": picture.copy()}
    return (editor, note + " · Paint the entire target head, including hair.",
            path, None, None, None, gr.update(interactive=False),
            "Frame ready. Paint the head, then press Swap head.")


def guided_swap(editor, frame_path, head_image, source_video, start):
    try:
        source = _path(source_video)
        head = _path(head_image)
        if not source or not source.is_file() or not head or not head.is_file():
            raise ValueError("Upload a video and a head reference first.")
        result = swap_head(editor, frame_path, head)
        state = {"result": str(result), "video": str(source.resolve()),
                 "head": str(head.resolve()), "start": float(start or 0)}
        return (str(result), state, "Head swap complete. Check the edited frame, then generate the video.",
                gr.update(interactive=True, value="Generate Stunt Double video · Ctrl+Enter"),
                gr.update(interactive=True, value="Swap head again"))
    except Exception as error:
        return (None, None, f"Head swap failed: {error}", gr.update(interactive=False),
                gr.update(interactive=True, value="Swap head"))


def guided_generate(video, head_image, state, target, start, duration, megapixels, turbo, preserve_audio, extra):
    try:
        source = _path(video)
        head = _path(head_image)
        if not state or not source or not head or not Path(state["result"]).is_file():
            raise ValueError("Preview a frame and finish its head swap first.")
        if (str(source.resolve()) != state["video"] or str(head.resolve()) != state["head"]
                or abs(float(start or 0) - state["start"]) > .01):
            raise ValueError("The video, head photo, or start time changed. Preview and swap the head again.")
        direction = "Keep the source video's body, outfit, and scene as close as possible. " + (extra or "")
        plan = JobPlan(source, Path(state["result"]), target or "the painted person",
                       float(start or 0), float(duration or 0), float(megapixels),
                       direction, bool(turbo), bool(preserve_audio))
        for message, result in generate(plan):
            yield message, result, gr.update(interactive=False, value="Generating…")
        yield message, result, gr.update(interactive=True, value="Generate Stunt Double video · Ctrl+Enter")
    except Exception as error:
        yield f"Error: {error}", None, gr.update(interactive=True, value="Generate Stunt Double video · Ctrl+Enter")


def stop_generation():
    return "Stopping this generation…" if cancel_active() else "No generation is running."


def status_models():
    missing = missing_models()
    if missing:
        return "Models missing: " + ", ".join(missing) + ". Run INSTALL.bat."
    return "All required model files are present."


def access_status():
    label = next((label for label, mode in MODES.items() if mode == ACTIVE_ACCESS), "This PC only")
    return f"Running: {label}. Local: {ACTIVE_LOCAL or 'starting'}. Phone: {ACTIVE_LINK or 'off'}"


def lan_phone_url(local_url: str) -> str:
    port = urlparse(local_url).port
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("1.1.1.1", 80))
            return f"http://{probe.getsockname()[0]}:{port}/"
    except OSError:
        candidates = socket.gethostbyname_ex(socket.gethostname())[2]
        for candidate in candidates:
            address = ipaddress.ip_address(candidate)
            if address.is_private and not address.is_loopback and not address.is_link_local:
                return f"http://{candidate}:{port}/"
        return f"Find this PC's Wi-Fi IP address and open port {port} on your phone."


def stop_server():
    if busy():
        return "A generation is running. Stop it first."
    def exit_later():
        time.sleep(1.5)
        os._exit(0)
    threading.Thread(target=exit_later, daemon=True).start()
    return "Server stopping. Restart RUN.bat on this PC to use the app again."


def check_updates():
    try:
        mirror, modified = check_source()
        if modified:
            return "Update available. Press Update to install and restart.", gr.update(interactive=True)
        return "App source is current.", gr.update(interactive=False)
    except Exception as error:
        return f"Could not check updates: {error}", gr.update(interactive=False)


def install_update():
    if busy():
        yield "Stop the current generation before updating."
        return
    try:
        mirror, modified = apply_source()
    except Exception as error:
        yield f"Update failed: {error}"
        return
    if not headliner_ready():
        installer = APP.parent / "INSTALL.bat"
        if not installer.is_file():
            yield "Source updated, but INSTALL.bat is missing. Run the installer package again."
            return
        yield "Installing and verifying Head Swap models for this app…"
        env = {**os.environ, "GGF_UNATTENDED": "1"}
        with subprocess.Popen(["cmd.exe", "/d", "/c", str(installer), "headswap"],
                              cwd=str(APP.parent), env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, bufsize=1,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as proc:
            assert proc.stdout is not None
            last = "Installing Head Swap models…"
            for line in proc.stdout:
                clean = line.strip()
                if clean.startswith(("[", "Downloading", "Head Swap", "Setup stopped")):
                    last = clean[-200:]
                    yield last
            if proc.wait() or not headliner_ready():
                yield f"Head Swap setup is incomplete. {last} Run INSTALL.bat to resume; existing files were kept."
                return
    if not modified:
        yield "App source and Head Swap models are current."
        return
    def restart_later():
        time.sleep(1.5)
        os._exit(75)
    threading.Thread(target=restart_later, daemon=True).start()
    yield "Updated source and verified required models. Restarting the app now…"


def build_ui():
    with gr.Blocks(title="Floyd Stunt Double") as demo:
        with gr.Column(elem_id="ggf-shell"):
            gr.HTML('''<div id="ggf-hero"><div class="kicker">GET GOING FAST · LOCAL AI</div>
                <h1>Floyd Stunt Double</h1><p>Put a new character into your video while keeping the performance.</p>
                <div class="links"><a href="https://getgoingfast.pro" target="_blank">GetGoingFast.pro ↗</a>
                <a href="https://youtube.com/@TheAIHobbyGuy" target="_blank">The AI Hobby Guy ↗</a></div></div>''')
            status = gr.Markdown("Ready. Upload a video and a character image.", elem_id="ggf-status")
            with gr.Tabs():
                with gr.Tab("Create"):
                    gr.Markdown("Choose the performance video, then the character who will replace one person in it.")
                    with gr.Row():
                        source = gr.Video(label="Your video", height=300)
                        character = gr.Image(label="Replacement character", type="filepath", height=300)
                    target = gr.Textbox(label="Who in the video should change?", placeholder="The woman on the left", lines=1)
                    with gr.Row():
                        start = gr.Number(label="Start at (seconds)", value=0, precision=1, minimum=0)
                        duration = gr.Number(label="Length (seconds; 0 = to the end)", value=8, precision=1, minimum=0)
                    with gr.Row():
                        preview = gr.Button("Preview start frame", variant="secondary")
                        frame_note = gr.Markdown("")
                    frame = gr.Image(label="Source frame · use this to describe the correct person", interactive=False, height=280)
                    with gr.Row():
                        submit = gr.Button("Generate · Ctrl+Enter", variant="primary", elem_id="ggf-generate")
                        stop = gr.Button("Stop current generation", elem_id="ggf-stop")
                    result = gr.Video(label="Your new video · use the player’s fullscreen and download controls", height=520, elem_id="ggf-result")
                    with gr.Accordion("More control", open=False):
                        resolution = gr.Slider(.3, .9, value=.4, step=.05, label="Output detail (megapixels)")
                        turbo = gr.Checkbox(value=True, label="Faster 8-step generation")
                        keep_audio = gr.Checkbox(value=True, label="Keep the source video’s audio")
                        extra = gr.Textbox(label="Extra direction", placeholder="Keep the same lighting and camera angle", lines=2)
                with gr.Tab("Head Swap + Video"):
                    gr.Markdown("**Video → frame → head swap → video.** Keep the original person's outfit and performance while transferring a new head. Paint the whole head, including hair, so the rest of the frame can stay untouched.")
                    with gr.Row():
                        guided_source = gr.Video(label="1 · Performance video", height=300)
                        guided_head = gr.Image(label="2 · New head reference", type="filepath", height=300)
                    with gr.Row():
                        guided_start = gr.Number(label="Start at (seconds)", value=0, precision=1, minimum=0)
                        guided_duration = gr.Number(label="Length (seconds; 0 = to the end)", value=8, precision=1, minimum=0)
                    guided_preview_button = gr.Button("3 · Preview frame", variant="secondary")
                    guided_frame_note = gr.Markdown("")
                    guided_frame_path = gr.State(None)
                    with gr.Row():
                        guided_editor = gr.ImageEditor(
                            type="pil", format="png", image_mode="RGBA", transforms=(), layers=False,
                            sources=[], brush=gr.Brush(colors=["#f5b942"], color_mode="fixed"),
                            label="Paint the head to replace · include hair and any hat", height=420,
                            elem_id="ggf-guided-frame")
                        guided_image = gr.Image(label="Head-swapped frame · only painted pixels are replaced",
                                                type="filepath", interactive=False, height=420)
                    guided_swap_button = gr.Button("4 · Swap head", variant="primary", elem_id="ggf-guided-swap")
                    guided_state = gr.State(None)
                    guided_status = gr.Markdown("Preview a frame to begin.", elem_id="ggf-guided-status")
                    guided_target = gr.Textbox(label="Which person in the video?", placeholder="The person in the blue shirt", lines=1)
                    with gr.Row():
                        guided_submit = gr.Button("Generate Stunt Double video · Ctrl+Enter", variant="primary",
                                                  interactive=False, elem_id="ggf-guided-generate")
                        guided_stop = gr.Button("Stop current generation", elem_id="ggf-guided-stop")
                    guided_result = gr.Video(label="Finished video · fullscreen and download are in the player",
                                             height=520, elem_id="ggf-guided-result")
                    gr.Markdown("The edited frame guides the video model. Complex movement or cuts can still change clothing or facial details; try a short section first.")
                    with gr.Accordion("More control", open=False):
                        guided_resolution = gr.Slider(.3, .9, value=.4, step=.05, label="Output detail (megapixels)")
                        guided_turbo = gr.Checkbox(value=True, label="Faster 8-step video generation")
                        guided_audio = gr.Checkbox(value=True, label="Keep the source video’s audio")
                        guided_extra = gr.Textbox(label="Extra video direction", lines=2)
                with gr.Tab("Settings"):
                    gr.Markdown("The PC does the generating. Your phone can open the same app while this PC stays on.")
                    saved = load_access()
                    current_label = next((key for key, value in MODES.items() if value == saved["mode"]), "This PC only")
                    mode = gr.Dropdown(list(MODES), value=current_label, label="Access mode", elem_id="ggf-network-mode")
                    username = gr.Textbox(label="Phone username (optional)", value=saved["username"])
                    password = gr.Textbox(label="Phone password (blank = no login)", type="password")
                    save = gr.Button("Save access setting")
                    access_note = gr.Markdown(access_status())
                    model_note = gr.Markdown(status_models())
                    head_model_note = gr.Markdown("Head Swap models ready." if headliner_ready()
                                                  else "Head Swap models are missing. Run INSTALL.bat to download and verify them.")
                    with gr.Row():
                        refresh = gr.Button("Check model files")
                        release = gr.Button("Release models / free GPU memory")
                    gr.Markdown("Models are unloaded after each generation. The next job loads them again.")
                    with gr.Row():
                        check_update = gr.Button("Check for updates")
                        update = gr.Button("Update and restart", interactive=False)
                    update_note = gr.Markdown("")
                    shutdown = gr.Button("Stop server")
                    confirm = gr.Button("Confirm: stop app on this PC", visible=False)
                    shutdown_note = gr.Markdown("")
            gr.HTML('<div id="ggf-footer">Powered by MiniMax H3, Qwen Image 2.1, BFS Head Swap, and Viggle Turbo · Floyd family / GGF</div>')
        preview.click(preview_frame, inputs=[source, start], outputs=[frame, frame_note], queue=False)
        submit.click(lambda: (None, "Queued…", gr.update(interactive=False, value="Generating…")),
                     outputs=[result, status, submit], queue=False).then(
            run_generation, inputs=[source, character, target, start, duration, resolution, turbo, keep_audio, extra],
            outputs=[status, result, submit])
        stop.click(stop_generation, outputs=[status], queue=False)
        guided_preview_button.click(
            guided_preview, inputs=[guided_source, guided_start],
            outputs=[guided_editor, guided_frame_note, guided_frame_path, guided_image,
                     guided_state, guided_result, guided_submit, guided_status], queue=False)
        guided_swap_button.click(
            lambda: ("Swapping head…", gr.update(interactive=False, value="Swapping…"),
                     gr.update(interactive=False), None, None),
            outputs=[guided_status, guided_swap_button, guided_submit, guided_image, guided_state],
            queue=False).then(
            guided_swap, inputs=[guided_editor, guided_frame_path, guided_head, guided_source, guided_start],
            outputs=[guided_image, guided_state, guided_status, guided_submit, guided_swap_button])
        guided_submit.click(
            lambda: (None, "Queued…", gr.update(interactive=False, value="Generating…")),
            outputs=[guided_result, guided_status, guided_submit], queue=False).then(
            guided_generate,
            inputs=[guided_source, guided_head, guided_state, guided_target, guided_start, guided_duration,
                    guided_resolution, guided_turbo, guided_audio, guided_extra],
            outputs=[guided_status, guided_result, guided_submit])
        guided_stop.click(stop_generation, outputs=[guided_status], queue=False)
        def reset_guided():
            return (None, None, None, None, gr.update(interactive=False),
                    "Input changed. Preview the frame and swap the head again.")
        for control in (guided_source, guided_head, guided_start):
            control.change(reset_guided, outputs=[guided_frame_path, guided_state, guided_image,
                                                  guided_result, guided_submit, guided_status],
                           queue=False)
        save.click(save_access, inputs=[mode, username, password], outputs=[access_note], queue=False)
        refresh.click(lambda: (status_models(), "Head Swap models ready." if headliner_ready()
                               else "Head Swap models are missing. Run INSTALL.bat."),
                      outputs=[model_note, head_model_note], queue=False)
        release.click(lambda: "Models are released after every job; no GPU models are resident." if not busy() else "Stop the current generation first.",
                      outputs=[model_note], queue=False)
        check_update.click(check_updates, outputs=[update_note, update], queue=False)
        update.click(install_update, outputs=[update_note], queue=False)
        shutdown.click(lambda: gr.update(visible=True), outputs=[confirm], queue=False)
        confirm.click(stop_server, outputs=[shutdown_note], queue=False)
        demo.load(access_status, outputs=[access_note], queue=False, js=CTRL_ENTER)
    return demo


def launch_one(demo, port, **kwargs):
    for candidate in range(port, port + 30):
        try:
            return demo.launch(server_port=candidate, prevent_thread_lock=True,
                               show_error=True, theme=gr.themes.Base(primary_hue="amber", neutral_hue="slate"),
                               css=CSS, allowed_paths=[str(APP / "outputs"), str(APP / "previews")], **kwargs)
        except OSError as error:
            if "Cannot find empty port" not in str(error) and getattr(error, "winerror", None) != 10048:
                raise
    raise RuntimeError("No free app port found.")


def main():
    global ACTIVE_ACCESS, ACTIVE_LINK, ACTIVE_LOCAL
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=7890)
    args = parser.parse_args()
    settings = load_access()
    ACTIVE_ACCESS = settings["mode"]
    local = build_ui().queue(default_concurrency_limit=1)
    _, ACTIVE_LOCAL, _ = launch_one(local, args.port, server_name="127.0.0.1",
                                    share=False, auth=None, inbrowser=not args.no_browser)
    print(f"Local app (no login): {ACTIVE_LOCAL}", flush=True)
    if ACTIVE_ACCESS != "local":
        try:
            remote = build_ui().queue(default_concurrency_limit=1)
            auth = (lambda u, p: verify_access(u, p, settings)) if settings["hash"] else None
            _, remote_local, public = launch_one(remote, args.port + 1000,
                server_name="0.0.0.0" if ACTIVE_ACCESS == "lan" else "127.0.0.1",
                share=ACTIVE_ACCESS == "public", auth=auth, inbrowser=False)
            ACTIVE_LINK = public or (lan_phone_url(remote_local) if ACTIVE_ACCESS == "lan" else remote_local)
            print(f"Phone access: {ACTIVE_LINK}", flush=True)
        except Exception as error:
            print(f"Phone access failed: {error}. Local app remains available at {ACTIVE_LOCAL}.", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cancel_active()


if __name__ == "__main__":
    main()
