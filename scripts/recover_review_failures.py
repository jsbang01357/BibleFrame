#!/usr/bin/env python3
"""JSON 교정 복구가 반복 실패한 소수 절을 Qwen 한 줄 응답으로 교정한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from recover_translation_failures import RECOVERY_SYSTEM_PROMPT, clean_text, validate_text
from review_qwen_maas import (
    DEFAULT_CHECKPOINTS,
    DEFAULT_DRAFT,
    DEFAULT_OUTPUT,
    reviewed_records,
)
from translate_qwen import append_checkpoint, load_completed, load_jsonl, merge_output
from translate_qwen_maas import DEFAULT_SOURCE, QwenMaaSClient


# Qwen이 반복적으로 고유명사의 일부 음절만 라틴 문자나 한자로 남기는 경우를
# 결정적으로 정규화한다. 이 목록은 실패 로그에서 실제로 확인한 표기만 포함한다.
MIXED_SCRIPT_REPLACEMENTS = {
    "온yx": "오닉스",
    "Widow": "과부",
    "에zion": "에츠욘",
    "your": "너의",
    "헤lez": "헬레츠",
    "이끄esh": "이케스",
    "에loth": "엘롯",
    "켐osh": "크모스",
    "샘mai": "삼마이",
    "야abez": "야베츠",
    "우즈zi": "우찌",
    "우ziel": "우찌엘",
    "야스ziel": "야흐치엘",
    "이kke": "이케스",
    "여ziel": "예지엘",
    "우zza": "우짜",
    "야아ziel": "야아지엘",
    "아ziel": "아지엘",
    "야하ziel": "야하지엘",
    "사نب알랏": "산발랏",
    "ziklag": "치클락",
    "meconah": "메코나",
    "케lod": "켈롯",
    "우zia": "우찌야",
    "Hoe": "괭이",
    "hoe": "괭이",
    "閉": "닫",
    "だから": "이기 때문",
    "네후\u0634\u062a아": "느후스타",
}


def normalize_known_mixed_script(text: str) -> str:
    for before, after in MIXED_SCRIPT_REPLACEMENTS.items():
        text = text.replace(before, after)
    return text.replace("언약 궤", "계약 궤")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="jisong-cloud-492111")
    parser.add_argument("--location", default="global")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--checkpoints", type=Path, default=DEFAULT_CHECKPOINTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    source = load_jsonl(args.source)
    drafts = load_jsonl(args.draft)
    completed = load_completed(args.checkpoints)
    pending = [item for item in drafts if str(item["id"]) not in completed]
    client = QwenMaaSClient(args.project, args.location)

    recovered = 0
    failures: list[dict[str, str]] = []
    for item in pending:
        if item["status"] == "omitted_in_source":
            append_checkpoint(args.checkpoints, [item])
            continue

        # 1차 번역 자체가 온전한 한국어이거나 알려진 혼합 표기만 고치면 되는 경우,
        # 모델을 다시 호출해 새로운 오류를 만들지 않고 그 문장을 보존한다.
        normalized_draft = normalize_known_mixed_script(str(item["text"]))
        try:
            validate_text(item, normalized_draft)
            record = reviewed_records(
                [item], [{"id": str(item["id"]), "text": normalized_draft}]
            )
            append_checkpoint(args.checkpoints, record)
            recovered += 1
            print(json.dumps({
                "recovered": item["id"],
                "method": "deterministic_normalization",
                "text": normalized_draft,
            }, ensure_ascii=False), flush=True)
            continue
        except ValueError:
            pass

        last_error: Exception | None = None
        for attempt in range(max(1, args.attempts)):
            prompt = (
                "영어 원문과 기계 번역 초안을 대조해 정확하고 자연스러운 현대 한국어 한 줄로 "
                "교정하세요. 초안의 라틴 알파벳과 외국 문자는 모두 한글로 바꾸세요.\n"
                "your는 문맥에 따라 너의·너희의로, gives you는 너에게·너희에게 준다로 옮기세요.\n"
                f"영어 원문: {item['source_text']}\n"
                f"교정할 초안: {item['text']}\n"
                f"재시도 번호: {attempt + 1}"
            )
            try:
                text = clean_text(client.generate(prompt, system_prompt=RECOVERY_SYSTEM_PROMPT))
                validate_text(item, text)
                record = reviewed_records([item], [{"id": str(item["id"]), "text": text}])
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
