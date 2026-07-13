import { normalize, parseReference, scoreVerse, termsFor } from "./search.mjs";

const FONT_SIZES = [19, 24, 29, 35];
const FONT_LABELS = [80, 100, 120, 145];
const state = {
  verses: [], books: [], chapters: new Map(), query: "", testament: "", book: "",
  view: "search", readerBook: "GEN", readerChapter: 1, readerVerse: null, fontStep: 1,
};
const el = {
  form: document.querySelector("#searchForm"), input: document.querySelector("#searchInput"),
  status: document.querySelector("#resultStatus"), results: document.querySelector("#results"),
  resultsTitle: document.querySelector("#resultsTitle"), clear: document.querySelector("#clearButton"),
  testament: document.querySelector("#testamentFilter"), book: document.querySelector("#bookFilter"),
  bookCount: document.querySelector("#bookCount"), chapterCount: document.querySelector("#chapterCount"),
  verseCount: document.querySelector("#verseCount"), readerBook: document.querySelector("#readerBook"),
  readerChapter: document.querySelector("#readerChapter"), chapterHeading: document.querySelector("#chapterHeading"),
  chapterReading: document.querySelector("#chapterReading"), previousChapter: document.querySelector("#previousChapter"),
  nextChapter: document.querySelector("#nextChapter"), fontDecrease: document.querySelector("#fontDecrease"),
  fontReset: document.querySelector("#fontReset"), fontIncrease: document.querySelector("#fontIncrease"),
  fontScale: document.querySelector("#fontScale"),
};

const escapeHtml = (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function highlight(value, terms) {
  let output = escapeHtml(value);
  if (!terms.length) return output;
  const pattern = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "giu");
  return output.replace(pattern, "<mark>$1</mark>");
}

function readerUrlFor(item) {
  const url = new URL(window.location.href);
  url.searchParams.delete("q");
  url.searchParams.set("view", "reader");
  url.searchParams.set("book", item.code);
  url.searchParams.set("chapter", item.chapter);
  url.searchParams.set("verse", item.verse);
  url.hash = "";
  return url.href;
}

function resultCard(item, terms) {
  const reference = `${item.book} ${item.chapter}:${item.verse}`;
  return `<article class="verse-card" id="${escapeHtml(item.id)}">
    <div class="verse-meta"><span>${item.testament === "old" ? "구약" : "신약"}</span><span>${escapeHtml(item.code)}</span></div>
    <button class="verse-open" type="button" data-open-verse data-code="${escapeHtml(item.code)}" data-chapter="${item.chapter}" data-verse="${item.verse}" aria-label="${escapeHtml(reference)} 성경 브라우저에서 읽기">
      <h3>${highlight(reference, terms)}</h3>
      <p>${highlight(item.text, terms)}</p>
      <span class="read-more">성경 브라우저에서 읽기 <span aria-hidden="true">→</span></span>
    </button>
    <button class="copy-link" type="button" data-link="${escapeHtml(readerUrlFor(item))}" data-reference="${escapeHtml(reference)}">구절 링크 복사</button>
  </article>`;
}

function renderSearch() {
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
    .filter((item) => !directReference || (item.code === directReference.code && item.chapter === directReference.chapter && item.verse === directReference.verse))
    .map((item) => ({ item, score: terms.length ? scoreVerse(item, terms, fullQuery) : 1 }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score || a.item._order - b.item._order)
    .slice(0, 100);
  el.status.textContent = ranked.length ? `관련 구절 ${ranked.length.toLocaleString("ko-KR")}개${ranked.length === 100 ? " (상위 100개)" : ""}` : "일치하는 구절이 없습니다.";
  el.results.innerHTML = ranked.length ? ranked.map(({ item }) => resultCard(item, terms)).join("") : `<div class="empty"><strong>다른 표현으로 찾아볼까요?</strong><p>검색어를 줄이거나 성경 필터를 전체로 바꿔보세요.</p></div>`;
}

function updateUrl(values, mode = "replace") {
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(values)) {
    if (value === null || value === undefined || value === "") url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  }
  url.hash = "";
  history[`${mode}State`](null, "", url);
}

function setQuery(value, updateAddress = true) {
  state.query = value.trim();
  el.input.value = value;
  if (updateAddress) updateUrl({ q: state.query || null });
  renderSearch();
}

function setView(view, { updateAddress = true, push = false, scroll = true } = {}) {
  state.view = ["search", "reader", "faq"].includes(view) ? view : "search";
  document.querySelectorAll("[data-view-panel]").forEach((panel) => { panel.hidden = panel.dataset.viewPanel !== state.view; });
  document.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === state.view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  });
  if (updateAddress) updateUrl({
    view: state.view === "search" ? null : state.view,
    book: state.view === "reader" ? state.readerBook : null,
    chapter: state.view === "reader" ? state.readerChapter : null,
    verse: state.view === "reader" ? state.readerVerse : null,
  }, push ? "push" : "replace");
  if (state.view === "reader" && state.verses.length) renderReader({ focusVerse: false });
  if (scroll) window.scrollTo({ top: 0, behavior: "auto" });
}

