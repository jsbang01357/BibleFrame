#!/usr/bin/env python3
"""Qwen MaaS 번역 초안을 영어 원문과 대조해 2차 교정한다."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from translate_qwen import (
    DEFAULT_SOURCE,
    append_checkpoint,
    batches_by_chapter,
    load_completed,
    load_jsonl,
    merge_output,
    parse_references,
    parse_translation,
    reference_selected,
)
from translate_qwen_maas import MODEL_NAME, QwenMaaSClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRAFT = ROOT / "translation" / "output" / "bibleframe-ko-draft-qwen3-next-v2.jsonl"
DEFAULT_CHECKPOINTS = ROOT / "translation" / "review-checkpoints-qwen3-next-v2b"
DEFAULT_OUTPUT = ROOT / "translation" / "output" / "bibleframe-ko-reviewed-qwen3-next-v2b.jsonl"
DEFAULT_FAILURES = ROOT / "translation" / "review-failures-qwen3-next-v2b.jsonl"
REVIEW_PROMPT_VERSION = "bibleframe-ko-review-v2"

REVIEW_SYSTEM_PROMPT = """당신은 Public Domain 영어 성경의 한국어 기계 번역을 교정하는 편집자입니다.
영어 원문과 초안을 대조해 의미 오류, 누락, 첨가, 족보 관계 역전, 전치사와 대명사의 대상,
어색한 문법을 고칩니다. 정확한 초안은 억지로 바꾸지 않습니다.

현대 한국어 평서체와 가톨릭식 일반 용어를 사용합니다. God=하느님, LORD=주님,
Holy Spirit=성령, Paul=바오로, Timothy=티모테오, Titus=티토, Philip=필리포스,
Stephen=스테파노, Matthew=마태오, Mark=마르코, Luke=루카, Barnabas=바르나바,
Nineveh=니네베, Naphtali=납탈리로 통일합니다.

조사, 서술어 활용, 오타와 번역투를 반드시 확인합니다. 예를 들어 '내가 자신이 죽음의 위협을'
같은 문장은 '내가 죽음의 위협을 받고 있음을'처럼 고치고, '도다님였다' 같은 오타는
'도다님이었다'처럼 바로잡습니다. 영어 어순을 기계적으로 유지해 부자연스러우면 의미를
바꾸지 않는 범위에서 자연스러운 한국어 어순으로 다듬습니다.

