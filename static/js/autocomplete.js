document.addEventListener('DOMContentLoaded', () => {
  const commanderInput = document.getElementById('commander-input');
  const commanderList = document.getElementById('commander-suggestions');
  const hint = document.getElementById('autocomplete-hint');
  const hintTop = document.getElementById('autocomplete-top');
  const partnerWrap = document.getElementById('partner-wrap');
  const partnerInput = document.getElementById('partner-input');
  const partnerList = document.getElementById('partner-suggestions');

  // Guard: only run on the landing page, where the search input exists.
  if (!commanderInput || !commanderList) return;

  const MAX_RESULTS = 10;
  let names = [];            // full commander list, fetched once
  let partnerNames = [];     // current legal-partner pool (per chosen commander)
  let partnerInited = false; // setupAutocomplete bound to partner input yet?

  // Reusable autocomplete bound to one input + suggestion list. ``getNames``
  // returns the current candidate array (so the partner pool can change without
  // rebinding). ``opts`` may carry primary-only hint elements and an ``onChoose``
  // override; by default choosing a suggestion submits the form.
  function setupAutocomplete(input, list, getNames, opts = {}) {
    if (!input || !list) return;
    const hintEl = opts.hint || null;
    const hintTopEl = opts.hintTop || null;
    const onChoose = opts.onChoose || ((name) => {
      input.value = name;
      input.form.requestSubmit();
    });

    let matches = [];   // current filtered suggestions (<= MAX_RESULTS)
    let active = -1;    // index of the highlighted suggestion, or -1

    // Rank: case-insensitive, prefix matches before substring matches, each
    // group kept in the source list's order. Capped to MAX_RESULTS.
    function findMatches(query) {
      const q = query.trim().toLowerCase();
      if (!q) return [];
      const prefix = [];
      const contains = [];
      for (const name of getNames()) {
        const lower = name.toLowerCase();
        if (lower.startsWith(q)) prefix.push(name);
        else if (lower.includes(q)) contains.push(name);
        if (prefix.length >= MAX_RESULTS) break;
      }
      return prefix.concat(contains).slice(0, MAX_RESULTS);
    }

    function closeList() {
      list.hidden = true;
      list.innerHTML = '';
      input.setAttribute('aria-expanded', 'false');
      active = -1;
      if (hintEl) hintEl.hidden = true;
    }

    function render() {
      if (!matches.length) {
        closeList();
        return;
      }
      const frag = document.createDocumentFragment();
      matches.forEach((name, i) => {
        const li = document.createElement('li');
        li.textContent = name;
        li.setAttribute('role', 'option');
        if (i === active) li.classList.add('active');
        // Mousedown (not click) so it fires before the input's blur closes the list.
        li.addEventListener('mousedown', e => {
          e.preventDefault();
          choose(name);
        });
        frag.appendChild(li);
      });
      list.innerHTML = '';
      list.appendChild(frag);
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');

      // Tab-completion hint shows the top match (the one Tab will accept).
      if (hintEl && hintTopEl) {
        hintTopEl.textContent = matches[0];
        hintEl.hidden = false;
      }
    }

    function filterAndRender() {
      matches = findMatches(input.value);
      active = -1;
      render();
    }

    function setActive(i) {
      active = i;
      Array.from(list.children).forEach((li, idx) => {
        li.classList.toggle('active', idx === active);
      });
    }

    // Fill the input with a name (does not submit). Used by Tab completion.
    function complete(name) {
      input.value = name;
      filterAndRender();
    }

    // Pick a suggestion: fill input, close list, run the configured action.
    function choose(name) {
      input.value = name;
      closeList();
      onChoose(name);
    }

    input.addEventListener('input', filterAndRender);

    input.addEventListener('keydown', e => {
      switch (e.key) {
        case 'ArrowDown':
          if (!matches.length) return;
          e.preventDefault();
          setActive((active + 1) % matches.length);
          break;
        case 'ArrowUp':
          if (!matches.length) return;
          e.preventDefault();
          setActive((active - 1 + matches.length) % matches.length);
          break;
        case 'Tab':
          // Complete to the highlighted match, or the top match if none is.
          if (matches.length) {
            e.preventDefault();
            complete(active >= 0 ? matches[active] : matches[0]);
          }
          break;
        case 'Enter':
          // If a suggestion is highlighted, pick it; otherwise let the form submit.
          if (active >= 0) {
            e.preventDefault();
            choose(matches[active]);
          }
          break;
        case 'Escape':
          closeList();
          break;
        default:
          break;
      }
    });

    // Close when focus leaves the field (mousedown on a suggestion runs first).
    input.addEventListener('blur', closeList);

    // Expose a re-filter hook so the page can refresh suggestions when the
    // candidate list arrives after the user has already typed.
    return { filterAndRender };
  }

  // Reveal / restrict the partner input based on commander 1's eligibility.
  // ``submitIfSingle`` submits the single-commander form when the chosen
  // commander has no partners (an active selection), but stays put on a passive
  // commit (blur) so the user can keep editing.
  function evaluatePartner(name, submitIfSingle) {
    if (!partnerWrap) return;
    if (!names.includes(name)) return;  // only react to real commander names
    fetch('/partners?name=' + encodeURIComponent(name))
      .then(resp => (resp.ok ? resp.json() : Promise.reject(resp.status)))
      .then(data => {
        if (data.eligible) {
          partnerNames = data.partners;
          partnerWrap.hidden = false;
          if (!partnerInited) {
            setupAutocomplete(partnerInput, partnerList, () => partnerNames);
            partnerInited = true;
          }
          partnerInput.focus();
        } else {
          // Not a partner commander: hide + clear so a later change re-evaluates.
          partnerWrap.hidden = true;
          if (partnerInput) partnerInput.value = '';
          if (submitIfSingle) commanderInput.form.requestSubmit();
        }
      })
      .catch(() => { /* eligibility unknown; manual submit still works */ });
  }

  // Primary input: choosing a real commander checks eligibility instead of
  // submitting outright, so a partner-eligible pick can reveal the second box.
  const primary = setupAutocomplete(
    commanderInput,
    commanderList,
    () => names,
    {
      hint,
      hintTop,
      onChoose: (name) => { evaluatePartner(name, true); },
    }
  );

  // Manual entry (typed full name, then blur) re-evaluates without submitting.
  commanderInput.addEventListener('blur', () => {
    evaluatePartner(commanderInput.value.trim(), false);
  });

  // Fetch the commander-name list once from the /commanders.json route
  // (relative path resolves against the landing page).
  fetch('commanders.json')
    .then(resp => (resp.ok ? resp.json() : Promise.reject(resp.status)))
    .then(data => {
      names = data;
      // If the user already typed before the list arrived, show matches now.
      if (document.activeElement === commanderInput && primary) primary.filterAndRender();
    })
    .catch(() => { /* suggestions unavailable; manual search still works */ });
});
