"""GGF Floyd Stunt Double: simple video character replacement UI."""
from __future__ import annotations

import argparse
import ipaddress
import os
import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import gradio as gr

from access import MODES, load as load_access, save as save_access, verify as verify_access
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
    const btn = document.querySelector('#ggf-generate button, button#ggf-generate');
    if (!btn || btn.disabled || btn.offsetParent === null) return;
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
        return "Stop the current generation before updating."
    try:
        mirror, modified = apply_source()
    except Exception as error:
        return f"Update failed: {error}"
    if not modified:
        return "Already current."
    def restart_later():
        time.sleep(1.5)
        os._exit(75)
    threading.Thread(target=restart_later, daemon=True).start()
    return "Updated source. Restarting the app now…"


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
            gr.HTML('<div id="ggf-footer">Powered by MiniMax H3 and the H3 Character Swap LoRA · Floyd family / GGF</div>')
        preview.click(preview_frame, inputs=[source, start], outputs=[frame, frame_note], queue=False)
        submit.click(lambda: (None, "Queued…", gr.update(interactive=False, value="Generating…")),
                     outputs=[result, status, submit], queue=False).then(
            run_generation, inputs=[source, character, target, start, duration, resolution, turbo, keep_audio, extra],
            outputs=[status, result, submit])
        stop.click(stop_generation, outputs=[status], queue=False)
        save.click(save_access, inputs=[mode, username, password], outputs=[access_note], queue=False)
        refresh.click(status_models, outputs=[model_note], queue=False)
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
