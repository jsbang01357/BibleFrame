#!/usr/bin/env python3
"""BibleFrame 생성 데이터의 최소 무결성을 검사한다."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    payload = json.loads((ROOT / "site" / "bible.json").read_text(encoding="utf-8"))
    assert payload["meta"]["license"] == "Public Domain"
    assert len(payload["books"]) == 66
    assert len(payload["verses"]) == 30_991
    assert payload["meta"]["chapters"] == 1_188
    assert len({item["id"] for item in payload["verses"]}) == 30_991

    john = next(item for item in payload["verses"] if item["id"] == "JOH-3-16")
    assert john["book"] == "요한복음"
    assert "독생자" in john["text"] and "영생" in john["text"]

    rag_lines = (ROOT / "rag" / "chapters.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rag_lines) == 1_188
    first = json.loads(rag_lines[0])
    assert first["metadata"]["book"] == "창세기"
    assert first["metadata"]["chapter"] == 1

    archive_path = ROOT / "site" / "downloads" / "bibleframe-rag.zip"
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {"chapters.jsonl", "README_RAG.md"}
        assert archive.testzip() is None

    peter = [item for item in payload["verses"] if item["code"] == "1PE"]
    assert max(item["chapter"] for item in peter) == 4
    assert max(item["verse"] for item in peter if item["chapter"] == 4) == 14

    print("OK: 66권 · 1,188장 · 30,991절 · 상류 누락 기록 · RAG ZIP 검증 완료")


if __name__ == "__main__":
    main()
