#!/usr/bin/env python3
"""Qwen 번역 프롬프트와 JSON 응답 검증 로직을 네트워크 없이 검사한다."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from translate_qwen import (  # noqa: E402
    MODEL_NAME,
    PROMPT_VERSION,
    batches_by_chapter,
    build_prompt,
    build_user_prompt,
    parse_references,
    parse_translation,
    translated_records,
    VertexQwenClient,
)


def main() -> None:
    source = [
        {"id": "GEN-1-1", "code": "GEN", "book": "창세기", "short": "창", "english": "Genesis", "testament": "old", "chapter": 1, "verse": "1", "verse_start": 1, "verse_end": 1, "text": "In the beginning, God created the heavens and the earth."},
        {"id": "GEN-1-2", "code": "GEN", "book": "창세기", "short": "창", "english": "Genesis", "testament": "old", "chapter": 1, "verse": "2", "verse_start": 2, "verse_end": 2, "text": "The earth was formless and empty."},
    ]
    glossary = json.loads((ROOT / "translation/glossary.json").read_text(encoding="utf-8"))
    prompt = build_prompt(source, glossary)
    user_prompt = build_user_prompt(source, glossary)
    assert "/no_think" in prompt
    assert "God=하느님" in prompt
    assert "GEN-1-1" in prompt
    assert "공인 번역이 아닌" in prompt
    assert user_prompt.startswith("/no_think") and "<|im_start|>" not in user_prompt

    raw = '<think>생각하지 않음</think>```json\n[{"id":"GEN-1-1","text":"한처음에 하느님께서 하늘과 땅을 창조하셨다."},{"id":"GEN-1-2","text":"땅은 아직 꼴을 갖추지 못하고 비어 있었다."}]\n```'
    parsed = parse_translation(raw, source)
    output = translated_records(source, parsed)
    assert output[0]["model"] == MODEL_NAME
    assert output[0]["prompt_version"] == PROMPT_VERSION
    assert output[0]["source_text"].startswith("In the beginning")
    assert output[0]["text"].startswith("한처음에")
    assert output[0]["source_chapter"] == 1
    assert output[0]["source_verse"] == "1"

    wrapped = json.dumps({"translations": parsed}, ensure_ascii=False)
    assert parse_translation(wrapped, source)[1]["text"].startswith("땅은")

    echoed = prompt + raw
    assert parse_translation(echoed, source)[0]["text"].startswith("한처음에")

    assert parse_references("GEN:1,JHN:3") == {("GEN", 1), ("JHN", 3)}
    client = VertexQwenClient("project", "region", "endpoint", "endpoint.region-project.prediction.vertexai.goog")
    assert client.url == "https://endpoint.region-project.prediction.vertexai.goog/v1/projects/project/locations/region/endpoints/endpoint:predict"
    assert [len(batch) for batch in batches_by_chapter(source, 1)] == [1, 1]
    try:
        parse_translation('[{"id":"GEN-1-2","text":"순서 오류"}]', source)
    except ValueError as error:
        assert "절 ID 불일치" in str(error)
    else:
        raise AssertionError("절 ID 불일치를 거부하지 않음")
    for invalid in ("공虛하다.", "아키아кур이 왔다.", "하나님이 창조하셨다.", "사망의 골짜기다."):
        bad = json.dumps([
            {"id": "GEN-1-1", "text": invalid},
            {"id": "GEN-1-2", "text": "땅은 비어 있었다."},
        ], ensure_ascii=False)
        try:
            parse_translation(bad, source)
        except ValueError:
            pass
        else:
            raise AssertionError(f"금지 표현을 거부하지 않음: {invalid}")
    print("OK: Qwen 번역 프롬프트 · JSON 정렬 · 체크포인트 레코드 검증 완료")


if __name__ == "__main__":
    main()
