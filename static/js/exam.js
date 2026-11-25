/* Timed exam, laid out like the Pearson VUE test driver used for the real ACC exam.
 *
 * Two sections of 30 items with a break between them. Inside a section people can
 * go back, flag items and use the Item Review Screen; End Review closes the section
 * for good, as on the real exam. Answers, flags and deadlines are saved to
 * localStorage after every change, so a reload or a closed tab resumes where the
 * person left off. Deadlines are wall-clock times, so the timer keeps running while
 * the page is closed. */
(() => {
  const cfg = JSON.parse(document.getElementById('exam-config').textContent);
  const T = cfg.t;
  const SIZE = cfg.sectionSize;
  const SECTION_MS = cfg.sectionSeconds * 1000;
  const BREAK_MS = cfg.breakSeconds * 1000;
  const RESUBMIT_GRACE_MS = 60 * 60 * 1000;

  const $ = (id) => document.getElementById(id);
  const form = $('exam-form');
  const questions = Array.from(document.querySelectorAll('.q'));
  const cells = Array.from(document.querySelectorAll('[data-cell]'));
  const total = questions.length;

  const tr = (key, vars = {}) => T[key].replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  const pad = (n) => String(n).padStart(2, '0');
  const formatTime = (ms) => {
    const s = Math.max(0, Math.ceil(ms / 1000));
    return pad(Math.floor(s / 3600)) + ':' + pad(Math.floor((s % 3600) / 60)) + ':' + pad(s % 60);
  };
  const rangeOf = (section) => (section === 1 ? [0, Math.min(SIZE, total)] : [SIZE, total]);
  const currentSection = () => (state.stage === 's2' ? 2 : 1);
  const qidAt = (i) => questions[i].dataset.qid;
  const isAnswered = (i) => Boolean(state.answers[qidAt(i)]);
  const isFlagged = (i) => state.flags.includes(qidAt(i));

  /* ── State ── */
  let state;
  let submitted = false;

  function freshState() {
    const now = Date.now();
    return {
      v: 1, stage: 's1', index: 0, answers: {}, flags: [],
      s1Start: now, s1End: now + SECTION_MS, s1Used: null, s1Auto: false,
      breakEnd: null, s2Start: null, s2End: null, submitted: false,
      view: 'item', reviewed: false, walk: null,
    };
  }

  /* A new section starts on its first item, with no review history. */
  function resetSectionView(s) {
    s.view = 'item';
    s.reviewed = false;
    s.walk = null;
  }

  function deadlineOf(s) {
    if (s.stage === 's1') return s.s1End + BREAK_MS + SECTION_MS;
    if (s.stage === 'break') return s.breakEnd + SECTION_MS;
    return s.s2End;
  }

  function save() {
    state.deadline = deadlineOf(state);
    try { localStorage.setItem(cfg.storageKey, JSON.stringify(state)); } catch (e) { /* private mode */ }
  }

  function loadSaved() {
    try {
      const s = JSON.parse(localStorage.getItem(cfg.storageKey));
      if (s && s.v === 1 && ['s1', 'break', 's2'].includes(s.stage) && !s.submitted) {
        if (!['item', 'review'].includes(s.view)) resetSectionView(s);
        return s;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  /* ── Rendering ── */
  function sectionIndexes(filter) {
    const [a, b] = rangeOf(currentSection());
    const out = [];
    for (let i = a; i < b; i++) if (!filter || filter(i)) out.push(i);
    return out;
  }

  function show(el, on) { el.hidden = !on; }

  function renderItem() {
    const [a, b] = rangeOf(currentSection());
    if (state.index < a || state.index >= b) state.index = a;
    questions.forEach((q, i) => { q.hidden = i !== state.index; });
    $('item-count').textContent = tr('item_of', { i: state.index - a + 1, total: b - a });
    $('btn-flag').setAttribute('aria-pressed', String(isFlagged(state.index)));

    const walk = state.walk;
    const pos = walk ? walk.indexOf(state.index) : -1;
    $('btn-prev').disabled = walk ? pos <= 0 : state.index === a;
  }

  function renderReview() {
    const section = currentSection();
    let incomplete = 0;
    cells.forEach((cell) => {
      const i = Number(cell.dataset.cell);
      const inSection = Number(cell.dataset.section) === section;
      cell.hidden = !inSection;
      if (!inSection) return;
      const answered = isAnswered(i);
      if (!answered) incomplete++;
      cell.querySelector('[data-cell-incomplete]').hidden = answered;
      cell.querySelector('[data-cell-flag]').setAttribute('aria-pressed', String(isFlagged(i)));
    });
    $('review-section-head').textContent = tr('section_of', { n: section });
    $('review-count').textContent = '(' + tr('review_incomplete_count', { n: incomplete }) + ')';
    $('btn-review-incomplete').disabled = incomplete === 0;
    $('btn-review-flagged').disabled = sectionIndexes(isFlagged).length === 0;
  }

  function render() {
    const onBreak = state.stage === 'break';
    const view = onBreak ? 'break' : state.view;

    show($('stage-item'), view === 'item');
    show($('stage-review'), view === 'review');
    show($('stage-break'), view === 'break');
    show($('break-timeup'), onBreak && state.s1Auto);
    show($('item-count'), view === 'item');
    show($('btn-flag'), view === 'item');
    $('section-label').textContent = onBreak ? T.break : tr('section_of', { n: currentSection() });

    show($('btn-prev'), view === 'item');
    show($('btn-next'), view === 'item');
    show($('btn-review-screen'), view === 'item' && state.reviewed);
    ['btn-end-review', 'btn-review-all', 'btn-review-incomplete', 'btn-review-flagged'].forEach((id) => show($(id), view === 'review'));
    show($('bottom-bar'), !onBreak);

    if (view === 'item') renderItem();
    if (view === 'review') renderReview();
    tick();
  }

  function setTimer(ms) {
    $('timer-value').textContent = formatTime(ms);
    $('timer').classList.toggle('is-danger', ms <= 5 * 60e3);
  }

  /* ── Navigation ── */
  function showItem(i, focus) {
    const [a, b] = rangeOf(currentSection());
    state.index = Math.min(Math.max(i, a), b - 1);
    state.view = 'item';
    save();
    render();
    window.scrollTo({ top: 0 });
    if (focus) questions[state.index].focus({ preventScroll: true });
  }

  function openReview() {
    state.view = 'review';
    state.reviewed = true;
    state.walk = null;
    save();
    render();
    window.scrollTo({ top: 0 });
    $('stage-review').focus({ preventScroll: true });
  }

  function next() {
    const walk = state.walk;
    if (walk) {
      const pos = walk.indexOf(state.index);
      if (pos >= 0 && pos < walk.length - 1) showItem(walk[pos + 1]);
      else openReview();
      return;
    }
    const [, b] = rangeOf(currentSection());
    if (state.index >= b - 1) openReview();
    else showItem(state.index + 1);
  }

  function prev() {
    const walk = state.walk;
    if (walk) {
      const pos = walk.indexOf(state.index);
      if (pos > 0) showItem(walk[pos - 1]);
      return;
    }
    if (state.index > rangeOf(currentSection())[0]) showItem(state.index - 1);
  }

  /* Review All / Incomplete / Flagged: step through a fixed list of items, then come back. */
  function startWalk(filter) {
    const list = sectionIndexes(filter);
    if (!list.length) return;
    state.walk = filter ? list : null;
    showItem(list[0], true);
  }

  function toggleFlagAt(i) {
    const qid = qidAt(i);
    state.flags = state.flags.includes(qid) ? state.flags.filter((f) => f !== qid) : state.flags.concat(qid);
    save();
    if (state.view === 'review') renderReview();
    else $('btn-flag').setAttribute('aria-pressed', String(isFlagged(state.index)));
  }

  /* ── Stage changes ── */
  function endSection1(auto) {
    const now = Date.now();
    state.s1Used = auto ? SECTION_MS : Math.min(SECTION_MS, now - state.s1Start);
    state.s1Auto = auto;
    state.stage = 'break';
    state.breakEnd = (auto ? state.s1End : now) + BREAK_MS;
    resetSectionView(state);
    save();
    render();
    window.scrollTo({ top: 0 });
    $('stage-break').focus({ preventScroll: true });
  }

  function startSection2(at) {
    state.stage = 's2';
    state.s2Start = at;
    state.s2End = at + SECTION_MS;
    state.index = SIZE;
    resetSectionView(state);
  }

  function startSection2Now() {
    startSection2(Date.now());
    save();
    render();
    window.scrollTo({ top: 0 });
    questions[state.index].focus({ preventScroll: true });
  }

  function submitExam() {
    if (submitted) return;
    submitted = true;
    const now = Date.now();
    const s1 = state.s1Used != null ? state.s1Used : Math.min(SECTION_MS, now - state.s1Start);
    const s2 = state.s2Start ? Math.min(SECTION_MS, now - state.s2Start) : 0;
    $('elapsed').value = String(Math.max(1, Math.round((s1 + s2) / 1000)));
    state.submitted = true;
    save();
    document.querySelectorAll('dialog[open]').forEach((d) => d.close());
    $('submitting').hidden = false;
    form.submit();
  }

  /* Bring a saved exam up to date with the clock. Returns true if time is up. */
  function catchUp(now) {
    if (state.stage === 's1' && now >= state.s1End) {
      state.stage = 'break';
      state.s1Used = SECTION_MS;
      state.s1Auto = true;
      state.breakEnd = state.s1End + BREAK_MS;
      resetSectionView(state);
    }
    if (state.stage === 'break' && now >= state.breakEnd) startSection2(state.breakEnd);
    return state.stage === 's2' && now >= state.s2End;
  }

  function tick() {
    if (submitted) return;
    const now = Date.now();
    if (state.stage === 's1') {
      const left = state.s1End - now;
      if (left <= 0) return endSection1(true);
      setTimer(left);
    } else if (state.stage === 'break') {
      const left = state.breakEnd - now;
      if (left <= 0) {
        startSection2(state.breakEnd);
        save();
        return render();
      }
      setTimer(left);
      $('break-timer').textContent = formatTime(left);
    } else {
      const left = state.s2End - now;
      if (left <= 0) return submitExam();
      setTimer(left);
    }
  }

  /* ── Events ── */
  form.addEventListener('change', (e) => {
    if (e.target.type !== 'radio') return;
    state.answers[e.target.name.slice(2)] = e.target.value;
    save();
  });

  $('btn-flag').addEventListener('click', () => toggleFlagAt(state.index));
  $('btn-next').addEventListener('click', next);
  $('btn-prev').addEventListener('click', prev);
  $('btn-review-screen').addEventListener('click', openReview);
  $('btn-review-all').addEventListener('click', () => startWalk(null));
  $('btn-review-incomplete').addEventListener('click', () => startWalk((i) => !isAnswered(i)));
  $('btn-review-flagged').addEventListener('click', () => startWalk(isFlagged));
  $('btn-start-s2').addEventListener('click', startSection2Now);
  cells.forEach((cell) => {
    const i = Number(cell.dataset.cell);
    cell.querySelector('[data-cell-go]').addEventListener('click', () => {
      state.walk = null;
      showItem(i, true);
    });
    cell.querySelector('[data-cell-flag]').addEventListener('click', () => toggleFlagAt(i));
  });

  $('btn-end-review').addEventListener('click', () => {
    $('end-body').textContent = currentSection() === 1 ? T.end_review_s1 : T.end_review_s2;
    $('end-dialog').showModal();
  });
  $('end-yes').addEventListener('click', () => {
    $('end-dialog').close();
    if (currentSection() === 1) endSection1(false);
    else submitExam();
  });
  document.querySelectorAll('dialog [data-close]').forEach((btn) => {
    btn.addEventListener('click', () => btn.closest('dialog').close());
  });

  const KEY_OPTIONS = {
    KeyA: 0, KeyB: 1, KeyC: 2, KeyD: 3,
    Digit1: 0, Digit2: 1, Digit3: 2, Digit4: 3,
    Numpad1: 0, Numpad2: 1, Numpad3: 2, Numpad4: 3,
  };

  document.addEventListener('keydown', (e) => {
    if (submitted || state.stage === 'break' || state.view !== 'item') return;
    if (e.ctrlKey || e.metaKey || e.repeat) return;
    if (document.querySelector('dialog[open]')) return;
    const target = e.target;
    if (target.tagName === 'TEXTAREA' || (target.tagName === 'INPUT' && target.type !== 'radio')) return;

    // Alt+N / Alt+P move, as in the real test driver.
    if (e.altKey) {
      if (e.code === 'KeyN') { e.preventDefault(); next(); }
      else if (e.code === 'KeyP') { e.preventDefault(); prev(); }
      return;
    }
    if (e.code in KEY_OPTIONS) {
      const input = questions[state.index].querySelectorAll('input[type=radio]')[KEY_OPTIONS[e.code]];
      if (input) {
        e.preventDefault();
        input.checked = true;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    } else if (e.code === 'ArrowRight') {
      e.preventDefault();
      next();
    } else if (e.code === 'ArrowLeft') {
      e.preventDefault();
      prev();
    } else if (e.code === 'KeyF') {
      e.preventDefault();
      toggleFlagAt(state.index);
    }
  });

  /* Keep the free hosting instance awake while an exam is open. */
  setInterval(() => { fetch('/ping', { cache: 'no-store' }).catch(() => {}); }, 50 * 1000);

  /* ── Start ── */
  const now = Date.now();
  const saved = loadSaved();
  let restored = false;
  let timeUp = false;
  if (saved && now < deadlineOf(saved)) {
    state = saved;
    restored = true;
  } else if (saved && now - deadlineOf(saved) < RESUBMIT_GRACE_MS && Object.keys(saved.answers).length) {
    state = saved; // time ran out while away: score what was answered
    timeUp = true;
  } else {
    state = freshState();
  }

  Object.entries(state.answers).forEach(([qid, value]) => {
    const input = form.querySelector(`input[name="q_${CSS.escape(qid)}"][value="${CSS.escape(value)}"]`);
    if (input) input.checked = true;
  });

  if (catchUp(now)) timeUp = true;
  save();
  if (timeUp) {
    submitExam();
    return;
  }
  render();
  if (restored) $('resume-note').hidden = false;
  setInterval(tick, 500);
})();
