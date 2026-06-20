document.addEventListener('DOMContentLoaded', () => {
  const priceCapInput = document.getElementById('price-cap');
  const pauperToggle = document.getElementById('pauper-toggle');
  const nSlider = document.getElementById('n-slider');
  const nLabel = document.getElementById('n-label');
  const inclusionSlider = document.getElementById('inclusion-cap');
  const inclusionLabel = document.getElementById('inclusion-label');

  // Guard: only run on the commander page (controls may not exist on index/error pages)
  if (!nSlider) return;

  const edhrecCards = document.querySelectorAll('#edhrec-section .card-item');
  const sleptOnGrid = document.getElementById('slept-on-grid');

  // ── Live re-scoring: mute features in Diagnostics, re-rank without a reload ──
  // Mirrors services/analysis.score_cards: a card's score is the sum of the
  // weights of the features it carries that are not currently muted.
  const WEIGHTS = JSON.parse(
    document.getElementById('feature-weights')?.textContent || '{}'
  );
  const muted = new Set();

  // Recompute every feature-carrying card's score, updating both the data-score
  // attribute and the visible .js-score span (toFixed(3) matches Jinja round(3)).
  function recomputeScores() {
    document.querySelectorAll('.card-item[data-features]').forEach(card => {
      const feats = card.dataset.features ? card.dataset.features.split('|') : [];
      let sum = 0;
      feats.forEach(f => { if (!muted.has(f)) sum += WEIGHTS[f] || 0; });
      card.dataset.score = sum;
      const span = card.querySelector('.js-score');
      if (span) span.textContent = 'Score: ' + sum.toFixed(3);
    });
  }

  // Re-rank the Slept On grid by current score, descending, so the N-limit in
  // applyFilters (which iterates the grid's live children) picks the true top-N.
  function reorderSleptOn() {
    const cards = Array.from(sleptOnGrid.querySelectorAll('.card-item'));
    cards.sort((a, b) => parseFloat(b.dataset.score) - parseFloat(a.dataset.score));
    cards.forEach(card => sleptOnGrid.appendChild(card));
  }

  function applyFilters() {
    const maxPrice = priceCapInput.value !== '' ? parseFloat(priceCapInput.value) : Infinity;
    const pauperOnly = pauperToggle.checked;
    const maxN = parseInt(nSlider.value, 10);
    const maxInclusion = parseInt(inclusionSlider.value, 10);

    // Update live labels
    nLabel.textContent = maxN;
    inclusionLabel.textContent = maxInclusion;

    // Apply price cap and pauper to EDHRec section
    edhrecCards.forEach(card => {
      const price = parseFloat(card.dataset.price);
      const rarity = card.dataset.rarity;
      const hide = price > maxPrice || (pauperOnly && rarity !== 'common');
      card.classList.toggle('hidden', hide);
    });

    // Apply price cap, pauper, and inclusion cap to Slept On section, then N limit.
    // Iterate the grid's live children so the N-limit respects the current score
    // order after a re-rank (reorderSleptOn re-appends nodes in score-desc order).
    let visibleCount = 0;
    sleptOnGrid.querySelectorAll('.card-item').forEach(card => {
      const price = parseFloat(card.dataset.price);
      const rarity = card.dataset.rarity;
      const inclusion = parseInt(card.dataset.inclusion, 10);

      const hiddenByFilters = price > maxPrice
        || (pauperOnly && rarity !== 'common')
        || inclusion > maxInclusion;

      if (hiddenByFilters) {
        card.classList.add('hidden');
      } else if (visibleCount < maxN) {
        card.classList.remove('hidden');
        visibleCount++;
      } else {
        card.classList.add('hidden');
      }
    });
  }

  // Attach listeners
  priceCapInput.addEventListener('input', applyFilters);
  pauperToggle.addEventListener('change', applyFilters);
  nSlider.addEventListener('input', applyFilters);
  inclusionSlider.addEventListener('input', applyFilters);

  // ── Diagnostics feature toggles: mute features and re-score/re-rank live ──
  const muteTypesSubs = document.getElementById('mute-types-subs');
  const featureToggles = document.querySelectorAll('.feature-toggle');

  function setMuted(feature, isMuted, row) {
    if (isMuted) muted.add(feature); else muted.delete(feature);
    if (row) row.classList.toggle('muted', isMuted);
  }

  function rescore() {
    recomputeScores();
    reorderSleptOn();
    applyFilters();
  }

  // Bulk: mute/unmute every type:* and sub:* feature, syncing the row checkboxes.
  if (muteTypesSubs) {
    muteTypesSubs.addEventListener('change', () => {
      const mute = muteTypesSubs.checked;
      featureToggles.forEach(cb => {
        const f = cb.dataset.feature;
        if (f.startsWith('type:') || f.startsWith('sub:')) {
          cb.checked = !mute;
          setMuted(f, mute, cb.closest('tr'));
        }
      });
      rescore();
    });
  }

  // Per-row: mute/unmute a single feature (checked = on/contributing).
  featureToggles.forEach(cb => {
    cb.addEventListener('change', () => {
      setMuted(cb.dataset.feature, !cb.checked, cb.closest('tr'));
      rescore();
    });
  });

  // Apply defaults on page load
  applyFilters();

  // ── Tabs: switch the visible panel ──
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.tab);
      if (!target) return;
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      target.classList.add('active');
    });
  });

  // ── Click a card to copy its name to the clipboard ──
  const toast = document.getElementById('copy-toast');
  let toastTimer = null;

  async function copyName(name) {
    try {
      await navigator.clipboard.writeText(name);
    } catch (e) {
      // Fallback for non-secure contexts / older browsers.
      const ta = document.createElement('textarea');
      ta.value = name;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (_) { /* give up silently */ }
      document.body.removeChild(ta);
    }
  }

  function showToast(name) {
    if (!toast) return;
    toast.textContent = `Copied "${name}"`;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 1400);
  }

  document.querySelectorAll('.card-item').forEach(card => {
    card.addEventListener('click', () => {
      const name = card.dataset.name;
      if (!name) return;
      copyName(name);
      showToast(name);
    });
  });
});
