"""Text-card Reels and carousel JPEGs drawn with Pillow. ffmpeg only encodes, joins, and muxes."""

from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from ig_pipeline.textfit import fit_text, load_font

REEL_W, REEL_H = 1080, 1920
REEL_SAFE_TOP = 220
REEL_SAFE_BOTTOM = 460
REEL_SAFE_X = 120

CARD_W, CARD_H = 1080, 1350
CARD_SAFE_TOP = 170
CARD_SAFE_BOTTOM = 150
CARD_SAFE_X = 96

FPS = 30


def allocate_durations(total_seconds: float, count: int) -> list[float]:
    frames = max(count, int(math.ceil(total_seconds * FPS - 1e-6)))
    base, extra = divmod(frames, count)
    counts = [base + (1 if index < extra else 0) for index in range(count)]
    return [item / FPS for item in counts]


def render_reel(
    cards: list[str],
    audio: Path | None,
    out: Path,
    duration_if_silent: float,
    silent: bool,
    hook: str,
    durations: list[float] | None = None,
) -> None:
    if silent or audio is None:
        total = max(duration_if_silent, len(cards) * 2.5)
        comment = (
            "SILENT FALLBACK. zh-HK voice was unavailable. "
            "Do not post until this silent track is replaced."
        )
        title = "SILENT FALLBACK"
    else:
        total = _duration(audio)
        comment = (
            "On-screen text is Traditional Chinese. "
            "Not investment advice."
        )
        title = hook
    if durations is None or len(durations) != len(cards):
        durations = allocate_durations(total, len(cards))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ig-reel-") as tmp_name:
        tmp = Path(tmp_name)
        segments = [
            _render_card(tmp, index, text, duration, len(cards))
            for index, (text, duration) in enumerate(zip(cards, durations, strict=True))
        ]
        silent_video = tmp / "video.mp4"
        _concat(segments, silent_video)
        video_length = sum(durations)
        if silent or audio is None:
            _mux_silence(silent_video, out, video_length, comment, title)
        else:
            _mux_audio(silent_video, audio, out, video_length, comment, title)


def render_carousel(pages: list[str], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    total = len(pages)
    for index, page in enumerate(pages, start=1):
        path = out_dir / f"page-{index:02}.jpg"
        _render_page(page, path, index, total)
        paths.append(path)
    return paths


def _render_card(tmp: Path, index: int, text: str, duration: float, total: int) -> Path:
    image_path = tmp / f"card-{index:02}.png"
    _paint_reel_card(text, image_path, index + 1, total)
    video = tmp / f"card-{index:02}.mp4"
    frames = max(1, round(duration * FPS))
    # Encode the still. No -vf, so a default Homebrew ffmpeg without drawtext works.
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            str(FPS),
            "-i",
            str(image_path),
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-an",
            str(video),
        ]
    )
    return video


def _paint_reel_card(text: str, path: Path, index: int, total: int) -> None:
    """Upper-middle caption plate. The line stays inside the safe area, fully drawn."""
    image = Image.new("RGB", (REEL_W, REEL_H), (22, 24, 28))
    draw = ImageDraw.Draw(image)
    label_font = load_font(30)
    label = f"{index} / {total}"
    label_width = label_font.getlength(label)
    draw.text(((REEL_W - label_width) / 2, 96), label, font=label_font, fill=(190, 190, 190))

    left = REEL_SAFE_X
    right = REEL_W - REEL_SAFE_X
    plate_width = right - left
    pad = 40
    max_width = plate_width - 2 * pad
    max_height = 520
    size, lines, line_height = fit_text(text, max_width, max_height)
    font = load_font(size)
    block = line_height * len(lines)
    plate_height = block + pad * 2
    plate_top = 360
    plate_bottom = plate_top + plate_height
    floor = REEL_H - REEL_SAFE_BOTTOM - 24
    if plate_bottom > floor:
        plate_top = max(REEL_SAFE_TOP, floor - plate_height)
    draw.rounded_rectangle(
        (left, plate_top, right, plate_top + plate_height),
        radius=32,
        fill=(8, 8, 8),
    )
    y = plate_top + pad
    for line in lines:
        width = font.getlength(line)
        x = left + (plate_width - width) / 2
        draw.text((x, y), line, font=font, fill="white")
        y += line_height
    image.save(path, format="PNG")


def _render_page(text: str, path: Path, index: int, total: int) -> None:
    image = Image.new("RGB", (CARD_W, CARD_H), "black")
    draw = ImageDraw.Draw(image)
    label_font = load_font(32)
    label = f"{index} / {total}"
    label_width = label_font.getlength(label)
    draw.text(
        ((CARD_W - label_width) / 2, 56),
        label,
        font=label_font,
        fill=(176, 176, 176),
    )
    max_width = CARD_W - 2 * CARD_SAFE_X
    max_height = CARD_H - CARD_SAFE_TOP - CARD_SAFE_BOTTOM
    size, lines, line_height = fit_text(text, max_width, max_height)
    font = load_font(size)
    block = line_height * len(lines)
    safe_height = max_height
    top = CARD_SAFE_TOP + max(0, (safe_height - block) // 2)
    for line_index, line in enumerate(lines):
        width = font.getlength(line)
        x = (CARD_W - width) / 2
        y = top + line_index * line_height
        draw.text((x, y), line, font=font, fill="white")
    image.save(path, format="JPEG", quality=92, subsampling=0, optimize=True)


def _concat(segments: list[Path], out: Path) -> None:
    listing = out.with_suffix(".txt")
    listing.write_text(
        "".join(f"file '{segment}'\n" for segment in segments),
        encoding="utf-8",
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(out),
        ]
    )


def _mux_audio(video: Path, audio: Path, out: Path, length: float, comment: str, title: str) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-filter_complex",
            "[1:a]apad[a]",
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-t",
            f"{length:.3f}",
            "-movflags",
            "+faststart",
            "-metadata",
            f"comment={comment}",
            "-metadata",
            f"title={title}",
            str(out),
        ]
    )


def _mux_silence(video: Path, out: Path, length: float, comment: str, title: str) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-f",
            "lavfi",
            "-t",
            f"{length:.3f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            "-metadata",
            f"comment={comment}",
            "-metadata",
            f"title={title}",
            str(out),
        ]
    )


def _duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        text=True,
    )
    return float(out.strip())


def _run(cmd: list[str]) -> None:
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip()[-800:]
        raise RuntimeError(f"ffmpeg failed: {tail}")
