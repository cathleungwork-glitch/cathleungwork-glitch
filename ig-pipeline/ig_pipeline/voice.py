"""Spoken Cantonese. Default is edge-tts zh-HK-HiuMaanNeural, which needs no key.

The playbook's official Azure voice is the same name. Pass --voice azure and set
AZURE_SPEECH_KEY plus AZURE_SPEECH_REGION to use that endpoint. If neither path
returns audio, the caller renders a labeled silent track.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import urllib.error
import urllib.request
import xml.sax.saxutils
from dataclasses import dataclass
from pathlib import Path

VOICE_NAME = "zh-HK-HiuMaanNeural"


@dataclass
class VoiceResult:
    engine: str
    voice: str
    fallback: bool
    detail: str


def synthesize_all(items: list[tuple[Path, str]], engine: str) -> VoiceResult:
    pending = [(path, text) for path, text in items if _stale(path, text, engine)]
    if engine == "silent":
        _delete_audio(items)
        return VoiceResult("silent-fallback", VOICE_NAME, True, "voice flag set to silent")
    if not pending:
        return VoiceResult(_engine_label(engine), VOICE_NAME, False, "reused existing audio")

    if engine == "azure":
        try:
            _azure_all(pending)
            return VoiceResult("azure", VOICE_NAME, False, "")
        except Exception as exc:  # noqa: BLE001 — fall through to the free voice
            print(f"Azure Speech failed ({_public_error(exc)}). Trying edge-tts.")

    try:
        asyncio.run(_edge_all(pending))
        return VoiceResult("edge-tts", VOICE_NAME, False, "")
    except Exception as exc:  # noqa: BLE001 — silent track is the documented fallback
        _delete_audio(items)
        return VoiceResult("silent-fallback", VOICE_NAME, True, _public_error(exc))


def _engine_label(engine: str) -> str:
    if engine == "azure":
        return "azure"
    if engine == "silent":
        return "silent-fallback"
    return "edge-tts"


def _digest(engine: str, text: str) -> str:
    return hashlib.sha256(f"{engine}\n{text}".encode("utf-8")).hexdigest()


def _stale(path: Path, text: str, engine: str) -> bool:
    side = path.with_suffix(".sha")
    if engine == "silent":
        return True
    label = _engine_label(engine)
    if not path.exists() or path.stat().st_size < 1000 or not side.exists():
        return True
    return side.read_text(encoding="utf-8").strip() != _digest(label, text)


def _mark(path: Path, text: str, engine_label: str) -> None:
    path.with_suffix(".sha").write_text(_digest(engine_label, text) + "\n", encoding="utf-8")


def _delete_audio(items: list[tuple[Path, str]]) -> None:
    for path, _text in items:
        for candidate in (path, path.with_suffix(".sha")):
            if candidate.exists():
                candidate.unlink()


def _public_error(exc: Exception) -> str:
    text = str(exc)
    for name in ("AZURE_SPEECH_KEY", "IG_ACCESS_TOKEN"):
        secret = os.environ.get(name, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:300]


async def _edge_all(items: list[tuple[Path, str]]) -> None:
    import edge_tts

    last_error: Exception | None = None
    for path, text in items:
        path.parent.mkdir(parents=True, exist_ok=True)
        saved = False
        for attempt in range(4):
            try:
                if path.exists():
                    path.unlink()
                communicate = edge_tts.Communicate(
                    text,
                    VOICE_NAME,
                    rate="+0%",
                    connect_timeout=20,
                    receive_timeout=90,
                )
                await communicate.save(str(path))
                if path.stat().st_size < 1000:
                    raise RuntimeError("audio file too small")
                _mark(path, text, "edge-tts")
                saved = True
                break
            except Exception as exc:  # noqa: BLE001 — the service sometimes returns no audio
                last_error = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        if not saved:
            raise RuntimeError(f"edge-tts failed for {text[:24]!r}: {last_error}")
        await asyncio.sleep(0.4)


def _azure_all(items: list[tuple[Path, str]]) -> None:
    key = os.environ.get("AZURE_SPEECH_KEY", "").strip()
    region = os.environ.get("AZURE_SPEECH_REGION", "").strip().lower()
    if not key or not region:
        raise RuntimeError(
            "Azure voice needs AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in the environment. "
            "Do not paste them into chat."
        )
    if not re.fullmatch(r"[a-z0-9]+", region):
        raise RuntimeError("AZURE_SPEECH_REGION must be a host label such as eastasia.")
    for path, text in items:
        path.parent.mkdir(parents=True, exist_ok=True)
        _azure_one(path, text, key, region)
        _mark(path, text, "azure")


def _azure_one(path: Path, text: str, key: str, region: str) -> None:
    escaped = xml.sax.saxutils.escape(text)
    ssml = (
        "<speak version='1.0' xml:lang='zh-HK'>"
        f"<voice name='{VOICE_NAME}'>{escaped}</voice>"
        "</speak>"
    )
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    request = urllib.request.Request(url, data=ssml.encode("utf-8"), method="POST")
    request.add_header("Ocp-Apim-Subscription-Key", key)
    request.add_header("Content-Type", "application/ssml+xml")
    request.add_header("X-Microsoft-OutputFormat", "audio-24khz-160kbitrate-mono-mp3")
    request.add_header("User-Agent", "ig-pipeline")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Azure HTTP {exc.code} {body}") from exc
    if path.stat().st_size < 1000:
        raise RuntimeError("Azure returned an empty audio file")
