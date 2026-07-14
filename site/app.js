import { normalize, parseReference, pickRandomVerse, scoreVerse, termsFor } from "./search.mjs?v=20260714-gcp-rag-audio-1";

const FONT_SIZES = [19, 24, 29, 35];
const FONT_LABELS = [80, 100, 120, 145];
const state = {
  verses: [], books: [], chapters: new Map(), query: "", testament: "", book: "",
  view: "search", readerBook: "GEN", readerChapter: 1, readerVerse: null, fontStep: 1, lastLuckyId: null,
  ragRequestId: 0,
};
const ttsState = {
  active: false, paused: false, verseIndex: 0, generation: 0,
  timerId: null, expiresAt: null, voices: [], utterance: null, mode: null, manifest: null,
};
const el = {
  form: document.querySelector("#searchForm"), input: document.querySelector("#searchInput"),
  lucky: document.querySelector("#luckyButton"),
  ragAnswer: document.querySelector("#ragAnswer"), ragStatus: document.querySelector("#ragStatus"),
  ragText: document.querySelector("#ragText"), ragSources: document.querySelector("#ragSources"),
  ragMode: document.querySelector("#ragMode"),
  status: document.querySelector("#resultStatus"), results: document.querySelector("#results"),
  resultsTitle: document.querySelector("#resultsTitle"), clear: document.querySelector("#clearButton"),
  testament: document.querySelector("#testamentFilter"), book: document.querySelector("#bookFilter"),
  bookCount: document.querySelector("#bookCount"), chapterCount: document.querySelector("#chapterCount"),
  verseCount: document.querySelector("#verseCount"), readerBook: document.querySelector("#readerBook"),
  readerChapter: document.querySelector("#readerChapter"), chapterHeading: document.querySelector("#chapterHeading"),
  chapterReading: document.querySelector("#chapterReading"), previousChapter: document.querySelector("#previousChapter"),
  nextChapter: document.querySelector("#nextChapter"), fontDecrease: document.querySelector("#fontDecrease"),
  fontReset: document.querySelector("#fontReset"), fontIncrease: document.querySelector("#fontIncrease"),
  fontScale: document.querySelector("#fontScale"), ttsVoice: document.querySelector("#ttsVoice"),
  ttsRate: document.querySelector("#ttsRate"), ttsTimer: document.querySelector("#ttsTimer"),
  ttsPlay: document.querySelector("#ttsPlay"), ttsStop: document.querySelector("#ttsStop"),
  ttsAutoNext: document.querySelector("#ttsAutoNext"), ttsStatus: document.querySelector("#ttsStatus"),
  chapterAudio: document.querySelector("#chapterAudio"),
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
  const nextQuery = value.trim();
  if (nextQuery !== state.query) clearRagAnswer();
  state.query = nextQuery;
  el.input.value = value;
  if (updateAddress) updateUrl({ q: state.query || null });
  renderSearch();
}

function clearRagAnswer() {
  state.ragRequestId += 1;
  el.ragAnswer.hidden = true;
  el.ragStatus.textContent = "";
  el.ragText.textContent = "";
  el.ragSources.replaceChildren();
}

function renderRagAnswer(payload) {
  el.ragMode.textContent = payload.mode === "hybrid" ? "BM25 + Vertex 의미 검색" : "BM25 검색";
  el.ragStatus.textContent = "비공인 기계 번역 초안에 근거한 AI 답변입니다.";
  el.ragText.innerHTML = escapeHtml(payload.answer || "답변을 만들지 못했습니다.").replaceAll("\n", "<br />");
  el.ragSources.innerHTML = (payload.sources || []).map((source) => `
    <button type="button" data-rag-source data-code="${escapeHtml(source.book_code)}" data-chapter="${source.chapter}" data-verse="${source.verse_start}">
      <span>[${source.index}]</span><strong>${escapeHtml(source.reference)}</strong><small>성경 브라우저에서 읽기 →</small>
    </button>`).join("");
}

