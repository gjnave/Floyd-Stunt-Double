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
from headliner_addon import ready as headliner_ready, swap as swap_head, reswap as reswap_head, automatic as automatic_head
from model_packs import (start_install, stop_install, remove_pack, has_files, status as pack_status,
                         video_ready, begin_generation, end_generation, work_busy, VIDEO_BYTES, HEAD_BYTES)
from pipeline import APP, OUTPUTS, JobPlan, cancel_active, generate, video_info, ffmpeg_path
from update_source import check as check_source, apply as apply_source

CSS = (APP / "ui.css").read_text(encoding="utf-8")
LIZ_ASSETS = APP / "assets"
LIZ_POSTER = LIZ_ASSETS / "liz-guide.png"
LIZ_WELCOME_CLIP = LIZ_ASSETS / "liz-stunt-welcome.mp4"
LIZ_CHOICES_CLIP = LIZ_ASSETS / "liz-stunt-choices.mp4"
VIDEO_GB = VIDEO_BYTES / 1e9
HEAD_GB = HEAD_BYTES / 1e9
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
  let sound = null;
  document.addEventListener('click', event => {
    if (!event.target.closest?.('#ggf-generate, #ggf-guided-generate, #ggf-guided-auto, #ggf-guided-swap, #ggf-guided-retry')) return;
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    sound ||= new Audio();
    sound.resume().catch(() => {});
  }, true);
  const chime = () => {
    if (!sound) return;
    sound.resume().then(() => {
      const now = sound.currentTime;
      for (const [frequency, delay] of [[660, 0], [880, 0.09]]) {
        const tone = sound.createOscillator();
        const volume = sound.createGain();
        tone.type = 'sine'; tone.frequency.value = frequency;
        volume.gain.setValueAtTime(0.0001, now + delay);
        volume.gain.exponentialRampToValueAtTime(0.025, now + delay + 0.012);
        volume.gain.exponentialRampToValueAtTime(0.0001, now + delay + 0.19);
        tone.connect(volume).connect(sound.destination);
        tone.start(now + delay); tone.stop(now + delay + 0.2);
      }
    }).catch(() => {});
  };
  for (const id of ['ggf-status', 'ggf-guided-status']) {
    const region = document.getElementById(id);
    if (!region) continue;
    let last = '';
    new MutationObserver(() => {
      const message = region.textContent || '';
      const finished = message.includes('Complete · saved to') || message.toLowerCase().includes('head swap complete');
      if (finished && message !== last) chime();
      last = message;
    }).observe(region, {subtree: true, childList: true, characterData: true});
  }
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
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(at),
           "-i", str(path), "-frames:v", "1", str(target)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode or not target.is_file():
        raise gr.Error("Could not preview that frame. Try another time.")
    return str(target), f"Frame at {at:.1f}s · source {width} × {height} · {total:.1f}s"


def run_generation(video, character, target, start, duration, megapixels, turbo, preserve_audio, extra):
    path = _path(video)
    image = _path(character)
    if not begin_generation():
        yield "Another generation or model download is running. Wait for it to finish.", None, gr.update(interactive=True, value="Generate · Ctrl+Enter")
        return
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
    finally:
        end_generation()


def guided_preview(video, start):
    path, note = preview_frame(video, start)
    with Image.open(path) as source:
        picture = source.convert("RGB")
    picture.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    editor = {"background": picture, "layers": [], "composite": picture.copy()}
    return (editor, path, note + " · One visible person? Press Swap head automatically. Painting is optional.",
            path, None, None, None, gr.update(interactive=False),
            "Frame ready. Press automatic Head Swap for one visible person, or paint a specific head below.", gr.update(interactive=False))


def guided_auto_swap(frame_path, head_image, source_video, start):
    if not begin_generation():
        return (gr.update(), gr.update(), "Another job or model download is running. Wait for it to finish.",
                gr.update(interactive=False), gr.update(interactive=True), gr.update())
    try:
        source = _path(source_video)
        head = _path(head_image)
        if not source or not source.is_file() or not head or not head.is_file():
            raise ValueError("Upload a video and head reference, then preview a frame.")
        result = automatic_head(frame_path, head)
        state = {"result": str(result), "video": str(source.resolve()),
                 "head": str(head.resolve()), "start": float(start or 0),
                 "mask": str(result.with_suffix(".mask.png"))}
        return (str(result), state,
                "Automatic head swap complete. Check the preview; use painting if it changed the wrong person or other details.",
                gr.update(interactive=True, value="Generate Stunt Double video · Ctrl+Enter"),
                gr.update(interactive=True), gr.update(interactive=True))
    except Exception as error:
        return (gr.update(), gr.update(), f"Automatic head swap failed: {error}",
                gr.update(interactive=False), gr.update(interactive=True), gr.update())
    finally:
        end_generation()


