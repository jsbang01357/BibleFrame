"""장별 음성 원고와 작업 분할을 만드는 순수 함수."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from service.audio_catalog import VOICE_SPECS, audio_object_name


@dataclass(frozen=True)
class Chapter:
    code: str
    book: str
    chapter: int
    verses: tuple[str, ...]


def load_chapters(path: Path) -> list[Chapter]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str, int], list[str]] = {}
    for verse in payload["verses"]:
        key = (str(verse["code"]), str(verse["book"]), int(verse["chapter"]))
        grouped.setdefault(key, []).append(str(verse["text"]).strip())
    return [Chapter(code, book, chapter, tuple(verses)) for (code, book, chapter), verses in grouped.items()]


def split_utf8(text: str, max_bytes: int) -> list[str]:
    if len(text.encode("utf-8")) <= max_bytes:
        return [text]
    sentences = [item.strip() for item in re.split(r"(?<=[.!?…])\s+", text) if item.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences or [text]:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate.encode("utf-8")) > max_bytes:
            chunks.append(current)
            current = ""
        if len(sentence.encode("utf-8")) <= max_bytes:
            current = f"{current} {sentence}".strip()
            continue
        piece = ""
        for character in sentence:
            if piece and len(f"{piece}{character}".encode("utf-8")) > max_bytes:
                chunks.append(piece)
                piece = ""
            piece += character
        current = piece
    if current:
        chunks.append(current)
    return chunks


def ensure_sentence_boundary(text: str) -> str:
    """Chirp가 줄바꿈을 한 문장으로 합치지 않도록 발화 단위 끝을 닫는다."""
    stripped = text.strip()
    if re.search(r'[.!?…。！？]["”’\)\]]*$', stripped):
        return stripped
    return f"{stripped}."


def spoken_chunks(chapter: Chapter, max_bytes: int = 4_500) -> list[str]:
    """절 번호 없이 장 제목과 본문만 TTS 요청 한도 아래로 묶는다."""
    rows = [f"{chapter.book} {chapter.chapter}장."]
    for verse in chapter.verses:
        rows.extend(ensure_sentence_boundary(piece) for piece in split_utf8(verse, max_bytes - 32))

    chunks: list[str] = []
    current: list[str] = []
    for row in rows:
        candidate = "\n".join([*current, row])
        if current and len(candidate.encode("utf-8")) > max_bytes:
            chunks.append("\n".join(current))
            current = []
        current.append(row)
    if current:
        chunks.append("\n".join(current))
    return chunks


def work_items(chapters: list[Chapter], voice_ids: list[str] | None = None) -> list[tuple[str, Chapter]]:
    selected = set(voice_ids or [str(voice["id"]) for voice in VOICE_SPECS])
    known = {str(voice["id"]) for voice in VOICE_SPECS}
    unknown = selected - known
    if unknown:
        raise ValueError(f"알 수 없는 음성: {', '.join(sorted(unknown))}")
    return [
        (str(voice["id"]), chapter)
        for voice in VOICE_SPECS if voice["id"] in selected
        for chapter in chapters
    ]


def select_partition(items: list[tuple[str, Chapter]], task_index: int, task_count: int) -> list[tuple[str, Chapter]]:
    if task_count < 1 or not 0 <= task_index < task_count:
        raise ValueError("Cloud Run 작업 인덱스가 올바르지 않습니다.")
    return [item for index, item in enumerate(items) if index % task_count == task_index]


def references_match(chapter: Chapter, references: set[tuple[str, int]]) -> bool:
    return not references or (chapter.code, chapter.chapter) in references


def output_object(voice_id: str, chapter: Chapter) -> str:
    return audio_object_name(voice_id, chapter.code, chapter.chapter)
