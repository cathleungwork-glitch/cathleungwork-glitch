"""Text-card Reels via ffmpeg, carousel JPEGs via Pillow. No stock footage."""

from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from ig_pipeline.textfit import fit_text, font_path, load_font

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
            "Voice zh-HK-HiuMaanNeural. On-screen text is the playbook script. "
            "Not investment advice."
        )
        title = hook
    durations = allocate_durations(total, len(cards))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ig-reel-") as tmp_name:
        tmp = Path(tmp_name)
        segments = [
            _render_card(tmp, index, text, duration)
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


def _render_card(tmp: Path, index: int, text: str, duration: float) -> Path:
    max_width = REEL_W - 2 * REEL_SAFE_X
    max_height = REEL_H - REEL_SAFE_TOP - REEL_SAFE_BOTTOM
    size, lines, line_height = fit_text(text, max_width, max_height)
    block = line_height * len(lines)
    safe_height = REEL_H - REEL_SAFE_TOP - REEL_SAFE_BOTTOM
    top = REEL_SAFE_TOP + max(0, (safe_height - block) // 2)
    text_file = tmp / f"card-{index:02}.txt"
    text_file.write_text("\n".join(lines), encoding="utf-8")
    video = tmp / f"card-{index:02}.mp4"
    vf = (
        "drawtext="
        f"fontfile={_ff_path(font_path())}:"
        f"textfile={_ff_path(text_file)}:"
        f"fontsize={size}:fontcolor=white:expansion=none:"
        f"line_spacing={max(14, size // 5)}:text_align=center:"
        f"x=(w-text_w)/2:y={top}"
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={REEL_W}x{REEL_H}:r={FPS}:d={duration:.3f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-r",
            str(FPS),
            "-an",
            str(video),
        ]
    )
    return video


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


def _ff_path(path: Path | str) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _run(cmd: list[str]) -> None:
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip()[-800:]
        raise RuntimeError(f"ffmpeg failed: {tail}")
