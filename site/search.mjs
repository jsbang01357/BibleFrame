const STOP_WORDS = new Set([
  "성경", "말씀", "구절", "내용", "관련", "대해", "대한", "에서", "으로", "에게",
  "무엇", "뭐라고", "어떻게", "알려줘", "찾아줘", "보여줘", "하는", "있는", "것은",
]);
const REFERENCE_ALIASES = {
  JHN: ["요", "요한복음", "요한 복음"],
  MAT: ["마태오복음", "마태오 복음"],
  MRK: ["마르코복음", "마르코 복음"],
  LUK: ["루카복음", "루카 복음"],
  REV: ["묵시록", "요한묵시록"],
};

export function normalize(value) {
  return String(value)
    .normalize("NFKC")
    .toLocaleLowerCase("ko-KR")
    .replace(/(\d+)\s*장/g, " $1 ")
    .replace(/(\d+)\s*절/g, " $1 ")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function termsFor(query) {
  const stripParticle = (term) => {
    if (!/[가-힣]/.test(term) || term.length < 3) return term;
    return term.replace(/(에게서|으로부터|이라고|라는|에는|에서|으로|에게|한테|까지|부터|처럼|보다|이나|라도|이며|하고|과|와|을|를|은|는|이|가|에|의|도|만)$/u, "");
  };
  return [...new Set(normalize(query).split(" ").map(stripParticle))]
    .filter(Boolean)
    .filter((term) => !STOP_WORDS.has(term))
    .filter((term) => term.length > 1 || /^\d+$/.test(term));
}

export function parseReference(query, books) {
  const normalized = normalize(query);
  const aliases = books
    .flatMap((book) => [book.name, book.short, book.code, book.english, ...(REFERENCE_ALIASES[book.code] || [])].map((alias) => ({
      alias: normalize(alias), code: book.code,
    })))
    .sort((a, b) => b.alias.length - a.alias.length);
  for (const candidate of aliases) {
    if (!normalized.startsWith(`${candidate.alias} `)) continue;
    const match = normalized.slice(candidate.alias.length).trim().match(/^(\d+)\s+(\d+)$/);
    if (match) return { code: candidate.code, chapter: Number(match[1]), verse: Number(match[2]) };
  }
  return null;
}

export function scoreVerse(item, terms, fullQuery) {
  if (!terms.length) return 0;
  const haystack = item._haystack || normalize(
    `${item.book} ${item.short} ${item.code} ${item.english} ${item.chapter} ${item.verse} ${item.text}`,
  );
  const matched = terms.filter((term) => haystack.includes(term));
  if (!matched.length) return 0;
  let score = matched.length * 12 + matched.reduce((sum, term) => sum + (normalize(item.text).includes(term) ? 5 : 0), 0);
  if (matched.length === terms.length) score += 35;
  const reference = normalize(`${item.book} ${item.chapter} ${item.verse}`);
  const shortReference = normalize(`${item.short} ${item.chapter} ${item.verse}`);
  if (fullQuery && (reference === fullQuery || shortReference === fullQuery)) score += 200;
  return score;
}
