#!/usr/bin/env python3
"""WEB-C USFM 73권을 번역용 절 단위 JSONL로 정규화한다."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USFM_DIR = ROOT / "vendor" / "web-c-usfm"
OUTPUT_DIR = ROOT / "translation" / "source"
OUTPUT_PATH = OUTPUT_DIR / "web-c.jsonl"
META_PATH = OUTPUT_DIR / "web-c.meta.json"
SOURCE_ARCHIVE_SHA256 = "b2807cd86cd2423214e5c51bc1b92217ceaf9420cfade84ff951766cd3e2aa4b"

BOOKS = [
    ("GEN", "창세기", "창", "Genesis"),
    ("EXO", "탈출기", "탈출", "Exodus"),
    ("LEV", "레위기", "레위", "Leviticus"),
    ("NUM", "민수기", "민수", "Numbers"),
    ("DEU", "신명기", "신명", "Deuteronomy"),
    ("JOS", "여호수아기", "여호", "Joshua"),
    ("JDG", "판관기", "판관", "Judges"),
    ("RUT", "룻기", "룻", "Ruth"),
    ("1SA", "사무엘기 상권", "1사무", "1 Samuel"),
    ("2SA", "사무엘기 하권", "2사무", "2 Samuel"),
    ("1KI", "열왕기 상권", "1열왕", "1 Kings"),
    ("2KI", "열왕기 하권", "2열왕", "2 Kings"),
    ("1CH", "역대기 상권", "1역대", "1 Chronicles"),
    ("2CH", "역대기 하권", "2역대", "2 Chronicles"),
    ("EZR", "에즈라기", "에즈", "Ezra"),
    ("NEH", "느헤미야기", "느헤", "Nehemiah"),
    ("TOB", "토빗기", "토빗", "Tobit"),
    ("JDT", "유딧기", "유딧", "Judith"),
    ("ESG", "에스테르기", "에스", "Esther (Greek)"),
    ("1MA", "마카베오기 상권", "1마카", "1 Maccabees"),
    ("2MA", "마카베오기 하권", "2마카", "2 Maccabees"),
    ("JOB", "욥기", "욥", "Job"),
    ("PSA", "시편", "시편", "Psalms"),
    ("PRO", "잠언", "잠언", "Proverbs"),
    ("ECC", "코헬렛", "코헬", "Ecclesiastes"),
    ("SNG", "아가", "아가", "Song of Songs"),
    ("WIS", "지혜서", "지혜", "Wisdom"),
    ("SIR", "집회서", "집회", "Sirach"),
    ("ISA", "이사야서", "이사", "Isaiah"),
    ("JER", "예레미야서", "예레", "Jeremiah"),
    ("LAM", "애가", "애가", "Lamentations"),
    ("BAR", "바룩서", "바룩", "Baruch"),
    ("EZK", "에제키엘서", "에제", "Ezekiel"),
    ("DAG", "다니엘서", "다니", "Daniel (Greek)"),
    ("HOS", "호세아서", "호세", "Hosea"),
    ("JOL", "요엘서", "요엘", "Joel"),
    ("AMO", "아모스서", "아모", "Amos"),
    ("OBA", "오바드야서", "오바", "Obadiah"),
    ("JON", "요나서", "요나", "Jonah"),
    ("MIC", "미카서", "미카", "Micah"),
    ("NAM", "나훔서", "나훔", "Nahum"),
    ("HAB", "하바쿡서", "하바", "Habakkuk"),
    ("ZEP", "스바니야서", "스바", "Zephaniah"),
    ("HAG", "하까이서", "하까", "Haggai"),
    ("ZEC", "즈카르야서", "즈카", "Zechariah"),
    ("MAL", "말라키서", "말라", "Malachi"),
    ("MAT", "마태오 복음서", "마태", "Matthew"),
    ("MRK", "마르코 복음서", "마르", "Mark"),
    ("LUK", "루카 복음서", "루카", "Luke"),
    ("JHN", "요한 복음서", "요한", "John"),
    ("ACT", "사도행전", "사도", "Acts"),
    ("ROM", "로마 신자들에게 보낸 서간", "로마", "Romans"),
    ("1CO", "코린토 신자들에게 보낸 첫째 서간", "1코린", "1 Corinthians"),
    ("2CO", "코린토 신자들에게 보낸 둘째 서간", "2코린", "2 Corinthians"),
    ("GAL", "갈라티아 신자들에게 보낸 서간", "갈라", "Galatians"),
    ("EPH", "에페소 신자들에게 보낸 서간", "에페", "Ephesians"),
    ("PHP", "필리피 신자들에게 보낸 서간", "필리", "Philippians"),
    ("COL", "콜로새 신자들에게 보낸 서간", "콜로", "Colossians"),
    ("1TH", "테살로니카 신자들에게 보낸 첫째 서간", "1테살", "1 Thessalonians"),
    ("2TH", "테살로니카 신자들에게 보낸 둘째 서간", "2테살", "2 Thessalonians"),
    ("1TI", "티모테오에게 보낸 첫째 서간", "1티모", "1 Timothy"),
    ("2TI", "티모테오에게 보낸 둘째 서간", "2티모", "2 Timothy"),
    ("TIT", "티토에게 보낸 서간", "티토", "Titus"),
    ("PHM", "필레몬에게 보낸 서간", "필레", "Philemon"),
    ("HEB", "히브리인들에게 보낸 서간", "히브", "Hebrews"),
    ("JAS", "야고보 서간", "야고", "James"),
    ("1PE", "베드로의 첫째 서간", "1베드", "1 Peter"),
    ("2PE", "베드로의 둘째 서간", "2베드", "2 Peter"),
    ("1JN", "요한의 첫째 서간", "1요한", "1 John"),
    ("2JN", "요한의 둘째 서간", "2요한", "2 John"),
    ("3JN", "요한의 셋째 서간", "3요한", "3 John"),
    ("JUD", "유다 서간", "유다", "Jude"),
    ("REV", "요한 묵시록", "묵시", "Revelation"),
]

VERSE_RE = re.compile(r"^\\v\s+(\d+(?:-\d+)?)\s*(.*)$")
CHAPTER_RE = re.compile(r"^\\c\s+(\d+)")
WORD_RE = re.compile(r"\\\+?w\s+([^|\\]+?)(?:\|[^\\]*?)?\\\+?w\*")
CONTENT_MARKER_RE = re.compile(r"^\\(?:p|m|q\d*|pi\d*|li\d*|nb|pc|b)\s*")
HEADING_MARKER_RE = re.compile(r"^\\(?:id|ide|h|toc\d*|mt\d*|ip|is\d*|ms\d*|s\d*|d|sp|cl)\b")
INLINE_MARKER_RE = re.compile(r"\\\+?[A-Za-z0-9]+\*?")


def strip_notes(raw: str) -> str:
    raw = re.sub(r"\\f\b.*?\\f\*", "", raw, flags=re.DOTALL)
    return re.sub(r"\\x\b.*?\\x\*", "", raw, flags=re.DOTALL)


def clean_inline(raw: str) -> str:
    previous = None
    while previous != raw:
        previous = raw
        raw = WORD_RE.sub(r"\1", raw)
    raw = INLINE_MARKER_RE.sub("", raw)
    raw = re.sub(r'\|[a-zA-Z0-9_-]+="[^"]*"', "", raw)
    return re.sub(r"\s+", " ", raw).strip()


def source_file(code: str) -> Path:
    matches = sorted(USFM_DIR.glob(f"*-{code}eng-web-c.usfm"))
    if len(matches) != 1:
        raise ValueError(f"{code} USFM 파일이 하나가 아님: {matches}")
    return matches[0]


def apply_catholic_versification(record: dict[str, object]) -> dict[str, object]:
    """WEB-C의 개신교식 요엘·말라키 장 구분을 가톨릭식으로 맞춘다."""
    code = str(record["code"])
    source_chapter = int(record["chapter"])
    source_verse = str(record["verse"])
    chapter = source_chapter
    verse = source_verse

    if code == "JOL":
        verse_number = int(source_verse)
        if source_chapter == 2 and verse_number >= 28:
            chapter = 3
            verse = str(verse_number - 27)
        elif source_chapter == 3:
            chapter = 4
    elif code == "MAL" and source_chapter == 4:
        chapter = 3
        verse = str(int(source_verse) + 18)

    if chapter == source_chapter and verse == source_verse:
        return record

    converted = {
        **record,
        "id": f"{code}-{chapter}-{verse}",
        "chapter": chapter,
        "verse": verse,
        "verse_start": int(verse),
        "verse_end": int(verse),
        "source_chapter": source_chapter,
        "source_verse": source_verse,
    }
    return converted


def parse_book(code: str, name: str, short: str, english: str, index: int) -> list[dict[str, object]]:
    raw = strip_notes(source_file(code).read_text(encoding="utf-8-sig"))
    chapter: int | None = None
    current_label: str | None = None
    fragments: list[str] = []
    records: list[dict[str, object]] = []

    def flush() -> None:
        nonlocal current_label, fragments
        if current_label is None or chapter is None:
            return
        start, _, end = current_label.partition("-")
        verse_start = int(start)
        verse_end = int(end or start)
        text = clean_inline(" ".join(fragments))
        records.append(apply_catholic_versification({
            "id": f"{code}-{chapter}-{current_label}",
            "code": code,
            "book": name,
            "short": short,
            "english": english,
            "testament": "old" if index < 46 else "new",
            "chapter": chapter,
            "verse": current_label,
            "verse_start": verse_start,
            "verse_end": verse_end,
            "text": text,
            "omitted_in_source": not bool(text),
        }))
        current_label = None
        fragments = []

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        chapter_match = CHAPTER_RE.match(line)
        if chapter_match:
            flush()
            chapter = int(chapter_match.group(1))
            continue
        verse_match = VERSE_RE.match(line)
        if verse_match:
            flush()
            if chapter is None:
                raise ValueError(f"{code}: 장 번호 전 절 발견")
            current_label = verse_match.group(1)
            fragments = [verse_match.group(2)]
            continue
        if current_label is None or HEADING_MARKER_RE.match(line):
            continue
        continuation = CONTENT_MARKER_RE.sub("", line)
        if continuation and not continuation.startswith("\\"):
            fragments.append(continuation)

    flush()
    return records


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build() -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_records: list[dict[str, object]] = []
    file_hashes: dict[str, str] = {}
    for index, (code, name, short, english) in enumerate(BOOKS):
        path = source_file(code)
        file_hashes[path.name] = sha256(path)
        all_records.extend(parse_book(code, name, short, english, index))

    with OUTPUT_PATH.open("w", encoding="utf-8") as stream:
        for record in all_records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    chapters = {(str(item["code"]), int(item["chapter"])) for item in all_records}
    by_book = Counter(str(item["code"]) for item in all_records)
    meta: dict[str, object] = {
        "id": "bibleframe-catholic-draft-source-v1",
        "title": "World English Bible (Catholic)",
        "language": "en",
        "source": "eBible.org",
        "source_url": "https://ebible.org/bible/details.php?id=eng-web-c",
        "download_url": "https://ebible.org/Scriptures/eng-web-c_usfm.zip",
        "download_sha256": SOURCE_ARCHIVE_SHA256,
        "license": "Public Domain",
        "source_release": "2020 stable text edition; upstream updated 2026-05-22",
        "books": len(BOOKS),
        "chapters": len(chapters),
        "verse_records": len(all_records),
        "omitted_records": sum(bool(item["omitted_in_source"]) for item in all_records),
        "book_verse_records": dict(by_book),
        "usfm_sha256": file_hashes,
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: meta[key] for key in ("books", "chapters", "verse_records", "omitted_records")}, ensure_ascii=False))
    return meta


if __name__ == "__main__":
    build()
