#!/usr/bin/env python3
"""Korean Bible 1910 VPL을 정적 검색 데이터와 장 단위 RAG로 변환한다."""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "vendor" / "kor1910" / "kor_vpl.txt"

BOOKS = [
    ("GEN", "창세기", "창", "Genesis"), ("EXO", "출애굽기", "출", "Exodus"),
    ("LEV", "레위기", "레", "Leviticus"), ("NUM", "민수기", "민", "Numbers"),
    ("DEU", "신명기", "신", "Deuteronomy"), ("JOS", "여호수아", "수", "Joshua"),
    ("JDG", "사사기", "삿", "Judges"), ("RUT", "룻기", "룻", "Ruth"),
    ("1SA", "사무엘상", "삼상", "1 Samuel"), ("2SA", "사무엘하", "삼하", "2 Samuel"),
    ("1KI", "열왕기상", "왕상", "1 Kings"), ("2KI", "열왕기하", "왕하", "2 Kings"),
    ("1CH", "역대상", "대상", "1 Chronicles"), ("2CH", "역대하", "대하", "2 Chronicles"),
    ("EZR", "에스라", "스", "Ezra"), ("NEH", "느헤미야", "느", "Nehemiah"),
    ("EST", "에스더", "에", "Esther"), ("JOB", "욥기", "욥", "Job"),
    ("PSA", "시편", "시", "Psalms"), ("PRO", "잠언", "잠", "Proverbs"),
    ("ECC", "전도서", "전", "Ecclesiastes"), ("SOL", "아가", "아", "Song of Songs"),
    ("ISA", "이사야", "사", "Isaiah"), ("JER", "예레미야", "렘", "Jeremiah"),
    ("LAM", "예레미야애가", "애", "Lamentations"), ("EZE", "에스겔", "겔", "Ezekiel"),
    ("DAN", "다니엘", "단", "Daniel"), ("HOS", "호세아", "호", "Hosea"),
    ("JOE", "요엘", "욜", "Joel"), ("AMO", "아모스", "암", "Amos"),
    ("OBA", "오바댜", "옵", "Obadiah"), ("JON", "요나", "욘", "Jonah"),
    ("MIC", "미가", "미", "Micah"), ("NAH", "나훔", "나", "Nahum"),
    ("HAB", "하박국", "합", "Habakkuk"), ("ZEP", "스바냐", "습", "Zephaniah"),
    ("HAG", "학개", "학", "Haggai"), ("ZEC", "스가랴", "슥", "Zechariah"),
    ("MAL", "말라기", "말", "Malachi"), ("MAT", "마태복음", "마", "Matthew"),
    ("MAR", "마가복음", "막", "Mark"), ("LUK", "누가복음", "눅", "Luke"),
    ("JOH", "요한복음", "요", "John"), ("ACT", "사도행전", "행", "Acts"),
    ("ROM", "로마서", "롬", "Romans"), ("1CO", "고린도전서", "고전", "1 Corinthians"),
    ("2CO", "고린도후서", "고후", "2 Corinthians"), ("GAL", "갈라디아서", "갈", "Galatians"),
    ("EPH", "에베소서", "엡", "Ephesians"), ("PHI", "빌립보서", "빌", "Philippians"),
    ("COL", "골로새서", "골", "Colossians"), ("1TH", "데살로니가전서", "살전", "1 Thessalonians"),
    ("2TH", "데살로니가후서", "살후", "2 Thessalonians"), ("1TI", "디모데전서", "딤전", "1 Timothy"),
    ("2TI", "디모데후서", "딤후", "2 Timothy"), ("TIT", "디도서", "딛", "Titus"),
    ("PHM", "빌레몬서", "몬", "Philemon"), ("HEB", "히브리서", "히", "Hebrews"),
    ("JAM", "야고보서", "약", "James"), ("1PE", "베드로전서", "벧전", "1 Peter"),
    ("2PE", "베드로후서", "벧후", "2 Peter"), ("1JO", "요한일서", "요일", "1 John"),
    ("2JO", "요한이서", "요이", "2 John"), ("3JO", "요한삼서", "요삼", "3 John"),
    ("JUD", "유다서", "유", "Jude"), ("REV", "요한계시록", "계", "Revelation"),
]

