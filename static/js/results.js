/* Results page: clear the finished exam from storage, fill the score ring,
 * and filter the answer review. */
(() => {
  const cfg = JSON.parse(document.getElementById('results-config').textContent);

  try {
    const saved = JSON.parse(localStorage.getItem(cfg.storageKey));
    if (saved && saved.submitted) localStorage.removeItem(cfg.storageKey);
  } catch (e) { /* ignore */ }

  const ring = document.querySelector('.ring-fill');
  if (ring) {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      ring.style.strokeDashoffset = ring.dataset.target;
    }));
  }

  const filters = Array.from(document.querySelectorAll('[data-filter]'));
  const items = Array.from(document.querySelectorAll('.review-item'));
  const empty = document.getElementById('filter-empty');
  filters.forEach((btn) => {
    btn.addEventListener('click', () => {
      const want = btn.dataset.filter;
      filters.forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
      let shown = 0;
      items.forEach((item) => {
        const visible = want === 'all' || item.dataset.state === want;
        item.hidden = !visible;
        if (visible) shown++;
      });
      empty.hidden = shown > 0;
    });
  });
})();
