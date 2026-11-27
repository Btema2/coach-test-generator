/* Mark exams that are in progress in this browser and offer to resume them. */
(() => {
  document.querySelectorAll('[data-exam]').forEach((row) => {
    let state = null;
    try { state = JSON.parse(localStorage.getItem('exam:v1:' + row.dataset.exam)); } catch (e) { return; }
    if (!state || state.submitted || !(state.deadline > Date.now())) return;
    const progress = row.querySelector('[data-status-progress]');
    const fresh = row.querySelector('[data-status-new]');
    const start = row.querySelector('[data-start]');
    if (progress) progress.hidden = false;
    if (fresh) fresh.hidden = true;
    if (start) start.textContent = start.dataset.resumeLabel;
  });
})();
