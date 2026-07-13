#!/usr/bin/env python3
"""BibleFrame 73권 기계 번역 배포 데이터의 무결성을 검사한다."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    payload = json.loads((ROOT / "site/bible.json").read_text(encoding="utf-8"))
    assert payload["meta"]["source_license"] == "Public Domain"
    assert payload["meta"]["translation_model"] == "Qwen3-Next-80B-A3B-Instruct"
    assert payload["meta"]["translation_status"] == "machine_reviewed_draft"
    assert payload["meta"]["data_license"] == "CC0-1.0"
    assert payload["meta"]["code_license"] == "MIT"
    assert payload["meta"]["notice"] == "가톨릭 정경 기반 · 비공인 기계 번역 초안"
    assert len(payload["books"]) == 73
    assert payload["meta"]["chapters"] == 1_328
    assert payload["meta"]["verses"] == 35_379
    assert payload["meta"]["omitted_source_records"] == 29
    assert len({item["id"] for item in payload["verses"]}) == 35_379
    assert payload["books"][0]["name"] == "창세기"

    by_id = {item["id"]: item for item in payload["verses"]}
    assert by_id["TOB-1-1"]["book"] == "토빗기"
    assert by_id["JOL-3-1"]["book"] == "요엘서"
    assert by_id["MAL-3-24"]["book"] == "말라키서"
    assert "하나님" not in by_id["JHN-3-16"]["text"]

    page = (ROOT / "site/index.html").read_text(encoding="utf-8")
    app = (ROOT / "site/app.js").read_text(encoding="utf-8")
    for marker in (
        'data-view="search"', 'data-view="reader"', 'data-view="downloads"',
        'data-view="faq"', 'id="fontIncrease"', 'id="ttsPlay"',
        'id="ttsVoice"', 'id="ttsTimer"', 'id="luckyButton"',
        'downloads/bibleframe-ko-catholic-73.pdf',
    ):
        assert marker in page
    assert "data-open-verse" in app
    assert 'url.searchParams.set("view", "reader")' in app
    assert "SpeechSynthesisUtterance" in app
    assert "scheduleSleepTimer" in app
    assert "pickRandomVerse" in app
    assert 'el.lucky.addEventListener("click", openLuckyVerse)' in app
    assert "SpeechSynthesisUtterance(`${heading}${item.verse}절." not in app

    rag_lines = (ROOT / "rag/chapters.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rag_lines) == 1_328
    assert json.loads(rag_lines[0])["metadata"]["book"] == "창세기"

    haystack_lines = (ROOT / "rag/haystack_documents.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(haystack_lines) == 1_328
    assert set(json.loads(haystack_lines[0])) == {"id", "content", "meta"}

    with zipfile.ZipFile(ROOT / "site/downloads/bibleframe-rag.zip") as archive:
        assert set(archive.namelist()) == {
            "chapters.jsonl", "haystack_documents.jsonl", "query_haystack.py",
            "requirements-haystack.txt", "README_RAG.md",
        }
        assert archive.testzip() is None
        assert {item.date_time for item in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}

    print("OK: 73권 기계 번역 검색 데이터 · 장 단위 RAG ZIP 검증 완료")


if __name__ == "__main__":
    main()
