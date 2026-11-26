"""Caption shape from the playbook: hook, one point, disclaimer, at most five tags."""

from __future__ import annotations

from ig_pipeline.playbook import Post

DISCLAIMER = "例子，唔係你嘅數。唔係投資建議。"


def build_caption(post: Post) -> str:
    tags = " ".join(post.hashtags)
    return f"{post.hook}\n{post.point}\n{DISCLAIMER}\n{tags}\n"