function populateBooks() {
  for (const book of state.books) {
    const searchOption = document.createElement("option");
    searchOption.value = book.code;
    searchOption.textContent = book.name;
    searchOption.dataset.testament = book.testament;
    el.book.append(searchOption);

    const readerOption = document.createElement("option");
    readerOption.value = book.code;
    readerOption.textContent = `${book.name} (${book.short})`;
    el.readerBook.append(readerOption);
  }
}

function populateChapters() {
  const chapters = state.chapters.get(state.readerBook);
  const count = chapters ? Math.max(...chapters.keys()) : 1;
  state.readerChapter = Math.min(Math.max(Number(state.readerChapter) || 1, 1), count);
  el.readerChapter.innerHTML = Array.from({ length: count }, (_, index) => `<option value="${index + 1}">${index + 1}장</option>`).join("");
  el.readerBook.value = state.readerBook;
  el.readerChapter.value = String(state.readerChapter);
}

function renderReader({ focusVerse = false } = {}) {
  const book = state.books.find((item) => item.code === state.readerBook) || state.books[0];
  if (!book) return;
  state.readerBook = book.code;
  populateChapters();
  const verses = state.chapters.get(state.readerBook)?.get(state.readerChapter) || [];
  el.chapterHeading.textContent = `${book.name} ${state.readerChapter}장`;
  el.chapterReading.innerHTML = `<h2>${escapeHtml(book.name)} <span>${state.readerChapter}장</span></h2>` + verses.map((item) => {
    const selected = Number(state.readerVerse) === item.verse;
    return `<p id="reader-${escapeHtml(item.id)}" class="reader-verse${selected ? " selected" : ""}"><span class="verse-number" aria-label="${item.verse}절">${item.verse}</span>${escapeHtml(item.text)}</p>`;
  }).join("");

  const bookIndex = state.books.findIndex((item) => item.code === state.readerBook);
  const lastChapter = Math.max(...state.chapters.get(state.readerBook).keys());
  el.previousChapter.disabled = bookIndex === 0 && state.readerChapter === 1;
  el.nextChapter.disabled = bookIndex === state.books.length - 1 && state.readerChapter === lastChapter;

  if (focusVerse && state.readerVerse) {
    requestAnimationFrame(() => document.querySelector(".reader-verse.selected")?.scrollIntoView({ behavior: reducedMotion(), block: "center" }));
  }
}

function openReader(code, chapter, verse = null, { push = true } = {}) {
  if (!state.chapters.has(code)) return;
  state.readerBook = code;
  state.readerChapter = Number(chapter) || 1;
  state.readerVerse = verse ? Number(verse) : null;
  setView("reader", { updateAddress: false, scroll: false });
  renderReader({ focusVerse: true });
  updateUrl({ view: "reader", book: state.readerBook, chapter: state.readerChapter, verse: state.readerVerse }, push ? "push" : "replace");
}

function moveChapter(direction) {
  const bookIndex = state.books.findIndex((item) => item.code === state.readerBook);
  const lastChapter = Math.max(...state.chapters.get(state.readerBook).keys());
  if (direction < 0 && state.readerChapter > 1) state.readerChapter -= 1;
  else if (direction > 0 && state.readerChapter < lastChapter) state.readerChapter += 1;
  else {
    const nextBook = state.books[bookIndex + direction];
    if (!nextBook) return;
    state.readerBook = nextBook.code;
    const nextChapters = state.chapters.get(state.readerBook);
    state.readerChapter = direction > 0 ? 1 : Math.max(...nextChapters.keys());
  }
  state.readerVerse = null;
  renderReader();
  updateUrl({ view: "reader", book: state.readerBook, chapter: state.readerChapter, verse: null });
  document.querySelector(".reader-controls")?.scrollIntoView({ behavior: reducedMotion(), block: "start" });
}

function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

function applyFontStep(step, persist = true) {
  state.fontStep = Math.min(Math.max(Number(step) || 0, 0), FONT_SIZES.length - 1);
  document.documentElement.style.setProperty("--reader-font-size", `${FONT_SIZES[state.fontStep]}px`);
  el.fontScale.textContent = `${FONT_LABELS[state.fontStep]}%`;
  el.fontDecrease.disabled = state.fontStep === 0;
  el.fontIncrease.disabled = state.fontStep === FONT_SIZES.length - 1;
  if (persist) {
    try { localStorage.setItem("bibleframe-font-step", String(state.fontStep)); } catch { /* 저장이 차단돼도 읽기는 계속된다. */ }
  }
}

function scrollToResults() {
  requestAnimationFrame(() => {
    el.input.blur();
    el.resultsTitle.scrollIntoView({ behavior: reducedMotion(), block: "start" });
  });
}

