#!/usr/bin/env python3
"""Qwen 기계 번역 체크포인트의 절 정렬과 기본 품질을 검사한다."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANGUL_RE = re.compile(r"[가-힣]")
PROTESTANT_TERM_RE = re.compile(r"하나님|여호와")
FOREIGN_SCRIPT_RE = re.compile(r"[A-Za-z\u0370-\u052f\u0590-\u08ff\u3040-\u30ff\u3400-\u9fff]")


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "translation/source/web-c.jsonl")
    parser.add_argument("--checkpoints", type=Path)
    parser.add_argument("--input", type=Path, help="체크포인트 대신 검증할 병합 JSONL")
    parser.add_argument("--expect-count", type=int)
    parser.add_argument("--model", default="Qwen3-14B-FP8")
    parser.add_argument("--prompt-version", default="bibleframe-ko-v1")
    parser.add_argument("--status", default="machine_draft")
    parser.add_argument("--review-prompt-version", default="bibleframe-ko-review-v2")
    args = parser.parse_args()

    source = {str(item["id"]): item for item in load_jsonl(args.source)}
    if args.input:
        translated = load_jsonl(args.input)
    else:
        checkpoints = args.checkpoints or ROOT / "translation/checkpoints"
        translated: list[dict[str, object]] = []
        for path in sorted(checkpoints.glob("*.jsonl")):
            translated.extend(load_jsonl(path))

    ids = [str(item["id"]) for item in translated]
    assert len(ids) == len(set(ids)), "체크포인트에 중복 절 ID가 있음"
    assert all(item_id in source for item_id in ids), "원문에 없는 절 ID가 있음"
    if args.expect_count is not None:
        assert len(translated) == args.expect_count, (len(translated), args.expect_count)

    term_failures: list[str] = []
    foreign_script_failures: list[str] = []
    for item in translated:
        original = source[str(item["id"])]
        assert item["source_text"] == original["text"], f"원문 변경: {item['id']}"
        assert item["code"] == original["code"]
        assert item["chapter"] == original["chapter"]
        assert item["verse"] == original["verse"]
        if item["status"] == "omitted_in_source":
            assert original["omitted_in_source"] and item["text"] == ""
            continue
        text = str(item["text"])
        assert item["status"] == args.status
        assert item["model"] == args.model
        assert item["prompt_version"] == args.prompt_version
        if args.status == "machine_reviewed":
            assert item["reviewer_model"] == args.model
            assert item["review_prompt_version"] == args.review_prompt_version
            assert item["draft_text"].strip()
        assert HANGUL_RE.search(text), f"한글 없는 번역: {item['id']}"
        if FOREIGN_SCRIPT_RE.search(text):
            foreign_script_failures.append(str(item["id"]))
        assert text.strip() and text != original["text"]
        if PROTESTANT_TERM_RE.search(text):
            term_failures.append(str(item["id"]))

    assert not term_failures, f"가톨릭 용어 위반: {term_failures[:20]}"
    assert not foreign_script_failures, f"외국 문자가 섞인 번역: {foreign_script_failures[:20]}"
    counts = Counter(str(item["code"]) for item in translated)
    print(json.dumps({
        "translated_records": len(translated),
        "books": len(counts),
        "by_book": dict(counts),
    }, ensure_ascii=False))
    print("OK: 번역 절 ID · 원문 보존 · 한글 출력 · 가톨릭 용어 기본 검사 완료")


if __name__ == "__main__":
    main()
