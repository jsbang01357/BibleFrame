#!/usr/bin/env python3
"""내려받은 장 단위 문서를 Haystack BM25로 검색하는 선택형 로컬 예제."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[1]
BUNDLED_DOCUMENTS = SCRIPT.parent / "haystack_documents.jsonl"
DEFAULT_DOCUMENTS = BUNDLED_DOCUMENTS if BUNDLED_DOCUMENTS.exists() else ROOT / "rag" / "haystack_documents.jsonl"
STOP_WORDS = {
    "성경", "말씀", "구절", "내용", "관련", "관한", "대해", "대한", "무엇", "뭐라고",
    "어떻게", "알려줘", "찾아줘", "보여줘", "하는", "있는", "것은",
}
PARTICLES = (
    "으로부터", "에게서", "이라고", "라는", "에는", "에서", "으로", "에게", "한테", "까지",
    "부터", "처럼", "보다", "이나", "라도", "이며", "하고", "과", "와", "을", "를", "은",
    "는", "이", "가", "에", "의", "도", "만",
)


def normalize_query(query: str) -> str:
    """질문형 한국어에서 BM25를 흐리는 일반어와 조사를 가볍게 제거한다."""
    normalized = unicodedata.normalize("NFKC", query).casefold()
    terms = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).split()
    cleaned: list[str] = []
    for term in terms:
        if re.search(r"[가-힣]", term) and len(term) >= 3:
            for particle in PARTICLES:
                if term.endswith(particle) and len(term) - len(particle) >= 2:
                    term = term[: -len(particle)]
                    break
        if term and term not in STOP_WORDS and term not in cleaned:
            cleaned.append(term)
    return " ".join(cleaned)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BibleFrame Haystack BM25 검색")
    parser.add_argument("query", help="찾을 말씀이나 주제")
    parser.add_argument("--top-k", type=int, default=5, help="표시할 결과 수 (기본 5)")
    parser.add_argument("--documents", type=Path, default=DEFAULT_DOCUMENTS, help="Haystack JSONL 경로")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.top_k < 1:
        raise SystemExit("--top-k는 1 이상이어야 합니다.")

    try:
        from haystack import Document
        from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
        from haystack.document_stores.in_memory import InMemoryDocumentStore
    except ImportError as error:
        raise SystemExit(
            "Haystack이 설치되지 않았습니다. "
            "`.venv-haystack/bin/pip install -r requirements-haystack.txt`를 먼저 실행하세요."
        ) from error

    if not args.documents.exists():
        raise SystemExit(f"문서 파일을 찾을 수 없습니다: {args.documents}")

    documents = []
    with args.documents.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            payload = json.loads(line)
            documents.append(Document(id=payload["id"], content=payload["content"], meta=payload["meta"]))

    store = InMemoryDocumentStore()
    store.write_documents(documents)
    retriever = InMemoryBM25Retriever(document_store=store)
    query = normalize_query(args.query) or args.query.strip()
    results = retriever.run(query=query, top_k=args.top_k)["documents"]

    if not results:
        print("검색 결과가 없습니다.")
        return

    if query != args.query.strip():
        print(f"정리한 검색어: {query}\n")

    for index, document in enumerate(results, 1):
        meta = document.meta
        score = f"{document.score:.4f}" if document.score is not None else "-"
        preview = " ".join((document.content or "").split())[:220]
        print(f"{index}. {meta['book']} {meta['chapter']}장 · score {score}")
        print(f"   {preview}")


if __name__ == "__main__":
    main()