LINE_RE = re.compile(r"^(\S+)\s+(\d+):(\d+)\s+(.+)$")


def load_verses() -> list[dict[str, object]]:
    book_map = {code: (name, short, english, index) for index, (code, name, short, english) in enumerate(BOOKS)}
    verses: list[dict[str, object]] = []
    for line_number, raw in enumerate(SOURCE.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = LINE_RE.match(raw.strip())
        if not match:
            raise ValueError(f"VPL 형식 오류: {line_number}행")
        code, chapter, verse, text = match.groups()
        if code not in book_map:
            raise ValueError(f"알 수 없는 성경 코드: {code}")
        name, short, english, book_index = book_map[code]
        verses.append({
            "id": f"{code}-{int(chapter)}-{int(verse)}",
            "code": code,
            "book": name,
            "short": short,
            "english": english,
            "testament": "old" if book_index < 39 else "new",
            "chapter": int(chapter),
            "verse": int(verse),
            "text": text.strip(),
        })
    return verses


def build() -> dict[str, int]:
    verses = load_verses()
    site = ROOT / "site"
    rag = ROOT / "rag"
    downloads = site / "downloads"
    site.mkdir(parents=True, exist_ok=True)
    rag.mkdir(parents=True, exist_ok=True)
    downloads.mkdir(parents=True, exist_ok=True)

    chapters: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for item in verses:
        chapters[(str(item["code"]), int(item["chapter"]))].append(item)

    books_payload = [
        {"code": code, "name": name, "short": short, "english": english,
         "testament": "old" if index < 39 else "new"}
        for index, (code, name, short, english) in enumerate(BOOKS)
    ]
    payload = {
        "meta": {
            "title": "Korean Bible 1910",
            "source": "eBible.org",
            "source_url": "https://ebible.org/bible/details.php?id=kor",
            "license": "Public Domain",
            "books": len(books_payload),
            "chapters": len(chapters),
            "verses": len(verses),
        },
        "books": books_payload,
        "verses": verses,
    }
    (site / "bible.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    rag_path = rag / "chapters.jsonl"
    with rag_path.open("w", encoding="utf-8") as stream:
        for (code, chapter), items in chapters.items():
            first = items[0]
            record = {
                "id": f"kor1910-{code}-{chapter}",
                "text": "\n".join(f'{item["verse"]} {item["text"]}' for item in items),
                "metadata": {
                    "translation": "Korean Bible 1910",
                    "language": "ko",
                    "license": "Public Domain",
                    "source_url": "https://ebible.org/bible/details.php?id=kor",
                    "book_code": code,
                    "book": first["book"],
                    "testament": first["testament"],
                    "chapter": chapter,
                    "verse_start": items[0]["verse"],
                    "verse_end": items[-1]["verse"],
                },
            }
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    guide = """# BibleFrame RAG 사용 안내

`chapters.jsonl`은 Korean Bible 1910을 장 단위로 나눈 RAG 코퍼스입니다.

ChatGPT 프로젝트나 대화에 파일을 업로드하고 다음처럼 요청하세요.

- 질문과 관련된 성경 구절을 찾아 책·장·절을 함께 표시해줘.
- 답변의 근거가 되는 구절을 먼저 인용하고, 해석과 본문을 구분해줘.
- 이 파일에 없는 내용은 성경 본문인 것처럼 만들지 말아줘.

본문: Korean Bible 1910 · eBible.org · Public Domain
"""
    (downloads / "README_RAG.md").write_text(guide, encoding="utf-8")
    with zipfile.ZipFile(downloads / "bibleframe-rag.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in (
            ("chapters.jsonl", rag_path.read_bytes()),
            ("README_RAG.md", guide.encode("utf-8")),
        ):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)

    stats = {"books": len(books_payload), "chapters": len(chapters), "verses": len(verses)}
    print(json.dumps(stats, ensure_ascii=False))
    return stats


if __name__ == "__main__":
    build()
