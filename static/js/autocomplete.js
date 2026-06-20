document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('commander-input');
  const list = document.getElementById('commander-suggestions');
  const hint = document.getElementById('autocomplete-hint');
  const hintTop = document.getElementById('autocomplete-top');

  // Guard: only run on the landing page, where the search input exists.
  if (!input || !list) return;

  const MAX_RESULTS = 10;
  let names = [];      // full commander list, fetched once
  let matches = [];    // current filtered suggestions (<= MAX_RESULTS)
  let active = -1;     // index of the highlighted suggestion, or -1

  // Fetch the commander-name list once (relative path resolves to the
  // /commanders.json route live, or docs/commanders.json in the static export).
  fetch('commanders.json')
    .then(resp => (resp.ok ? resp.json() : Promise.reject(resp.status)))
    .then(data => {
      names = data;
      // If the user already typed before the list arrived, show matches now.
      if (document.activeElement === input) filterAndRender();
    })
    .catch(() => { /* suggestions unavailable; manual search still works */ });

  // Rank: case-insensitive, prefix matches before substring matches, each group
  // kept in the list's existing alphabetical order. Capped to MAX_RESULTS.
  function findMatches(query) {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const prefix = [];
    const contains = [];
    for (const name of names) {
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
    if (hint) hint.hidden = true;
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
    if (hint && hintTop) {
      hintTop.textContent = matches[0];
      hint.hidden = false;
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

  // Pick a suggestion and run the search (fills input, then submits the form).
  function choose(name) {
    input.value = name;
    closeList();
    input.form.requestSubmit();
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
});
