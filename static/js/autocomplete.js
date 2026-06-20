document.addEventListener('DOMContentLoaded', () => {
  const datalist = document.getElementById('commander-list');

  // Guard: only run on the landing page, where the datalist exists.
  if (!datalist) return;

  // Fetch the commander-name list once (relative path resolves to the
  // /commanders.json route live, or docs/commanders.json in the static export),
  // then inject every name as an <option> in a single DOM insert. The native
  // <datalist> handles filtering, the dropdown, and keyboard navigation.
  fetch('commanders.json')
    .then(resp => resp.ok ? resp.json() : Promise.reject(resp.status))
    .then(names => {
      const frag = document.createDocumentFragment();
      names.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        frag.appendChild(opt);
      });
      datalist.appendChild(frag);
    })
    .catch(() => { /* suggestions unavailable; manual search still works */ });
});
