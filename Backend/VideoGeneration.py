import requests
import os
import shutil
import subprocess
import json
import sys
import tempfile
from PIL import Image
from dotenv import dotenv_values

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Backend.PollinationsModel import chat_completion, chat_completion_openai

_env = dotenv_values("jarvis.env")
MODEL = _env.get("ModelName", "openai-large")
VIDEO_IMAGE_MODEL = _env.get("VideoImageModel", "flux")

FRAME_COUNT = 16
CROSSFADE = 0.5
WIDTH, HEIGHT = 1024, 576
FPS = 24

STYLE_KEYWORDS = {
    "anime": "anime style, vibrant colors, cel shading, Studio Ghibli inspired",
    "cinematic": "cinematic lighting, film grain, anamorphic, dramatic shadows, ultra realistic",
    "pixel art": "pixel art, 8-bit, retro game, blocky, limited palette",
    "3d render": "3D render, octane render, photorealistic, ray tracing, detailed textures",
    "oil painting": "oil painting, thick brush strokes, canvas texture, classical style",
    "watercolor": "watercolor painting, soft edges, paper texture, gentle washes",
    "sketch": "pencil sketch, black and white, crosshatching, rough lines",
    "cyberpunk": "cyberpunk, neon lights, rain, dark atmosphere, futuristic city",
    "fantasy": "fantasy art, magical glow, ethereal, mythical creatures, enchanted",
    "vaporwave": "vaporwave, neon grid, retro 80s, pastel colors, synthwave",
}

DURATIONS_DEFAULT = 1.5
DURATIONS_FIRST = 3.0
DURATIONS_LAST = 3.0

CAMERA_ANGLES = [
    "Wide establishing shot", "Low angle shot", "Tracking shot following subject",
    "Over-the-shoulder shot", "Medium shot", "Close-up on subject",
    "Dutch angle / tilted shot", "Aerial bird's-eye view", "POV shot from subject's perspective",
    "Crane shot rising", "Dolly zoom / push in", "Side tracking shot",
    "Extreme close-up on detail", "Wide shot revealing environment", "Steadicam following shot",
    "Drone shot pulling back"
]


def detect_style(prompt):
    lower = prompt.lower()
    for kw in STYLE_KEYWORDS:
        if kw in lower:
            return STYLE_KEYWORDS[kw]
    return "cinematic lighting, ultra realistic, high detail"


def make_temporal_prompts(base_prompt, count=FRAME_COUNT):
    style_desc = detect_style(base_prompt)

    system_prompt = f"""
You are a professional Hollywood storyboard artist.

Your job is to create exactly {count} consecutive image prompts for an AI image generator.

Style: {style_desc}

Rules:
1. Keep the SAME subject, environment, lighting, clothing, colors, and art style across ALL frames.
2. Change ONLY the camera angle and action.
3. Every frame must continue naturally from the previous.
4. Avoid sudden jumps or time skips.
5. Describe only visible things — no emotions, no "beautiful"/"epic"/"awesome".
6. Vary camera angles widely: use close-ups, wide shots, tracking shots, low angles, overhead, POV, etc.
7. Start with an establishing shot, build action in the middle, end with a dramatic final frame.
8. Make each frame feel like a different shot in a movie scene.

Return ONLY valid JSON — an array of objects with "camera" and "action" keys.

Example:
[
    {{"camera":"Wide establishing shot", "action":"A red Ferrari parked at the starting line"}},
    {{"camera":"Low angle tracking shot", "action":"The Ferrari launches forward with tire smoke"}},
    {{"camera":"Close-up", "action":"The driver shifts gears intently"}},
    {{"camera":"Aerial drone shot", "action":"The Ferrari speeds along the curving track"}},
    {{"camera":"Dutch angle", "action":"The Ferrari drifts around a sharp corner"}},
    {{"camera":"Rear tracking shot", "action":"The Ferrari crosses the finish line, dust kicking up"}},
    {{"camera":"Wide final shot", "action":"The Ferrari slows down, track stretching into the distance"}}
]
"""

    try:
        result = chat_completion_openai(
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": base_prompt}],
            max_tokens=3072, model=MODEL)
        text = result["choices"][0]["message"]["content"]
        text = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON array, got {type(parsed).__name__}")
        storyboard = parsed

        base = f"""{base_prompt},
consistent subject,
same environment,
same lighting,
same color palette,
{style_desc}
"""

        prompts = []
        for frame in storyboard:
            prompt = f"""{base},
Camera: {frame['camera']},
Action: {frame['action']}"""
            prompts.append(prompt.replace("\n", " "))

        return prompts[:count]

    except Exception as e:
        print(f"Storyboard generation failed: {e}", flush=True)
        return [f"{base_prompt}, {CAMERA_ANGLES[i % len(CAMERA_ANGLES)]}" for i in range(count)]


def has_water_content(prompt):
    water_kw = ["ocean", "sea", "wave", "water", "river", "lake", "rain", "flood",
                "underwater", "beach", "shore", "coast", "surf", "tide", "current",
                "stream", "cascade", "waterfall", "swim"]
    lower = prompt.lower()
    return any(kw in lower for kw in water_kw)


def get_frame_durations(n):
    if n == 1:
        return [DURATIONS_LAST]
    durations = [DURATIONS_FIRST]
    for _ in range(1, n - 1):
        durations.append(DURATIONS_DEFAULT)
    durations.append(DURATIONS_LAST)
    return durations