def guided_swap(editor, frame_path, head_image, source_video, start):
    if not begin_generation():
        return (gr.update(), gr.update(), "Another job or model download is running. Wait for it to finish.",
                gr.update(interactive=False), gr.update(interactive=True), gr.update())
    try:
        source = _path(source_video)
        head = _path(head_image)
        if not source or not source.is_file() or not head or not head.is_file():
            raise ValueError("Upload a video and a head reference first.")
        result = swap_head(editor, frame_path, head)
        state = {"result": str(result), "video": str(source.resolve()),
                 "head": str(head.resolve()), "start": float(start or 0),
                 "mask": str(result.with_suffix(".mask.png"))}
        return (str(result), state, "Head swap complete. Check the edited frame, then generate the video.",
                gr.update(interactive=True, value="Generate Stunt Double video · Ctrl+Enter"),
                gr.update(interactive=True, value="Swap using painted area"),
                gr.update(interactive=True))
    except Exception as error:
        return (gr.update(), gr.update(), f"Head swap failed: {error}", gr.update(interactive=False),
                gr.update(interactive=True, value="Swap using painted area"), gr.update())
    finally:
        end_generation()


def guided_reswap(frame_path, state, head_image, source_video, start):
    if not begin_generation():
        return (gr.update(), gr.update(), "Another job or model download is running. Wait for it to finish.",
                gr.update(interactive=False), gr.update(interactive=True))
    try:
        source = _path(source_video)
        head = _path(head_image)
        if not state or not source or not source.is_file() or not head or not head.is_file():
            raise ValueError("Preview, paint, and swap a head first.")
        if str(source.resolve()) != state["video"] or abs(float(start or 0) - state["start"]) > .01:
            raise ValueError("The video or start time changed. Preview the frame again.")
        result = reswap_head(frame_path, state.get("mask"), head)
        updated = {**state, "result": str(result), "head": str(head.resolve()),
                   "mask": str(result.with_suffix(".mask.png"))}
        return (str(result), updated, "Head swap complete. Check the edited frame, then generate the video.",
                gr.update(interactive=True, value="Generate Stunt Double video · Ctrl+Enter"),
                gr.update(interactive=True))
    except Exception as error:
        return (gr.update(), gr.update(), f"Head swap failed: {error}", gr.update(interactive=False),
                gr.update(interactive=True))
    finally:
        end_generation()


def latest_saved_video():
    files = [file for file in OUTPUTS.glob("Floyd-Stunt-Double-*.mp4") if file.is_file()]
    if not files:
        return None, "No saved video found yet."
    latest = max(files, key=lambda file: file.stat().st_mtime_ns)
    return str(latest), f"Loaded saved video: {latest.name}"


def guided_generate(video, head_image, state, target, start, duration, megapixels, turbo, preserve_audio, extra):
    if not begin_generation():
        yield "Another generation or model download is running. Wait for it to finish.", None, gr.update(interactive=True, value="Generate Stunt Double video · Ctrl+Enter")
        return
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
    finally:
        end_generation()


def stop_generation():
    return "Stopping this generation…" if cancel_active() else "No generation is running."


def status_models():
    return "Video Swap models are ready." if video_ready() else "Video Swap models are not installed yet. Open Settings to add them."


def liz_guide_media(clip: Path) -> None:
    """Use a finished Liz clip when present; keep the guide usable without it."""
    if clip.is_file():
        gr.Video(value=str(clip), interactive=False, show_label=False, height=220)
    else:
        gr.Image(value=str(LIZ_POSTER), interactive=False, show_label=False, height=220)


