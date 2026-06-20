# Plan: Issue #4 — Client-Side Filters and CSS Styling

## Summary
Replace the stub `static/js/filters.js` with a full vanilla ES6 filter implementation, and replace the stub `static/css/style.css` with a complete stylesheet. The JS reads `data-*` attributes on `.card-item` divs and shows/hides them in response to four controls: price cap input, pauper toggle, N slider (Slept On only), and inclusion cap slider (Slept On only). No page reloads, no frameworks. CSS provides a flexbox card grid, hidden state, controls bar, and legible card display.

## User Story
As a deckbuilder, I want to instantly filter cards by price, rarity, and Slept On count using sliders and toggles — without any page reload — so that I can interactively explore the card pool.

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | LOW |
| GitHub Issue | #4 |
| Systems Affected | static/js/filters.js (replace stub), static/css/style.css (replace stub) |

---

## Prerequisite: Issue #3 must be complete

This plan targets `data-*` attributes and `id`s defined by Issue #3's templates. Implement Issue #3 first, then this issue.

---

## Confirmed Contracts from Issue #3 Templates

### Control element IDs (in `commander.html`)
| ID | Element type | Default value |
|---|---|---|
| `price-cap` | `<input type="number">` | empty (no cap) |
| `pauper-toggle` | `<input type="checkbox">` | unchecked |
| `n-slider` | `<input type="range" min="1" max="100">` | `value="50"` |
| `n-label` | `<span>` | `50` |
| `inclusion-cap` | `<input type="range" min="0" max="100">` | `value="10"` |
| `inclusion-label` | `<span>` | `10` |

### Card element contract (every `.card-item` div)
| Attribute | Example value | Notes |
|---|---|---|
| `data-price` | `"1.20"` or `"9999"` | 9999 = no price / never hide |
| `data-rarity` | `"common"` | lowercase Scryfall rarity |
| `data-inclusion` | `"34"` | integer 0–100, percent |

### Slept On cards additionally
| Attribute | Example value |
|---|---|
| `data-score` | `"14.32"` |

### Section structure
- EDHRec cards: `.card-item` divs inside `#edhrec-section`
- Slept On cards: `.card-item` divs inside `#slept-on-section` (specifically `#slept-on-grid`)
- Slept On cards are **pre-sorted server-side** by buzzword_score descending — JS just shows/hides from the top

---

## Filter Logic Spec

### Price cap (applies to BOTH sections)
```
if (priceCap is set and not empty):
    hide card if parseFloat(card.dataset.price) > priceCap
```

### Pauper toggle (applies to BOTH sections)
```
if (pauperOnly is checked):
    hide card if card.dataset.rarity !== "common"
```

### Inclusion cap (applies to Slept On ONLY)
```
hide slept-on card if parseInt(card.dataset.inclusion) > maxInclusion
```

### N slider (applies to Slept On ONLY — counts AFTER other filters applied)
```
visibleCount = 0
for each slept-on card in DOM order:
    if card is NOT already hidden by price/pauper/inclusion:
        if visibleCount < N: show it, visibleCount++
        else: hide it
    (cards already hidden by other filters stay hidden — don't count toward N)
```

**Key**: The N slider must be applied LAST, after price/pauper/inclusion have already determined each card's hidden state.

### Application order
1. Reset all `.card-item` hidden states (start clean)
2. Apply price cap to ALL cards
3. Apply pauper toggle to ALL cards
4. Apply inclusion cap to Slept On cards only
5. Apply N limit to Slept On cards only (counting only those not hidden by steps 2–4)

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `static/js/filters.js` | UPDATE (replace stub) | Full filter implementation |
| `static/css/style.css` | UPDATE (replace stub) | Card grid, hidden state, controls, layout |

---

## Tasks

### Task 1: Implement static/js/filters.js

- **File**: `static/js/filters.js`
- **Action**: UPDATE (replace stub comment with full implementation)
- **Implement**:

```javascript
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
```

- **Validate**: File saved, no syntax errors (open in browser DevTools console — should be clean).

---

### Task 2: Implement static/css/style.css

- **File**: `static/css/style.css`
- **Action**: UPDATE (replace stub comment with full styles)
- **Implement**:

