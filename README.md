# BibleFrame

`bibleframe.jisong.dev`에서 운영할 한국어 성경 검색·RAG 프로젝트입니다.

의료정책 검색기 `RIHP_RAG`의 재생성 가능한 정적 검색 구조를 계승하되, 성경 본문과
메타데이터는 별도 저장소에서 독립적으로 관리합니다. 첫 버전은 서버, API 키, 벡터 DB 없이
브라우저에서 전체 66권을 검색합니다.

## 포함 기능

- eBible.org 배포본 기준 66권, 1,188장, 30,991절 검색
- `요한복음 3:16`, `요 3장 16절` 같은 구절 위치 검색
- 본문 키워드 검색과 구약·신약/성경 필터
- 검색 결과에서 해당 책·장·절을 바로 여는 성경 브라우저
- 어르신도 편하게 읽을 수 있는 본문 글자 확대·축소와 기기별 설정 저장
- 이전 장·다음 장 이동 및 공유 가능한 읽기 URL
- 검색 결과 링크 복사와 FAQ 화면
- 장 단위 RAG JSONL과 ChatGPT 업로드용 ZIP 재생성
- 데스크톱 사이드바와 모바일 상단 탭을 갖춘 정적 사이트

## 데이터와 권리

본문은 eBible.org의 **Korean Bible 1910** VPL 배포본을 사용합니다. eBible.org는 이
번역을 Public Domain으로 명시합니다. 자세한 출처와 재배포 경계는 `RIGHTS.md`를 봅니다.

현대 한국어 번역본은 권리자의 명시적 허락 없이는 저장소나 공개 사이트에 넣지 않습니다.
원본 배포본은 베드로전서를 4장까지만 수록합니다. 이 상류 데이터 차이는
`qa/source-audit.md`에 숨기지 않고 기록합니다.

## 빌드와 검증

```bash
python3 scripts/build_data.py
python3 scripts/test_build.py
node scripts/test_search.mjs
python3 -m http.server 8000 --directory site
```

생성물:

- `site/bible.json`: 브라우저 검색용 절 단위 데이터
- `rag/chapters.jsonl`: 검색·임베딩용 장 단위 청크
- `site/downloads/bibleframe-rag.zip`: ChatGPT 업로드용 패키지

## 배포

Cloudflare Pages 프로젝트 이름은 `bibleframe`, 운영 주소는
`https://bibleframe.jisong.dev`를 사용합니다.

```bash
npx wrangler pages deploy site --project-name bibleframe --branch main
```

GitHub 저장소에는 생성된 검색 데이터와 RAG 파일을 함께 커밋해 별도 빌드 환경 없이도
정적 배포가 가능하게 유지합니다.
