(() => {
  'use strict';
  const input = document.getElementById('doc-search');
  const results = document.getElementById('search-results');
  const status = document.getElementById('search-status');
  const list = results.querySelector('ul');
  const docs = window.LCOS_DOCS || [];
  const hide = () => { results.hidden = true; input.setAttribute('aria-expanded', 'false'); };
  input.addEventListener('input', () => {
    const query = input.value.trim().toLowerCase();
    list.replaceChildren();
    if (!query) { hide(); return; }
    const words = query.split(/\s+/);
    const matches = docs.filter(doc => words.every(word => (doc.title + ' ' + doc.text).toLowerCase().includes(word)))
      .sort((a, b) => Number(b.title.toLowerCase().includes(query)) - Number(a.title.toLowerCase().includes(query))).slice(0, 12);
    status.textContent = matches.length ? `${matches.length} matching topics` : 'No matching topics. Try “capture”, “move”, or “fonts”.';
    for (const doc of matches) {
      const li = document.createElement('li'); const a = document.createElement('a'); a.href = doc.url;
      const title = document.createElement('strong'); title.textContent = doc.title;
      const excerpt = document.createElement('small'); excerpt.textContent = doc.description;
      a.append(title, excerpt); li.append(a); list.append(li);
    }
    results.hidden = false; input.setAttribute('aria-expanded', 'true');
  });
  input.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown') { const first = list.querySelector('a'); if (first) { event.preventDefault(); first.focus(); } }
    if (event.key === 'Enter' && !results.hidden) { const first = list.querySelector('a'); if (first) { event.preventDefault(); first.click(); } }
    if (event.key === 'Escape') hide();
  });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); input.focus(); input.select(); }
    if (event.key === 'Escape') { hide(); document.body.classList.remove('nav-open'); document.querySelector('.menu-toggle').setAttribute('aria-expanded', 'false'); }
  });
  document.addEventListener('click', event => { if (!event.target.closest('.search')) hide(); });
  const menu = document.querySelector('.menu-toggle');
  menu.addEventListener('click', () => { const open = document.body.classList.toggle('nav-open'); menu.setAttribute('aria-expanded', String(open)); });
  for (const pre of document.querySelectorAll('pre')) {
    const code = pre.querySelector('code'); if (!code) continue;
    const button = document.createElement('button'); button.type = 'button'; button.className = 'copy-code'; button.textContent = 'Copy'; button.setAttribute('aria-label', 'Copy code example');
    button.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(code.textContent); button.textContent = 'Copied'; }
      catch { const range = document.createRange(); range.selectNodeContents(code); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range); button.textContent = 'Selected — press Ctrl+C'; }
      setTimeout(() => { button.textContent = 'Copy'; }, 2200);
    });
    pre.append(button);
  }
})();
