/* Untimed practice: check each answer against the server and show the explanation.
 * Used on the practice page (many questions, one at a time) and for the
 * landing page's sample question (one question). */
(() => {
  document.querySelectorAll('[data-practice]').forEach((root) => {
    const cfg = JSON.parse(root.querySelector('script[data-config]').textContent);
    const T = cfg.t;
    const tr = (key, vars = {}) => T[key].replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
    const items = Array.from(root.querySelectorAll('.pq'));
    const counter = root.querySelector('[data-counter]');
    const score = root.querySelector('[data-score]');
    const done = root.querySelector('[data-done]');
    const results = new Map();
    let index = 0;

    function updateBar() {
      if (counter) counter.textContent = tr('question_of', { i: index + 1, total: items.length });
      if (score && results.size) {
        const correct = Array.from(results.values()).filter(Boolean).length;
        score.textContent = tr('practice_score', { c: correct, n: results.size });
      }
    }

    function show(i) {
      index = i;
      items.forEach((item, j) => { item.hidden = j !== i; });
      if (done) done.hidden = true;
      updateBar();
      items[i].focus({ preventScroll: true });
      const top = root.getBoundingClientRect().top;
      if (top < 0) window.scrollTo({ top: window.scrollY + top - 24 });
    }

    function tag(label, text) {
      const span = document.createElement('span');
      span.className = 'option-tag';
      span.textContent = text;
      label.querySelector('.option-text').appendChild(span);
    }

    function reveal(item, chosen, data) {
      item.querySelectorAll('input').forEach((input) => { input.disabled = true; });
      item.querySelectorAll('.option-label').forEach((label) => {
        const id = label.dataset.option;
        if (id === data.correct) {
          label.classList.add('is-correct');
          tag(label, id === chosen ? T.marker_yours : T.marker_correct);
        } else if (id === chosen) {
          label.classList.add('is-wrong');
          tag(label, T.marker_yours);
        }
      });
      const fb = item.querySelector('[data-feedback]');
      fb.replaceChildren();
      fb.className = 'feedback ' + (data.ok ? 'feedback-good' : 'feedback-bad');
      const title = document.createElement('p');
      title.className = 'feedback-title';
      title.textContent = data.ok ? T.answer_correct : tr('answer_wrong', { id: data.correct });
      const body = document.createElement('p');
      body.textContent = data.explanation;
      fb.append(title, body);
      fb.hidden = false;

      item.querySelector('[data-check]').hidden = true;
      const after = item.querySelector('[data-next], [data-after]');
      if (after) after.hidden = false;
      results.set(item.dataset.qid, data.ok);
      updateBar();
      if (after) after.focus();
    }

    function selectedInput(item) {
      return item.querySelector('input[type=radio]:checked');
    }

    async function check(item) {
      const chosen = selectedInput(item);
      const btn = item.querySelector('[data-check]');
      if (!chosen || btn.hidden) return;
      btn.disabled = true;
      const fb = item.querySelector('[data-feedback]');
      try {
        const url = cfg.checkUrl.replace('__QID__', encodeURIComponent(item.dataset.qid));
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answer: chosen.value }),
        });
        if (!res.ok) throw new Error(String(res.status));
        reveal(item, chosen.value, await res.json());
      } catch (err) {
        fb.className = 'feedback feedback-bad';
        fb.textContent = T.check_failed;
        fb.hidden = false;
        btn.disabled = false;
      }
    }

    items.forEach((item, i) => {
      const btn = item.querySelector('[data-check]');
      item.addEventListener('change', (e) => {
        if (e.target.type === 'radio') btn.disabled = false;
      });
      btn.addEventListener('click', () => check(item));
      const nextBtn = item.querySelector('[data-next]');
      if (nextBtn) {
        nextBtn.addEventListener('click', () => {
          if (i + 1 < items.length) return show(i + 1);
          item.hidden = true;
          if (done) {
            const correct = Array.from(results.values()).filter(Boolean).length;
            done.querySelector('[data-final-score]').textContent = tr('practice_score', { c: correct, n: results.size });
            done.hidden = false;
            done.focus();
          }
        });
      }
      const prevBtn = item.querySelector('[data-prev]');
      if (prevBtn) {
        prevBtn.disabled = i === 0;
        prevBtn.addEventListener('click', () => { if (i > 0) show(i - 1); });
      }
    });

    /* Keyboard: A–D or 1–4 choose, Enter checks or moves on. Only when this
     * practice block is the page's main content (not the landing sample). */
    if (root.dataset.mode !== 'sample') {
      const KEYS = { KeyA: 0, KeyB: 1, KeyC: 2, KeyD: 3, Digit1: 0, Digit2: 1, Digit3: 2, Digit4: 3 };
      document.addEventListener('keydown', (e) => {
        if (e.altKey || e.ctrlKey || e.metaKey || e.repeat) return;
        const item = items[index];
        if (!item || item.hidden) return;
        if (e.code in KEYS) {
          const input = item.querySelectorAll('input[type=radio]')[KEYS[e.code]];
          if (input && !input.disabled) {
            e.preventDefault();
            input.checked = true;
            input.dispatchEvent(new Event('change', { bubbles: true }));
          }
        } else if (e.code === 'Enter' && !e.target.closest('button, a, summary, textarea, input:not([type=radio])')) {
          e.preventDefault();
          const checkBtn = item.querySelector('[data-check]');
          if (!checkBtn.hidden) check(item);
          else item.querySelector('[data-next]')?.click();
        }
      });
      updateBar();
    }
  });
})();
