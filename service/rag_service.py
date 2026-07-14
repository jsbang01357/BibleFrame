"""Haystack BM25와 Vertex 의미 검색을 결합한 BibleFrame RAG."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from haystack import Document, Pipeline, component
from haystack.components.joiners import DocumentJoiner
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever, InMemoryEmbeddingRetriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from service.gcp_clients import QwenMaaSGenerator, VertexEmbeddingClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENTS = ROOT / "rag" / "haystack_passages.jsonl"
DEFAULT_EMBEDDINGS = ROOT / "rag" / "haystack_embeddings.jsonl"
DEFAULT_BIBLE = ROOT / "site" / "bible.json"
REFERENCE_ALIASES = {
    "JHN": ("요", "요한복음", "요한 복음"),
    "MAT": ("마태오복음", "마태오 복음"),
    "MRK": ("마르코복음", "마르코 복음"),
    "LUK": ("루카복음", "루카 복음"),
    "REV": ("묵시록", "요한묵시록"),
}
SYSTEM_PROMPT = """당신은 한국어 가톨릭 성경 탐색 도우미입니다.
제공된 BibleFrame 비공인 기계 번역 초안만 근거로 답하십시오.
본문과 해설을 명확히 구분하고, 근거가 부족하면 모른다고 답하십시오.
각 문단 끝에 반드시 [1]처럼 제공된 근거 번호를 표시하십시오.
한국천주교주교회의 공용 번역본이나 교리 판정인 것처럼 말하지 마십시오."""


@component
class VertexQueryEmbedder:
    def __init__(self, client: Any) -> None:
        self.client = client

    @component.output_types(embedding=list[float])
    def run(self, text: str) -> dict[str, list[float]]:
        return {"embedding": self.client.embed_query(text)}


def normalize_reference(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).lower()
    normalized = re.sub(r"(\d+)\s*장", r" \1 ", normalized)
    normalized = re.sub(r"(\d+)\s*절", r" \1 ", normalized)
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", normalized)).strip()


def load_reference_catalog(path: Path) -> tuple[list[tuple[str, str]], dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    aliases: list[tuple[str, str]] = []
    names: dict[str, str] = {}
    for book in payload["books"]:
        code = str(book["code"])
        names[code] = str(book["name"])
        values = [book["name"], book["short"], code, book["english"], *REFERENCE_ALIASES.get(code, ())]
        aliases.extend((normalize_reference(alias), code) for alias in values if alias)
    aliases.sort(key=lambda item: len(item[0]), reverse=True)
    return aliases, names


def parse_reference(query: str, aliases: list[tuple[str, str]]) -> tuple[str, int, int] | None:
    normalized = normalize_reference(query)
    for alias, code in aliases:
        prefix = f"{alias} "
        if not normalized.startswith(prefix):
            continue
        match = re.fullmatch(r"(\d+)\s+(\d+)", normalized[len(prefix):].strip())
        if match:
            return code, int(match.group(1)), int(match.group(2))
    return None


def exact_reference_document(document: Document, verse: int) -> Document:
    pattern = re.compile(rf"^{verse}\s+")
    content = next((line for line in str(document.content or "").splitlines() if pattern.match(line)), document.content)
    return Document(
        id=document.id,
        content=content,
        meta={**document.meta, "verse_start": verse, "verse_end": verse},
        score=1.0,
    )


def load_documents(documents_path: Path, embeddings_path: Path | None = None) -> tuple[list[Document], bool]:
    embedding_by_id: dict[str, list[float]] = {}
    if embeddings_path and embeddings_path.exists():
        for line in embeddings_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                embedding_by_id[str(item["id"])] = item["embedding"]

    documents: list[Document] = []
    for line in documents_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        documents.append(Document(
            id=item["id"],
            content=item["content"],
            meta=item["meta"],
            embedding=embedding_by_id.get(str(item["id"])),
        ))
    return documents, bool(documents) and len(embedding_by_id) == len(documents)


class HybridRagService:
    def __init__(
        self,
        documents_path: Path = DEFAULT_DOCUMENTS,
        embeddings_path: Path = DEFAULT_EMBEDDINGS,
        embedder: Any | None = None,
        generator: Any | None = None,
        generation_enabled: bool | None = None,
        bible_path: Path = DEFAULT_BIBLE,
    ) -> None:
        documents, embeddings_ready = load_documents(documents_path, embeddings_path)
        if not documents:
            raise RuntimeError("Haystack 검색 문서가 없습니다.")
        self.document_count = len(documents)
        self.embeddings_ready = embeddings_ready
        self.reference_aliases, self.book_names = load_reference_catalog(bible_path)
        self.documents = documents
        self.store = InMemoryDocumentStore(embedding_similarity_function="cosine")
        self.store.write_documents(documents)
        self.bm25 = InMemoryBM25Retriever(self.store, top_k=12, scale_score=True)
        self.pipeline: Pipeline | None = None

        if embeddings_ready:
            embedding_client = embedder or VertexEmbeddingClient()
            self.pipeline = Pipeline()
            self.pipeline.add_component("query_embedder", VertexQueryEmbedder(embedding_client))
            self.pipeline.add_component("dense", InMemoryEmbeddingRetriever(self.store, top_k=12, scale_score=True))
            self.pipeline.add_component("bm25", self.bm25)
            self.pipeline.add_component(
                "joiner", DocumentJoiner(
                    join_mode="reciprocal_rank_fusion", weights=[0.75, 0.25], top_k=8,
                ),
            )
            self.pipeline.connect("query_embedder.embedding", "dense.query_embedding")
            self.pipeline.connect("dense.documents", "joiner.documents")
            self.pipeline.connect("bm25.documents", "joiner.documents")

        enabled = generation_enabled
        if enabled is None:
            enabled = os.getenv("RAG_GENERATION_ENABLED", "true").lower() not in {"0", "false", "no"}
        self.generator = (generator or QwenMaaSGenerator()) if enabled else None

    def retrieve(self, query: str, top_k: int = 6) -> list[Document]:
        top_k = min(max(int(top_k), 1), 10)
        direct = parse_reference(query, self.reference_aliases)
        pinned: list[Document] = []
        effective_query = query
        if direct:
            code, chapter, verse = direct
            pinned = [
                exact_reference_document(document, verse) for document in self.documents
                if document.meta.get("book_code") == code
                and int(document.meta.get("chapter", 0)) == chapter
                and int(document.meta.get("verse_start", 0)) <= verse <= int(document.meta.get("verse_end", 0))
            ]
            effective_query = f"{self.book_names.get(code, code)} {chapter}장 {verse}절 {query}"
        if self.pipeline:
            result = self.pipeline.run({
                "query_embedder": {"text": effective_query},
                "dense": {"top_k": max(top_k * 2, 8)},
                "bm25": {"query": effective_query, "top_k": max(top_k * 2, 8)},
                "joiner": {"top_k": top_k},
            })
            retrieved = result["joiner"]["documents"]
        else:
            retrieved = self.bm25.run(query=effective_query, top_k=top_k)["documents"]
        if not pinned:
            return retrieved
        pinned_ids = {document.id for document in pinned}
        return [*pinned, *(document for document in retrieved if document.id not in pinned_ids)][:top_k]

    @staticmethod
    def source_for(document: Document, index: int) -> dict[str, Any]:
        meta = document.meta
        start = int(meta["verse_start"])
        end = int(meta["verse_end"])
        verse_label = f"{start}절" if start == end else f"{start}-{end}절"
        return {
            "index": index,
            "id": document.id,
            "reference": f'{meta["book"]} {meta["chapter"]}장 {verse_label}',
            "book": meta["book"],
            "book_code": meta["book_code"],
            "chapter": int(meta["chapter"]),
            "verse_start": start,
            "verse_end": end,
            "content": document.content,
            "score": document.score,
            "reader_url": (
                f'/?view=reader&book={meta["book_code"]}&chapter={meta["chapter"]}&verse={start}'
            ),
        }

    def answer(self, query: str, top_k: int = 6) -> dict[str, Any]:
        documents = self.retrieve(query, top_k)
        sources = [self.source_for(document, index) for index, document in enumerate(documents, 1)]
        if not sources:
            return {"answer": "관련된 성경 본문을 찾지 못했습니다.", "sources": [], "mode": "none"}

        if self.generator is None:
            references = ", ".join(source["reference"] for source in sources[:3])
            return {
                "answer": f"관련 본문으로 {references} 등을 찾았습니다. 아래 근거를 직접 확인해 주세요.",
                "sources": sources,
                "mode": "hybrid" if self.pipeline else "bm25",
            }

        context = "\n\n".join(
            f'[{source["index"]}] {source["reference"]}\n{source["content"]}' for source in sources
        )
        user_prompt = f"질문: {query}\n\n근거 본문:\n{context}\n\n한국어로 간결하고 따뜻하게 답하세요."
        return {
            "answer": self.generator.generate(SYSTEM_PROMPT, user_prompt),
            "sources": sources,
            "mode": "hybrid" if self.pipeline else "bm25",
        }
