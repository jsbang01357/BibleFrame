import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../site/index.html", import.meta.url), "utf8");
const app = readFileSync(new URL("../site/app.js", import.meta.url), "utf8");

for (const marker of ["id=\"ragAnswer\"", "id=\"ragSources\"", "id=\"chapterAudio\"", "id=\"ttsVoice\""]) {
  assert.ok(html.includes(marker), `HTML 누락: ${marker}`);
}
for (const marker of ["fetch(\"/api/rag\"", "fetch(\"/api/audio/manifest\"", "cloud:kore", "playCloudChapter", "data-rag-source"]) {
  assert.ok(app.includes(marker), `앱 연결 누락: ${marker}`);
}
assert.ok(app.includes("String(state.readerChapter).padStart(3, \"0\")"));
assert.ok(html.includes("절 번호 없는 장별 MP3"));

console.log("OK: Haystack RAG 화면 · 근거 이동 · GCP 장별 MP3 스트리밍 연결 검증 완료");
