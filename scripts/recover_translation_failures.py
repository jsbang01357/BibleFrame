#!/usr/bin/env python3
"""JSON 형식 복구가 반복 실패한 소수 절을 Qwen 한 줄 응답으로 복구한다."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from translate_qwen import (
    FOREIGN_SCRIPT_RE,
    HANGUL_RE,
    PROTESTANT_TERM_RE,
    append_checkpoint,
    load_completed,
    load_jsonl,
    merge_output,
    translated_records,
)
from translate_qwen_maas import (
    DEFAULT_CHECKPOINTS,
    DEFAULT_OUTPUT,
    DEFAULT_SOURCE,
    MAAS_PROMPT_VERSION,
    MODEL_NAME,
    QwenMaaSClient,
)


RECOVERY_SYSTEM_PROMPT = """당신은 Public Domain 영어 성경을 현대 한국어로 번역합니다.
God은 하느님, LORD와 Lord는 주님으로 옮깁니다. 영어 알파벳, 한자, 그리스 문자,
키릴 문자, 히브리 문자, 아랍 문자, 일본 문자를 단 한 글자도 남기지 않습니다.
해설, 머리말, 절 번호, 따옴표, JSON 없이 번역 본문 한 줄만 출력합니다."""


def clean_text(raw: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    text = text.replace("```json", "").replace("```", "").strip()
    text = re.sub(r"^(번역|한국어 번역)\s*:\s*", "", text).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    return " ".join(text.splitlines()).strip()


def validate_text(item: dict[str, object], text: str) -> None:
    if not text or not HANGUL_RE.search(text):
        raise ValueError(f"한국어 번역 누락: {item['id']}")
    if FOREIGN_SCRIPT_RE.search(text):
        raise ValueError(f"외국 문자가 섞인 번역: {item['id']} · {text}")
    if PROTESTANT_TERM_RE.search(text):
        raise ValueError(f"가톨릭 용어 위반: {item['id']} · {text}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="jisong-cloud-492111")
    parser.add_argument("--location", default="global")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--checkpoints", type=Path, default=DEFAULT_CHECKPOINTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    source = load_jsonl(args.source)
    completed = load_completed(args.checkpoints)
    pending = [item for item in source if str(item["id"]) not in completed]
    client = QwenMaaSClient(args.project, args.location)

    recovered = 0
    failures: list[dict[str, str]] = []
    for item in pending:
        last_error: Exception | None = None
        for attempt in range(max(1, args.attempts)):
            prompt = (
                "다음 영어 성경 문장을 정확하고 자연스러운 현대 한국어 한 줄로만 번역하세요.\n"
                "gives you는 반드시 '너희에게 준다' 또는 문맥에 맞는 온전한 한글 표현으로 옮기세요.\n"
                f"영어 원문: {item['text']}\n"
                f"재시도 번호: {attempt + 1}"
            )
            try:
                text = clean_text(client.generate(prompt, system_prompt=RECOVERY_SYSTEM_PROMPT))
                validate_text(item, text)
                record = translated_records(
                    [item], [{"id": str(item["id"]), "text": text}], MODEL_NAME, MAAS_PROMPT_VERSION
                )
                append_checkpoint(args.checkpoints, record)
                recovered += 1
                print(json.dumps({"recovered": item["id"], "text": text}, ensure_ascii=False), flush=True)
                break
            except (RuntimeError, ValueError) as error:
                last_error = error
        else:
            failures.append({"id": str(item["id"]), "error": str(last_error)})

    completed = load_completed(args.checkpoints)
    merge_output(source, completed, args.output)
    print(json.dumps({
        "recovered": recovered,
        "failed": failures,
        "completed": len(completed),
        "output": str(args.output),
    }, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
