import assert from "node:assert/strict";
import { normalize, parseReference, pickRandomVerse, scoreVerse, termsFor } from "../site/search.mjs";

const verse = {
  code: "JHN", book: "요한 복음서", short: "요한", english: "John",
  chapter: 3, verse: 16, text: "하느님께서는 세상을 이토록 사랑하시어 외아들을 내주셨다. 그를 믿는 사람은 누구나 멸망하지 않고 영원한 생명을 얻게 하려는 것이다.",
};

assert.equal(normalize("요한 복음서 3장 16절"), "요한 복음서 3 16");
assert.deepEqual(termsFor("사랑에 대해 성경 구절 찾아줘"), ["사랑"]);
assert.ok(scoreVerse(verse, termsFor("사랑에 대해 알려줘"), normalize("사랑에 대해 알려줘")) > 0);
assert.ok(scoreVerse(verse, termsFor("요한 복음서 3장 16절"), normalize("요한 복음서 3장 16절")) > 200);
assert.ok(scoreVerse(verse, termsFor("외아들 생명"), normalize("외아들 생명")) > 50);
assert.equal(scoreVerse(verse, termsFor("모세"), normalize("모세")), 0);
const books = [{ code: "JHN", name: "요한 복음서", short: "요한", english: "John" }];
assert.deepEqual(parseReference("요한 복음서 3장 16절", books), { code: "JHN", chapter: 3, verse: 16 });
assert.deepEqual(parseReference("요한복음 3:16", books), { code: "JHN", chapter: 3, verse: 16 });
assert.deepEqual(parseReference("요 3:16", books), { code: "JHN", chapter: 3, verse: 16 });
assert.equal(parseReference("요한복음 사랑", books), null);

const randomVerses = [{ id: "GEN-1-1" }, { id: "JHN-3-16" }, { id: "REV-22-21" }];
assert.equal(pickRandomVerse([], () => 0), null);
assert.equal(pickRandomVerse(randomVerses, () => 0)?.id, "GEN-1-1");
assert.equal(pickRandomVerse(randomVerses, () => 0.999)?.id, "REV-22-21");
assert.equal(pickRandomVerse(randomVerses, () => 0, "GEN-1-1")?.id, "JHN-3-16");
assert.equal(pickRandomVerse(randomVerses, () => Number.NaN)?.id, "GEN-1-1");

console.log("OK: 검색 정규화·구절 일치·본문 점수·랜덤 말씀 검증 완료");
