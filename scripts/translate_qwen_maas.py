#!/usr/bin/env python3
"""Vertex AI Qwen MaaS로 WEB-C 73권을 병렬·재개 가능하게 번역한다."""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from translate_qwen import (
    DEFAULT_GLOSSARY,
    DEFAULT_SOURCE,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    append_checkpoint,
    batches_by_chapter,
    build_user_prompt,
    load_completed,
    load_jsonl,
    merge_output,
    parse_references,
    parse_translation,
    reference_selected,
    translated_records,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINTS = ROOT / "translation" / "checkpoints-qwen3-next-v2"
DEFAULT_OUTPUT = ROOT / "translation" / "output" / "bibleframe-ko-draft-qwen3-next-v2.jsonl"
DEFAULT_FAILURES = ROOT / "translation" / "failures-qwen3-next-v2.jsonl"
MODEL_ID = "qwen/qwen3-next-80b-a3b-instruct-maas"
MODEL_NAME = "Qwen3-Next-80B-A3B-Instruct-MaaS"
MAAS_PROMPT_VERSION = "bibleframe-ko-v2-maas"

REPAIR_SYSTEM_PROMPT = """당신은 한국어 성경 기계 번역 JSON을 복구하는 편집자입니다.
영어 원문과 실패한 번역을 대조해 오류가 난 항목만 고칩니다. 라틴 알파벳·그리스어·키릴문자·
히브리문자·아랍문자·한자·일본어 등 외국 문자는 모두 자연스러운 한글 번역이나 음역으로 바꾸고,
영어 단어와 로마자를 단 한 글자도 남기지 않습니다. 하나님·여호와·사망은 각각 문맥에 맞게
하느님·주님·죽음으로 고칩니다. 누락된 ID나 잘못된 JSON 구조도 복원합니다. 입력 ID와 순서를
정확히 보존하고 지정된 JSON 배열 하나만 출력합니다."""


def access_token() -> str:
    completed = subprocess.run(
        ["gcloud", "auth", "print-access-token"], check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


class QwenMaaSClient:
    def __init__(self, project: str, location: str = "global", timeout: int = 120) -> None:
        self.url = (
            f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}"
            "/endpoints/openapi/chat/completions"
        )
        self.timeout = timeout
        self._token = ""
        self._token_time = 0.0
        self._token_lock = threading.Lock()

    def _headers(self, refresh: bool = False) -> dict[str, str]:
        with self._token_lock:
            if refresh or not self._token or time.monotonic() - self._token_time > 2_700:
                self._token = access_token()
                self._token_time = time.monotonic()
            return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def generate(
        self,
        user_prompt: str,
        retries: int = 5,
        system_prompt: str = SYSTEM_PROMPT,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, object] = {
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": 8192,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None
        refresh_token = False
        for attempt in range(retries):
            request = urllib.request.Request(self.url, data=body, headers=self._headers(refresh_token))
            refresh_token = False
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                choices = payload.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ValueError(f"MaaS 응답에 choices가 없음: {payload}")
                message = choices[0].get("message") if isinstance(choices[0], dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str):
                    raise ValueError(f"MaaS 응답 본문이 없음: {choices[0]}")
                return content
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
                last_error = error
                if isinstance(error, urllib.error.HTTPError):
                    refresh_token = error.code == 401
                    detail = error.read().decode("utf-8", errors="replace")
                    last_error = RuntimeError(f"Vertex MaaS HTTP {error.code}: {detail}")
                if attempt + 1 < retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Vertex MaaS 요청 실패: {last_error}")


def translate_batch(
    client: QwenMaaSClient,
    records: list[dict[str, object]],
    glossary: dict[str, str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    try:
        raw = client.generate(build_user_prompt(records, glossary))
        try:
            parsed = parse_translation(raw, records)
        except ValueError as parse_error:
            source_rows = [{"id": item["id"], "text": item["text"]} for item in records]
            schema_rows = {"translations": [
                {"id": item["id"], "text": "복구된 한국어 번역"} for item in records
            ]}
            repair_prompt = (
                f"검사 오류: {parse_error}\n영어 원문:\n"
                + json.dumps(source_rows, ensure_ascii=False, separators=(",", ":"))
                + "\n실패한 번역:\n" + raw
                + "\n출력 형식:\n"
                + json.dumps(schema_rows, ensure_ascii=False, separators=(",", ":"))
            )
            repaired_raw = client.generate(
                repair_prompt, system_prompt=REPAIR_SYSTEM_PROMPT, json_mode=True
            )
            parsed = parse_translation(repaired_raw, records)
        return translated_records(records, parsed, MODEL_NAME, MAAS_PROMPT_VERSION), []
    except (ValueError, RuntimeError) as error:
        if len(records) == 1:
            item = records[0]
            return [], [{
                "id": item["id"],
                "code": item["code"],
                "chapter": item["chapter"],
                "verse": item["verse"],
                "source_text": item["text"],
                "error": str(error),
                "model": MODEL_NAME,
                "prompt_version": MAAS_PROMPT_VERSION,
            }]
        middle = len(records) // 2
        left_output, left_failures = translate_batch(client, records[:middle], glossary)
        right_output, right_failures = translate_batch(client, records[middle:], glossary)
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
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--checkpoints", type=Path, default=DEFAULT_CHECKPOINTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--failures", type=Path, default=DEFAULT_FAILURES)
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--references", help="예: GEN:1,JHN:3,TOB:1,PSA:23")
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    source = load_jsonl(args.source)
    glossary = json.loads(args.glossary.read_text(encoding="utf-8"))
    selectors = parse_references(args.references)
    candidates = [item for item in source if reference_selected(item, selectors)]
    if args.limit is not None:
        candidates = candidates[:args.limit]
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

    omitted = [item for item in pending if bool(item["omitted_in_source"])]
    if omitted:
        append_checkpoint(args.checkpoints, [{
            **item,
            "source_text": item["text"],
            "text": "",
            "status": "omitted_in_source",
            "model": None,
            "prompt_version": MAAS_PROMPT_VERSION,
        } for item in omitted])
    pending = [item for item in pending if not bool(item["omitted_in_source"])]

    client = QwenMaaSClient(args.project, args.location)
    batches = list(batches_by_chapter(pending, args.batch_size))
    translated_count = 0
    failed_count = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(translate_batch, client, batch, glossary) for batch in batches]
        for future in as_completed(futures):
            output_records, failures = future.result()
            if output_records:
                append_checkpoint(args.checkpoints, output_records)
            append_failures(args.failures, failures)
            translated_count += len(output_records)
            failed_count += len(failures)
            print(json.dumps({
                "translated": translated_count,
                "failed": failed_count,
                "last_id": output_records[-1]["id"] if output_records else failures[-1]["id"],
                "remaining": len(pending) - translated_count - failed_count,
            }, ensure_ascii=False), flush=True)

    completed = load_completed(args.checkpoints)
    merge_output(source, completed, args.output)
    print(json.dumps({
        "completed": len(completed),
        "failed_this_run": failed_count,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