def model_panel_state(previous=None):
    state = pack_status()
    video, head = bool(state["video_ready"]), bool(state["head_ready"])
    running = bool(state["running"])
    actions_idle = not running and not work_busy()
    earlier = previous if isinstance(previous, (tuple, list)) and len(previous) == 2 else (video, head)
    welcome = ("**First, download Video Swap models to this PC in Settings.** "
               "Head Swap is an optional second download for closer facial likeness.")
    guided_missing = ("**Video Swap is not installed.** Install it in Settings first."
                      if not video else "**Head Swap is optional and not installed.** Add it in Settings to use this tab.")
    video_note = (("**Video Swap · ready** — use the Create tab. "
                   if video else f"**Video Swap · not installed** — about {VIDEO_GB:.1f} GB of model downloads. ")
                  + "Changes a person's overall look from a character image, including face, body, and outfit, "
                    "while following the source video's performance.")
    head_note = (("**Head Swap · ready** — Head Swap + Video is available. "
                  if head else f"**Head Swap · not installed** — about {HEAD_GB:.1f} GB more. Install Video Swap first. ")
                 + "Adds Headliner's frame-based head replacement for closer facial likeness. The video step "
                   "aims to retain the original body, clothes, and scene; fast motion or cuts can still change details.")
    job_note = str(state["status"] or "Choose a model pack below. Downloads are verified and can be resumed.")
    create_button = gr.update(interactive=video) if video != earlier[0] else gr.update()
    swap_button = gr.update(interactive=head) if head != earlier[1] else gr.update()
    guided_button = gr.update(interactive=False) if (video, head) != tuple(earlier) and not (video and head) else gr.update()
    return (
        gr.update(value=welcome, visible=not video),
        gr.update(visible=not video), gr.update(visible=not video),
        gr.update(value=guided_missing, visible=not (video and head)),
        gr.update(visible=not (video and head)),
        video_note, head_note, job_note,
        gr.update(interactive=not video and actions_idle),
        gr.update(interactive=video and not head and actions_idle),
        gr.update(interactive=has_files("video") and actions_idle),
        gr.update(interactive=has_files("head") and actions_idle),
        gr.update(interactive=running),
        create_button, swap_button, swap_button, guided_button, (video, head),
        gr.update(visible=video), gr.update(visible=head),
    )


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
    if work_busy() or pack_status()["running"]:
        return "A generation or model download is running. Let it finish or stop it first."
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
    if work_busy() or pack_status()["running"]:
        yield "Finish the current generation or model download before updating."
        return
    try:
        mirror, modified = apply_source()
    except Exception as error:
        yield f"Update failed: {error}"
        return
    if not modified:
        yield "App source is current. Optional model packs were not changed."
        return
    def restart_later():
        time.sleep(1.5)
        os._exit(75)
    threading.Thread(target=restart_later, daemon=True).start()
    yield "Updated app source. Optional model packs were kept; restarting now…"


