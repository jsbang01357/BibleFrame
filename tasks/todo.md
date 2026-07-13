# 작업 계획

## 진행 중

- 없음

## 완료

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

## 현재 요약

- 기준 본문: Korean Bible 1910
- 성경: 66권
- 장: 1,188장 (eBible.org 배포본 기준)
- 절: 30,991절
- 운영 주소: `https://bibleframe.jisong.dev`
- Pages 주소: `https://bibleframe.pages.dev`
- GitHub: `https://github.com/jsbang01357/BibleFrame`
- 이번 변경: 사이드바 3개 화면, 성경 브라우저, 본문 확대·축소, 검색 결과 연결
- 운영 배포 커밋: `46d7d30`
- 남은 작업: 없음
- 차단 사항: 없음