def generate_video(prompt):
    print(f"Generating AI video: {prompt}", flush=True)
    os.makedirs("Data", exist_ok=True)
    os.makedirs("Data/frames", exist_ok=True)
    filename = f"Data/{prompt.replace(' ', '_')}.mp4"

    frame_prompts = make_temporal_prompts(prompt)
    n = len(frame_prompts)
    frame_files = [None] * n

    import time
    for i, fp in enumerate(frame_prompts):
        url = (f"https://image.pollinations.ai/prompt/"
               f"{requests.utils.quote(fp)}?model={VIDEO_IMAGE_MODEL}&width={WIDTH}&height={HEIGHT}&seed={i * 100}")
        success = False
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=120)
                if resp.status_code == 200:
                    fpath = f"Data/frames/frame_{i:02d}.jpg"
                    with open(fpath, 'wb') as f:
                        f.write(resp.content)
                    try:
                        img = Image.open(fpath)
                        w, h = img.size
                        if w < 512 or h < 288:
                            raise ValueError(f"image too small ({w}x{h})")
                        img.close()
                    except Exception:
                        os.remove(fpath)
                        print(f"  Frame {i+1} invalid image, retrying...", flush=True)
                        time.sleep(3)
                        continue
                    frame_files[i] = fpath
                    print(f"  Frame {i+1}/{n} downloaded", flush=True)
                    success = True
                    break
                print(f"  Frame {i+1} HTTP {resp.status_code}, retrying...", flush=True)
            except Exception as e:
                print(f"  Frame {i+1} attempt {attempt+1}: {e}", flush=True)
            time.sleep(3 * (attempt + 1))
        if not success:
            print(f"  Frame {i+1}/{n} failed", flush=True)
        time.sleep(2.0)

    frame_files = [f for f in frame_files if f and os.path.getsize(f) > 1000]
    n = len(frame_files)
    print(f"  {n}/{len(frame_prompts)} frames ready", flush=True)

    if n < 2:
        print("Not enough frames generated", flush=True)
        shutil.rmtree("Data/frames", ignore_errors=True)
        return

    durations = get_frame_durations(n)
    zoom_max = 1.12
    is_water = has_water_content(prompt)

    filter_parts = []
    for i in range(n):
        d = int(durations[i] * FPS)
        zoom_step = (zoom_max - 1) / d if d > 0 else 0
        x_expr = "x='iw/2-(iw/zoom/2)'"
        y_expr = "y='ih/2-(ih/zoom/2)'"
        if is_water:
            x_expr = "x='iw/2-(iw/zoom/2)+6*sin(2*PI*on/40)'"
            y_expr = "y='ih/2-(ih/zoom/2)+4*sin(2*PI*on/30)'"
        zm = (f"zoompan=z='if(lte(on,1),1,min(zoom+{zoom_step},{zoom_max}))'"
              f":d={d}:s={WIDTH}x{HEIGHT}:fps={FPS}"
              f":{x_expr}:{y_expr}")
        filter_parts.append(f"[{i}:v]{zm},setpts=PTS-STARTPTS[v{i}]")

    # Correct chained xfade:
    #   offset[i] = cumulative_before_i - CROSSFADE
    #   cumulative = sum(d[0..i-1]) - i * CROSSFADE
    label = "v0"
    cumulative = durations[0]
    for i in range(1, n):
        offset = cumulative - CROSSFADE
        new_label = f"c{i}"
        filter_parts.append(
            f"[{label}][v{i}]xfade=transition=fade:duration={CROSSFADE}:offset={offset}[{new_label}]"
        )
        label = new_label
        cumulative += durations[i] - CROSSFADE

    total_seconds = cumulative

    filter_parts.append(f"[{label}]format=yuv420p[v]")
    filter_complex = ";".join(filter_parts)
    inputs = sum((["-i", f] for f in frame_files), [])
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-pix_fmt", "yuv420p",
        filename
    ]

    print(f"  ffmpeg command:", flush=True)
    print(f"    {' '.join(cmd[:6])} ...", flush=True)
    print(f"    filter_complex: {filter_complex[:200]}...", flush=True)
    print(f"Assembling {n} frames into video (~{total_seconds:.1f}s)", flush=True)

    try:
        stderr_file = filename.replace(".mp4", "_ffmpeg_stderr.txt")
        with open(stderr_file, 'w') as err_f:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=err_f,
                                    timeout=int(total_seconds * 2 + 60))
        if result.returncode != 0:
            with open(stderr_file, 'r') as err_f:
                err = err_f.read()[-2000:]
            os.remove(stderr_file)
            raise RuntimeError(f"ffmpeg exited with code {result.returncode}:\n{err}")
        if os.path.exists(stderr_file):
            os.remove(stderr_file)

        size = os.path.getsize(filename) if os.path.exists(filename) else 0
        if size > 5000:
            print(f"Video saved: {filename} ({size//1024}KB, ~{total_seconds:.1f}s)", flush=True)
            with open("Frontend/Files/VideoDisplay.data", "w") as f:
                f.write(filename)
        else:
            print("Video generation failed (empty output)", flush=True)
    except Exception as e:
        print(f"ffmpeg error: {e}", flush=True)
    finally:
        shutil.rmtree("Data/frames", ignore_errors=True)


try:
    with open("Frontend/Files/VideoGeneration.data", "r") as file:
        Data = file.read()
    *Prompt_parts, Status_part = Data.rsplit(",", 1)
    if Status_part.strip() == "True":
        Prompt = ",".join(Prompt_parts).strip()
        print(f"Generating Video: {Prompt}", flush=True)
        generate_video(Prompt)
except Exception as e:
    print(f"Error: {e}", flush=True)
finally:
    with open("Frontend/Files/VideoGeneration.data", "w") as file:
        file.write("False,False")
