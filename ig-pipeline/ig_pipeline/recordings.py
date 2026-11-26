"""A wav or m4a dropped in recordings/ replaces edge-tts for that day."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

AUDIO_SUFFIXES = (".wav", ".m4a", ".mp3", ".aac")


def find_recording(day: int, folder: Path) -> Path | None:
    if not folder.is_dir():
        return None
    stem = f"day-{day:02}"
    for suffix in AUDIO_SUFFIXES:
        path = folder / f"{stem}{suffix}"
        if _usable(path):
            return path
    nested = folder / stem
    if nested.is_dir():
        files = [path for path in sorted(nested.iterdir()) if _usable(path)]
        if len(files) == 1:
            return files[0]
    return None


def line_recordings(day: int, folder: Path, count: int) -> list[Path] | None:
    nested = folder / f"day-{day:02}"
    if not nested.is_dir() or count < 1:
        return None
    found: list[Path] = []
    for index in range(1, count + 1):
        match = None
        for suffix in AUDIO_SUFFIXES:
            path = nested / f"{index:02}{suffix}"
            if _usable(path):
                match = path
                break
        if match is None:
            return None
        found.append(match)
    return found


def _usable(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES and path.stat().st_size > 1000


def concat_audio(parts: list[Path], out: Path) -> None:
    listing = out.with_suffix(".concat.txt")
    listing.write_text(
        "".join(f"file '{part.resolve()}'\n" for part in parts),
        encoding="utf-8",
    )
    done = subprocess.run(
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
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0 or not out.exists():
        raise RuntimeError((done.stderr or "could not join the voice lines")[-400:])


def trim_leading(src: Path, dest: Path) -> None:
    """Drop only the silence before the first word, so the card is not late."""
    done = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-af",
            "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-40dB",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0 or not dest.exists() or dest.stat().st_size < 800:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(src),
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(dest),
            ],
            check=True,
            capture_output=True,
        )


def probe_duration(path: Path) -> float:
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
    return max(0.2, float(out.strip() or "0"))


def line_durations(path: Path, lines: list[str]) -> list[float]:
    """Put each card on screen while that line is spoken.

    Silence between sentences is the boundary. If the pauses do not match
    the script, fall back to character length so a short line does not wait
    for an equal slice of the whole file.
    """
    total = probe_duration(path)
    regions = _speech_regions(path, total)
    if len(regions) == len(lines) and lines:
        starts = [0.0] + [item[0] for item in regions[1:]]
        ends = [item[0] for item in regions[1:]] + [total]
        durations = [max(0.2, ends[index] - starts[index]) for index in range(len(lines))]
        durations[-1] = max(0.2, total - sum(durations[:-1]))
        return durations
    weights = [max(1, len(line)) for line in lines] or [1]
    scale = total / sum(weights)
    durations = [weight * scale for weight in weights]
    durations[-1] = max(0.2, total - sum(durations[:-1]))
    return durations


def _speech_regions(path: Path, total: float) -> list[tuple[float, float]]:
    done = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "silencedetect=noise=-35dB:d=0.28",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    starts = [float(item) for item in re.findall(r"silence_start: ([0-9.]+)", done.stderr)]
    ends = [float(item) for item in re.findall(r"silence_end: ([0-9.]+)", done.stderr)]
    silences: list[tuple[float, float]] = []
    for index, start in enumerate(starts):
        end = ends[index] if index < len(ends) else total
        if end > start:
            silences.append((start, min(end, total)))
    regions: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in silences:
        if start - cursor > 0.12:
            regions.append((cursor, start))
        cursor = max(cursor, end)
    if total - cursor > 0.12:
        regions.append((cursor, total))
    return regions
