document.addEventListener('DOMContentLoaded', () => {
  const priceCapInput = document.getElementById('price-cap');
  const pauperToggle = document.getElementById('pauper-toggle');
  const nSlider = document.getElementById('n-slider');
  const nLabel = document.getElementById('n-label');
  const inclusionSlider = document.getElementById('inclusion-cap');
  const inclusionLabel = document.getElementById('inclusion-label');

  // Guard: only run on the commander page (controls may not exist on index/error pages)
  if (!nSlider) return;

  // ── Scope selectors (theme/budget/bracket): a change updates that query param
  // on the current URL and reloads, so the server re-runs the scope logic
  // (which set is displayed, and — for theme only — re-scores Slept On).
  document.querySelectorAll('select[data-param]').forEach(sel => {
    sel.addEventListener('change', () => {
      const url = new URL(window.location.href);
      if (sel.value) url.searchParams.set(sel.dataset.param, sel.value);
      else url.searchParams.delete(sel.dataset.param);
      window.location.assign(url.toString());
    });
  });

  const edhrecCards = document.querySelectorAll('#edhrec-section .card-item');
  // The overall Top 10 grid (#slept-on-grid) plus the seven per-type sections,
  // all sharing .slept-on-grid. Filters and the N limit apply to every grid: the
  // Top 10 grid is N-limited to a fixed 10 via data-fixed-n, while the type grids
  // follow the shared slider (see applyFilters).
  const sleptOnGrids = document.querySelectorAll('.slept-on-grid');

  // Hide any type section that rendered zero cards (e.g. a commander with no
  // sorceries among its picks) so the page shows no bare <h3>. Evaluated once on
  // load — sections don't gain cards from filtering, only lose them.
  sleptOnGrids.forEach(grid => {
    if (grid.querySelectorAll('.card-item').length === 0) {
      grid.classList.add('hidden-section');
      const heading = grid.previousElementSibling;
      if (heading && heading.tagName === 'H3') heading.classList.add('hidden-section');
    }
  });

  // ── Live re-scoring: mute features in Diagnostics, re-rank without a reload ──
  // Mirrors services/analysis.score_cards: a card's score is the sum of the
  // weights of the features it carries that are not currently muted.
  const WEIGHTS = JSON.parse(
    document.getElementById('feature-weights')?.textContent || '{}'
  );
  const muted = new Set();

  // Mirrors services/analysis.score_breakdown: top contributors to a card's
  // displayed score. Muted features contribute 0 and are dropped, so the list
  // reconciles with the (post-mute) score shown in .js-score.
  const TOOLTIP_TOP_N = 5;
  function topContributors(card, n = TOOLTIP_TOP_N) {
    const feats = card.dataset.features ? card.dataset.features.split('|') : [];
    return feats
      .map(f => [f, muted.has(f) ? 0 : (WEIGHTS[f] || 0)])
      .filter(([, w]) => w !== 0)
      .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      .slice(0, n);
  }
  function featureLabel(f) {            // "otag:ramp" -> {kind:"otag", name:"ramp"}
    const i = f.indexOf(':');
    return { kind: f.slice(0, i), name: f.slice(i + 1) };
  }

  // A single floating tooltip, appended to <body> so it escapes each card's
  // overflow:hidden and hover transform (either of which would clip or contain
  // an in-card overlay). Built fresh on each hover, so it always reflects the
  // current muted set without needing a rescore hook.
  const scoreTooltip = document.createElement('div');
  scoreTooltip.className = 'score-tooltip';
  document.body.appendChild(scoreTooltip);

  function tooltipHTML(card) {
    const rows = topContributors(card);
    if (!rows.length) return '<em>No positive contributors</em>';
    return '<strong>Top contributors</strong>' + rows.map(([f, w]) => {
      const { kind, name } = featureLabel(f);
      return `<span class="tip-row"><span class="kind kind-${kind}">${kind}</span>`
           + `${name}<span class="tip-val">${w >= 0 ? '+' : ''}${w.toFixed(3)}</span></span>`;
    }).join('');
  }

  // Float the tooltip to the right of the hovered card, flipping to the left if
  // it would overflow the viewport, and clamping vertically so it stays on screen.
  function positionTooltip(card) {
    const r = card.getBoundingClientRect();
    const gap = 8;
    let left = r.right + gap;
    if (left + scoreTooltip.offsetWidth > window.innerWidth - gap) {
      left = r.left - gap - scoreTooltip.offsetWidth;
    }
    if (left < gap) left = gap;
    let top = Math.min(r.top, window.innerHeight - gap - scoreTooltip.offsetHeight);
    if (top < gap) top = gap;
    scoreTooltip.style.left = left + 'px';
    scoreTooltip.style.top = top + 'px';
  }

  document.querySelectorAll('.card-item[data-features]').forEach(card => {
    card.addEventListener('mouseenter', () => {
      scoreTooltip.innerHTML = tooltipHTML(card);
      scoreTooltip.classList.add('visible');  // display:block before measuring
      positionTooltip(card);
    });
    card.addEventListener('mouseleave', () => {
      scoreTooltip.classList.remove('visible');
    });
  });

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

  // Re-rank every Slept On grid by current score, descending, so the N-limit in
  // applyFilters (which iterates each grid's live children) picks the true top-N
  // after a Diagnostics re-score changed the ordering.
  function reorderSleptOnGrids() {
    sleptOnGrids.forEach(grid => {
      const cards = Array.from(grid.querySelectorAll('.card-item'));
      cards.sort((a, b) => parseFloat(b.dataset.score) - parseFloat(a.dataset.score));
      cards.forEach(card => grid.appendChild(card));
    });
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

    // Apply price cap, pauper, inclusion cap, and the N limit to every Slept On
    // grid (the overall Top 10 plus the per-type sections). The N limit counts
    // per grid, so each section independently shows its top N passing cards.
    // A grid with data-fixed-n (the Top 10) uses that fixed limit; the type grids
    // follow the shared slider. Iterating each grid's live children means the
    // N-limit respects the current score order after a re-rank
    // (reorderSleptOnGrids re-appends nodes in score-desc order).
    sleptOnGrids.forEach(grid => {
      const fixed = grid.dataset.fixedN;
      const gridMaxN = fixed ? parseInt(fixed, 10) : maxN;
      let visibleCount = 0;
      grid.querySelectorAll('.card-item').forEach(card => {
        const price = parseFloat(card.dataset.price);
        const rarity = card.dataset.rarity;
        const inclusion = parseInt(card.dataset.inclusion, 10);

        const hiddenByFilters = price > maxPrice
          || (pauperOnly && rarity !== 'common')
          || inclusion > maxInclusion;

        if (hiddenByFilters) {
          card.classList.add('hidden');
        } else if (visibleCount < gridMaxN) {
          card.classList.remove('hidden');
          visibleCount++;
        } else {
          card.classList.add('hidden');
        }
      });
    });
  }

  // Attach listeners
  priceCapInput.addEventListener('input', applyFilters);
  pauperToggle.addEventListener('change', applyFilters);
  nSlider.addEventListener('input', applyFilters);
  inclusionSlider.addEventListener('input', applyFilters);

  // ── Diagnostics feature toggles: mute features and re-score/re-rank live ──
  const featureToggles = document.querySelectorAll('.feature-toggle');

  function setMuted(feature, isMuted, row) {
    if (isMuted) muted.add(feature); else muted.delete(feature);
    if (row) row.classList.toggle('muted', isMuted);
  }

  function rescore() {
    recomputeScores();
    reorderSleptOnGrids();
    applyFilters();
  }

  // Bulk: mute/unmute every feature of one kind (type:* or sub:*), syncing the
  // per-row checkboxes, then re-score. Each kind toggles independently.
  function bindKindMute(checkboxId, prefix) {
    const box = document.getElementById(checkboxId);
    if (!box) return;
    box.addEventListener('change', () => {
      const mute = box.checked;
      featureToggles.forEach(cb => {
        if (cb.dataset.feature.startsWith(prefix)) {
          cb.checked = !mute;
          setMuted(cb.dataset.feature, mute, cb.closest('tr'));
        }
      });
      rescore();
    });
  }
  bindKindMute('mute-types', 'type:');
  bindKindMute('mute-subs', 'sub:');

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
  // The active tab is remembered in sessionStorage so it survives the full page
  // reload triggered by a Theme/Budget/Bracket change (which re-runs the server
  // scope logic) instead of snapping back to the default Slept On tab.
  const TAB_KEY = 'activeTab';
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');

  function activateTab(tabId) {
    const target = document.getElementById(tabId);
    const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    if (!target || !btn) return;
    tabButtons.forEach(b => b.classList.remove('active'));
    tabPanels.forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    target.classList.add('active');
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      if (!document.getElementById(btn.dataset.tab)) return;
      sessionStorage.setItem(TAB_KEY, btn.dataset.tab);
      activateTab(btn.dataset.tab);
    });
  });

  // Restore the previously active tab after a reload.
  const savedTab = sessionStorage.getItem(TAB_KEY);
  if (savedTab) activateTab(savedTab);

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
