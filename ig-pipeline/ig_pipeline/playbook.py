"""Read the 14-day scripts. The markdown file is the source, not this module."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CONTENT_PATH = Path(__file__).resolve().parent.parent / "content" / "14-day.md"

REEL_FORMATS = ("字卡", "螢幕", "警告", "概念", "共鳴")
SCREEN_DAYS = {2, 6, 10}

_HEADING = re.compile(
    r"^###\s*第\s*(\d+)\s*日[\s\u3000]+(Reels|圖文)[\s\u3000]+(.+?)\s*$"
)
_VOICE_ITEM = re.compile(r"^(\d+)\.\s+(.+)$")
_PAGE_ITEM = re.compile(r"^(\d+)\.\s*(.+)$")


@dataclass
class Post:
    day: int
    kind: str
    format: str
    topic: str
    hook: str
    seconds: int | None
    spoken: str
    cta: str
    board: str
    pages: list[str]
    cards: list[str]
    point: str
    hashtags: list[str]
    source: str
    items: list[str] = field(default_factory=list)


def load_playbook(path: Path | None = None) -> tuple[list[Post], list[str]]:
    text = (path or CONTENT_PATH).read_text(encoding="utf-8")
    voice_checks: list[str] = []
    posts: list[Post] = []
    mode = "intro"
    block: list[str] = []
    heading: re.Match[str] | None = None

    def flush() -> None:
        nonlocal block, heading
        if heading is None:
            block = []
            return
        posts.append(_parse_day(heading, block))
        block = []
        heading = None

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## 試聲"):
            flush()
            mode = "voice"
            continue
        if line.startswith("### "):
            mode = "day"
            flush()
            heading = _HEADING.match(line)
            if heading is None:
                raise ValueError(f"bad day heading: {line}")
            block = []
            continue
        if line.startswith("## "):
            flush()
            mode = "intro"
            continue
        if mode == "voice":
            match = _VOICE_ITEM.match(line)
            if match:
                voice_checks.append(match.group(2).strip())
            continue
        if mode == "day":
            block.append(line)

    flush()
    posts.sort(key=lambda post: post.day)
    days = [post.day for post in posts]
    if days != list(range(1, 15)):
        raise ValueError(f"expected days 1-14, got {days}")
    if len(voice_checks) != 4:
        raise ValueError(f"expected 4 voice-check lines, got {len(voice_checks)}")
    return posts, voice_checks


def _parse_day(heading: re.Match[str], lines: list[str]) -> Post:
    day = int(heading.group(1))
    kind_word = heading.group(2)
    rest = heading.group(3).replace("\u3000", " ").strip()
    source = "\n".join(lines)
    if kind_word == "圖文":
        cover = _field(lines, "封面")
        point = _field(lines, "重點")
        tags = _tags(_field(lines, "標籤"))
        items = _numbered(lines)
        pages = _carousel_pages(cover, items)
        return Post(
            day=day,
            kind="carousel",
            format="清單圖文",
            topic=rest,
            hook=cover,
            seconds=None,
            spoken="",
            cta="",
            board="",
            pages=pages,
            cards=[],
            point=point,
            hashtags=tags,
            source=source,
            items=items,
        )

    fmt, topic = _split_reel(rest)
    hook = _field(lines, "第一秒畫面")
    length = _field(lines, "長度")
    seconds_match = re.search(r"(\d+)", length)
    if seconds_match is None:
        raise ValueError(f"day {day} has no length")
    spoken = _field(lines, "口播")
    cta = _field(lines, "行動呼籲")
    board = _field(lines, "畫面字")
    point = _field(lines, "重點")
    tags = _tags(_field(lines, "標籤"))
    cards = cards_for(hook, board, cta)
    return Post(
        day=day,
        kind="reel",
        format=fmt,
        topic=topic,
        hook=hook,
        seconds=int(seconds_match.group(1)),
        spoken=spoken,
        cta=cta,
        board=board,
        pages=[],
        cards=cards,
        point=point,
        hashtags=tags,
        source=source,
        items=[],
    )


def _split_reel(rest: str) -> tuple[str, str]:
    for fmt in REEL_FORMATS:
        if rest.startswith(fmt):
            return fmt, rest[len(fmt) :].strip()
    raise ValueError(f"unknown reel format: {rest}")


def _field(lines: list[str], name: str) -> str:
    for line in lines:
        stripped = re.sub(r"^-\s*", "", line.strip())
        for sep in ("：", ":"):
            prefix = f"{name}{sep}"
            if stripped.startswith(prefix):
                return stripped[len(prefix) :].strip()
    raise ValueError(f"missing field {name}")


def _tags(value: str) -> list[str]:
    return re.findall(r"#[^\s#]+", value)


def _numbered(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        match = _PAGE_ITEM.match(line.strip())
        if match:
            items.append(match.group(2).strip())
    return items


def _carousel_pages(cover: str, items: list[str]) -> list[str]:
    if items and items[0] == cover:
        return list(items)
    # Day 11's cover and its first numbered line say the same warning in
    # two wordings. The cover is the swipe line. Keeping both would make
    # nine pages; the format is seven or eight. The numbered line stays in
    # the caption's second line.
    return [cover, *items[1:]]


def board_phrases(board: str) -> list[str]:
    parts = re.split(r"[一二三四五六七八]、|。", board)
    phrases: list[str] = []
    for part in parts:
        text = part.strip()
        if not text:
            continue
        as_next = re.fullmatch(r"(.+?)下一行", text)
        as_line = re.fullmatch(r"(.+?)一行", text)
        if as_next:
            text = as_next.group(1).strip()
        elif as_line:
            text = as_line.group(1).strip()
        if text:
            phrases.append(text)
    return phrases


def _empty_cta(cta: str) -> bool:
    bare = cta.strip().rstrip("。.")
    return bare in {"", "冇", "無", "没有", "沒有"}


def cards_for(hook: str, board: str, cta: str) -> list[str]:
    phrases = board_phrases(board)
    cards: list[str] = []
    if hook and (not phrases or phrases[0] != hook):
        cards.append(hook)
    for phrase in phrases:
        if cards and phrase == cards[-1]:
            continue
        cards.append(phrase)
    if not _empty_cta(cta) and cta not in cards:
        cards.append(cta)
    if not cards:
        raise ValueError("a reel has no cards")
    if cards[0] != hook:
        raise ValueError(f"first card {cards[0]!r} is not the hook {hook!r}")
    return cards
