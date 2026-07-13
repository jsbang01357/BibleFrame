# 작업 계획

## 진행 중

- 없음

## 완료

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

## 현재 요약

- 기준 본문: Korean Bible 1910
- 성경: 66권
- 장: 1,188장 (eBible.org 배포본 기준)
- 절: 30,991절
- 운영 주소: `https://bibleframe.jisong.dev`
- Pages 주소: `https://bibleframe.pages.dev`
- GitHub: `https://github.com/jsbang01357/BibleFrame`
- 차단 사항: 없음
