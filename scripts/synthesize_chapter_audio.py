#!/usr/bin/env python3
"""Google Cloud TTS로 절 번호 없는 장별 MP3를 만들고 Cloud Storage에 올린다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service.audio_catalog import VOICE_SPECS
from service.audio_pipeline import (
    Chapter,
    load_chapters,
    output_object,
    references_match,
    select_partition,
    spoken_chunks,
    work_items,
)


DEFAULT_BIBLE = ROOT / "site" / "bible.json"
TRANSIENT_TTS_STATUS = re.compile(r"(?:^|\D)(429|500|502|503|504)(?:\D|$)")


def parse_references(value: str | None) -> set[tuple[str, int]]:
    if not value:
        return set()
    output: set[tuple[str, int]] = set()
    for item in value.split(","):
        code, chapter = item.strip().upper().split(":", 1)
        output.add((code, int(chapter)))
    return output


def voice_spec(voice_id: str) -> dict[str, str]:
    return next(dict(item) for item in VOICE_SPECS if item["id"] == voice_id)


def is_transient_tts_error(error: Exception) -> bool:
    """Google TTS의 일시적 서버·할당량 오류만 재시도한다."""
    message = str(error)
    return bool(TRANSIENT_TTS_STATUS.search(message)) or any(
        marker in message.lower()
        for marker in ("deadline exceeded", "temporarily unavailable", "connection reset")
    )


def merge_mp3(parts: list[bytes], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        output.write_bytes(parts[0])
        return
    ffmpeg = shutil.which(os.getenv("FFMPEG_BIN", "ffmpeg"))
    if not ffmpeg:
        raise RuntimeError("여러 TTS 조각을 합칠 ffmpeg를 찾을 수 없습니다.")
    with tempfile.TemporaryDirectory(prefix="bibleframe-audio-") as directory:
        temp = Path(directory)
        files: list[Path] = []
        for index, content in enumerate(parts):
            path = temp / f"part-{index:03d}.mp3"
            path.write_bytes(content)
            files.append(path)
        concat = temp / "concat.txt"
        concat.write_text("\n".join(f"file '{path}'" for path in files) + "\n", encoding="utf-8")
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(concat), "-c", "copy", "-y", str(output),
        ], check=True)


class AudioPublisher:
    def __init__(self, bucket_name: str | None, local_dir: Path | None, speaking_rate: float) -> None:
        from google.cloud import storage, texttospeech

        location = os.getenv("TTS_LOCATION", "asia-northeast1")
        options = {"api_endpoint": f"{location}-texttospeech.googleapis.com"} if location != "global" else {}
        self.texttospeech = texttospeech
        self.tts = texttospeech.TextToSpeechClient(client_options=options or None)
        self.local_dir = local_dir
        self.bucket = storage.Client().bucket(bucket_name) if bucket_name and not local_dir else None
        self.speaking_rate = speaking_rate
        self.max_attempts = max(1, int(os.getenv("TTS_MAX_ATTEMPTS", "5")))
        self.retry_base_seconds = max(0.0, float(os.getenv("TTS_RETRY_BASE_SECONDS", "1")))

    def exists(self, object_name: str) -> bool:
        if self.local_dir:
            return (self.local_dir / object_name).exists()
        return bool(self.bucket and self.bucket.blob(object_name).exists())

    def synthesize(self, voice_id: str, chapter: Chapter) -> tuple[Path, str, int]:
        spec = voice_spec(voice_id)
        parts = []
        chunks = spoken_chunks(chapter)
        for text in chunks:
            response = self._synthesize_chunk(text, spec)
            parts.append(bytes(response.audio_content))
        directory = Path(tempfile.mkdtemp(prefix="bibleframe-chapter-"))
        output = directory / "chapter.mp3"
        merge_mp3(parts, output)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        return output, digest, len(chunks)

    def _synthesize_chunk(self, text: str, spec: dict[str, str]):
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self.tts.synthesize_speech(
                    input=self.texttospeech.SynthesisInput(text=text),
                    voice=self.texttospeech.VoiceSelectionParams(
                        language_code="ko-KR", name=spec["gcp_name"],
                    ),
                    audio_config=self.texttospeech.AudioConfig(
                        audio_encoding=self.texttospeech.AudioEncoding.MP3,
                        speaking_rate=self.speaking_rate,
                    ),
                )
            except Exception as error:
                if attempt >= self.max_attempts or not is_transient_tts_error(error):
                    raise
                delay = self.retry_base_seconds * min(2 ** (attempt - 1), 16)
                print(json.dumps({
                    "status": "retrying", "attempt": attempt + 1,
                    "delay_seconds": delay, "error": str(error),
                }, ensure_ascii=False), flush=True)
                time.sleep(delay)
        raise RuntimeError("도달할 수 없는 TTS 재시도 상태")

    def publish(self, voice_id: str, chapter: Chapter, output: Path, digest: str) -> None:
        object_name = output_object(voice_id, chapter)
        if self.local_dir:
            target = self.local_dir / object_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output, target)
            return
        if not self.bucket:
            raise RuntimeError("AUDIO_BUCKET이 필요합니다.")
        blob = self.bucket.blob(object_name)
        blob.cache_control = "public,max-age=31536000,immutable"
        blob.content_type = "audio/mpeg"
        blob.metadata = {
            "book": chapter.book,
            "book_code": chapter.code,
            "chapter": str(chapter.chapter),
            "voice": voice_id,
            "sha256": digest,
            "verse_numbers_spoken": "false",
        }
        blob.upload_from_filename(output, content_type="audio/mpeg", checksum="crc32c")
        blob.patch()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bible", type=Path, default=DEFAULT_BIBLE)
    parser.add_argument("--bucket", default=os.getenv("AUDIO_BUCKET"))
    parser.add_argument("--local-dir", type=Path)
    parser.add_argument("--voices", default="kore,charon")
    parser.add_argument("--references", help="예: GEN:1,JHN:3")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--speaking-rate", type=float, default=0.9)
    args = parser.parse_args()

    chapters = load_chapters(args.bible)
    references = parse_references(args.references)
    chapters = [chapter for chapter in chapters if references_match(chapter, references)]
    items = work_items(chapters, [item.strip() for item in args.voices.split(",") if item.strip()])
    task_index = int(os.getenv("CLOUD_RUN_TASK_INDEX", "0"))
    task_count = int(os.getenv("CLOUD_RUN_TASK_COUNT", "1"))
    items = select_partition(items, task_index, task_count)
    if args.limit is not None:
        items = items[:args.limit]

    if args.dry_run:
        print(json.dumps({
            "task_index": task_index, "task_count": task_count, "items": len(items),
            "chapters": [{"voice": voice, "book": chapter.code, "chapter": chapter.chapter} for voice, chapter in items],
        }, ensure_ascii=False))
        return

    publisher = AudioPublisher(args.bucket, args.local_dir, args.speaking_rate)
    failures: list[dict[str, object]] = []
    for voice_id, chapter in items:
        object_name = output_object(voice_id, chapter)
        if not args.force and publisher.exists(object_name):
            print(json.dumps({"status": "skipped", "object": object_name}, ensure_ascii=False), flush=True)
            continue
        output: Path | None = None
        try:
            output, digest, chunk_count = publisher.synthesize(voice_id, chapter)
            publisher.publish(voice_id, chapter, output, digest)
            print(json.dumps({
                "status": "created", "object": object_name, "sha256": digest,
                "bytes": output.stat().st_size, "chunks": chunk_count,
            }, ensure_ascii=False), flush=True)
        except Exception as error:
            failure = {"object": object_name, "error": str(error)}
            failures.append(failure)
            print(json.dumps({"status": "failed", **failure}, ensure_ascii=False), flush=True)
        finally:
            if output:
                shutil.rmtree(output.parent, ignore_errors=True)
    if failures:
        raise SystemExit(f"오디오 생성 실패 {len(failures)}개")


if __name__ == "__main__":
    main()
