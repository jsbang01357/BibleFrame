"""Cloud Storage 장별 MP3 카탈로그."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIBLE_PATH = ROOT / "site" / "bible.json"
AUDIO_VERSION = "v1"
VOICE_SPECS = (
    {"id": "kore", "name": "차분한 여성 · Kore", "gcp_name": "ko-KR-Chirp3-HD-Kore", "gender": "female"},
    {"id": "charon", "name": "차분한 남성 · Charon", "gcp_name": "ko-KR-Chirp3-HD-Charon", "gender": "male"},
)


def audio_base_url() -> str:
    configured = os.getenv("AUDIO_BASE_URL", "").rstrip("/")
    if configured:
        return configured
    bucket = os.getenv("AUDIO_BUCKET", "bibleframe-audio-jisong-cloud-492111")
    return f"https://storage.googleapis.com/{bucket}"


def audio_object_name(voice_id: str, book_code: str, chapter: int) -> str:
    return f"audio/{AUDIO_VERSION}/{voice_id}/{book_code}/{int(chapter):03d}.mp3"


def audio_url(voice_id: str, book_code: str, chapter: int) -> str:
    return f"{audio_base_url()}/{audio_object_name(voice_id, book_code, chapter)}"


def manifest() -> dict[str, object]:
    payload = json.loads(BIBLE_PATH.read_text(encoding="utf-8"))
    chapter_counts: dict[str, int] = {}
    for verse in payload["verses"]:
        code = str(verse["code"])
        chapter_counts[code] = max(chapter_counts.get(code, 0), int(verse["chapter"]))
    return {
        "version": AUDIO_VERSION,
        "provider": "Google Cloud Text-to-Speech · Chirp 3 HD",
        "speaking_rate": 0.9,
        "verse_numbers_spoken": False,
        "base_url": audio_base_url(),
        "path_template": f"audio/{AUDIO_VERSION}/{{voice}}/{{book}}/{{chapter_padded}}.mp3",
        "voices": list(VOICE_SPECS),
        "chapter_counts": chapter_counts,
        "chapters": sum(chapter_counts.values()),
    }
