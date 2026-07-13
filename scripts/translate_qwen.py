#!/usr/bin/env python3
"""Vertex AI의 Qwen 엔드포인트로 WEB-C 73권을 재개 가능하게 번역한다."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "translation" / "source" / "web-c.jsonl"
DEFAULT_GLOSSARY = ROOT / "translation" / "glossary.json"
DEFAULT_CHECKPOINTS = ROOT / "translation" / "checkpoints"
DEFAULT_OUTPUT = ROOT / "translation" / "output" / "bibleframe-ko-draft.jsonl"
MODEL_NAME = "Qwen3-14B-FP8"
PROMPT_VERSION = "bibleframe-ko-v1"
HANGUL_RE = re.compile(r"[가-힣]")
FOREIGN_SCRIPT_RE = re.compile(r"[A-Za-z\u0370-\u052f\u0590-\u08ff\u3040-\u30ff\u3400-\u9fff]")
PROTESTANT_TERM_RE = re.compile(r"하나님|여호와|사망")


SYSTEM_PROMPT = """당신은 Public Domain 영어 성경을 현대 한국어로 옮기는 전문 번역가입니다.
이 원문은 가톨릭 정경 순서의 World English Bible (Catholic)입니다.

원칙:
1. 원문의 의미, 인칭, 시제, 부정, 수량, 고유명사와 문장 순서를 충실히 보존합니다.
2. 해설, 요약, 교리 설명, 각주, 절 번호, 제목을 본문에 추가하지 않습니다.
3. 자연스러운 현대 한국어 문장으로 쓰되 문학적 표현을 임의로 확대하지 않습니다.
4. God은 '하느님', LORD와 Lord는 문맥에 따라 '주님', Holy Spirit은 '성령'으로 통일합니다.
5. 입력 ID를 바꾸거나 빠뜨리거나 합치지 않습니다.
6. 출력은 translations 배열을 담은 지정된 JSON 객체 한 개뿐이며 코드 블록이나 설명을 덧붙이지 않습니다.
7. 현대 한국어 한글만 쓰고 한자를 섞지 않습니다. 예: '공虛'가 아니라 '공허'로 씁니다.
8. '하나님'과 '여호와'라는 표현은 사용하지 않습니다.
9. 연속된 'son of' 같은 족보는 사람과 부모의 순서를 바꾸지 말고, 전치사와 대명사의 대상을 정확히 보존합니다.
10. 현대 평서체로 쓰고 개신교식 관용구나 고어체를 피합니다. death는 문맥에 따라 '죽음'이나 '죽다'로 옮깁니다.
11. 출력 전에 원문과 한 번 더 대조하여 누락·첨가·관계 역전·부자연스러운 문법·외국 문자가 없는지 교정합니다.
12. 이 번역은 교회 공인 번역이 아닌 공개 기계 번역 초안입니다."""


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def reference_selected(item: dict[str, object], selectors: set[tuple[str, int]] | None) -> bool:
    return selectors is None or (str(item["code"]), int(item["chapter"])) in selectors


def parse_references(raw: str | None) -> set[tuple[str, int]] | None:
    if not raw:
        return None
    result: set[tuple[str, int]] = set()
    for token in raw.split(","):
        code, separator, chapter = token.strip().partition(":")
        if not separator or not chapter.isdigit():
            raise ValueError(f"잘못된 --references 값: {token}")
        result.add((code.upper(), int(chapter)))
    return result


def batches_by_chapter(records: Iterable[dict[str, object]], batch_size: int) -> Iterable[list[dict[str, object]]]:
    current_key: tuple[str, int] | None = None
    batch: list[dict[str, object]] = []
    for item in records:
        key = (str(item["code"]), int(item["chapter"]))
        if batch and (key != current_key or len(batch) >= batch_size):
            yield batch
            batch = []
        current_key = key
        batch.append(item)
    if batch:
        yield batch


def build_user_prompt(records: list[dict[str, object]], glossary: dict[str, str]) -> str:
    first = records[0]
    compact_glossary = ", ".join(f"{source}={target}" for source, target in glossary.items())
    source_rows = [{"id": item["id"], "text": item["text"]} for item in records]
    schema_rows = {"translations": [
        {"id": item["id"], "text": "한국어 번역"} for item in records
    ]}
    return f"""/no_think
책: {first['book']} ({first['english']}) {first['chapter']}장
용어 기준: {compact_glossary}

다음 JSON 배열의 text만 한국어로 번역하세요.
입력:
{json.dumps(source_rows, ensure_ascii=False, separators=(',', ':'))}

