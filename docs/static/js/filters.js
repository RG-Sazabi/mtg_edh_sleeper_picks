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

    // Step 1+2: Apply price cap and pauper to EDHRec section
    edhrecCards.forEach(card => {
      const price = parseFloat(card.dataset.price);
      const rarity = card.dataset.rarity;
      const hide = price > maxPrice || (pauperOnly && rarity !== 'common');
      card.classList.toggle('hidden', hide);
    });

    // Step 1+2+3: Apply price cap, pauper, and inclusion cap to Slept On section
    // Then step 4: Apply N limit (count only cards not already hidden)
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
});
