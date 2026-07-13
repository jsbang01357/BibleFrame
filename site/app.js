import { normalize, parseReference, scoreVerse, termsFor } from "./search.mjs";

const state = { verses: [], books: [], query: "", testament: "", book: "" };
const el = {
  form: document.querySelector("#searchForm"), input: document.querySelector("#searchInput"),
  status: document.querySelector("#resultStatus"), results: document.querySelector("#results"),
  clear: document.querySelector("#clearButton"), testament: document.querySelector("#testamentFilter"),
  book: document.querySelector("#bookFilter"), bookCount: document.querySelector("#bookCount"),
  chapterCount: document.querySelector("#chapterCount"), verseCount: document.querySelector("#verseCount"),
};

const escapeHtml = (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function highlight(value, terms) {
  let output = escapeHtml(value);
  if (!terms.length) return output;
  const pattern = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "giu");
  return output.replace(pattern, "<mark>$1</mark>");
}

function resultCard(item, terms) {
  const reference = `${item.book} ${item.chapter}:${item.verse}`;
  const shareUrl = new URL(window.location.href);
  shareUrl.search = "";
  shareUrl.hash = item.id;
  return `<article class="verse-card" id="${escapeHtml(item.id)}">
    <div class="verse-meta"><span>${item.testament === "old" ? "구약" : "신약"}</span><span>${escapeHtml(item.code)}</span></div>
    <h3>${highlight(reference, terms)}</h3>
    <p>${highlight(item.text, terms)}</p>
    <button class="copy-link" type="button" data-link="${escapeHtml(shareUrl.href)}" data-reference="${escapeHtml(reference)}">구절 링크 복사</button>
  </article>`;
}

function render() {
  const terms = termsFor(state.query);
  const fullQuery = normalize(state.query);
  const directReference = parseReference(state.query, state.books);
  el.clear.hidden = !state.query && !state.testament && !state.book;
  if (!terms.length && !state.testament && !state.book) {
    el.status.textContent = "검색어를 입력하거나 빠른 검색을 선택하세요.";
    el.results.innerHTML = `<div class="empty"><strong>어떤 말씀을 찾고 있나요?</strong><p>책·장·절 또는 기억나는 본문 단어를 입력해보세요.</p></div>`;
    return;
  }
  const ranked = state.verses
    .filter((item) => !state.testament || item.testament === state.testament)
    .filter((item) => !state.book || item.code === state.book)
    .filter((item) => !directReference || (
      item.code === directReference.code &&
      item.chapter === directReference.chapter &&
      item.verse === directReference.verse
    ))
    .map((item) => ({ item, score: terms.length ? scoreVerse(item, terms, fullQuery) : 1 }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score || a.item._order - b.item._order)
    .slice(0, 100);
  el.status.textContent = ranked.length ? `관련 구절 ${ranked.length.toLocaleString("ko-KR")}개${ranked.length === 100 ? " (상위 100개)" : ""}` : "일치하는 구절이 없습니다.";
  el.results.innerHTML = ranked.length ? ranked.map(({ item }) => resultCard(item, terms)).join("") : `<div class="empty"><strong>다른 표현으로 찾아볼까요?</strong><p>검색어를 줄이거나 성경 필터를 전체로 바꿔보세요.</p></div>`;
}

function setQuery(value, updateUrl = true) {
  state.query = value.trim();
  el.input.value = value;
  if (updateUrl) {
    const url = new URL(window.location.href);
    state.query ? url.searchParams.set("q", state.query) : url.searchParams.delete("q");
    url.hash = "";
    history.replaceState(null, "", url);
  }
  render();
}

function populateBooks() {
  for (const book of state.books) {
    const option = document.createElement("option");
    option.value = book.code;
    option.textContent = book.name;
    option.dataset.testament = book.testament;
    el.book.append(option);
  }
}

el.form.addEventListener("submit", (event) => { event.preventDefault(); setQuery(el.input.value); });
let debounce;
let composing = false;
el.input.addEventListener("compositionstart", () => { composing = true; clearTimeout(debounce); });
el.input.addEventListener("compositionend", () => { composing = false; setQuery(el.input.value); });
el.input.addEventListener("input", (event) => { if (composing || event.isComposing) return; clearTimeout(debounce); debounce = setTimeout(() => setQuery(el.input.value), 160); });
el.testament.addEventListener("change", () => { state.testament = el.testament.value; if (state.book) { const book = state.books.find((item) => item.code === state.book); if (book?.testament !== state.testament && state.testament) { state.book = ""; el.book.value = ""; } } render(); });
el.book.addEventListener("change", () => { state.book = el.book.value; const book = state.books.find((item) => item.code === state.book); if (book) { state.testament = book.testament; el.testament.value = book.testament; } render(); });
el.clear.addEventListener("click", () => { state.testament = ""; state.book = ""; el.testament.value = ""; el.book.value = ""; setQuery(""); });
document.querySelectorAll("[data-query]").forEach((button) => button.addEventListener("click", () => { setQuery(button.dataset.query || ""); document.querySelector("#resultsTitle").scrollIntoView({ behavior: "smooth" }); }));
document.addEventListener("keydown", (event) => { if (event.key === "/" && document.activeElement !== el.input) { event.preventDefault(); el.input.focus(); } });
el.results.addEventListener("click", async (event) => { const button = event.target.closest(".copy-link"); if (!button) return; try { await navigator.clipboard.writeText(`${button.dataset.reference} · ${button.dataset.link}`); button.textContent = "복사했어요 ✓"; setTimeout(() => { button.textContent = "구절 링크 복사"; }, 1500); } catch { button.textContent = "복사하지 못했어요"; } });

async function boot() {
  try {
    const response = await fetch("./bible.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.books = payload.books;
    state.verses = payload.verses.map((item, index) => ({ ...item, _order: index, _haystack: normalize(`${item.book} ${item.short} ${item.code} ${item.english} ${item.chapter} ${item.verse} ${item.text}`) }));
    el.bookCount.textContent = payload.meta.books.toLocaleString("ko-KR");
    el.chapterCount.textContent = payload.meta.chapters.toLocaleString("ko-KR");
    el.verseCount.textContent = payload.meta.verses.toLocaleString("ko-KR");
    populateBooks();
    const url = new URL(window.location.href);
    setQuery(url.searchParams.get("q") || "", false);
    if (url.hash) document.querySelector(url.hash)?.scrollIntoView();
  } catch (error) {
    el.status.textContent = "성경 데이터를 불러오지 못했습니다.";
    el.results.innerHTML = `<div class="empty"><strong>데이터 로드 실패</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

boot();
