"""Record a real terminal run of the Sentinel agent and render it as a demo video.

Two steps:

  capture  Runs the commands below for real, timestamps every output line as it
           arrives, and writes docs/live_run_capture.jsonl.
  render   Replays that capture as terminal frames (compressing long router
           idle waits while keeping true wall-clock timestamps), adds a short
           title card and narration, and writes docs/cortensor_live_demo.mp4.

Nothing on screen is scripted: every terminal line comes from the capture file.

Usage:
  uv run --with pillow python scripts/record_live_demo.py capture --provider portal
  uv run --with pillow python scripts/record_live_demo.py render
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CAPTURE = ROOT / "docs" / "live_run_capture.jsonl"
OUTPUT = ROOT / "docs" / "cortensor_live_demo.mp4"

W, H = 1280, 720
FPS = 10
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 17
LINE_H = 23
COLS = 112
MARGIN = 24
BG = (18, 20, 24)
FG = (220, 223, 228)
PROMPT = (120, 200, 140)
DIM = (140, 146, 156)

IDLE_GAP_THRESHOLD_S = 2.5
COMPRESSED_GAP_DURATION_S = 4.0

INTRO = (
    "This is Cortensor Task Sentinel, a code verification agent built with the OpenMinion 0.1 Python SDK, "
    "running live against the Cortensor Portal API. "
    "First I run the offline unit tests, then the live Portal verification across two miner tasks. "
    "Long router waits are compressed during playback while showing real wall clock time."
)
DURING = (
    "The agent receives an honest Fibonacci function and an os.system exploit. "
    "By disabling pre-turn reflection overhead in OpenMinion, the Portal model drives all verification tools end-to-end. "
    "Verdicts come strictly from tool outputs on the submitted code."
)
OUTRO = (
    "On live Cortensor Portal, the agent certified the honest Fibonacci function and rejected the os.system exploit. "
    "If a model rewrites submitted code during a turn, the AST parity check fails closed."
)


def _load_env_file(env_path: Path) -> dict[str, str]:
    """Read key-value pairs from a dotenv file without echoing them."""
    parsed: dict[str, str] = {}
    if not env_path.exists():
        return parsed
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            parsed[key] = val
    return parsed


def _build_capture_spec(provider: str) -> tuple[dict[str, str], str, str, list[str]]:
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    secret_env = _load_env_file(ROOT / ".env")
    for k, v in secret_env.items():
        env.setdefault(k, v)

    if provider == "portal":
        if not env.get("CORTENSOR_API_KEY"):
            sys.exit("CORTENSOR_API_KEY must be set in environment or .env for portal capture")
        model = env.get("SENTINEL_MODEL", "").strip() or "oss-20b"
        base_url = env.get("SENTINEL_BASE_URL", "https://api.cortensor.app/v1")
        commands = [
            "uv run pytest -q",
            "uv run sentinel --live --provider portal",
        ]
    else:
        model = env.get("SENTINEL_MODEL", "").strip()
        if not model:
            sys.exit("set SENTINEL_MODEL first for local capture")
        base_url = env.get("SENTINEL_BASE_URL", "http://localhost:11434/v1")
        commands = [
            "uv run pytest -q",
            "uv run sentinel --live",
        ]
    return env, model, base_url, commands


def _redact_secret(text: str, secret: str | None) -> str:
    if secret and secret in text:
        return text.replace(secret, "[REDACTED]")
    return text


def capture(provider: str = "portal") -> None:
    env, model, base_url, commands = _build_capture_spec(provider)
    secret = env.get("CORTENSOR_API_KEY") if provider == "portal" else None
    explicit_model = os.getenv("SENTINEL_MODEL", "").strip()

    events: list[dict] = []
    exit_codes: list[int] = []
    t0 = time.perf_counter()

    for cmd in commands:
        if "--live" in cmd and explicit_model:
            shown = f"SENTINEL_MODEL={explicit_model} {cmd}"
        else:
            shown = cmd
        cmd_env = env if "--live" in cmd else {k: v for k, v in env.items() if k != "CORTENSOR_API_KEY"}
        events.append({"t": round(time.perf_counter() - t0, 3), "kind": "cmd", "text": shown})
        proc = subprocess.Popen(
            cmd.split(),
            cwd=ROOT,
            env=cmd_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            safe_line = _redact_secret(line.rstrip("\n"), secret)
            events.append({"t": round(time.perf_counter() - t0, 3), "kind": "out", "text": safe_line})
            print(safe_line, flush=True)
        rc = proc.wait()
        exit_codes.append(rc)
        events.append({"t": round(time.perf_counter() - t0, 3), "kind": "exit", "text": str(rc)})

    header = {
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "commands": commands,
        "exit_codes": exit_codes,
    }
    with CAPTURE.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"header": header}) + "\n")
        for e in events:
            f.write(json.dumps(e) + "\n")
    print(f"\nwrote {CAPTURE} (exit_codes={exit_codes})")
    if any(rc != 0 for rc in exit_codes):
        sys.exit(1)


def _tts(text: str, out: Path) -> float:
    pocket = shutil.which("pocket-tts") or str(Path.home() / ".local/bin/pocket-tts")
    with tempfile.TemporaryDirectory() as td:
        parts = []
        for i, sentence in enumerate(
            s.strip() for s in text.replace("? ", "?|").replace(". ", ".|").split("|")
        ):
            if not sentence:
                continue
            wav = Path(td) / f"{i}.wav"
            subprocess.run(
                [
                    pocket,
                    "generate",
                    "--text",
                    sentence,
                    "--device",
                    "cpu",
                    "--quantize",
                    "--max-tokens",
                    "150",
                    "--output-path",
                    str(wav),
                    "-q",
                ],
                check=True,
                capture_output=True,
            )
            parts.append(wav)
        lst = Path(td) / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(lst),
                "-ar",
                "24000",
                "-ac",
                "1",
                str(out),
            ],
            check=True,
            capture_output=True,
        )
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(probe.stdout)


def _screen_lines(events: list[dict], until: float) -> list[tuple[str, tuple[int, int, int]]]:
    lines: list[tuple[str, tuple[int, int, int]]] = []
    for e in events:
        if e["t"] > until:
            break
        if e["kind"] == "cmd":
            lines.append(("$ " + e["text"], PROMPT))
        elif e["kind"] == "out":
            for chunk in textwrap.wrap(
                e["text"], COLS, drop_whitespace=False, replace_whitespace=False
            ) or [""]:
                lines.append((chunk, FG))
    return lines


def _build_playback_segments(events: list[dict], rec_end: float) -> list[tuple[float, float, float, float, bool]]:
    """Map real-time event intervals to playback video intervals.

    Gaps exceeding IDLE_GAP_THRESHOLD_S compress to COMPRESSED_GAP_DURATION_S
    so router wait latency does not produce a multi-minute silent stretch.
    """
    points = sorted({0.0, *(float(e["t"]) for e in events), rec_end})
    segments: list[tuple[float, float, float, float, bool]] = []
    vid_t = 0.0
    for ra, rb in zip(points, points[1:]):
        dt = rb - ra
        if dt <= 1e-6:
            continue
        compressed = dt > IDLE_GAP_THRESHOLD_S
        v_dt = COMPRESSED_GAP_DURATION_S if compressed else dt
        segments.append((ra, rb, vid_t, vid_t + v_dt, compressed))
        vid_t += v_dt
    return segments


def _map_video_to_real(
    segments: list[tuple[float, float, float, float, bool]], video_t: float
) -> tuple[float, bool]:
    for ra, rb, va, vb, compressed in segments:
        if video_t <= vb + 1e-9:
            frac = max(0.0, min(1.0, (video_t - va) / max(1e-9, vb - va)))
            return ra + frac * (rb - ra), compressed
    if segments:
        return segments[-1][1], False
    return 0.0, False


def _draw(lines: list[tuple[str, tuple[int, int, int]]], footer: str, path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(FONT, FONT_SIZE)
    small = ImageFont.truetype(FONT, 14)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    rows = (H - 2 * MARGIN - 30) // LINE_H
    for i, (text, color) in enumerate(lines[-rows:]):
        d.text((MARGIN, MARGIN + i * LINE_H), text, font=font, fill=color)
    d.text((MARGIN, H - MARGIN - 14), footer, font=small, fill=DIM)
    img.save(path)


def _title(path: Path, provider: str, model: str, base_url: str, recorded_at: str) -> None:
    if provider == "portal":
        endpoint_line = f"Live Provider: Cortensor Portal ({base_url}), model={model}"
    else:
        endpoint_line = f"Model: {model} via {base_url}"
    lines = [
        ("Cortensor Task Sentinel", FG),
        ("", FG),
        ("A code verification agent built with the OpenMinion 0.1.24 Python SDK", FG),
        ("Cortensor Hackathon #5", FG),
        ("", FG),
        (endpoint_line, DIM),
        (f"Recorded {recorded_at}. Real terminal output (long router waits compressed; real wall-clock shown).", DIM),
        ("Source: github.com/manderson240/cortensor-subnet-validator", DIM),
    ]
    _draw([("", FG)] * 8 + lines, "", path)


def render() -> None:
    rows = [json.loads(line) for line in CAPTURE.read_text(encoding="utf-8").splitlines()]
    header = rows[0]["header"]
    events = rows[1:]
    provider = header.get("provider", "local")
    model = header["model"]
    base_url = header["base_url"]
    recorded_at = header["recorded_at"]

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        intro_wav, during_wav, outro_wav = tdp / "intro.wav", tdp / "during.wav", tdp / "outro.wav"
        intro_s = _tts(INTRO, intro_wav) + 1.0
        during_s = _tts(DURING, during_wav)
        outro_s = _tts(OUTRO, outro_wav) + 3.5

        rec_end = events[-1]["t"] + 1.0
        segments = _build_playback_segments(events, rec_end)
        rec_video_s = segments[-1][3] if segments else 1.0

        live_real_start = next(
            float(e["t"]) for e in events if e["kind"] == "cmd" and "--live" in e["text"]
        )
        live_video_start = next(
            (va for ra, _, va, _, _ in segments if ra >= live_real_start - 1e-6),
            0.0,
        )

        frames = tdp / "frames"
        frames.mkdir()
        n = 0
        title = tdp / "title.png"
        _title(title, provider, model, base_url, recorded_at)
        for _ in range(int(intro_s * FPS)):
            shutil.copy(title, frames / f"{n:06d}.png")
            n += 1

        if provider == "portal":
            footer_base = f"real Portal recording, {model}, {base_url}"
            wall_label = "portal wall"
        else:
            footer_base = f"real recording, {model}"
            wall_label = "t"

        last_key = None
        last_png = None
        for i in range(int(rec_video_s * FPS)):
            v_t = i / FPS
            real_t, compressed = _map_video_to_real(segments, v_t)
            lines = _screen_lines(events, real_t)
            key = (len(lines), compressed, round(real_t, 1) if compressed else -1.0)
            if key != last_key:
                last_png = tdp / f"s{n}.png"
                suffix = "   [waiting on Cortensor Portal router, idle wait compressed]" if compressed else ""
                _draw(lines, f"{footer_base}   {wall_label}={real_t:5.1f}s{suffix}", last_png)
                last_key = key
            assert last_png is not None
            shutil.copy(last_png, frames / f"{n:06d}.png")
            n += 1

        final = tdp / "final.png"
        _draw(
            _screen_lines(events, rec_end),
            f"{footer_base}   {wall_label}={events[-1]['t']:5.1f}s   (final screen held for narration)",
            final,
        )
        for _ in range(int(outro_s * FPS)):
            shutil.copy(final, frames / f"{n:06d}.png")
            n += 1

        during_at = intro_s + live_video_start
        outro_at = intro_s + rec_video_s
        total = n / FPS
        if during_at + during_s > outro_at:
            print(
                f"warning: 'during' narration ({during_s:.1f}s) overlaps the outro; "
                f"available={outro_at - during_at:.1f}s"
            )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                str(frames / "%06d.png"),
                "-i",
                str(intro_wav),
                "-i",
                str(during_wav),
                "-i",
                str(outro_wav),
                "-filter_complex",
                f"[1]adelay=500:all=1[a1];[2]adelay={int(during_at * 1000)}:all=1[a2];"
                f"[3]adelay={int(outro_at * 1000)}:all=1[a3];[a1][a2][a3]amix=inputs=3:normalize=0,apad[a]",
                "-map",
                "0:v",
                "-map",
                "[a]",
                "-t",
                f"{total:.2f}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(OUTPUT),
            ],
            check=True,
            capture_output=True,
        )
    print(f"wrote {OUTPUT} ({total:.1f}s, real capture={events[-1]['t']:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture and render live Sentinel demo video")
    parser.add_argument("action", nargs="?", choices=["capture", "render"], default="capture")
    parser.add_argument("--provider", choices=["local", "portal"], default="portal")
    args = parser.parse_args()
    if args.action == "capture":
        capture(provider=args.provider)
    else:
        render()


if __name__ == "__main__":
    main()