async function requestRagAnswer(query) {
  const trimmed = query.trim();
  if (trimmed.length < 2) { clearRagAnswer(); return; }
  const requestId = ++state.ragRequestId;
  el.ragAnswer.hidden = false;
  el.ragMode.textContent = "BM25 + Vertex 의미 검색";
  el.ragStatus.textContent = "관련 본문을 찾고 답변을 만들고 있어요…";
  el.ragText.textContent = "";
  el.ragSources.replaceChildren();
  try {
    const response = await fetch("/api/rag", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: trimmed, top_k: 6 }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (requestId !== state.ragRequestId) return;
    renderRagAnswer(payload);
  } catch {
    if (requestId !== state.ragRequestId) return;
    el.ragStatus.textContent = "말씀 길잡이에 잠시 연결하지 못했어요. 아래 정확한 구절 검색은 그대로 사용할 수 있습니다.";
    el.ragText.textContent = "";
  }
}

function setView(view, { updateAddress = true, push = false, scroll = true } = {}) {
  state.view = ["search", "reader", "downloads", "faq"].includes(view) ? view : "search";
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

function openLuckyVerse() {
  const item = pickRandomVerse(state.verses, Math.random, state.lastLuckyId);
  if (!item) return;
  state.lastLuckyId = item.id;
  openReader(item.code, item.chapter, item.verse);
}

function moveChapter(direction, { scroll = true, stopAudio = true } = {}) {
  if (stopAudio && ttsState.active) stopReading("장을 이동해 재생을 멈췄어요.");
  const bookIndex = state.books.findIndex((item) => item.code === state.readerBook);
  const lastChapter = Math.max(...state.chapters.get(state.readerBook).keys());
  if (direction < 0 && state.readerChapter > 1) state.readerChapter -= 1;
  else if (direction > 0 && state.readerChapter < lastChapter) state.readerChapter += 1;
  else {
    const nextBook = state.books[bookIndex + direction];
    if (!nextBook) return false;
    state.readerBook = nextBook.code;
    const nextChapters = state.chapters.get(state.readerBook);
    state.readerChapter = direction > 0 ? 1 : Math.max(...nextChapters.keys());
  }
  state.readerVerse = null;
  renderReader();
  updateUrl({ view: "reader", book: state.readerBook, chapter: state.readerChapter, verse: null });
  if (scroll) document.querySelector(".reader-controls")?.scrollIntoView({ behavior: reducedMotion(), block: "start" });
  return true;
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

function speechSupported() {
  return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

function getStoredSetting(key, fallback = "") {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}

function storeSetting(key, value) {
  try { localStorage.setItem(key, String(value)); } catch { /* 설정 저장이 막혀도 재생은 계속된다. */ }
}

function populateVoices() {
  const stored = getStoredSetting("bibleframe-tts-voice");
  const selected = stored || (ttsState.manifest ? "cloud:kore" : el.ttsVoice.value);
  const voices = speechSupported() ? window.speechSynthesis.getVoices() : [];
  const koreanVoices = voices.filter((voice) => /^ko(?:-|_)/i.test(voice.lang));
  ttsState.voices = (koreanVoices.length ? koreanVoices : voices).sort((a, b) => a.name.localeCompare(b.name, "ko"));
  el.ttsVoice.replaceChildren();
  for (const voice of ttsState.manifest?.voices || []) {
    el.ttsVoice.append(new Option(`${voice.name} · GCP MP3`, `cloud:${voice.id}`));
  }
  if (speechSupported()) el.ttsVoice.append(new Option("기기 기본 음성 · 실시간", "device:"));
  for (const voice of ttsState.voices) {
    const suffix = voice.localService ? "" : " · 온라인";
    el.ttsVoice.append(new Option(`${voice.name} (${voice.lang})${suffix}`, `device:${voice.voiceURI}`));
  }
  const options = [...el.ttsVoice.options];
  if (options.some((option) => option.value === selected)) el.ttsVoice.value = selected;
  else if (options.some((option) => option.value === "cloud:kore")) el.ttsVoice.value = "cloud:kore";
  else if (options.length) el.ttsVoice.selectedIndex = 0;
  el.ttsPlay.disabled = options.length === 0;
  if (!ttsState.active) {
    const cloudCount = ttsState.manifest?.voices?.length || 0;
    if (cloudCount) el.ttsStatus.textContent = `장별 MP3 ${cloudCount}개 목소리 · 절 번호 없이 이어서 들을 수 있어요.`;
    else if (options.length) el.ttsStatus.textContent = `기기 음성 ${Math.max(ttsState.voices.length, 1)}개 · 목소리와 시간을 고른 뒤 재생해보세요.`;
    else el.ttsStatus.textContent = "이 브라우저에서 사용할 수 있는 음성을 찾지 못했어요.";
  }
}

function cloudVoiceId() {
  return el.ttsVoice.value.startsWith("cloud:") ? el.ttsVoice.value.slice(6) : null;
}

function selectedDeviceVoice() {
  if (!el.ttsVoice.value.startsWith("device:")) return null;
  const voiceUri = el.ttsVoice.value.slice(7);
  return ttsState.voices.find((voice) => voice.voiceURI === voiceUri) || null;
}

function cloudAudioUrl() {
  const voice = cloudVoiceId();
  const manifest = ttsState.manifest;
  if (!voice || !manifest) return null;
  const path = manifest.path_template
    .replace("{voice}", voice)
    .replace("{book}", state.readerBook)
    .replace("{chapter_padded}", String(state.readerChapter).padStart(3, "0"));
  return `${manifest.base_url.replace(/\/$/, "")}/${path}`;
}

function resetCloudAudio(clearSource = true) {
  el.chapterAudio.pause();
  try { el.chapterAudio.currentTime = 0; } catch { /* 메타데이터 로드 전에는 이동할 수 없다. */ }
  if (clearSource) {
    el.chapterAudio.removeAttribute("src");
    el.chapterAudio.load();
  }
}

function updateTtsButtons() {
  el.ttsPlay.textContent = ttsState.active ? (ttsState.paused ? "▶ 계속 듣기" : "Ⅱ 일시정지") : "▶ 재생";
  el.ttsStop.disabled = !ttsState.active;
  el.ttsPlay.setAttribute("aria-pressed", String(ttsState.active && !ttsState.paused));
}

function clearSleepTimer() {
  if (ttsState.timerId) clearTimeout(ttsState.timerId);
  ttsState.timerId = null;
  ttsState.expiresAt = null;
}

function scheduleSleepTimer() {
  clearSleepTimer();
  const minutes = Number(el.ttsTimer.value);
  if (!minutes || !ttsState.active) return;
  ttsState.expiresAt = Date.now() + minutes * 60_000;
  ttsState.timerId = setTimeout(() => stopReading("취침 타이머가 끝나 재생을 멈췄어요."), minutes * 60_000);
}

function currentChapterVerses() {
  return state.chapters.get(state.readerBook)?.get(state.readerChapter) || [];
}

function markSpeakingVerse(item) {
  document.querySelectorAll(".reader-verse.speaking").forEach((verse) => verse.classList.remove("speaking"));
  const target = document.querySelector(`#reader-${item.id}`);
  target?.classList.add("speaking");
  if (target) {
    const bounds = target.getBoundingClientRect();
    if (bounds.top < 100 || bounds.bottom > window.innerHeight - 80) target.scrollIntoView({ behavior: reducedMotion(), block: "center" });
  }
}

function finishReading(message = "이 장을 모두 읽었어요.") {
  clearSleepTimer();
  ttsState.active = false;
  ttsState.paused = false;
  ttsState.utterance = null;
  ttsState.mode = null;
  document.querySelectorAll(".reader-verse.speaking").forEach((verse) => verse.classList.remove("speaking"));
  el.ttsStatus.textContent = message;
  updateTtsButtons();
}

function stopReading(message = "재생을 멈췄어요.") {
  ttsState.generation += 1;
  if (speechSupported()) window.speechSynthesis.cancel();
  resetCloudAudio();
  finishReading(message);
}

async function playCloudChapter(generation) {
  if (!ttsState.active || ttsState.mode !== "cloud" || generation !== ttsState.generation) return;
  const source = cloudAudioUrl();
  if (!source) { stopReading("장별 MP3 주소를 만들지 못했어요. 기기 음성을 선택해보세요."); return; }
  document.querySelectorAll(".reader-verse.speaking").forEach((verse) => verse.classList.remove("speaking"));
  if (el.chapterAudio.src !== source) {
    el.chapterAudio.src = source;
    el.chapterAudio.load();
  }
  el.chapterAudio.playbackRate = Number(el.ttsRate.value) || 1;
  el.chapterAudio.preservesPitch = true;
  const book = state.books.find((entry) => entry.code === state.readerBook);
  const timerText = ttsState.expiresAt ? ` · ${el.ttsTimer.value}분 후 자동 정지` : "";
  el.ttsStatus.textContent = `${book?.name || state.readerBook} ${state.readerChapter}장 MP3 연결 중${timerText}`;
  try {
    await el.chapterAudio.play();
  } catch {
    if (generation === ttsState.generation) stopReading("장별 MP3를 재생하지 못했어요. 기기 음성을 선택하거나 잠시 뒤 다시 시도해주세요.");
  }
}

function speakCurrentVerse(generation) {
  if (!ttsState.active || generation !== ttsState.generation) return;
  const verses = currentChapterVerses();
  if (ttsState.verseIndex >= verses.length) {
    if (el.ttsAutoNext.checked && moveChapter(1, { scroll: false, stopAudio: false })) {
      ttsState.verseIndex = 0;
      setTimeout(() => speakCurrentVerse(generation), 180);
    } else finishReading("마지막 장까지 모두 읽었어요.");
    return;
  }

  const item = verses[ttsState.verseIndex];
  const book = state.books.find((entry) => entry.code === state.readerBook);
  const heading = ttsState.verseIndex === 0 ? `${book?.name || item.book} ${state.readerChapter}장. ` : "";
  const utterance = new SpeechSynthesisUtterance(`${heading}${item.text}`);
  const selectedVoice = selectedDeviceVoice();
  if (selectedVoice) utterance.voice = selectedVoice;
  utterance.lang = selectedVoice?.lang || "ko-KR";
  utterance.rate = Number(el.ttsRate.value) || 0.9;
  utterance.pitch = 0.95;
  ttsState.utterance = utterance;
  utterance.onstart = () => {
    if (generation !== ttsState.generation) return;
    markSpeakingVerse(item);
    const timerText = ttsState.expiresAt ? ` · ${el.ttsTimer.value}분 후 자동 정지` : "";
    el.ttsStatus.textContent = `${item.book} ${item.chapter}장 ${item.verse}절 읽는 중${timerText}`;
  };
  utterance.onend = () => {
    if (!ttsState.active || generation !== ttsState.generation) return;
    ttsState.verseIndex += 1;
    speakCurrentVerse(generation);
  };
  utterance.onerror = (event) => {
    if (generation !== ttsState.generation || ["canceled", "interrupted"].includes(event.error)) return;
    stopReading("음성을 재생하지 못했어요. 다른 목소리를 선택해보세요.");
  };
  window.speechSynthesis.speak(utterance);
}

function toggleReading() {
  const cloudSelected = Boolean(cloudVoiceId());
  if (!cloudSelected && !speechSupported()) {
    el.ttsStatus.textContent = "이 브라우저는 기기 음성 읽기를 지원하지 않아요. GCP MP3를 선택해보세요.";
    return;
  }
  if (ttsState.active) {
    if (ttsState.paused) {
      if (ttsState.mode === "cloud") el.chapterAudio.play().catch(() => stopReading("MP3 재생을 다시 시작하지 못했어요."));
      else window.speechSynthesis.resume();
      ttsState.paused = false;
      el.ttsStatus.textContent = "말씀 읽기를 계속합니다.";
    } else {
      if (ttsState.mode === "cloud") el.chapterAudio.pause();
      else window.speechSynthesis.pause();
      ttsState.paused = true;
      el.ttsStatus.textContent = "잠시 멈췄어요.";
    }
    updateTtsButtons();
    return;
  }

  const verses = currentChapterVerses();
  if (!verses.length) return;
  ttsState.generation += 1;
  if (speechSupported()) window.speechSynthesis.cancel();
  resetCloudAudio();
  ttsState.active = true;
  ttsState.paused = false;
  ttsState.mode = cloudSelected ? "cloud" : "device";
  const selectedIndex = state.readerVerse ? verses.findIndex((item) => item.verse === Number(state.readerVerse)) : -1;
  ttsState.verseIndex = cloudSelected ? 0 : (selectedIndex >= 0 ? selectedIndex : 0);
  storeSetting("bibleframe-tts-voice", el.ttsVoice.value);
  storeSetting("bibleframe-tts-rate", el.ttsRate.value);
  storeSetting("bibleframe-tts-timer", el.ttsTimer.value);
  storeSetting("bibleframe-tts-auto-next", el.ttsAutoNext.checked ? "1" : "0");
  scheduleSleepTimer();
  updateTtsButtons();
  if (cloudSelected) playCloudChapter(ttsState.generation);
  else speakCurrentVerse(ttsState.generation);
}

async function initTts() {
  el.ttsRate.value = getStoredSetting("bibleframe-tts-rate", "0.9");
  el.ttsTimer.value = getStoredSetting("bibleframe-tts-timer", "30");
  el.ttsAutoNext.checked = getStoredSetting("bibleframe-tts-auto-next", "1") !== "0";
  populateVoices();
  if (speechSupported()) {
    if (window.speechSynthesis.addEventListener) window.speechSynthesis.addEventListener("voiceschanged", populateVoices);
    else window.speechSynthesis.onvoiceschanged = populateVoices;
  }
  try {
    const response = await fetch("/api/audio/manifest");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const manifest = await response.json();
    if (!Array.isArray(manifest.voices) || !manifest.path_template) throw new Error("manifest format");
    ttsState.manifest = manifest;
    populateVoices();
  } catch {
    ttsState.manifest = null;
    populateVoices();
  }
  updateTtsButtons();
}

function scrollToResults() {
  requestAnimationFrame(() => {
    el.input.blur();
    el.resultsTitle.scrollIntoView({ behavior: reducedMotion(), block: "start" });
  });
}

let debounce;
let composing = false;
el.form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!composing) {
    setQuery(el.input.value);
    requestRagAnswer(el.input.value);
    scrollToResults();
  }
});
el.lucky.addEventListener("click", openLuckyVerse);
el.input.addEventListener("compositionstart", () => { composing = true; clearTimeout(debounce); });
el.input.addEventListener("compositionend", () => { composing = false; setQuery(el.input.value); });
el.input.addEventListener("input", (event) => { if (composing || event.isComposing) return; clearTimeout(debounce); debounce = setTimeout(() => setQuery(el.input.value), 160); });
el.input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !composing && !event.isComposing) { event.preventDefault(); el.form.requestSubmit(); } });
el.testament.addEventListener("change", () => { state.testament = el.testament.value; if (state.book) { const book = state.books.find((item) => item.code === state.book); if (book?.testament !== state.testament && state.testament) { state.book = ""; el.book.value = ""; } } renderSearch(); });
el.book.addEventListener("change", () => { state.book = el.book.value; const book = state.books.find((item) => item.code === state.book); if (book) { state.testament = book.testament; el.testament.value = book.testament; } renderSearch(); });
el.clear.addEventListener("click", () => { state.testament = ""; state.book = ""; el.testament.value = ""; el.book.value = ""; setQuery(""); clearRagAnswer(); });
document.querySelectorAll("[data-query]").forEach((button) => button.addEventListener("click", () => {
  const query = button.dataset.query || "";
  setQuery(query);
  requestRagAnswer(query);
  scrollToResults();
}));
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => {
  if (button.dataset.view !== "reader" && ttsState.active) stopReading();
  setView(button.dataset.view, { push: true });
}));
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

