"""One spoken sentence per card, so the picture can follow the voice."""

from __future__ import annotations

from ig_pipeline.playbook import Post

_STOPS = "。！？"


def split_spoken(text: str) -> list[str]:
    parts: list[str] = []
    buf = ""
    for char in text.strip():
        buf += char
        if char in _STOPS:
            piece = buf.strip()
            if piece:
                parts.append(piece)
            buf = ""
    tail = buf.strip()
    if tail:
        parts.append(tail)
    if parts:
        return parts
    stripped = text.strip()
    return [stripped] if stripped else []


def reel_beats(post: Post) -> list[tuple[str, str]]:
    """Return (on-screen line, spoken sentence) in lockstep."""
    lines = split_spoken(post.spoken)
    cards = list(post.cards)
    if len(cards) == len(lines):
        return list(zip(cards, lines))
    return [(line.rstrip("。！？"), line) for line in lines]
