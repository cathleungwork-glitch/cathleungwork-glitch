"""Official Instagram content publishing. Dry-run unless --live and credentials exist.

Uses the Instagram Graph API on graph.facebook.com and, for Reels, the resumable
upload on rupload.facebook.com. No scrapers, no follow bots, no unofficial clients.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ig_pipeline.schedule import HK

GRAPH_HOST = "graph.facebook.com"
UPLOAD_HOST = "rupload.facebook.com"
DEFAULT_VERSION = "v22.0"
GAP = timedelta(hours=12)

NO_CREDENTIALS = """Instagram publish did not run.
No IG_ACCESS_TOKEN or IG_USER_ID in the environment.
Nothing was sent to Instagram. This command does not scrape, follow, or ask you to paste a token into chat.
Create the Creator account and the same-name Facebook Page in Meta Business Suite yourself. Then put a long-lived Page access token in IG_ACCESS_TOKEN and the Instagram professional account id in IG_USER_ID. Run this command again. It stays a dry run until you pass --live.
"""


@dataclass
class Selection:
    post: dict | None
    message: str


def credentials() -> tuple[str, str] | None:
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("IG_USER_ID", "").strip()
    if token and user_id:
        return token, user_id
    return None


def graph_version() -> str:
    version = os.environ.get("IG_GRAPH_VERSION", DEFAULT_VERSION).strip()
    if not version.startswith("v"):
        raise RuntimeError("IG_GRAPH_VERSION must look like v22.0")
    return version


def select_for_live(posts: list[dict], now: datetime) -> Selection:
    ordered = sorted(posts, key=lambda post: (post["post_at"], post["day"]))
    published_at = [
        datetime.fromisoformat(post["published_at"])
        for post in ordered
        if post.get("status") == "published" and post.get("published_at")
    ]
    if published_at:
        last = max(published_at)
        if now - last < GAP:
            return Selection(
                None,
                "A post went out at "
                f"{last.isoformat()}. Live mode waits 12 hours so this account does not burst. "
                "Nothing was sent.",
            )
    for post in ordered:
        when = datetime.fromisoformat(post["post_at"])
        if when > now or post.get("status") == "published":
            continue
        if post.get("status") == "publishing":
            return Selection(
                None,
                f"Day {post['day']} is marked publishing. Check Instagram before retrying. "
                "Nothing was sent.",
            )
        if post.get("status") in {"draft", "failed"}:
            return Selection(post, f"Day {post['day']} is due at {post['post_at']}.")
    future = [
        post
        for post in ordered
        if datetime.fromisoformat(post["post_at"]) > now and post.get("status") != "published"
    ]
    if future:
        nxt = future[0]
        return Selection(
            None,
            f"Nothing is due. Next is day {nxt['day']} at {nxt['post_at']} Hong Kong. "
            "Nothing was sent.",
        )
    return Selection(None, "Every post in this schedule is already marked published. Nothing was sent.")


def format_dry_run(data: dict, manifest: Path, now: datetime | None = None) -> str:
    current = now or datetime.now(HK)
    lines = []
    creds = credentials()
    if creds is None:
        lines.append(NO_CREDENTIALS.strip())
        lines.append("")
    else:
        lines.append("IG_ACCESS_TOKEN is set. The value is not shown.")
        lines.append(f"IG_USER_ID is set ({creds[1]}).")
        lines.append("Dry run. Nothing was sent to Instagram.")
        lines.append("")
    lines.append(f"Manifest: {manifest}")
    lines.append(f"Voice: {data.get('voice', {}).get('engine', 'unknown')} {data.get('voice', {}).get('name', '')}")
    if data.get("voice", {}).get("fallback"):
        lines.append("Voice is a SILENT FALLBACK. Do not post until you replace it.")
    lines.append("")
    for post in data["posts"]:
        files = post.get("files") or [post.get("file")]
        lines.append(
            f"Day {post['day']:2}  {post['post_at']}  {post['kind']:8}  {post['status']:10}  {files[0]}"
        )
    selection = select_for_live(data["posts"], current)
    lines.append("")
    lines.append(f"If you passed --live right now: {selection.message}")
    if selection.post and creds is not None:
        lines.append("The live call would be the official content-publishing API:")
        lines.extend(_plan_lines(selection.post, creds[1]))
    elif selection.post and creds is None:
        lines.append("No container would be created, because the token is not set.")
    lines.append("Nothing was sent to Instagram.")
    return "\n".join(lines) + "\n"


def _plan_lines(post: dict, user_id: str) -> list[str]:
    version = graph_version()
    lines = [
        f"POST https://{GRAPH_HOST}/{version}/{user_id}/media",
        "Authorization: Bearer [redacted]",
    ]
    if post["kind"] == "reel":
        lines.append("media_type=REELS upload_type=resumable share_to_feed=true")
        if post.get("ai_generated_voice"):
            lines.append("is_ai_generated=true")
        lines.append(f"caption from {Path(post['file']).parent / 'caption.txt'}")
        lines.append(f"then POST https://{UPLOAD_HOST}/ig-api-upload/{version}/{{container}} with the local mp4")
    else:
        base = os.environ.get("IG_MEDIA_PUBLIC_BASE_URL", "").strip()
        if not base:
            lines.append(
                "Carousel images need IG_MEDIA_PUBLIC_BASE_URL (https). "
                "Meta fetches each JPEG. This live run would stop before creating a container."
            )
        else:
            lines.append(f"image_url under {base} for each JPEG, is_carousel_item=true")
            lines.append("then media_type=CAROUSEL with those container ids")
    lines.append(f"then POST https://{GRAPH_HOST}/{version}/{user_id}/media_publish")
    return lines


def publish_live(manifest: Path, now: datetime | None = None) -> int:
    creds = credentials()
    if creds is None:
        print(NO_CREDENTIALS.strip())
        return 2
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("voice", {}).get("fallback"):
        print(
            "This folder's voice is a SILENT FALLBACK. "
            "Live publish is refused until you generate again with a real zh-HK track."
        )
        return 2
    current = now or datetime.now(HK)
    selection = select_for_live(data["posts"], current)
    if selection.post is None:
        print(selection.message)
        return 0
    post = selection.post
    print(selection.message)
    token, user_id = creds
    _check_quota(user_id, token)
    post["status"] = "publishing"
    _save(manifest, data)
    try:
        if post["kind"] == "reel":
            media_id = _publish_reel(manifest.parent, post, user_id, token)
        elif post["kind"] == "carousel":
            media_id = _publish_carousel(manifest.parent, post, user_id, token)
        else:
            raise RuntimeError(f"unknown kind {post['kind']}")
    except Exception as exc:  # noqa: BLE001 — record the failure and do not retry blindly
        post["status"] = "failed"
        post["error"] = _redact(str(exc))[:500]
        _save(manifest, data)
        print(f"Publish failed. Nothing further was sent. {post['error']}")
        return 1
    post["status"] = "published"
    post["media_id"] = media_id
    post["published_at"] = datetime.now(HK).isoformat(timespec="seconds")
    post.pop("error", None)
    _save(manifest, data)
    print(f"Published day {post['day']} as media {media_id}.")
    return 0


def _publish_reel(root: Path, post: dict, user_id: str, token: str) -> str:
    version = graph_version()
    video = root / post["file"]
    body: dict[str, object] = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": post["caption"].rstrip("\n"),
        "share_to_feed": True,
    }
    if post.get("ai_generated_voice"):
        body["is_ai_generated"] = True
    created = _graph_post(version, f"{user_id}/media", body, token)
    container = str(created["id"])
    upload_uri = str(created.get("uri") or f"https://{UPLOAD_HOST}/ig-api-upload/{version}/{container}")
    _upload_video(upload_uri, video, token)
    _wait_until_finished(version, container, token)
    published = _graph_post(version, f"{user_id}/media_publish", {"creation_id": container}, token)
    return str(published["id"])


def _publish_carousel(root: Path, post: dict, user_id: str, token: str) -> str:
    base = os.environ.get("IG_MEDIA_PUBLIC_BASE_URL", "").strip()
    if not base.startswith("https://"):
        raise RuntimeError(
            "Carousel publish needs IG_MEDIA_PUBLIC_BASE_URL set to an https folder "
            "Meta's servers can fetch. Reels can upload from disk. Nothing was sent."
        )
    version = graph_version()
    child_ids: list[str] = []
    for relative in post["files"]:
        url = base.rstrip("/") + "/" + relative.lstrip("/")
        created = _graph_post(
            version,
            f"{user_id}/media",
            {
                "image_url": url,
                "is_carousel_item": True,
                "alt_text": _page_alt(root, post, relative),
            },
            token,
        )
        child = str(created["id"])
        _wait_until_finished(version, child, token)
        child_ids.append(child)
    parent = _graph_post(
        version,
        f"{user_id}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": post["caption"].rstrip("\n"),
        },
        token,
    )
    container = str(parent["id"])
    _wait_until_finished(version, container, token)
    published = _graph_post(version, f"{user_id}/media_publish", {"creation_id": container}, token)
    return str(published["id"])


def _page_alt(root: Path, post: dict, relative: str) -> str:
    pages = root / Path(relative).parent / "pages.txt"
    if not pages.exists():
        return Path(relative).name
    lines = [line for line in pages.read_text(encoding="utf-8").splitlines() if line.strip()]
    name = Path(relative).stem
    try:
        index = int(name.split("-")[-1]) - 1
    except ValueError:
        index = 0
    if 0 <= index < len(lines):
        return lines[index][:1000]
    return lines[0][:1000]


def _check_quota(user_id: str, token: str) -> None:
    version = graph_version()
    payload = _graph_get(version, f"{user_id}/content_publishing_limit", token)
    data = payload.get("data") or []
    if not data:
        return
    usage = data[0].get("quota_usage")
    config = data[0].get("config") or {}
    total = config.get("quota_total")
    if usage is not None and total is not None and int(usage) >= int(total):
        raise RuntimeError(
            f"Instagram content publishing limit is full ({usage}/{total}). Nothing was sent."
        )


def _wait_until_finished(version: str, container: str, token: str) -> None:
    for _ in range(36):
        payload = _graph_get(version, container, token, {"fields": "status_code"})
        status = payload.get("status_code")
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"container {container} status {status}")
        time.sleep(5)
    raise RuntimeError(
        f"container {container} still processing after 3 minutes. "
        "It was not published. Check it before running --live again."
    )


def _upload_video(uri: str, video: Path, token: str) -> None:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "https" or parsed.hostname != UPLOAD_HOST:
        raise RuntimeError("Refusing to upload video to a host other than rupload.facebook.com")
    payload = video.read_bytes()
    request = urllib.request.Request(uri, data=payload, method="POST")
    request.add_header("Authorization", f"OAuth {token}")
    request.add_header("offset", "0")
    request.add_header("file_size", str(len(payload)))
    request.add_header("Content-Type", "application/octet-stream")
    _open(request)


def _graph_post(version: str, path: str, body: dict, token: str) -> dict:
    url = f"https://{GRAPH_HOST}/{version}/{path.lstrip('/')}"
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    return _open(request)


def _graph_get(version: str, path: str, token: str, query: dict | None = None) -> dict:
    params = dict(query or {})
    suffix = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"https://{GRAPH_HOST}/{version}/{path.lstrip('/')}{suffix}"
    request = urllib.request.Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    return _open(request)


def _open(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} {_redact(detail)}") from exc
    if not raw:
        return {}
    return json.loads(raw)


def _redact(text: str) -> str:
    for name in ("IG_ACCESS_TOKEN", "AZURE_SPEECH_KEY"):
        secret = os.environ.get(name, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def _save(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def find_manifest(explicit: str | None, root: Path) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f"No manifest at {path}")
        return path
    found = sorted((root / "output").glob("*/schedule.json"))
    if not found:
        raise SystemExit("No schedule.json yet. Run: python -m ig_pipeline generate")
    if len(found) > 1:
        listed = "\n".join(str(path) for path in found)
        raise SystemExit(f"Several schedules. Pass --manifest.\n{listed}")
    return found[0]
