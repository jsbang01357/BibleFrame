import assert from "node:assert/strict";
import { normalize, parseReference, scoreVerse, termsFor } from "../site/search.mjs";

const verse = {
  code: "JOH", book: "요한복음", short: "요", english: "John",
  chapter: 3, verse: 16, text: "하나님이 세상을 이처럼 사랑하사 독생자를 주셨으니 영생을 얻게 하려 하심이니라",
};

assert.equal(normalize("요한복음 3장 16절"), "요한복음 3 16");
assert.deepEqual(termsFor("사랑에 대해 성경 구절 찾아줘"), ["사랑"]);
assert.ok(scoreVerse(verse, termsFor("사랑에 대해 알려줘"), normalize("사랑에 대해 알려줘")) > 0);
assert.ok(scoreVerse(verse, termsFor("요한복음 3장 16절"), normalize("요한복음 3장 16절")) > 200);
assert.ok(scoreVerse(verse, termsFor("독생자 영생"), normalize("독생자 영생")) > 50);
assert.equal(scoreVerse(verse, termsFor("모세"), normalize("모세")), 0);
const books = [{ code: "JOH", name: "요한복음", short: "요", english: "John" }];
assert.deepEqual(parseReference("요한복음 3장 16절", books), { code: "JOH", chapter: 3, verse: 16 });
assert.deepEqual(parseReference("요 3:16", books), { code: "JOH", chapter: 3, verse: 16 });
assert.equal(parseReference("요한복음 사랑", books), null);

console.log("OK: 검색 정규화·구절 일치·본문 점수 검증 완료");
