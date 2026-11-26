"""Reject scripts that leave the playbook's niche or posting rules."""

from __future__ import annotations

from ig_pipeline.playbook import Post

ALLOWED_TAGS = ("#出糧", "#打工仔", "#信用卡", "#香港", "#人工智能")

# Buy/sell wording that the scripts already use in the negative ("唔係叫你買")
# is allowed. These phrases are positive recommendations or out-of-niche topics.
# Simplified forms that must not appear on screen or in the script.
SIMPLIFIED = set(
    "饭门国这说后来发为与时过还从开关长东车电话经买卖银账单费总数额户储转笔约现险务报证书网币结签条读听声让进见问请谢认识实际应该钱们样种类点体学习问题对会于没个"
)


FORBIDDEN = (
    "強積金",
    "mpf",
    "稅",
    "保證回報",
    "保證賺",
    "穩賺",
    "必賺",
    "包賺",
    "你應該買",
    "快啲買",
    "建議你買",
    "推薦你買",
    "必買",
    "全倉",
    "買入呢隻",
    "叫你買呢隻",
)


def lint_text(text: str) -> list[str]:
    folded = text.lower()
    issues = [phrase for phrase in FORBIDDEN if phrase.lower() in folded]
    simplified = sorted({char for char in text if char in SIMPLIFIED})
    issues.extend(f"simplified:{char}" for char in simplified)
    return issues


def lint_post(post: Post) -> list[str]:
    issues: list[str] = []
    blob = "\n".join(
        [
            post.topic,
            post.hook,
            post.spoken,
            post.cta,
            post.board,
            post.point,
            post.source,
            "\n".join(post.cards),
            "\n".join(post.pages),
            " ".join(post.hashtags),
        ]
    )
    issues.extend(f"forbidden:{phrase}" for phrase in lint_text(blob))
    if not 1 <= len(post.hashtags) <= 5:
        issues.append(f"hashtag count {len(post.hashtags)}")
    for tag in post.hashtags:
        if tag not in ALLOWED_TAGS:
            issues.append(f"hashtag {tag}")
    if post.point not in post.source and post.point not in post.spoken:
        issues.append("caption point is not a line from the script")
    if post.kind == "reel":
        if not post.cards or post.cards[0] != post.hook:
            issues.append("first card is not the first-second line")
        if not 3 <= len(post.cards) <= 9:
            issues.append(f"card count {len(post.cards)}")
        if not post.spoken:
            issues.append("missing spoken script")
    else:
        if not 7 <= len(post.pages) <= 8:
            issues.append(f"page count {len(post.pages)}")
        if not post.pages or post.pages[0] != post.hook:
            issues.append("cover is not page 1")
    return issues