출력 형식 예시:
{json.dumps(schema_rows, ensure_ascii=False, separators=(',', ':'))}"""


def build_prompt(records: list[dict[str, object]], glossary: dict[str, str]) -> str:
    user_prompt = build_user_prompt(records, glossary)
    return (
        "<|im_start|>system\n" + SYSTEM_PROMPT + "<|im_end|>\n"
        "<|im_start|>user\n" + user_prompt + "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def strip_reasoning(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = raw.replace("```json", "").replace("```", "")
    return raw.strip()


def parse_translation(
    raw: str,
    expected: list[dict[str, object]],
    allow_unchanged: bool = False,
) -> list[dict[str, str]]:
    raw = strip_reasoning(raw)
    expected_ids = [str(item["id"]) for item in expected]
    parsed: list[object] | None = None
    last_ids: list[str] = []
    decoder = json.JSONDecoder()
    for start, character in enumerate(raw):
        if character not in "[{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            candidate = candidate.get("translations")
        if not isinstance(candidate, list):
            continue
        candidate_ids = [str(item.get("id", "")) for item in candidate if isinstance(item, dict)]
        last_ids = candidate_ids
        if candidate_ids == expected_ids:
            parsed = candidate
    if parsed is None:
        if not last_ids:
            raise ValueError("응답에서 translations JSON 배열을 찾지 못함")
        raise ValueError(f"절 ID 불일치: expected={expected_ids}, actual={last_ids}")
    result: list[dict[str, str]] = []
    for source, item in zip(expected, parsed, strict=True):
        text = str(item.get("text", "")).strip()
        if not text or not HANGUL_RE.search(text):
            raise ValueError(f"한국어 번역 누락: {source['id']}")
        if not allow_unchanged and text == str(source["text"]).strip():
            raise ValueError(f"원문이 그대로 반환됨: {source['id']}")
        if FOREIGN_SCRIPT_RE.search(text):
            raise ValueError(f"외국 문자가 섞인 번역: {source['id']}")
        if PROTESTANT_TERM_RE.search(text):
            raise ValueError(f"가톨릭 용어 위반: {source['id']}")
        result.append({"id": str(source["id"]), "text": text})
    return result


def access_token() -> str:
    completed = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def dedicated_domain(project: str, region: str, endpoint_id: str) -> str:
    completed = subprocess.run(
        [
            "gcloud", "ai", "endpoints", "describe", endpoint_id,
            f"--project={project}", f"--region={region}",
            "--format=value(dedicatedEndpointDns)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    domain = completed.stdout.strip().removeprefix("https://").rstrip("/")
    if not domain:
        raise ValueError(f"전용 엔드포인트 DNS를 찾지 못함: {endpoint_id}")
    return domain


def response_text(payload: dict[str, object]) -> str:
    predictions = payload.get("predictions")
    if not isinstance(predictions, list) or not predictions:
        raise ValueError(f"Vertex 응답에 predictions가 없음: {payload}")
    value: object = predictions[0]
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("generated_text", "text", "content", "output"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
        choices = value.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            choice = choices[0]
            if isinstance(choice.get("text"), str):
                return str(choice["text"])
            message = choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return str(message["content"])
    raise ValueError(f"Vertex 응답 본문 형식을 해석하지 못함: {value}")


class VertexQwenClient:
    def __init__(self, project: str, region: str, endpoint_id: str, dedicated_dns: str, timeout: int = 300) -> None:
        host = dedicated_dns.removeprefix("https://").rstrip("/")
        self.url = (
            f"https://{host}/v1/projects/{project}"
            f"/locations/{region}/endpoints/{endpoint_id}:predict"
        )
        self.timeout = timeout
        self._token = ""
        self._token_time = 0.0

    def _headers(self, refresh: bool = False) -> dict[str, str]:
        if refresh or not self._token or time.monotonic() - self._token_time > 2_700:
            self._token = access_token()
            self._token_time = time.monotonic()
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def generate(self, prompt: str, retries: int = 4) -> str:
        body = json.dumps({
            "instances": [{"text": prompt}],
            "parameters": {"sampling_params": {
                "max_new_tokens": 4096,
                "temperature": 0.1,
                "top_p": 0.9,
                "top_k": 20,
                "repetition_penalty": 1.02,
            }},
        }).encode("utf-8")
        last_error: Exception | None = None
        refresh_token = False
        for attempt in range(retries):
            request = urllib.request.Request(self.url, data=body, headers=self._headers(refresh=refresh_token))
            refresh_token = False
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response_text(json.loads(response.read().decode("utf-8")))
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
                last_error = error
                if isinstance(error, urllib.error.HTTPError):
                    refresh_token = error.code == 401
                    detail = error.read().decode("utf-8", errors="replace")
                    last_error = RuntimeError(f"Vertex HTTP {error.code}: {detail}")
                if attempt + 1 < retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Vertex 요청 실패: {last_error}")


def checkpoint_path(directory: Path, code: str) -> Path:
    return directory / f"{code}.jsonl"


def load_completed(directory: Path) -> dict[str, dict[str, object]]:
    completed: dict[str, dict[str, object]] = {}
    if not directory.exists():
        return completed
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                completed[str(item["id"])] = item
    return completed


def append_checkpoint(directory: Path, records: list[dict[str, object]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in records:
        grouped[str(item["code"])].append(item)
    for code, items in grouped.items():
        with checkpoint_path(directory, code).open("a", encoding="utf-8") as stream:
            for item in items:
                stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()


def translated_records(
    source: list[dict[str, object]],
    translated: list[dict[str, str]],
    model_name: str = MODEL_NAME,
    prompt_version: str = PROMPT_VERSION,
) -> list[dict[str, object]]:
    return [{
        "id": item["id"],
        "code": item["code"],
        "book": item["book"],
        "short": item["short"],
        "english": item["english"],
        "testament": item["testament"],
        "chapter": item["chapter"],
        "verse": item["verse"],
        "verse_start": item["verse_start"],
        "verse_end": item["verse_end"],
        "source_chapter": item.get("source_chapter", item["chapter"]),
        "source_verse": item.get("source_verse", item["verse"]),
        "text": target["text"],
        "source_text": item["text"],
        "status": "machine_draft",
        "model": model_name,
        "prompt_version": prompt_version,
    } for item, target in zip(source, translated, strict=True)]


def translate_batch(client: VertexQwenClient, records: list[dict[str, object]], glossary: dict[str, str]) -> list[dict[str, object]]:
    try:
        raw = client.generate(build_prompt(records, glossary))
        return translated_records(records, parse_translation(raw, records))
    except (ValueError, RuntimeError) as error:
        if len(records) == 1:
            raise RuntimeError(f"{records[0]['id']} 번역 실패: {error}") from error
        middle = len(records) // 2
        return translate_batch(client, records[:middle], glossary) + translate_batch(client, records[middle:], glossary)


def merge_output(source: list[dict[str, object]], completed: dict[str, dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for item in source:
            translated = completed.get(str(item["id"]))
            if translated is not None:
                stream.write(json.dumps(translated, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="jisong-cloud-492111")
    parser.add_argument("--region", default="asia-northeast3")
    parser.add_argument("--endpoint-id")
    parser.add_argument("--dedicated-domain", help="생략하면 gcloud로 endpoint의 dedicatedEndpointDns를 조회")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--checkpoints", type=Path, default=DEFAULT_CHECKPOINTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--references", help="예: GEN:1,JHN:3,TOB:1,PSA:23")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = load_jsonl(args.source)
    glossary = json.loads(args.glossary.read_text(encoding="utf-8"))
    selectors = parse_references(args.references)
    candidates = [item for item in source if reference_selected(item, selectors)]
    if args.limit is not None:
        candidates = candidates[:args.limit]
    completed = load_completed(args.checkpoints)
    pending = [item for item in candidates if str(item["id"]) not in completed]

    omitted = [item for item in pending if bool(item["omitted_in_source"])]
    if omitted:
        append_checkpoint(args.checkpoints, [{
            **item,
            "source_text": item["text"],
            "text": "",
            "status": "omitted_in_source",
            "model": None,
            "prompt_version": PROMPT_VERSION,
        } for item in omitted])
    pending = [item for item in pending if not bool(item["omitted_in_source"])]

    if args.dry_run:
        sample = pending[: min(args.batch_size, len(pending))]
        if sample:
            print(build_prompt(sample, glossary))
        return
    if pending and not args.endpoint_id:
        parser.error("번역 실행에는 --endpoint-id가 필요함")

    endpoint_id = str(args.endpoint_id)
    domain = args.dedicated_domain or dedicated_domain(args.project, args.region, endpoint_id)
    client = VertexQwenClient(args.project, args.region, endpoint_id, domain)
    translated_count = 0
    for batch in batches_by_chapter(pending, args.batch_size):
        output_records = translate_batch(client, batch, glossary)
        append_checkpoint(args.checkpoints, output_records)
        translated_count += len(output_records)
        print(json.dumps({
            "translated": translated_count,
            "last_id": output_records[-1]["id"],
            "remaining": len(pending) - translated_count,
        }, ensure_ascii=False), flush=True)

    completed = load_completed(args.checkpoints)
    merge_output(source, completed, args.output)
    print(json.dumps({"completed": len(completed), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