let debounce;
let composing = false;
el.form.addEventListener("submit", (event) => { event.preventDefault(); if (!composing) { setQuery(el.input.value); scrollToResults(); } });
el.input.addEventListener("compositionstart", () => { composing = true; clearTimeout(debounce); });
el.input.addEventListener("compositionend", () => { composing = false; setQuery(el.input.value); });
el.input.addEventListener("input", (event) => { if (composing || event.isComposing) return; clearTimeout(debounce); debounce = setTimeout(() => setQuery(el.input.value), 160); });
el.input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !composing && !event.isComposing) { event.preventDefault(); el.form.requestSubmit(); } });
el.testament.addEventListener("change", () => { state.testament = el.testament.value; if (state.book) { const book = state.books.find((item) => item.code === state.book); if (book?.testament !== state.testament && state.testament) { state.book = ""; el.book.value = ""; } } renderSearch(); });
el.book.addEventListener("change", () => { state.book = el.book.value; const book = state.books.find((item) => item.code === state.book); if (book) { state.testament = book.testament; el.testament.value = book.testament; } renderSearch(); });
el.clear.addEventListener("click", () => { state.testament = ""; state.book = ""; el.testament.value = ""; el.book.value = ""; setQuery(""); });
document.querySelectorAll("[data-query]").forEach((button) => button.addEventListener("click", () => { setQuery(button.dataset.query || ""); scrollToResults(); }));
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view, { push: true })));
document.addEventListener("keydown", (event) => { if (event.key === "/" && state.view === "search" && document.activeElement !== el.input) { event.preventDefault(); el.input.focus(); } });

el.results.addEventListener("click", async (event) => {
  const openButton = event.target.closest("[data-open-verse]");
  if (openButton) { openReader(openButton.dataset.code, openButton.dataset.chapter, openButton.dataset.verse); return; }
  const copyButton = event.target.closest(".copy-link");
  if (!copyButton) return;
  try {
    await navigator.clipboard.writeText(`${copyButton.dataset.reference} · ${copyButton.dataset.link}`);
    copyButton.textContent = "복사했어요 ✓";
    setTimeout(() => { copyButton.textContent = "구절 링크 복사"; }, 1500);
  } catch { copyButton.textContent = "복사하지 못했어요"; }
});

el.readerBook.addEventListener("change", () => { state.readerBook = el.readerBook.value; state.readerChapter = 1; state.readerVerse = null; renderReader(); updateUrl({ view: "reader", book: state.readerBook, chapter: 1, verse: null }); });
el.readerChapter.addEventListener("change", () => { state.readerChapter = Number(el.readerChapter.value); state.readerVerse = null; renderReader(); updateUrl({ view: "reader", book: state.readerBook, chapter: state.readerChapter, verse: null }); });
el.previousChapter.addEventListener("click", () => moveChapter(-1));
el.nextChapter.addEventListener("click", () => moveChapter(1));
el.fontDecrease.addEventListener("click", () => applyFontStep(state.fontStep - 1));
el.fontReset.addEventListener("click", () => applyFontStep(1));
el.fontIncrease.addEventListener("click", () => applyFontStep(state.fontStep + 1));

function applyUrlState() {
  const url = new URL(window.location.href);
  const requestedView = ["reader", "faq"].includes(url.searchParams.get("view")) ? url.searchParams.get("view") : "search";
  if (requestedView === "reader") {
    openReader(url.searchParams.get("book") || state.readerBook, url.searchParams.get("chapter") || 1, url.searchParams.get("verse"), { push: false });
  } else setView(requestedView, { updateAddress: false });
}
window.addEventListener("popstate", applyUrlState);

async function boot() {
  try {
    const response = await fetch("./bible.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.books = payload.books;
    state.verses = payload.verses.map((item, index) => ({ ...item, _order: index, _haystack: normalize(`${item.book} ${item.short} ${item.code} ${item.english} ${item.chapter} ${item.verse} ${item.text}`) }));
    for (const item of state.verses) {
      if (!state.chapters.has(item.code)) state.chapters.set(item.code, new Map());
      const bookChapters = state.chapters.get(item.code);
      if (!bookChapters.has(item.chapter)) bookChapters.set(item.chapter, []);
      bookChapters.get(item.chapter).push(item);
    }
    el.bookCount.textContent = payload.meta.books.toLocaleString("ko-KR");
    el.chapterCount.textContent = payload.meta.chapters.toLocaleString("ko-KR");
    el.verseCount.textContent = payload.meta.verses.toLocaleString("ko-KR");
    populateBooks();
    try { applyFontStep(Number(localStorage.getItem("bibleframe-font-step") ?? 1), false); } catch { applyFontStep(1, false); }
    const url = new URL(window.location.href);
    setQuery(url.searchParams.get("q") || "", false);
    const legacyVerse = url.hash ? state.verses.find((item) => item.id === url.hash.slice(1)) : null;
    if (legacyVerse) openReader(legacyVerse.code, legacyVerse.chapter, legacyVerse.verse, { push: false });
    else applyUrlState();
  } catch (error) {
    el.status.textContent = "성경 데이터를 불러오지 못했습니다.";
    el.results.innerHTML = `<div class="empty"><strong>데이터 로드 실패</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

boot();
