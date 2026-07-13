# BibleFrame 73권 공개 번역

## 성격

- 원문: `World English Bible (Catholic)` USFM
- 원문 권리: Public Domain
- 정경: 가톨릭식 73권, 확장된 에스테르기와 다니엘서 포함
- 장절: WEB-C의 요엘·말라키 장 구분을 가톨릭식 요엘 4장·말라키 3장으로 변환
- 번역 방식: Qwen 기계 번역 후 Qwen 원문 대조 교정과 자동 QA
- 표시명: `BibleFrame 73권 공개 번역 초안`
- 필수 고지: `가톨릭 정경 기반 · 비공인 기계 번역 초안`
- 한국어 본문·데이터 라이선스: CC0 1.0 Universal (`CC0-1.0`)

이 산출물은 한국천주교주교회의의 공용 번역본이 아니며 전례용·교리 판정용으로 사용하지
않습니다. CBCK 본문을 학습 입력, 번역 메모리, 검수 정답 또는 TTS 원문으로 복제하지
않습니다.

## 원문 생성과 검증

```bash
python3 scripts/prepare_web_c.py
python3 scripts/test_translation_source.py
```

생성물:

- `translation/source/web-c.jsonl`: 절 단위 번역 원문
- `translation/source/web-c.meta.json`: 출처·권리·해시·통계
- `translation/glossary.json`: 가톨릭식 한국어 용어 기준

## 번역 실행

Vertex AI의 관리형 `Qwen3-Next-80B-A3B-Instruct` MaaS를 사용합니다. 번역은 책별
JSONL에 즉시 덧붙여 저장하므로 중단되어도 같은 명령으로 이어집니다. 별도 GPU 배포를
유지하지 않으며 호출한 토큰만 과금됩니다.

```bash
python3 scripts/translate_qwen_maas.py --batch-size 24 --workers 8
```

검증된 레코드는 `translation/checkpoints-qwen3-next-v2/`에 저장되고 병합본은
`translation/output/bibleframe-ko-draft-qwen3-next-v2.jsonl`에 생성됩니다. 실패 절은
전체 작업을 중단하지 않고 별도 큐로 격리하며, 전체 실행 뒤 아래처럼 다시 처리합니다.

```bash
python3 scripts/translate_qwen_maas.py --batch-size 1 --workers 4 --retry-failures
# JSON 복구가 반복 실패한 소수 절이 남은 경우
python3 scripts/recover_translation_failures.py
python3 scripts/test_translation_output.py \
  --checkpoints translation/checkpoints-qwen3-next-v2 \
  --expect-count 35408 \
  --model Qwen3-Next-80B-A3B-Instruct-MaaS \
  --prompt-version bibleframe-ko-v2-maas
```

## 2차 교정과 빌드

초안 전체를 같은 Qwen 80B가 영어 원문과 다시 대조합니다. 조사·서술어·오타까지 교정하고,
교정 단계의 실패도 별도 큐로 격리합니다.

```bash
python3 scripts/review_qwen_maas.py --batch-size 24 --workers 8
python3 scripts/review_qwen_maas.py --batch-size 1 --workers 4 --retry-failures
# JSON 복구가 반복 실패한 소수 교정문이 남은 경우
python3 scripts/recover_review_failures.py
python3 scripts/test_translation_output.py \
  --input translation/output/bibleframe-ko-reviewed-qwen3-next-v2b.jsonl \
  --expect-count 35408 \
  --model Qwen3-Next-80B-A3B-Instruct-MaaS \
  --prompt-version bibleframe-ko-v2-maas \
  --status machine_reviewed \
  --review-prompt-version bibleframe-ko-review-v2
python3 scripts/build_catholic_data.py
python3 scripts/test_catholic_build.py
```

`Qwen3-14B-FP8` 전용 엔드포인트는 품질·속도 시험 뒤 모델을 언디플로이했으며 현재 GPU
시간 과금은 없습니다. 남아 있는 빈 엔드포인트와 모델 리소스는 산출물 검증 후 별도로
정리합니다.

eBible의 2026-05-22 VPL ZIP에는 창세기 1,533절이 빠져 있어 사용하지 않습니다. 같은
배포본의 USFM 73권을 기준으로 삼고 책·장·절 수를 자동 검사합니다.
