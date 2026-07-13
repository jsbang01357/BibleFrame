# BibleFrame

`bibleframe.jisong.dev`에서 운영할 한국어 성경 검색·RAG 프로젝트입니다.

의료정책 검색기 `RIHP_RAG`의 재생성 가능한 정적 검색 구조를 계승하되, 성경 본문과
메타데이터는 별도 저장소에서 독립적으로 관리합니다. 서버, API 키, 벡터 DB 없이
브라우저에서 가톨릭 정경 73권 공개 번역 초안을 검색합니다.

## 포함 기능

- 가톨릭 정경 73권, 1,328장, 검색 가능한 35,379절
- `요한복음 3:16`, `요 3장 16절` 같은 구절 위치 검색
- 본문 키워드 검색과 구약·신약/성경 필터
- 첫 화면에서 35,379절 중 한 구절을 무작위로 여는 `랜덤 말씀`
- 검색 결과에서 해당 책·장·절을 바로 여는 성경 브라우저
- 어르신도 편하게 읽을 수 있는 본문 글자 확대·축소와 기기별 설정 저장
- 기기 내장 음성을 이용한 말씀 듣기, 읽기 속도, 절 강조
- 15~60분 취침 타이머와 다음 장 자동재생
- 이전 장·다음 장 이동 및 공유 가능한 읽기 URL
- 검색 결과 링크 복사와 FAQ 화면
- 범용 장 단위 RAG JSONL, Haystack 네이티브 문서와 업로드용 ZIP 재생성
- TXT·JSON·JSONL·Word·PDF·RAG 전체 본문 다운로드
- 73권 자동 목차·PDF 책갈피와 절마다 새 줄로 시작하는 PDF 읽기본
- 데스크톱 사이드바와 모바일 상단 탭을 갖춘 정적 사이트

음성 목록과 화면 잠금 중 재생 여부는 운영체제와 브라우저의 Web Speech API 지원 범위에
따라 달라집니다. 외부 유료 TTS API와 서버는 사용하지 않습니다.

## 데이터와 권리

영어 원문은 eBible.org의 **World English Bible (Catholic)** USFM 73권입니다. eBible.org는
이 판본을 Public Domain으로 명시합니다. 한국어 본문은 원문을 Vertex AI의
`Qwen3-Next-80B-A3B-Instruct`로 새로 번역하고 같은 모델로 원문 대조 교정을 거친
비공인 기계 번역 초안입니다. 자세한 출처와 재배포 경계는 `RIGHTS.md`를 봅니다.

한국어 본문과 데이터 산출물은 `DATA_LICENSE.md`의 CC0 1.0 Universal, 사이트와 빌드
코드는 `LICENSE`의 MIT License로 공개합니다.

현대 한국어 번역본은 권리자의 명시적 허락 없이는 저장소나 공개 사이트에 넣지 않습니다.
한국천주교주교회의 공용 번역본을 복제·학습 입력·검수 정답으로 사용하지 않았으며, 이
초안은 전례용이나 교리 판정용이 아닙니다. 출처 검토는 `qa/catholic-source-audit.md`에
기록합니다.

## 빌드와 검증

PDF 생성에는 나눔고딕 TTF가 필요합니다. Ubuntu에서는 `fonts-nanum` 패키지를 설치하고,
문서 생성용 Python 패키지를 준비합니다.

```bash
python3 -m pip install python-docx reportlab pypdf
python3 scripts/test_translation_source.py
python3 scripts/test_translation_output.py \
  --input translation/output/bibleframe-ko-reviewed-qwen3-next-v2b.jsonl \
  --expect-count 35408 \
  --model Qwen3-Next-80B-A3B-Instruct-MaaS \
  --prompt-version bibleframe-ko-v2-maas \
  --status machine_reviewed \
  --review-prompt-version bibleframe-ko-review-v2
python3 scripts/build_catholic_data.py
python3 scripts/build_downloads.py
python3 scripts/test_catholic_build.py
python3 scripts/test_downloads.py
node scripts/test_search.mjs
python3 scripts/test_haystack_export.py
python3 -m http.server 8000 --directory site
```

Haystack은 정적 사이트의 필수 의존성이 아니라 로컬·백엔드 실험용 선택 사항입니다.

```bash
python3 -m venv .venv-haystack
.venv-haystack/bin/pip install -r requirements-haystack.txt
.venv-haystack/bin/python scripts/query_haystack.py "두려움에 관한 말씀" --top-k 5
```

생성물:

- `site/bible.json`: 브라우저 검색용 절 단위 데이터
- `rag/chapters.jsonl`: 검색·임베딩용 장 단위 청크
- `rag/haystack_documents.jsonl`: Haystack `Document` 호환 장 단위 청크
- `site/downloads/bibleframe-rag.zip`: 범용·Haystack JSONL을 묶은 AI 연결 패키지
- `site/downloads/bibleframe-ko-catholic-73.txt`: UTF-8 읽기·가공용 본문
- `site/downloads/bibleframe-ko-catholic-73.json`: 전체 메타데이터와 절 배열
- `site/downloads/bibleframe-ko-catholic-73.jsonl`: 한 줄에 한 절인 스트리밍 데이터
- `site/downloads/bibleframe-ko-catholic-73.docx`: 책·장 제목이 있는 Word 편집본
- `site/downloads/bibleframe-ko-catholic-73.pdf`: 73권 목차·책갈피·절별 줄바꿈 PDF

## 배포

Cloudflare Pages 프로젝트 이름은 `bibleframe`, 운영 주소는
`https://bibleframe.jisong.dev`를 사용합니다.

```bash
npx wrangler pages deploy site --project-name bibleframe --branch main
```

GitHub 저장소에는 생성된 검색 데이터와 RAG 파일을 함께 커밋해 별도 빌드 환경 없이도
정적 배포가 가능하게 유지합니다.