```css
/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: system-ui, sans-serif;
  background: #1a1a2e;
  color: #e0e0e0;
  min-height: 100vh;
}

/* ── Nav ── */
nav {
  background: #16213e;
  padding: 0.75rem 1.5rem;
  border-bottom: 2px solid #0f3460;
}

nav a {
  color: #e94560;
  text-decoration: none;
  font-size: 1.2rem;
  font-weight: bold;
  letter-spacing: 0.03em;
}

/* ── Main layout ── */
main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1.5rem;
}

/* ── Landing page ── */
h1 { font-size: 2rem; margin-bottom: 0.5rem; color: #e94560; }
p  { margin-bottom: 1rem; color: #aaa; }

form {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 1rem;
}

input[type="text"] {
  flex: 1;
  min-width: 280px;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  border: 1px solid #0f3460;
  background: #16213e;
  color: #e0e0e0;
  font-size: 1rem;
}

button[type="submit"] {
  padding: 0.6rem 1.4rem;
  background: #e94560;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  cursor: pointer;
}

button[type="submit"]:hover { background: #c73652; }

/* ── Controls bar ── */
#controls {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  align-items: center;
  background: #16213e;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  border: 1px solid #0f3460;
}

#controls label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
  color: #ccc;
}

#controls input[type="number"] {
  width: 80px;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  border: 1px solid #0f3460;
  background: #1a1a2e;
  color: #e0e0e0;
}

#controls input[type="range"] { width: 120px; accent-color: #e94560; }
#controls input[type="checkbox"] { accent-color: #e94560; width: 16px; height: 16px; }

/* ── Section headings ── */
h2 {
  font-size: 1.5rem;
  margin: 1.5rem 0 0.5rem;
  color: #e94560;
  border-bottom: 1px solid #0f3460;
  padding-bottom: 0.3rem;
}

h3 {
  font-size: 1.1rem;
  margin: 1rem 0 0.5rem;
  color: #aac4e8;
}

/* ── Slept On controls ── */
#slept-on-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

#slept-on-controls label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
  color: #ccc;
}

#slept-on-controls input[type="range"] { width: 120px; accent-color: #e94560; }

/* ── Card grid ── */
.card-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

/* ── Card item ── */
.card-item {
  width: 180px;
  background: #16213e;
  border: 1px solid #0f3460;
  border-radius: 8px;
  overflow: hidden;
  transition: transform 0.15s;
}

.card-item:hover { transform: translateY(-3px); border-color: #e94560; }

.card-item img {
  width: 100%;
  display: block;
}

.card-info {
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.card-info strong {
  font-size: 0.78rem;
  color: #e0e0e0;
  line-height: 1.2;
}

.card-info span {
  font-size: 0.72rem;
  color: #999;
}

/* ── Hidden state (toggled by filters.js) ── */
.card-item.hidden { display: none; }

/* ── Error page ── */
.error-page { text-align: center; padding: 4rem 1rem; }
.error-page h1 { color: #e94560; }
.error-page a { color: #aac4e8; }
```

- **Validate**: Open app in browser — cards appear in a grid, layout is readable.

---

### Task 3: Browser validation checklist

After both files are saved with the app running (`python app.py`), navigate to a commander page and verify manually:

- [ ] Cards render in a flexbox grid (~180px wide each)
- [ ] Price cap input: type `1.00` — cards above $1 disappear from both sections
- [ ] Price cap input: clear it — all cards reappear
- [ ] Pauper toggle: check it — only common-rarity cards remain in both sections
- [ ] Pauper toggle: uncheck — all cards reappear
- [ ] N slider: drag to `10` — Slept On shrinks to 10 cards; EDHRec unaffected
- [ ] N slider: drag to `100` — Slept On shows up to 100 cards
- [ ] Inclusion cap: drag to `0` — Slept On empties (all color-pool cards have 0.0 inclusion by default, so at cap=0 they should ALL show — wait, `data-inclusion=0` and cap=0 means `0 <= 0` so they pass. This is correct.)
- [ ] N label and inclusion label update live as sliders move
- [ ] Navigate to `/` — no JS console errors (guard `if (!nSlider) return` fires)
- [ ] DevTools console on commander page: zero errors

---

## Validation Sequence

```
1. Open http://localhost:5000/commander/atraxa-praetors-voice (after Issue #3 is done)
2. Run Task 3 browser checklist above
3. Open DevTools console — confirm zero errors on both / and /commander/... pages
```

No lint needed for CSS/JS in this personal project. The browser console is the validator.

---

## Acceptance Criteria

- [ ] `static/js/filters.js` is no longer a stub — contains full `applyFilters()` implementation
- [ ] Guard `if (!nSlider) return` prevents errors on non-commander pages
- [ ] Price cap hides cards in BOTH sections where `data-price > value`
- [ ] Pauper toggle hides non-`"common"` rarity cards in BOTH sections
- [ ] N slider limits Slept On to top N cards counting only those not hidden by other filters
- [ ] Inclusion cap hides Slept On cards where `data-inclusion > value`
- [ ] All four filters fire on `input`/`change` events with no page reload
- [ ] `#n-label` and `#inclusion-label` update live as sliders move
- [ ] `applyFilters()` runs on page load to apply defaults (N=50, inclusion cap=10%)
- [ ] `static/css/style.css` is no longer a stub — cards render in a flexbox grid
- [ ] `.card-item.hidden { display: none }` present in CSS
- [ ] Zero JS console errors on both the landing page and commander page
- [ ] Resolves GitHub Issue #4
