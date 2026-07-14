#!/usr/bin/env python3
"""네트워크 없이 Haystack 하이브리드 파이프라인과 인용을 검사한다."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service.rag_service import HybridRagService, load_reference_catalog, parse_reference


class FakeEmbedder:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0] if "사랑" in text else [0.0, 1.0, 0.0]


class FakeGenerator:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        assert "[1]" in user_prompt
        return "사랑의 근거 본문을 찾았습니다. [1]"


def main() -> None:
    docs = [
        {"id": "love", "content": "하느님께서는 세상을 사랑하셨다.", "meta": {
            "book": "요한 복음서", "book_code": "JHN", "chapter": 3,
            "verse_start": 16, "verse_end": 16,
        }},
        {"id": "fear", "content": "두려워하지 마라.", "meta": {
            "book": "이사야서", "book_code": "ISA", "chapter": 41,
            "verse_start": 10, "verse_end": 10,
        }},
    ]
    embeddings = [
        {"id": "love", "embedding": [1.0, 0.0, 0.0]},
        {"id": "fear", "embedding": [0.0, 1.0, 0.0]},
    ]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        docs_path = root / "documents.jsonl"
        embeddings_path = root / "embeddings.jsonl"
        docs_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in docs), encoding="utf-8")
        embeddings_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in embeddings), encoding="utf-8",
        )
        service = HybridRagService(
            docs_path, embeddings_path, embedder=FakeEmbedder(), generator=FakeGenerator(),
        )
        result = service.answer("사랑에 관한 말씀", 2)
        direct_result = service.answer("요 3:16", 2)
    assert service.embeddings_ready is True
    assert result["mode"] == "hybrid"
    assert result["sources"][0]["id"] == "love"
    assert result["sources"][0]["reader_url"].endswith("book=JHN&chapter=3&verse=16")
    assert "[1]" in result["answer"]
    aliases, _ = load_reference_catalog(ROOT / "site" / "bible.json")
    assert parse_reference("요 3:16", aliases) == ("JHN", 3, 16)
    assert parse_reference("요한복음 3장 16절", aliases) == ("JHN", 3, 16)
    assert direct_result["sources"][0]["id"] == "love"
    assert direct_result["sources"][0]["reference"] == "요한 복음서 3장 16절"
    assert direct_result["sources"][0]["content"] == "하느님께서는 세상을 사랑하셨다."
    assert direct_result["sources"][0]["reader_url"].endswith("book=JHN&chapter=3&verse=16")
    print("OK: Haystack BM25 + 의미 검색 + Qwen 인용 응답 경로 검증 완료")


if __name__ == "__main__":
    main()
