#!/usr/bin/env python3
"""Haystack 네이티브 JSONL을 외부 의존성 없이 검사한다."""

from __future__ import annotations

import json
from pathlib import Path

from query_haystack import normalize_query


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    lines = (ROOT / "rag" / "haystack_documents.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1_328
    documents = [json.loads(line) for line in lines]
    assert all(set(document) == {"id", "content", "meta"} for document in documents)
    assert len({document["id"] for document in documents}) == 1_328
    assert all(document["content"].strip() for document in documents)
    assert documents[0]["meta"]["book"] == "창세기"
    assert documents[0]["meta"]["chapter"] == 1
    assert documents[-1]["meta"]["book"] == "요한 묵시록"
    assert documents[-1]["meta"]["chapter"] == 22
    assert all(document["meta"]["data_license"] == "CC0-1.0" for document in documents)
    assert all(document["meta"]["translation_model"] == "Qwen3-Next-80B-A3B-Instruct" for document in documents)
    assert normalize_query("두려움에 관한 말씀") == "두려움"
    assert normalize_query("사랑에 대해 알려줘") == "사랑"
    print("OK: Haystack 네이티브 장 문서 1,328개 검증 완료")


if __name__ == "__main__":
    main()