el.ragSources.addEventListener("click", (event) => {
  const source = event.target.closest("[data-rag-source]");
  if (source) openReader(source.dataset.code, source.dataset.chapter, source.dataset.verse);
});

el.readerBook.addEventListener("change", () => { if (ttsState.active) stopReading("성경을 바꿔 재생을 멈췄어요."); state.readerBook = el.readerBook.value; state.readerChapter = 1; state.readerVerse = null; renderReader(); updateUrl({ view: "reader", book: state.readerBook, chapter: 1, verse: null }); });
el.readerChapter.addEventListener("change", () => { if (ttsState.active) stopReading("장을 바꿔 재생을 멈췄어요."); state.readerChapter = Number(el.readerChapter.value); state.readerVerse = null; renderReader(); updateUrl({ view: "reader", book: state.readerBook, chapter: state.readerChapter, verse: null }); });
el.previousChapter.addEventListener("click", () => moveChapter(-1));
el.nextChapter.addEventListener("click", () => moveChapter(1));
el.fontDecrease.addEventListener("click", () => applyFontStep(state.fontStep - 1));
el.fontReset.addEventListener("click", () => applyFontStep(1));
el.fontIncrease.addEventListener("click", () => applyFontStep(state.fontStep + 1));
el.ttsPlay.addEventListener("click", toggleReading);
el.ttsStop.addEventListener("click", () => stopReading());
el.ttsVoice.addEventListener("change", () => { storeSetting("bibleframe-tts-voice", el.ttsVoice.value); if (ttsState.active) stopReading("목소리를 바꿨어요. 다시 재생해주세요."); });
el.ttsRate.addEventListener("change", () => { storeSetting("bibleframe-tts-rate", el.ttsRate.value); if (ttsState.active) stopReading("읽기 속도를 바꿨어요. 다시 재생해주세요."); });
el.ttsTimer.addEventListener("change", () => { storeSetting("bibleframe-tts-timer", el.ttsTimer.value); if (ttsState.active) { scheduleSleepTimer(); el.ttsStatus.textContent = Number(el.ttsTimer.value) ? `${el.ttsTimer.value}분 후 자동으로 멈춥니다.` : "취침 타이머를 해제했어요."; } });
el.ttsAutoNext.addEventListener("change", () => storeSetting("bibleframe-tts-auto-next", el.ttsAutoNext.checked ? "1" : "0"));
el.chapterAudio.addEventListener("playing", () => {
  if (!ttsState.active || ttsState.mode !== "cloud") return;
  const book = state.books.find((entry) => entry.code === state.readerBook);
  const timerText = ttsState.expiresAt ? ` · ${el.ttsTimer.value}분 후 자동 정지` : "";
  el.ttsStatus.textContent = `${book?.name || state.readerBook} ${state.readerChapter}장 듣는 중${timerText}`;
});
el.chapterAudio.addEventListener("ended", () => {
  if (!ttsState.active || ttsState.mode !== "cloud") return;
  const generation = ttsState.generation;
  if (el.ttsAutoNext.checked && moveChapter(1, { scroll: false, stopAudio: false })) playCloudChapter(generation);
  else finishReading("마지막 장까지 모두 들었어요.");
});
el.chapterAudio.addEventListener("error", () => {
  if (ttsState.active && ttsState.mode === "cloud") stopReading("장별 MP3를 불러오지 못했어요. 기기 음성을 선택해보세요.");
});

function applyUrlState() {
  const url = new URL(window.location.href);
  const requestedView = ["reader", "downloads", "faq"].includes(url.searchParams.get("view")) ? url.searchParams.get("view") : "search";
  if (requestedView === "reader") {
    openReader(url.searchParams.get("book") || state.readerBook, url.searchParams.get("chapter") || 1, url.searchParams.get("verse"), { push: false });
  } else setView(requestedView, { updateAddress: false });
}
window.addEventListener("popstate", applyUrlState);

async function boot() {
  try {
    const response = await fetch("./bible.json?v=20260714-gcp-rag-audio-1");
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
    el.lucky.disabled = false;
    initTts();
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
