#!/usr/bin/env python3
"""Cloud Storage 장별 MP3가 예상 목록과 정확히 일치하는지 검증한다."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from google.cloud import storage

from service.audio_pipeline import load_chapters, output_object, work_items


DEFAULT_BIBLE = ROOT / "site" / "bible.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--bible", type=Path, default=DEFAULT_BIBLE)
    args = parser.parse_args()

    chapters = load_chapters(args.bible)
    expected = {output_object(voice, chapter) for voice, chapter in work_items(chapters)}
    blobs = list(storage.Client().list_blobs(args.bucket, prefix="audio/v1/"))
    audio_blobs = [blob for blob in blobs if blob.name.endswith(".mp3")]
    actual = {blob.name for blob in audio_blobs}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    invalid = sorted(
        blob.name for blob in audio_blobs
        if not blob.size
        or blob.content_type != "audio/mpeg"
        or "immutable" not in (blob.cache_control or "")
        or (blob.metadata or {}).get("verse_numbers_spoken") != "false"
        or (blob.metadata or {}).get("voice") != blob.name.split("/")[2]
    )
    by_voice = Counter(name.split("/")[2] for name in actual)

    print(f"expected={len(expected)} actual={len(actual)}")
    print("voices=" + " ".join(f"{voice}:{by_voice[voice]}" for voice in sorted(by_voice)))
    print(f"missing={len(missing)} extra={len(extra)} invalid={len(invalid)}")
    for label, names in (("MISSING", missing), ("EXTRA", extra), ("INVALID", invalid)):
        for name in names[:20]:
            print(f"{label} {name}")

    if missing or extra or invalid or len(actual) != 2_656:
        raise SystemExit("오디오 객체 전수 검증 실패")
    print("OK: 1,328장 × 2개 음성 = 2,656개 MP3 전수 검증 완료")


if __name__ == "__main__":
    main()
