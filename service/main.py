"""BibleFrame Cloud Run 웹·RAG API."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from service.audio_catalog import manifest as audio_manifest
from service.rag_service import DEFAULT_DOCUMENTS, DEFAULT_EMBEDDINGS, HybridRagService


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
app = FastAPI(title="BibleFrame API", version="1.0.0")


class RagRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=6, ge=1, le=10)


@lru_cache(maxsize=1)
def rag_service() -> HybridRagService:
    return HybridRagService()


@app.get("/api/health")
def health() -> dict[str, object]:
    passage_count = sum(1 for line in DEFAULT_DOCUMENTS.open(encoding="utf-8") if line.strip())
    return {
        "status": "ok",
        "service": "bibleframe",
        "haystack_passages": passage_count,
        "embeddings_ready": DEFAULT_EMBEDDINGS.exists(),
        "audio": audio_manifest(),
    }


@app.get("/api/audio/manifest")
def get_audio_manifest() -> dict[str, object]:
    return audio_manifest()


@app.post("/api/rag")
async def rag(request: RagRequest) -> dict[str, object]:
    try:
        return await run_in_threadpool(rag_service().answer, request.query.strip(), request.top_k)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"RAG 검색을 완료하지 못했습니다: {error}") from error


app.mount("/", StaticFiles(directory=SITE, html=True), name="site")