한자나 외국 문자, '하나님', '여호와', '사망'을 쓰지 않습니다. 절 번호와 해설을 본문에
추가하지 않습니다. 입력 ID와 순서를 보존하고 translations 배열을 담은 JSON 객체 하나만 출력합니다."""

REVIEW_REPAIR_SYSTEM_PROMPT = """당신은 한국어 성경 교정 JSON의 검사 오류를 복구합니다.
영어 원문과 초안을 대조해 의미를 보존하면서 실패한 항목을 고칩니다. 초안에 라틴 알파벳,
그리스어, 키릴문자, 히브리문자, 아랍문자, 한자, 일본어가 한 글자라도 있으면 그대로 복사하지
말고 자연스러운 한글 번역이나 음역으로 완전히 바꿉니다. 예: Shechem=스켐, Jemuel=여무엘,
Mordecai=모르도카이, Hazor=하초르, Uzziel=우찌엘, incense=향, lawful=허용되는,
widow=과부, flesh=육체, offerings=제물, your=너희의. 하나님·여호와·사망은 쓰지 않습니다.
입력 ID와 순서를 정확히 보존하고 translations 배열을 담은 JSON 객체 하나만 출력합니다."""


def build_review_prompt(records: list[dict[str, object]]) -> str:
    rows = [{"id": item["id"], "source_text": item["source_text"], "draft": item["text"]} for item in records]
    schema = {"translations": [
        {"id": item["id"], "text": "교정된 한국어 본문"} for item in records
    ]}
    return (
        "다음 JSON 배열의 draft만 영어 source_text와 대조해 교정하세요.\n입력:\n"
        + json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
        + "\n출력 형식:\n"
        + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    )


def reviewed_records(
    drafts: list[dict[str, object]],
    reviewed: list[dict[str, str]],
) -> list[dict[str, object]]:
    return [{
        **draft,
        "draft_text": draft["text"],
        "text": target["text"],
        "status": "machine_reviewed",
        "reviewer_model": MODEL_NAME,
        "review_prompt_version": REVIEW_PROMPT_VERSION,
    } for draft, target in zip(drafts, reviewed, strict=True)]


def review_batch(
    client: QwenMaaSClient,
    records: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    try:
        raw = client.generate(build_review_prompt(records), system_prompt=REVIEW_SYSTEM_PROMPT)
        try:
            reviewed = parse_translation(raw, records, allow_unchanged=True)
        except ValueError as parse_error:
            rows = [{
                "id": item["id"],
                "source_text": item["source_text"],
                "draft": item["text"],
            } for item in records]
            schema = {"translations": [
                {"id": item["id"], "text": "검사를 통과한 한국어 교정문"} for item in records
            ]}
            repair_prompt = (
                f"검사 오류: {parse_error}\n교정 대상:\n"
                + json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
                + "\n출력 형식:\n"
                + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
            )
            repaired_raw = client.generate(
                repair_prompt, system_prompt=REVIEW_REPAIR_SYSTEM_PROMPT, json_mode=True
            )
            reviewed = parse_translation(repaired_raw, records, allow_unchanged=True)
        return reviewed_records(records, reviewed), []
    except (ValueError, RuntimeError) as error:
        if len(records) == 1:
            item = records[0]
            return [], [{
                "id": item["id"],
                "code": item["code"],
                "chapter": item["chapter"],
                "verse": item["verse"],
                "source_text": item["source_text"],
                "draft_text": item["text"],
                "error": str(error),
                "reviewer_model": MODEL_NAME,
                "review_prompt_version": REVIEW_PROMPT_VERSION,
            }]
        middle = len(records) // 2
        left_output, left_failures = review_batch(client, records[:middle])
        right_output, right_failures = review_batch(client, records[middle:])
        return left_output + right_output, left_failures + right_failures


def append_failures(path: Path, failures: list[dict[str, object]]) -> None:
    if not failures:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for item in failures:
            stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="jisong-cloud-492111")
    parser.add_argument("--location", default="global")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--checkpoints", type=Path, default=DEFAULT_CHECKPOINTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--failures", type=Path, default=DEFAULT_FAILURES)
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--references", help="예: GEN:1,JHN:3,TOB:1,PSA:23")
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    source = {str(item["id"]): item for item in load_jsonl(args.source)}
    drafts = load_jsonl(args.draft)
    selectors = parse_references(args.references)
    candidates = [item for item in drafts if reference_selected(item, selectors)]
    completed = load_completed(args.checkpoints)
    known_failures = {
        str(item["id"])
        for item in load_jsonl(args.failures)
    } if args.failures.exists() else set()
    pending = [
        item for item in candidates
        if str(item["id"]) not in completed
        and (args.retry_failures or str(item["id"]) not in known_failures)
    ]

    omitted = [item for item in pending if item["status"] == "omitted_in_source"]
    if omitted:
        append_checkpoint(args.checkpoints, omitted)
    pending = [item for item in pending if item["status"] != "omitted_in_source"]

    client = QwenMaaSClient(args.project, args.location)
    batches = list(batches_by_chapter(pending, args.batch_size))
    reviewed_count = 0
    failed_count = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(review_batch, client, batch) for batch in batches]
        for future in as_completed(futures):
            output_records, failures = future.result()
            if output_records:
                append_checkpoint(args.checkpoints, output_records)
            append_failures(args.failures, failures)
            reviewed_count += len(output_records)
            failed_count += len(failures)
            print(json.dumps({
                "reviewed": reviewed_count,
                "failed": failed_count,
                "last_id": output_records[-1]["id"] if output_records else failures[-1]["id"],
                "remaining": len(pending) - reviewed_count - failed_count,
            }, ensure_ascii=False), flush=True)

    completed = load_completed(args.checkpoints)
    ordered_source = [source[str(item["id"])] for item in load_jsonl(args.source)]
    merge_output(ordered_source, completed, args.output)
    print(json.dumps({
        "completed": len(completed),
        "failed_this_run": failed_count,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
