/* Hover and focus tooltip for the progress chart. */
(() => {
  document.querySelectorAll('[data-chart]').forEach((frame) => {
    const tip = frame.querySelector('.chart-tip');
    const points = Array.from(frame.querySelectorAll('.chart-point'));

    function show(point) {
      const frameBox = frame.getBoundingClientRect();
      const box = point.getBoundingClientRect();
      tip.replaceChildren();
      const pct = document.createElement('strong');
      pct.textContent = point.dataset.pct;
      tip.append(pct, document.createElement('br'), point.dataset.title, document.createElement('br'), point.dataset.date);
      tip.hidden = false;
      // Centre over the dot, but keep the tooltip inside the frame.
      const half = tip.offsetWidth / 2;
      const centre = box.left - frameBox.left + box.width / 2;
      tip.style.left = Math.min(Math.max(centre, half + 4), frameBox.width - half - 4) + 'px';
      tip.style.top = box.top - frameBox.top + box.height / 2 + 'px';
      points.forEach((p) => p.classList.toggle('is-active', p === point));
    }

    function hide() {
      tip.hidden = true;
      points.forEach((p) => p.classList.remove('is-active'));
    }

    points.forEach((point) => {
      point.addEventListener('mouseenter', () => show(point));
      point.addEventListener('focus', () => show(point));
      point.addEventListener('mouseleave', hide);
      point.addEventListener('blur', hide);
    });
  });
})();
