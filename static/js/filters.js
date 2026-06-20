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
  const sleptOnCards = document.querySelectorAll('#slept-on-grid .card-item');

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

    // Apply price cap, pauper, and inclusion cap to Slept On section, then N limit
    let visibleCount = 0;
    sleptOnCards.forEach(card => {
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
