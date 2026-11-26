"""Wrap Cantonese lines so they stay large and inside the safe area."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# Mac system fonts first, then the Linux paths this already used, then a
# user-installed WenQuanYi file. No sudo and no /usr/share required.
_MAC_FONTS = (
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
)
_LINUX_FONTS = (
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
)


def font_candidates() -> tuple[Path, ...]:
    return _MAC_FONTS + _LINUX_FONTS + tuple(_user_wqy_fonts())


def _user_wqy_fonts() -> list[Path]:
    folder = Path.home() / "Library" / "Fonts"
    if not folder.is_dir():
        return []
    found = [path for path in folder.iterdir() if path.is_file() and "wqy" in path.name.lower()]
    return sorted(found, key=lambda path: path.name.lower())


def font_path() -> str:
    for candidate in font_candidates():
        if candidate.is_file():
            return str(candidate)
    raise SystemExit(
        "No CJK font found. On macOS this looks for PingFang, STHeiti Medium, "
        "or Hiragino Sans GB in /System/Library/Fonts, or a wqy file in ~/Library/Fonts. "
        "On Linux it looks for WenQuanYi Micro Hei or Droid Sans Fallback."
    )


def _face_index(path: str) -> int:
    """Prefer a Traditional / Hong Kong face inside a .ttc. Index 0 of PingFang is often Simplified."""
    best = 0
    best_score = -10
    for index in range(8):
        try:
            font = ImageFont.truetype(path, 40, index=index)
        except OSError:
            break
        family, style = font.getname()
        label = f"{family} {style}".lower()
        score = 0
        if any(token in label for token in ("hk", "hong kong", "tc", "traditional", "繁")):
            score += 5
        if any(token in label for token in ("sc", "simplified", "简", "gb")):
            score -= 4
        if score > best_score:
            best_score = score
            best = index
    return best


@lru_cache(maxsize=4)
def _cached_face_index(path: str) -> int:
    return _face_index(path)


@lru_cache(maxsize=32)
def load_font(size: int) -> ImageFont.FreeTypeFont:
    path = font_path()
    return ImageFont.truetype(path, size, index=_cached_face_index(path))


_PUNCT = set("，、。！？：；")


def wrap_text(text: str, size: int, max_width: int) -> list[str]:
    """Wrap on character width, preferring a break after ，、。 when the line is full."""
    font = load_font(size)
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if not current or font.getlength(trial) <= max_width:
            current = trial
            continue
        if char in _PUNCT and font.getlength(trial) <= max_width:
            lines.append(trial)
            current = ""
            continue
        split_at = max(current.rfind(mark) for mark in _PUNCT)
        if 0 <= split_at < len(current) - 1:
            lines.append(current[: split_at + 1])
            current = current[split_at + 1 :] + char
            if font.getlength(current) > max_width:
                broken, current = _hard_split(current, font, max_width)
                lines.extend(broken)
            continue
        lines.append(current)
        current = char
    if current:
        lines.append(current)
    return [line for line in lines if line] or [text]


def _hard_split(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> tuple[list[str], str]:
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if current and font.getlength(trial) > max_width:
            lines.append(current)
            current = char
        else:
            current = trial
    return lines, current


def fit_text(text: str, max_width: int, max_height: int) -> tuple[int, list[str], int]:
    for size in (84, 76, 68, 60, 54, 48, 42, 36):
        lines = wrap_text(text, size, max_width)
        font = load_font(size)
        if any(font.getlength(line) > max_width + 1 for line in lines):
            continue
        if "".join(lines) != text:
            continue
        spacing = max(12, size // 6)
        line_height = _line_box(font) + spacing
        if lines and line_height * len(lines) <= max_height:
            return size, lines, line_height
    lines = wrap_text(text, 36, max_width)
    font = load_font(36)
    return 36, lines, _line_box(font) + 12


def _line_box(font: ImageFont.FreeTypeFont) -> int:
    box = font.getbbox("香港出糧午飯")
    return max(1, box[3] - box[1])
