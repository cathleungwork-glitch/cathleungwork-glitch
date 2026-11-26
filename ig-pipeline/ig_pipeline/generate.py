"""Build the 14 posts: voice, text-card Reels, carousel JPEGs, schedule manifest."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date, datetime
from pathlib import Path

from PIL import Image

from ig_pipeline.captions import build_caption
from ig_pipeline.guardrails import lint_post
from ig_pipeline.lines import reel_beats
from ig_pipeline.playbook import CONTENT_PATH, SCREEN_DAYS, Post, load_playbook
from ig_pipeline.recordings import (
    concat_audio,
    find_recording,
    line_durations,
    line_recordings,
    probe_duration,
    trim_leading,
)
from ig_pipeline.render import render_carousel, render_reel
from ig_pipeline.schedule import HK, post_at
from ig_pipeline.voice import VOICE_NAME, synthesize_all

PIPELINE_ROOT = Path(__file__).resolve().parent.parent


def generate(
    start: date,
    output: Path | None,
    voice: str,
    force: bool,
    limit: int | None = None,
) -> int:
    posts, checks = load_playbook()
    issues: list[str] = []
    for post in posts:
        issues.extend(f"day {post.day}: {item}" for item in lint_post(post))
    if issues:
        print("The script file failed the niche check:")
        print("\n".join(issues))
        return 1
    if limit is not None:
        if limit < 1 or limit > len(posts):
            print(f"--limit must be from 1 to {len(posts)}. Omit it to write all {len(posts)}.")
            return 1
        posts = posts[:limit]

    folder = output or (PIPELINE_ROOT / "output" / start.isoformat())
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "schedule.json"
    if manifest_path.exists() and not force:
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if any(item.get("status") in {"published", "publishing"} for item in old.get("posts", [])):
            print(
                "This folder already has a post marked published or publishing. "
                "Pass --force only if you mean to discard that record."
            )
            return 1

    voice_dir = folder / "voice-check"
    voice_dir.mkdir(exist_ok=True)
    check_items = [(voice_dir / f"{index:02}.mp3", line) for index, line in enumerate(checks, start=1)]
    print(f"Voice fallback: {voice} ({VOICE_NAME})")
    result = synthesize_all(check_items, voice)
    _write_listen_note(voice_dir, checks, result.engine, result.fallback, result.detail)
    if result.fallback and voice != "silent":
        print("Voice-check audio was not generated.")
        print(result.detail)
    recordings = PIPELINE_ROOT / "recordings"

    records = []
    for post in posts:
        day_dir = folder / f"day-{post.day:02}"
        day_dir.mkdir(exist_ok=True)
        caption = build_caption(post)
        (day_dir / "caption.txt").write_text(caption, encoding="utf-8")
        when = post_at(start, post.day)
        if post.kind == "reel":
            beats = reel_beats(post)
            card_text = [card for card, _line in beats]
            spoken_lines = [line for _card, line in beats]
            audio, durations, engine, fallback = _reel_voice(
                post.day, day_dir, spoken_lines, voice, recordings
            )
            record = _record(post, caption, when, fallback, engine)
            print(f"Rendering day {post.day} reel ({len(card_text)} cards, {engine})")
            render_reel(
                card_text,
                audio,
                day_dir / "reel.mp4",
                float(post.seconds or 20),
                fallback or audio is None,
                post.hook,
                durations,
            )
            (day_dir / "cards.txt").write_text("\n".join(card_text) + "\n", encoding="utf-8")
            (day_dir / "VOICE.txt").write_text(
                "SILENT FALLBACK\n"
                if fallback or audio is None
                else f"{engine}\nDrop a replacement in recordings/day-{post.day:02}.wav or .m4a\n",
                encoding="utf-8",
            )
        else:
            record = _record(post, caption, when, False, "none")
            print(f"Rendering day {post.day} carousel ({len(post.pages)} pages)")
            render_carousel(post.pages, day_dir)
            (day_dir / "pages.txt").write_text("\n".join(post.pages) + "\n", encoding="utf-8")
        records.append(record)

    manifest = {
        "account_name": "出糧之後",
        "timezone": "Asia/Hong_Kong",
        "start_date": start.isoformat(),
        "generated_at": datetime.now(HK).isoformat(timespec="seconds"),
        "content_sha256": hashlib.sha256(CONTENT_PATH.read_bytes()).hexdigest(),
        "monthly_generation_cost_hkd": 0,
        "listen_before_posting": True,
        "post_count": len(records),
        "limit": limit,
        "voice": {
            "engine": result.engine,
            "name": result.voice,
            "fallback": result.fallback,
            "detail": result.detail,
        },
        "rules": {
            "posts_per_day": 1,
            "odd_day_time": "12:20",
            "even_day_time": "21:00",
            "topics": ["出糧同預算", "信用卡", "保險概念", "ETF 入門", "加密貨幣概念", "每日 AI 工具"],
            "excluded": ["強積金", "稅務", "買賣建議", "保證回報"],
            "music": "none",
            "third_party_media": False,
        },
        "screen_days_note": (
            "第 2、6、10 日喺播放清單係螢幕格式。呢度用同一段口播同畫面字做成字卡。"
            "程式唔會錄你部電腦，亦都唔會下載第二個人條片。"
            "你想換自己一鏡過嘅螢幕，出帖前換走 reel.mp4。"
        ),
        "posts": records,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    problems = verify_output(manifest_path)
    if problems:
        print("Output check failed:")
        print("\n".join(problems))
        return 1
    _print_summary(folder, manifest)
    return 0


def _reel_voice(
    day: int,
    day_dir: Path,
    lines: list[str],
    voice: str,
    recordings: Path,
) -> tuple[Path | None, list[float] | None, str, bool]:
    if voice != "silent":
        pieces = line_recordings(day, recordings, len(lines))
        whole = None if pieces else find_recording(day, recordings)
        if pieces or whole:
            out = day_dir / "voice.m4a"
            if pieces:
                concat_audio(pieces, out)
            else:
                assert whole is not None
                concat_audio([whole], out)
            return out, line_durations(out, lines), "recording", False
    if voice == "silent":
        return None, None, "silent", True
    clips: list[Path] = []
    items = []
    for index, line in enumerate(lines, start=1):
        raw = day_dir / f"line-{index:02}.mp3"
        items.append((raw, line))
    spoken = synthesize_all(items, voice)
    if spoken.fallback:
        print(f"Day {day}: no recording in recordings/, and edge-tts failed. Silent track.")
        print(spoken.detail)
        return None, None, spoken.engine, True
    for index in range(1, len(lines) + 1):
        raw = day_dir / f"line-{index:02}.mp3"
        cut = day_dir / f"line-{index:02}.m4a"
        trim_leading(raw, cut)
        clips.append(cut)
    out = day_dir / "voice.m4a"
    concat_audio(clips, out)
    return out, [probe_duration(clip) for clip in clips], spoken.engine, False


def _record(post: Post, caption: str, when: datetime, fallback: bool, engine: str) -> dict:
    record: dict = {
        "day": post.day,
        "date": when.date().isoformat(),
        "post_at": when.isoformat(timespec="seconds"),
        "kind": post.kind,
        "playbook_format": post.format,
        "topic": post.topic,
        "caption": caption,
        "hashtags": post.hashtags,
        "status": "draft",
        "ai_generated_voice": post.kind == "reel" and not fallback,
    }
    if post.kind == "reel":
        record["file"] = f"day-{post.day:02}/reel.mp4"
        record["voice_file"] = None if fallback else f"day-{post.day:02}/voice.mp3"
        record["voice_status"] = "silent-fallback" if fallback else f"{engine} {VOICE_NAME}"
        record["call_to_action"] = post.cta
        if post.day in SCREEN_DAYS:
            record["render_note"] = "text-card stand-in for the playbook screen format"
    else:
        record["files"] = [f"day-{post.day:02}/page-{index:02}.jpg" for index in range(1, len(post.pages) + 1)]
        record["voice_status"] = "none"
    return record


def _write_listen_note(folder: Path, lines: list[str], engine: str, fallback: bool, detail: str) -> None:
    body = [
        "聽呢四句，先至好考慮出帖。",
        "買同賣要分到聲調。七百二唔好變英文。claim 唔好似換咗個人。冇唔好讀成沒有。",
        "程式唔會替你話過關。一把聲用足十四日，唔好轉。",
        "",
    ]
    for index, line in enumerate(lines, start=1):
        body.append(f"{index}. {line}")
    body.append("")
    if fallback:
        body.append("呢四句未生成到。條片係靜音，檔案標明 SILENT FALLBACK。未換返把聲，唔好出。")
        body.append(detail)
    else:
        body.append(f"聲：{VOICE_NAME}（{engine}）。每月生成費用 HK$0。")
    (folder / "LISTEN.txt").write_text("\n".join(body) + "\n", encoding="utf-8")


def verify_output(manifest_path: Path) -> list[str]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    problems: list[str] = []
    reels = 0
    images = 0
    for post in data["posts"]:
        caption_path = root / f"day-{post['day']:02}" / "caption.txt"
        if not caption_path.exists():
            problems.append(f"day {post['day']} missing caption")
            continue
        first = caption_path.read_text(encoding="utf-8").splitlines()[0]
        if not first:
            problems.append(f"day {post['day']} empty caption")
        if post["kind"] == "reel":
            path = root / post["file"]
            problems.extend(_check_reel(path, post["day"]))
            reels += 1
        else:
            for relative in post["files"]:
                path = root / relative
                problems.extend(_check_jpeg(path))
                images += 1
    # A full queue is 10 reels and 4 carousels. A --limit run is only the days it wrote.
    if len(data["posts"]) == 14:
        if reels != 10:
            problems.append(f"expected 10 reels, found {reels}")
        if images < 28:
            problems.append(f"expected at least 28 carousel images, found {images}")
    elif reels + sum(1 for post in data["posts"] if post["kind"] != "reel") != len(data["posts"]):
        problems.append(f"schedule lists {len(data['posts'])} posts")
    return problems


def _check_reel(path: Path, day: int) -> list[str]:
    problems = []
    if not path.exists() or path.stat().st_size < 10_000:
        return [f"day {day} reel missing or empty"]
    probe = _probe(path)
    streams = probe.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video is None or video.get("codec_name") != "h264":
        problems.append(f"day {day} is not an h264 video")
    if video and (video.get("width") != 1080 or video.get("height") != 1920):
        problems.append(f"day {day} is not 1080x1920")
    if audio is None:
        problems.append(f"day {day} has no audio track")
    duration = float((probe.get("format") or {}).get("duration") or 0)
    if duration < 12:
        problems.append(f"day {day} is only {duration:.1f}s")
    frame = path.with_name("preview.png")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "0.4",
            "-i",
            str(path),
            "-frames:v",
            "1",
            str(frame),
        ],
        check=True,
    )
    if _bright_pixels(frame) < 800:
        problems.append(f"day {day} frame looks blank")
    if _bright_pixels(frame, bottom=True) > 40:
        problems.append(f"day {day} text sits in the bottom UI band")
    return problems


def _check_jpeg(path: Path) -> list[str]:
    if not path.exists() or path.stat().st_size < 1000:
        return [f"{path.name} missing or empty"]
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        if image.size != (1080, 1350) or image.format != "JPEG":
            return [f"{path.name} is {image.size} {image.format}"]
        if _bright_pixels(path) < 400:
            return [f"{path.name} looks blank"]
    return []


def _bright_pixels(path: Path, bottom: bool = False) -> int:
    image = Image.open(path).convert("L")
    if bottom:
        width, height = image.size
        image = image.crop((0, int(height * 0.78), width, height))
    histogram = image.histogram()
    return sum(histogram[160:])


def _probe(path: Path) -> dict:
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height:format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    return json.loads(raw)


def _print_summary(folder: Path, manifest: dict) -> None:
    voice = manifest["voice"]
    print("")
    print(f"Generated {len(manifest['posts'])} posts in {folder}")
    print(f"Voice: {voice['engine']} {voice['name']}")
    print("Monthly generation cost: HK$0")
    if voice["fallback"]:
        print("The reels have a silent audio track labeled SILENT FALLBACK. Do not post them yet.")
    else:
        print("Listen to voice-check/ before you post. This program does not judge tones.")
    print("")
    for post in manifest["posts"]:
        target = post.get("file") or post["files"][0]
        print(f"Day {post['day']:2}  {post['post_at']}  {post['kind']:8}  {target}")
    print("")
    print("Dry-run publish (sends nothing): python -m ig_pipeline publish")
