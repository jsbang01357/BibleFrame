#!/usr/bin/env python3
"""검증된 WEB-C 한국어 기계 번역을 정적 검색 데이터와 RAG ZIP으로 만든다."""

from __future__ import annotations

import json
import zipfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "translation" / "output" / "bibleframe-ko-reviewed-qwen3-next-v2b.jsonl"
EXPECTED_RECORDS = 35_408
EXPECTED_OMITTED = 29
TRANSLATION_TITLE = "BibleFrame 73권 공개 번역 초안"
NOTICE = "가톨릭 정경 기반 · 비공인 기계 번역 초안"
SOURCE_URL = "https://ebible.org/bible/details.php?id=eng-web-c"


def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"전체 번역 파일이 없음: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(records: list[dict[str, object]]) -> None:
    if len(records) != EXPECTED_RECORDS:
        raise ValueError(f"전체 번역 전에는 빌드할 수 없음: {len(records):,}/{EXPECTED_RECORDS:,}")
    ids = [str(item["id"]) for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError("번역 파일에 중복 절 ID가 있음")
    omitted = [item for item in records if item["status"] == "omitted_in_source"]
    if len(omitted) != EXPECTED_OMITTED:
        raise ValueError(f"원문 공절 수 불일치: {len(omitted)}/{EXPECTED_OMITTED}")
    if any(not str(item["text"]).strip() for item in records if item["status"] != "omitted_in_source"):
        raise ValueError("번역된 절 중 빈 본문이 있음")


def build() -> dict[str, int]:
    records = load_jsonl(SOURCE)
    validate(records)
    readable = [item for item in records if item["status"] != "omitted_in_source"]

    books: list[dict[str, object]] = []
    seen_books: set[str] = set()
    for item in records:
        code = str(item["code"])
        if code in seen_books:
            continue
        seen_books.add(code)
        books.append({
            "code": item["code"],
            "name": item["book"],
            "short": item["short"],
            "english": item["english"],
            "testament": item["testament"],
        })

    verses = [{
        "id": item["id"],
        "code": item["code"],
        "book": item["book"],
        "short": item["short"],
        "english": item["english"],
        "testament": item["testament"],
        "chapter": int(item["chapter"]),
        "verse": int(item["verse"]),
        "text": item["text"],
        "status": item["status"],
    } for item in readable]

    chapters: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for item in verses:
        chapters[(str(item["code"]), int(item["chapter"]))].append(item)

    site = ROOT / "site"
    rag = ROOT / "rag"
    downloads = site / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "title": TRANSLATION_TITLE,
            "notice": NOTICE,
            "source": "World English Bible (Catholic)",
            "source_url": SOURCE_URL,
            "source_license": "Public Domain",
            "translation_model": "Qwen3-Next-80B-A3B-Instruct",
            "review_model": "Qwen3-Next-80B-A3B-Instruct",
            "translation_status": "machine_reviewed_draft",
            "data_license": "CC0-1.0",
            "code_license": "MIT",
            "project_url": "https://github.com/jsbang01357/BibleFrame",
            "books": len(books),
            "chapters": len(chapters),
            "verses": len(verses),
            "omitted_source_records": EXPECTED_OMITTED,
        },
        "books": books,
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
                "id": f"bibleframe-ko-draft-{code}-{chapter}",
                "text": "\n".join(f'{item["verse"]} {item["text"]}' for item in items),
                "metadata": {
                    "translation": TRANSLATION_TITLE,
                    "notice": NOTICE,
                    "language": "ko",
                    "source": "World English Bible (Catholic)",
                    "source_license": "Public Domain",
                    "source_url": SOURCE_URL,
                    "translation_model": "Qwen3-Next-80B-A3B-Instruct",
                    "data_license": "CC0-1.0",
                    "book_code": code,
                    "book": first["book"],
                    "testament": first["testament"],
                    "chapter": chapter,
                    "verse_start": items[0]["verse"],
                    "verse_end": items[-1]["verse"],
                },
            }
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    guide = f"""# BibleFrame 가톨릭 정경 RAG 사용 안내

`chapters.jsonl`은 Public Domain 영어 원문을 한국어로 기계 번역한 73권 장 단위 코퍼스입니다.

- 표시명: {TRANSLATION_TITLE}
- 고지: {NOTICE}
- 원문: World English Bible (Catholic) · Public Domain
- 주의: 한국천주교주교회의 공용 번역본이 아니며 전례용·교리 판정용으로 사용하지 마세요.

질문과 관련된 구절을 찾을 때 책·장·절을 함께 표시하고, 본문과 해설을 구분하세요.
이 파일에 없는 내용을 성경 본문처럼 만들지 마세요.
"""
    (downloads / "README_RAG.md").write_text(guide, encoding="utf-8")
    with zipfile.ZipFile(downloads / "bibleframe-rag.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in (("chapters.jsonl", rag_path.read_bytes()), ("README_RAG.md", guide.encode("utf-8"))):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)

    stats = {"books": len(books), "chapters": len(chapters), "verses": len(verses)}
    print(json.dumps(stats, ensure_ascii=False))
    return stats


if __name__ == "__main__":
    build()