def build_ui():
    initial_video = video_ready()
    initial_head = headliner_ready()
    with gr.Blocks(title="Floyd Stunt Double") as demo:
        with gr.Column(elem_id="ggf-shell"):
            gr.HTML('''<div id="ggf-hero"><div class="kicker">GET GOING FAST · LOCAL AI</div>
                <h1>Floyd Stunt Double</h1><p>Put a new character into your video while keeping the performance.</p>
                <div class="links"><a href="https://getgoingfast.pro" target="_blank">GetGoingFast.pro ↗</a>
                <a href="https://youtube.com/@TheAIHobbyGuy" target="_blank">The AI Hobby Guy ↗</a></div></div>''')
            welcome = gr.Markdown(
                "**First, download Video Swap models to this PC in Settings.** Head Swap is an optional second download for closer facial likeness.",
                visible=not initial_video, elem_id="ggf-model-welcome")
            status = gr.Markdown("Ready. Upload a video and a character image." if initial_video
                                 else "Choose Video Swap models in Settings to begin.", elem_id="ggf-status")
            model_previous = gr.State((initial_video, initial_head))
            with gr.Tabs(selected="settings" if not initial_video else "create") as tabs:
                with gr.Tab("Create", id="create"):
                    gr.Markdown("Choose the performance video, then the character who will replace one person in it.")
                    create_notice = gr.Markdown("**Video Swap isn't installed yet.** Choose it in Settings, then return here.", visible=not initial_video)
                    create_jump = gr.Button("Open Settings to install Video Swap", visible=not initial_video)
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
                        submit = gr.Button("Generate · Ctrl+Enter", variant="primary", elem_id="ggf-generate",
                                           interactive=initial_video)
                        stop = gr.Button("Stop current generation", elem_id="ggf-stop")
                    result = gr.Video(label="Your new video · use the player’s fullscreen and download controls", height=520, elem_id="ggf-result")
                    recover = gr.Button("Show latest saved video on this PC", variant="secondary")
                    gr.Markdown("If the phone page disconnects after a long run, press this to reopen the finished file without generating again.")
                    with gr.Accordion("More control", open=False):
                        resolution = gr.Slider(.3, .9, value=.4, step=.05, label="Output detail (megapixels)")
                        turbo = gr.Checkbox(value=True, label="Faster 8-step generation")
                        keep_audio = gr.Checkbox(value=True, label="Keep the source video’s audio")
                        extra = gr.Textbox(label="Extra direction", placeholder="Keep the same lighting and camera angle", lines=2)
                with gr.Tab("Head Swap + Video", id="guided"):
                    gr.Markdown("**Video → frame → head swap → video.** Preview the frame, swap the only visible head automatically, then generate. For several people or a precise edit, painting remains optional.")
                    guided_install_notice = gr.Markdown(
                        "**Video Swap isn't installed yet.** Open Settings to add it."
                        if not initial_video else "**Head Swap isn't installed yet.** Open Settings to add it.",
                        visible=not (initial_video and initial_head))
                    guided_install_jump = gr.Button("Open Settings for model downloads", visible=not (initial_video and initial_head))
                    with gr.Row():
                        guided_source = gr.Video(label="1 · Performance video", height=300)
                        guided_head = gr.Image(label="2 · New head reference", type="filepath", height=300)
                    with gr.Row():
                        guided_start = gr.Number(label="Start at (seconds)", value=0, precision=1, minimum=0)
                        guided_duration = gr.Number(label="Length (seconds; 0 = to the end)", value=8, precision=1, minimum=0)
                    guided_preview_button = gr.Button("3 · Preview frame", variant="secondary")
                    guided_frame_note = gr.Markdown("")
                    guided_frame_path = gr.State(None)
                    guided_preview_image = gr.Image(label="Selected video frame", interactive=False, height=350)
                    guided_auto_button = gr.Button("4 · Swap the visible head automatically", variant="primary",
                                                   interactive=initial_head, elem_id="ggf-guided-auto")
                    gr.Markdown("If the frame has more than one person, open the optional painted selection below.")
                    with gr.Accordion("Choose a specific head by painting (optional)", open=False):
                        guided_editor = gr.ImageEditor(
                            type="pil", format="png", image_mode="RGBA", transforms=(), layers=False,
                            sources=[], brush=gr.Brush(colors=["#f5b942"], color_mode="fixed"),
                            label="Paint the head to replace · include hair and any hat", height=420,
                            elem_id="ggf-guided-frame")
                        guided_swap_button = gr.Button("Swap using painted area", variant="secondary",
                                                       interactive=initial_head, elem_id="ggf-guided-swap")
                    with gr.Row():
                        guided_image = gr.Image(label="Head-swapped frame · check the whole result",
                                                type="filepath", interactive=False, height=420)
                        guided_retry_button = gr.Button("Try another head with same selection", interactive=False,
                                                        elem_id="ggf-guided-retry")
                    guided_state = gr.State(None)
                    guided_status = gr.Markdown("Preview a frame to begin.", elem_id="ggf-guided-status")
                    guided_target = gr.Textbox(label="Which person in the video?", placeholder="The person in the blue shirt", lines=1)
                    with gr.Row():
                        guided_submit = gr.Button("Generate Stunt Double video · Ctrl+Enter", variant="primary",
                                                  interactive=False, elem_id="ggf-guided-generate")
                        guided_stop = gr.Button("Stop current generation", elem_id="ggf-guided-stop")
                    guided_result = gr.Video(label="Finished video · fullscreen and download are in the player",
                                             height=520, elem_id="ggf-guided-result")
                    guided_recover = gr.Button("Show latest saved video on this PC", variant="secondary")
                    gr.Markdown("If the phone page disconnects after a long run, press this to reopen the finished file without generating again.")
                    gr.Markdown("The edited frame guides the video model. Complex movement or cuts can still change clothing or facial details; try a short section first.")
                    with gr.Accordion("More control", open=False):
                        guided_resolution = gr.Slider(.3, .9, value=.4, step=.05, label="Output detail (megapixels)")
                        guided_turbo = gr.Checkbox(value=True, label="Faster 8-step video generation")
                        guided_audio = gr.Checkbox(value=True, label="Keep the source video’s audio")
                        guided_extra = gr.Textbox(label="Extra video direction", lines=2)
                with gr.Tab("Settings", id="settings"):
                    with gr.Column(visible=not initial_video, elem_id="ggf-liz-guide") as liz_guide:
                        with gr.Column(visible=True) as liz_step_one:
                            gr.Markdown("### Meet Liz · Step 1 of 2")
                            with gr.Row():
                                with gr.Column(scale=1, min_width=180):
                                    liz_guide_media(LIZ_WELCOME_CLIP)
                                with gr.Column(scale=2, min_width=250):
                                    gr.Markdown("**Howdy, pardner! Welcome to Floyd Stunt Double. First, download the Video Swap models to your PC. Then you're ready to create.**")
                                    gr.Markdown("Using the page on a phone controls this PC; the models download to the PC, not the phone.")
                            with gr.Row():
                                liz_next = gr.Button("Next · choose your look", variant="primary")
                                liz_skip = gr.Button("Skip introduction")
                        with gr.Column(visible=False) as liz_step_two:
                            gr.Markdown("### Meet Liz · Step 2 of 2")
                            with gr.Row():
                                with gr.Column(scale=1, min_width=180):
                                    liz_guide_media(LIZ_CHOICES_CLIP)
                                with gr.Column(scale=2, min_width=250):
                                    gr.Markdown("**Video Swap changes the whole character. Add Head Swap for a closer face while trying to keep the original body and clothes.**")
                                    gr.Markdown("Head Swap models are optional and require Video Swap first. Motion and scene cuts can still change details.")
                            liz_done = gr.Button("Choose models below", variant="primary")
                    liz_replay = gr.Button("Meet Liz · replay the 2-step guide", variant="secondary", visible=initial_video)
                    gr.Markdown("### Model downloads")
                    gr.Markdown("**Start here:** Video Swap downloads to this PC and enables full-character replacement. Add Head Swap later for closer facial likeness while aiming to keep the original body, clothes, and scene. Your phone controls the app; it does not run the models.")
                    model_note = gr.Markdown("Video Swap models are ready." if initial_video else
                                             f"**Video Swap · not installed** — about {VIDEO_GB:.1f} GB. Changes a person's overall look while following the video performance.")
                    video_installed = gr.Markdown("✓ Video Swap INSTALLED — download complete and verified.",
                                                  visible=initial_video, elem_id="ggf-video-installed")
                    with gr.Row():
                        video_install = gr.Button(f"Download Video Swap models to this PC · about {VIDEO_GB:.1f} GB", variant="primary",
                                                  interactive=not initial_video)
                        video_remove = gr.Button("Remove Video Swap models", interactive=has_files("video"))
                    video_confirm = gr.Button("Confirm: remove this app's Video Swap model files", visible=False)
                    head_model_note = gr.Markdown("Head Swap models are ready." if initial_head else
                                                  f"**Head Swap · not installed** — about {HEAD_GB:.1f} GB more. For closer facial likeness; install Video Swap first.")
                    head_installed = gr.Markdown("✓ Head Swap INSTALLED — download complete and verified.",
                                                 visible=initial_head, elem_id="ggf-head-installed")
                    with gr.Row():
                        head_install = gr.Button(f"Add Head Swap models to this PC · about {HEAD_GB:.1f} GB", variant="secondary",
                                                 interactive=initial_video and not initial_head)
                        head_remove = gr.Button("Remove Head Swap models", interactive=has_files("head"))
                    head_confirm = gr.Button("Confirm: remove this app's Head Swap model files", visible=False)
                    stop_download = gr.Button("Stop model download · keep partial files", interactive=False)
                    install_note = gr.Markdown("Downloads are verified and can be resumed. Model removal keeps your outputs and other apps.")
                    install_timer = gr.Timer(2)
                    gr.Markdown("Model removal affects this app's exact model files and download copies only. It does not remove outputs, the app, or files belonging to Headliner.")
                    gr.Markdown("### App access and maintenance")
                    gr.Markdown("The PC does the generating. Your phone can open the same app while this PC stays on.")
                    saved = load_access()
                    current_label = next((key for key, value in MODES.items() if value == saved["mode"]), "This PC only")
                    mode = gr.Dropdown(list(MODES), value=current_label, label="Access mode", elem_id="ggf-network-mode")
                    username = gr.Textbox(label="Phone username (optional)", value=saved["username"])
                    password = gr.Textbox(label="Phone password (blank = no login)", type="password")
                    save = gr.Button("Save access setting")
                    access_note = gr.Markdown(access_status())
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
        liz_next.click(lambda: (gr.update(visible=False), gr.update(visible=True)),
                       outputs=[liz_step_one, liz_step_two], queue=False)
        liz_skip.click(lambda: (gr.update(visible=False), gr.update(visible=True)),
                       outputs=[liz_guide, liz_replay], queue=False)
        liz_done.click(lambda: (gr.update(visible=False), gr.update(visible=True)),
                       outputs=[liz_guide, liz_replay], queue=False)
        liz_replay.click(lambda: (gr.update(visible=True), gr.update(visible=True),
                                  gr.update(visible=False), gr.update(visible=False)),
                         outputs=[liz_guide, liz_step_one, liz_step_two, liz_replay], queue=False)
        create_jump.click(lambda: gr.update(selected="settings"), outputs=[tabs], queue=False)
        guided_install_jump.click(lambda: gr.update(selected="settings"), outputs=[tabs], queue=False)
        submit.click(lambda: (None, "Queued…", gr.update(interactive=False, value="Generating…")),
                     outputs=[result, status, submit], queue=False).then(
            run_generation, inputs=[source, character, target, start, duration, resolution, turbo, keep_audio, extra],
            outputs=[status, result, submit])
        stop.click(stop_generation, outputs=[status], queue=False)
        recover.click(latest_saved_video, outputs=[result, status], queue=False)
        guided_preview_button.click(
            guided_preview, inputs=[guided_source, guided_start],
            outputs=[guided_editor, guided_preview_image, guided_frame_note, guided_frame_path, guided_image,
                     guided_state, guided_result, guided_submit, guided_status, guided_retry_button], queue=False)
        auto_event = guided_auto_button.click(
            lambda: ("Swapping the visible head…", gr.update(interactive=False),
                     gr.update(interactive=False), None),
            outputs=[guided_status, guided_auto_button, guided_submit, guided_result],
            queue=False).then(
            guided_auto_swap, inputs=[guided_frame_path, guided_head, guided_source, guided_start],
            outputs=[guided_image, guided_state, guided_status, guided_submit, guided_auto_button,
                     guided_retry_button])
        auto_event.failure(
            lambda: ("The head image did not finish uploading. Upload it again and retry.", gr.update(interactive=True)),
            outputs=[guided_status, guided_auto_button], queue=False)
        swap_event = guided_swap_button.click(
            lambda: ("Swapping head…", gr.update(interactive=False, value="Swapping…"),
                     gr.update(interactive=False), None),
            outputs=[guided_status, guided_swap_button, guided_submit, guided_result],
            queue=False).then(
            guided_swap, inputs=[guided_editor, guided_frame_path, guided_head, guided_source, guided_start],
            outputs=[guided_image, guided_state, guided_status, guided_submit, guided_swap_button,
                     guided_retry_button])
        swap_event.failure(
            lambda: ("The painted image did not finish uploading. Preview and repaint the frame, or use the saved selection with Try another head.",
                     gr.update(interactive=True, value="Swap using painted area")),
            outputs=[guided_status, guided_swap_button], queue=False)
        retry_event = guided_retry_button.click(
            lambda: ("Trying another head…", gr.update(interactive=False), gr.update(interactive=False), None),
            outputs=[guided_status, guided_retry_button, guided_submit, guided_result], queue=False).then(
            guided_reswap, inputs=[guided_frame_path, guided_state, guided_head, guided_source, guided_start],
            outputs=[guided_image, guided_state, guided_status, guided_submit, guided_retry_button])
        retry_event.failure(lambda: gr.update(interactive=True), outputs=[guided_retry_button], queue=False)
        guided_submit.click(
            lambda: (None, "Queued…", gr.update(interactive=False, value="Generating…")),
            outputs=[guided_result, guided_status, guided_submit], queue=False).then(
            guided_generate,
            inputs=[guided_source, guided_head, guided_state, guided_target, guided_start, guided_duration,
                    guided_resolution, guided_turbo, guided_audio, guided_extra],
            outputs=[guided_status, guided_result, guided_submit])
        guided_stop.click(stop_generation, outputs=[guided_status], queue=False)
        guided_recover.click(latest_saved_video, outputs=[guided_result, guided_status], queue=False)
        def reset_guided():
            return (None, None, None, None, None, gr.update(interactive=False),
                    "Video or start time changed. Preview the frame again; painting is optional.", gr.update(interactive=False))
        for control in (guided_source, guided_start):
            control.change(reset_guided, outputs=[guided_frame_path, guided_state, guided_preview_image, guided_image,
                                                  guided_result, guided_submit, guided_status, guided_retry_button],
                           queue=False)
        def head_changed(state):
            note = ("Head photo changed. Use the same painted area with Try another head, or repaint and press Swap using current paint."
                    if state and state.get("mask") else "Head photo ready. Preview a frame, paint the head, and press Swap using current paint.")
            return None, None, gr.update(interactive=False), note
        guided_head.change(head_changed, inputs=[guided_state],
                           outputs=[guided_image, guided_result, guided_submit, guided_status], queue=False)
        save.click(save_access, inputs=[mode, username, password], outputs=[access_note], queue=False)
        video_install.click(lambda: start_install("video"), outputs=[install_note], queue=False)
        head_install.click(lambda: start_install("head"), outputs=[install_note], queue=False)
        stop_download.click(stop_install, outputs=[install_note], queue=False)
        video_remove.click(lambda: gr.update(visible=True), outputs=[video_confirm], queue=False)
        head_remove.click(lambda: gr.update(visible=True), outputs=[head_confirm], queue=False)
        video_confirm.click(lambda: (remove_pack("video"), gr.update(visible=False)),
                            outputs=[install_note, video_confirm], queue=False)
        head_confirm.click(lambda: (remove_pack("head"), gr.update(visible=False)),
                           outputs=[install_note, head_confirm], queue=False)
        panel_outputs = [welcome, create_notice, create_jump, guided_install_notice, guided_install_jump,
                         model_note, head_model_note, install_note, video_install, head_install,
                         video_remove, head_remove, stop_download, submit, guided_auto_button, guided_swap_button,
                         guided_submit, model_previous, video_installed, head_installed]
        install_timer.tick(model_panel_state, inputs=[model_previous], outputs=panel_outputs, queue=False)
        refresh.click(lambda: (status_models(), "Head Swap models ready." if headliner_ready()
                               else "Head Swap models are not installed. Add them above if you want this workflow."),
                      outputs=[model_note, head_model_note], queue=False)
        release.click(lambda: "Models are released after every job; no GPU models are resident." if not work_busy() else "Stop the current generation first.",
                      outputs=[model_note], queue=False)
        check_update.click(check_updates, outputs=[update_note, update], queue=False)
        update.click(install_update, outputs=[update_note], queue=False)
        shutdown.click(lambda: gr.update(visible=True), outputs=[confirm], queue=False)
        confirm.click(stop_server, outputs=[shutdown_note], queue=False)
        demo.load(access_status, outputs=[access_note], queue=False, js=CTRL_ENTER)
        demo.load(model_panel_state, inputs=[model_previous], outputs=panel_outputs, queue=False)
    return demo


def launch_one(demo, port, **kwargs):
    for candidate in range(port, port + 30):
        try:
            return demo.launch(server_port=candidate, prevent_thread_lock=True,
                               show_error=True, theme=gr.themes.Base(primary_hue="amber", neutral_hue="slate"),
                               css=CSS, allowed_paths=[str(APP / "outputs"), str(APP / "previews"), str(LIZ_ASSETS)], **kwargs)
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
