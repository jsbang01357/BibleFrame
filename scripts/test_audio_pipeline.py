#!/usr/bin/env python3
"""장별 음성 원고가 절 번호 없이 완전하게 분할되는지 검사한다."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service.audio_pipeline import ensure_sentence_boundary, load_chapters, select_partition, spoken_chunks, work_items
from scripts.synthesize_chapter_audio import is_transient_tts_error


def main() -> None:
    chapters = load_chapters(ROOT / "site" / "bible.json")
    assert len(chapters) == 1_328
    assert chapters[0].book == "창세기"
    assert chapters[-1].book == "요한 묵시록"
    for chapter in chapters:
        chunks = spoken_chunks(chapter)
        assert chunks
        assert max(len(chunk.encode("utf-8")) for chunk in chunks) <= 4_500
        spoken = "\n".join(chunks)
        assert spoken.startswith(f"{chapter.book} {chapter.chapter}장.")
        assert not re.search(r"(?:^|\s)\d+절(?:\s|[.,])", spoken)
        assert all(verse in spoken for verse in chapter.verses)
        assert all(re.search(r'[.!?…。！？]["”’\)\]]*$', line) for line in spoken.splitlines())

    items = work_items(chapters)
    assert len(items) == 2_656
    partitions = [select_partition(items, index, 17) for index in range(17)]
    flattened = [item for partition in partitions for item in partition]
    assert len(flattened) == len(items)
    assert {(voice, chapter.code, chapter.chapter) for voice, chapter in flattened} == {
        (voice, chapter.code, chapter.chapter) for voice, chapter in items
    }
    assert is_transient_tts_error(RuntimeError("500 Internal error encountered."))
    assert is_transient_tts_error(RuntimeError("503 502:Bad Gateway"))
    assert is_transient_tts_error(RuntimeError("Deadline Exceeded"))
    assert not is_transient_tts_error(RuntimeError("400 Invalid voice name"))
    assert ensure_sentence_boundary("아멘") == "아멘."
    assert ensure_sentence_boundary('평화가 있기를!"') == '평화가 있기를!"'
    print("OK: 1,328장 · 2개 음성 원고 분할과 절 번호 제외 검증 완료")


if __name__ == "__main__":
    main()
