/* Timed exam: one question per screen, two sections with a break.
 * Answers, flags and deadlines are saved to localStorage after every change,
 * so a reload or a closed tab resumes where the person left off. Deadlines are
 * wall-clock times, so the timer keeps running while the page is closed. */
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
  const navButtons = Array.from(document.querySelectorAll('.nav-btn'));
  const total = questions.length;

  const tr = (key, vars = {}) => T[key].replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  const pad = (n) => String(n).padStart(2, '0');
  const formatTime = (ms) => {
    const s = Math.max(0, Math.ceil(ms / 1000));
    return pad(Math.floor(s / 60)) + ':' + pad(s % 60);
  };
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const rangeOf = (section) => (section === 1 ? [0, Math.min(SIZE, total)] : [SIZE, total]);
  const currentSection = () => (state.stage === 's2' ? 2 : 1);

  /* ── State ── */
  let state;
  let submitted = false;

  function freshState() {
    const now = Date.now();
    return {
      v: 1, stage: 's1', index: 0, answers: {}, flags: [],
      s1Start: now, s1End: now + SECTION_MS, s1Used: null, s1Auto: false,
      breakEnd: null, s2Start: null, s2End: null, submitted: false,
    };
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
      if (s && s.v === 1 && ['s1', 'break', 's2'].includes(s.stage) && !s.submitted) return s;
    } catch (e) { /* ignore */ }
    return null;
  }

  /* ── Rendering ── */
  function answeredIn(section) {
    const [a, b] = rangeOf(section);
    let n = 0;
    for (let i = a; i < b; i++) if (state.answers[questions[i].dataset.qid]) n++;
    return n;
  }

  function updateProgress() {
    if (state.stage === 'break') {
      $('answered-label').textContent = '';
      $('progress-fill').style.width = '100%';
      return;
    }
    const section = currentSection();
    const [a, b] = rangeOf(section);
    const answered = answeredIn(section);
    $('answered-label').textContent = tr('progress', { a: answered, total: b - a });
    $('progress-fill').style.width = (answered / (b - a)) * 100 + '%';
  }

  function updateNav() {
    navButtons.forEach((btn) => {
      const i = Number(btn.dataset.goto);
      const qid = questions[i].dataset.qid;
      const answered = Boolean(state.answers[qid]);
      const flagged = state.flags.includes(qid);
      btn.classList.toggle('is-answered', answered);
      btn.classList.toggle('is-flagged', flagged);
      if (i === state.index) btn.setAttribute('aria-current', 'true');
      else btn.removeAttribute('aria-current');
      const parts = [btn.dataset.label];
      if (answered) parts.push(T.legend_answered);
      if (flagged) parts.push(T.legend_flagged);
      btn.setAttribute('aria-label', parts.join(', '));
    });
  }

  function updateFlagButton() {
    const q = questions[state.index];
    const btn = q.querySelector('[data-flag]');
    const on = state.flags.includes(q.dataset.qid);
    btn.setAttribute('aria-pressed', String(on));
    btn.querySelector('[data-flag-text]').textContent = on ? T.flagged : T.flag;
  }

  function render() {
    const onBreak = state.stage === 'break';
    $('stage-questions').hidden = onBreak;
    $('stage-break').hidden = !onBreak;
    $('break-timeup').hidden = !(onBreak && state.s1Auto);
    const section = currentSection();
    $('section-label').textContent = onBreak ? T.break : tr('section_of', { n: section });
    document.querySelectorAll('[data-nav-section]').forEach((ol) => {
      ol.hidden = Number(ol.dataset.navSection) !== section;
    });

    if (!onBreak) {
      const [a, b] = rangeOf(section);
      if (state.index < a || state.index >= b) state.index = a;
      questions.forEach((q, i) => { q.hidden = i !== state.index; });
      $('btn-prev').disabled = state.index === a;
      const last = state.index === b - 1;
      $('btn-next').textContent = last ? (section === 1 ? T.review_section : T.review_exam) : T.next;
      $('btn-review').textContent = section === 1 ? T.review_section : T.review_exam;
      updateFlagButton();
    }
    updateProgress();
    updateNav();
    tick();
  }

  function setTimer(ms, warnMs, dangerMs) {
    const el = $('timer');
    $('timer-value').textContent = formatTime(ms);
    el.classList.toggle('is-danger', ms <= dangerMs);
    el.classList.toggle('is-warn', ms > dangerMs && ms <= warnMs);
  }

  /* ── Navigation ── */
  function go(i, focus) {
    const [a, b] = rangeOf(currentSection());
    state.index = Math.min(Math.max(i, a), b - 1);
    save();
    render();
    const pane = $('stage-questions');
    const top = pane.getBoundingClientRect().top;
    if (top < 0) window.scrollTo({ top: window.scrollY + top - 80, behavior: reducedMotion ? 'auto' : 'smooth' });
    if (focus) questions[state.index].focus({ preventScroll: true });
  }

  function next() {
    const [, b] = rangeOf(currentSection());
    if (state.index >= b - 1) openReview();
    else go(state.index + 1);
  }

  function prev() { go(state.index - 1); }

  function toggleFlag() {
    const qid = questions[state.index].dataset.qid;
    state.flags = state.flags.includes(qid) ? state.flags.filter((f) => f !== qid) : state.flags.concat(qid);
    save();
    updateFlagButton();
    updateNav();
  }

  /* ── Stage changes ── */
  function endSection1(auto) {
    const now = Date.now();
    state.s1Used = auto ? SECTION_MS : Math.min(SECTION_MS, now - state.s1Start);
    state.s1Auto = auto;
    state.stage = 'break';
    state.breakEnd = (auto ? state.s1End : now) + BREAK_MS;
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
      setTimer(left, 15 * 60e3, 5 * 60e3);
    } else if (state.stage === 'break') {
      const left = state.breakEnd - now;
      if (left <= 0) {
        startSection2(state.breakEnd);
        save();
        return render();
      }
      setTimer(left, 3 * 60e3, 60e3);
      $('break-timer').textContent = formatTime(left);
    } else {
      const left = state.s2End - now;
      if (left <= 0) return submitExam();
      setTimer(left, 15 * 60e3, 5 * 60e3);
    }
  }

  /* ── Dialogs ── */
  function fillChips(listId, groupId, indexes) {
    const list = $(listId);
    list.replaceChildren();
    indexes.forEach((i) => {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip';
      btn.textContent = String((i % SIZE) + 1);
      btn.setAttribute('aria-label', navButtons[i].dataset.label);
      btn.addEventListener('click', () => {
        $('review-dialog').close();
        go(i, true);
      });
      li.appendChild(btn);
      list.appendChild(li);
    });
    $(groupId).hidden = indexes.length === 0;
  }

  function openReview() {
    const section = currentSection();
    const [a, b] = rangeOf(section);
    const unanswered = [];
    const flagged = [];
    for (let i = a; i < b; i++) {
      const qid = questions[i].dataset.qid;
      if (!state.answers[qid]) unanswered.push(i);
      if (state.flags.includes(qid)) flagged.push(i);
    }
    $('review-title').textContent = section === 1 ? tr('review_title', { n: 1 }) : T.review_title_exam;
    $('review-answered').textContent = unanswered.length
      ? tr('review_answered', { a: b - a - unanswered.length, total: b - a })
      : T.review_all_done;
    fillChips('review-unanswered', 'review-unanswered-group', unanswered);
    fillChips('review-flagged', 'review-flagged-group', flagged);
    $('review-note').textContent = section === 1 ? T.review_note_s1 : T.review_note_s2;
    $('review-confirm').textContent = section === 1 ? T.submit_section : T.submit_test;
    $('review-dialog').showModal();
  }

  function openEnd() {
    $('end-body').textContent = state.stage === 's1' ? T.end_body_s1 : T.end_body_s2;
    $('end-dialog').showModal();
  }

  /* ── Events ── */
  form.addEventListener('change', (e) => {
    if (e.target.type !== 'radio') return;
    state.answers[e.target.name.slice(2)] = e.target.value;
    save();
    updateProgress();
    updateNav();
  });

  questions.forEach((q) => q.querySelector('[data-flag]').addEventListener('click', toggleFlag));
  navButtons.forEach((btn) => btn.addEventListener('click', () => go(Number(btn.dataset.goto), true)));
  $('btn-next').addEventListener('click', next);
  $('btn-prev').addEventListener('click', prev);
  $('btn-review').addEventListener('click', openReview);
  $('btn-end').addEventListener('click', openEnd);
  $('btn-start-s2').addEventListener('click', startSection2Now);
  $('review-confirm').addEventListener('click', () => {
    $('review-dialog').close();
    if (currentSection() === 1) endSection1(false);
    else submitExam();
  });
  $('end-confirm').addEventListener('click', submitExam);
  document.querySelectorAll('dialog [data-close]').forEach((btn) => {
    btn.addEventListener('click', () => btn.closest('dialog').close());
  });

  const KEY_OPTIONS = {
    KeyA: 0, KeyB: 1, KeyC: 2, KeyD: 3,
    Digit1: 0, Digit2: 1, Digit3: 2, Digit4: 3,
    Numpad1: 0, Numpad2: 1, Numpad3: 2, Numpad4: 3,
  };

  document.addEventListener('keydown', (e) => {
    if (submitted || state.stage === 'break') return;
    if (e.altKey || e.ctrlKey || e.metaKey || e.repeat) return;
    if (document.querySelector('dialog[open]')) return;
    const target = e.target;
    if (target.tagName === 'TEXTAREA' || (target.tagName === 'INPUT' && target.type !== 'radio')) return;

    if (e.code in KEY_OPTIONS) {
      const inputs = questions[state.index].querySelectorAll('input[type=radio]');
      const input = inputs[KEY_OPTIONS[e.code]];
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
      if (state.index > rangeOf(currentSection())[0]) prev();
    } else if (e.code === 'KeyF') {
      e.preventDefault();
      toggleFlag();
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
