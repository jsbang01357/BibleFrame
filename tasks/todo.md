# 작업 계획

## 진행 중

- [x] 첫 화면에 무작위 구절을 바로 여는 `랜덤 말씀` 기능을 추가한다.
- [x] Haystack 네이티브 문서 JSONL과 선택형 로컬 BM25 검색 예제를 추가한다.
- [x] 정적 검색 회귀·RAG 산출물·데스크톱/모바일 화면을 검증한다.
- [ ] Cloudflare Pages 운영 배포와 GitHub 초안 PR·Actions를 갱신한다.
- [x] 현재 66권 Korean Bible 1910 데이터와 화면·RAG 의존 범위를 확인한다.
- [x] 한국어 가톨릭 73권 본문의 합법적 공개 데이터와 CBCK 이용조건을 확인한다.
- [x] Public Domain `World English Bible (Catholic)` 73권을 Qwen으로 새 번역하는 경로를 결정한다.
- [x] WEB-C 원문을 내려받아 73권·장·절·권리 정보를 검증한다.
- [x] 요엘·말라키를 가톨릭식 장절 체계로 변환하고 경계 절을 검증한다.
- [x] 재개 가능한 Qwen 번역·체크포인트·자동 QA 파이프라인을 구현한다.
- [x] 전체 번역 완료 전에는 실행되지 않는 73권 검색·RAG 빌더를 구현한다.
- [x] 대표 장을 Qwen 80B로 번역해 가톨릭 용어와 장·절 정렬을 검수한다.
- [x] GCP Vertex AI Qwen MaaS에서 전체 73권 번역과 2차 교정을 완료한다.
- [x] 검색·브라우저·RAG를 비공인 기계 번역판으로 교체하고 회귀 검증한다.
- [x] 코드와 한국어 번역 데이터의 오픈 라이선스 경계를 명확히 문서화한다.
- [x] TXT·JSON·JSONL·Word·PDF 전체 본문 다운로드를 생성하고 검증한다.
- [x] 사이드바 3번째에 다운로드 화면을 추가하고 FAQ를 4번째로 옮긴다.
- [x] 다운로드 화면과 파일을 Cloudflare Pages에 재배포하고 실제 브라우저에서 확인한다.

## 완료

- [x] 취침 TTS에서 절 번호를 읽지 않고 장 제목과 본문만 이어 읽도록 수정했다.
- [x] 기기 내장 한국어 TTS 음성 목록과 기기 기본 음성을 연결했다.
- [x] 재생·일시정지·정지·속도·15~60분 취침 타이머를 구현했다.
- [x] 현재 절 강조와 다음 장 자동재생을 연결했다.
- [x] 데스크톱·모바일 화면, 음성 목록, 재생 실패 안내를 검증했다.
- [x] GitHub `main`과 Cloudflare Pages 운영 주소에 TTS를 반영하고 음성 목록을 확인했다.
- [x] 사이드바에 `RAG 검색`, `성경 브라우저`, `FAQ` 화면을 구성했다.
- [x] 검색 결과를 선택하면 해당 책·장·절을 성경 브라우저에서 열고 강조한다.
- [x] 책·장·이전·다음 이동과 80~145% 글자 확대·축소 및 기기 저장을 구현했다.
- [x] 공유 가능한 읽기 URL과 기존 구절 링크 호환을 구현했다.
- [x] 데스크톱·모바일 화면 및 기존 검색·데이터 회귀 검사를 통과했다.
- [x] GitHub `main`과 Cloudflare Pages 운영 주소에 반영하고 실제 검색-읽기 흐름을 확인했다.
- [x] `RIHP_RAG`에서 계승할 정적 검색·RAG 구조를 확인했다.
- [x] Public Domain으로 명시된 Korean Bible 1910 원본을 확보했다.
- [x] 절 단위 검색 데이터와 장 단위 RAG 생성기를 구현했다.
- [x] 한국어 성경 검색 UI와 필터·구절 링크 기능을 구현했다.
- [x] 데이터 무결성과 검색 회귀 검사를 추가했다.
- [x] Cloudflare Pages 프로젝트 `bibleframe`을 만들고 실배포 응답을 검증했다.
- [x] `bibleframe.pages.dev`의 HTML, 검색 JSON, RAG ZIP이 모두 `200`인지 확인했다.
- [x] GitHub 공개 저장소 `jsbang01357/BibleFrame`을 만들고 `main`을 푸시했다.
- [x] `bibleframe.jisong.dev`를 Pages에 연결하고 TLS 포함 `200` 응답을 확인했다.
- [x] 운영 주소에서 `요 3:16` 검색 결과와 브라우저 콘솔을 재검증했다.
- [x] RAG ZIP을 결정적으로 생성하도록 수정하고 연속 빌드 해시와 GitHub Actions 성공을 확인했다.
- [x] 전체 본문 다운로드를 결정적으로 생성하고 PDF·DOCX 전체 렌더와 실서비스 파일 응답을 확인했다.
- [x] GitHub 작업 브랜치와 초안 PR `#1`에 원문·번역·다운로드 산출물을 게시했다.

## 현재 요약

- 현재 운영 본문: Public Domain WEB-C 기반 한국어 가톨릭 정경 73권 기계 번역 초안
- 전환 원문: Public Domain World English Bible (Catholic) 73권
- 전환 장·절: 1,328장, 원문 레코드 35,408개
- 운영 주소: `https://bibleframe.jisong.dev`
- Pages 주소: `https://bibleframe.pages.dev`
- GitHub: `https://github.com/jsbang01357/BibleFrame`
- 이번 변경: Qwen3-Next 80B 전체 번역·2차 교정, 가톨릭 정경 73권 검색·RAG 전환
- 운영 배포: Cloudflare Pages 73권판 배포 및 HTML·JSON·RAG ZIP `200` 확인
- 남은 작업: GitHub 초안 PR `#1` 검토·병합
- 현재 진행: GitHub Actions 최종 확인

## 가톨릭 성경 전환 메모

- 전환 전 본문은 개신교 정경 66권 기반의 `Korean Bible 1910`이었다.
- 가톨릭 성경 전환에는 제2경전이 포함된 73권 본문과 가톨릭식 책 이름·순서가 필요하다.
- 현대 한국어 가톨릭 성경은 이용허락 확인 전까지 저장소나 배포물에 수록하지 않는다.
- CBCK는 개인 홈페이지의 본문 사용을 승인하지 않는다고 명시하므로 무단 수집 경로를 제외한다.
- 영어 Public Domain 73권인 `World English Bible (Catholic)`을 원문으로 사용해 자체 한국어 번역을 만든다.
- L4의 `Qwen3-14B-FP8`은 품질과 처리속도가 부족해 모델을 언디플로이했다.
- 전체 번역과 교정은 GCP 크레딧을 쓸 수 있는 `Qwen3-Next-80B-A3B-Instruct` MaaS로 진행한다.
- 번역 결과는 `가톨릭 정경 기반 · 비공인 기계 번역 초안`으로 표시하고 공용 번역본으로 오인시키지 않는다.
- 상세 검토: `qa/catholic-source-audit.md`
