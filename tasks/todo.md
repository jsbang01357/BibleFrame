# 작업 계획

## 진행 중

- [ ] GitHub에 독립 저장소 `BibleFrame`을 만들고 `main`을 푸시한다.
- [ ] `bibleframe.jisong.dev` 사용자 지정 도메인을 연결하고 실제 응답을 확인한다.

## 완료

- [x] `RIHP_RAG`에서 계승할 정적 검색·RAG 구조를 확인했다.
- [x] Public Domain으로 명시된 Korean Bible 1910 원본을 확보했다.
- [x] 절 단위 검색 데이터와 장 단위 RAG 생성기를 구현했다.
- [x] 한국어 성경 검색 UI와 필터·구절 링크 기능을 구현했다.
- [x] 데이터 무결성과 검색 회귀 검사를 추가했다.
- [x] Cloudflare Pages 프로젝트 `bibleframe`을 만들고 실배포 응답을 검증했다.
- [x] `bibleframe.pages.dev`의 HTML, 검색 JSON, RAG ZIP이 모두 `200`인지 확인했다.

## 현재 요약

- 기준 본문: Korean Bible 1910
- 성경: 66권
- 장: 1,188장 (eBible.org 배포본 기준)
- 절: 30,991절
- 운영 예정 주소: `https://bibleframe.jisong.dev`
- 현재 공개 주소: `https://bibleframe.pages.dev`
- 차단 사항: GitHub CLI 재로그인, Cloudflare 대시보드 로그인 후 사용자 지정 도메인 연결
