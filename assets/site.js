/* NanoBaseLib site script — no dependencies.
   Theme toggle, mobile sidebar, TOC scroll-spy, copy buttons,
   sortable tables, dataset table filtering, back-to-top. */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  /* ---------- theme ---------- */
  const root = document.documentElement;
  function currentTheme() {
    const t = root.getAttribute('data-theme');
    if (t) return t;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  $$('.theme-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const next = currentTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('nbl-theme', next); } catch (e) { /* storage unavailable */ }
    });
  });

  /* ---------- mobile sidebar ---------- */
  const sidebar = $('.sidebar');
  const backdrop = $('.sidebar-backdrop');
  const menuBtn = $('.menu-btn');
  function closeSidebar() { sidebar && sidebar.classList.remove('open'); backdrop && backdrop.classList.remove('show'); menuBtn && menuBtn.setAttribute('aria-expanded', 'false'); }
  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', () => {
      const open = !sidebar.classList.contains('open');
      sidebar.classList.toggle('open', open); backdrop && backdrop.classList.toggle('show', open);
      menuBtn.setAttribute('aria-expanded', String(open));
    });
    backdrop && backdrop.addEventListener('click', closeSidebar);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSidebar(); });
  }

  /* ---------- TOC scroll-spy ---------- */
  const tocLinks = $$('.toc a[href^="#"]');
  if (tocLinks.length && 'IntersectionObserver' in window) {
    const byId = new Map(tocLinks.map(a => [a.getAttribute('href').slice(1), a]));
    const headings = Array.from(byId.keys()).map(id => document.getElementById(id)).filter(Boolean);
    let active = null;
    const setActive = id => {
      if (active === id) return; active = id;
      tocLinks.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + id));
    };
    const io = new IntersectionObserver(entries => {
      const visible = entries.filter(e => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible.length) setActive(visible[0].target.id);
    }, { rootMargin: '-72px 0px -70% 0px', threshold: 0 });
    headings.forEach(h => io.observe(h));
  }

  /* ---------- copy buttons ---------- */
  $$('.code-block').forEach(block => {
    const pre = $('pre', block); if (!pre) return;
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'copy'; btn.textContent = 'Copy'; btn.setAttribute('aria-label', 'Copy code to clipboard');
    btn.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(pre.innerText.replace(/\n$/, '')); btn.textContent = 'Copied'; }
      catch (e) { btn.textContent = 'Press ⌘C'; }
      setTimeout(() => { btn.textContent = 'Copy'; }, 1600);
    });
    block.appendChild(btn);
  });

  /* ---------- sortable tables ---------- */
  function cellValue(td) {
    const v = td.getAttribute('data-sort');
    if (v !== null) { const n = parseFloat(v); return isNaN(n) ? v : n; }
    const t = td.textContent.trim().replace(/,/g, '');
    const n = parseFloat(t); return isNaN(n) || !/^-?[\d.]+/.test(t) ? t.toLowerCase() : n;
  }
  $$('table[data-sortable]').forEach(table => {
    const ths = $$('thead th', table);
    ths.forEach((th, idx) => {
      if (th.hasAttribute('data-nosort')) return;
      th.classList.add('sortable'); th.tabIndex = 0; th.setAttribute('role', 'button');
      const sort = () => {
        const dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
        ths.forEach(o => o.removeAttribute('aria-sort')); th.setAttribute('aria-sort', dir);
        const tbody = $('tbody', table);
        const rows = $$('tr', tbody).filter(r => !r.classList.contains('empty-row'));
        rows.sort((a, b) => {
          const va = cellValue(a.children[idx]), vb = cellValue(b.children[idx]);
          const cmp = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb), undefined, { numeric: true });
          return dir === 'ascending' ? cmp : -cmp;
        });
        rows.forEach(r => tbody.appendChild(r));
        table.classList.add('sorted');
      };
      th.addEventListener('click', sort);
      th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sort(); } });
    });
  });

  /* ---------- dataset filtering (dataset.html / raw.html) ---------- */
  $$('[data-filter-table]').forEach(toolbar => {
    const table = document.getElementById(toolbar.getAttribute('data-filter-table')); if (!table) return;
    const search = $('input[type="search"]', toolbar);
    const selects = $$('select', toolbar);
    const chips = $$('.chip[data-task]', toolbar);
    const count = $('.count', toolbar);
    const rows = $$('tbody tr', table).filter(r => !r.classList.contains('empty-row'));
    let empty = $('tbody tr.empty-row', table);
    if (!empty) {
      empty = document.createElement('tr'); empty.className = 'empty-row'; empty.hidden = true;
      const td = document.createElement('td'); td.colSpan = $$('thead th', table).length; td.textContent = 'No samples match the current filters.';
      empty.appendChild(td); $('tbody', table).appendChild(empty);
    }
    const state = { q: '', tasks: new Set() };
    function apply() {
      const q = state.q.trim().toLowerCase();
      let shown = 0;
      rows.forEach(r => {
        let ok = true;
        if (q && !r.textContent.toLowerCase().includes(q)) ok = false;
        selects.forEach(sel => { if (ok && sel.value && r.getAttribute('data-' + sel.name) !== sel.value) ok = false; });
        if (ok && state.tasks.size) { const t = (r.getAttribute('data-tasks') || '').split(' '); for (const need of state.tasks) if (!t.includes(need)) { ok = false; break; } }
        r.hidden = !ok; if (ok) shown++;
      });
      empty.hidden = shown > 0;
      if (count) count.textContent = shown === rows.length ? `${rows.length} samples` : `${shown} of ${rows.length} samples`;
      // group cells: hide group label rows whose whole group is hidden is handled by per-row rendering (no rowspans).
    }
    search && search.addEventListener('input', () => { state.q = search.value; apply(); });
    selects.forEach(sel => sel.addEventListener('change', apply));
    chips.forEach(ch => ch.addEventListener('click', () => {
      const t = ch.getAttribute('data-task'); const on = ch.getAttribute('aria-pressed') !== 'true';
      ch.setAttribute('aria-pressed', String(on)); on ? state.tasks.add(t) : state.tasks.delete(t); apply();
    }));
    const reset = $('.reset', toolbar);
    reset && reset.addEventListener('click', () => {
      state.q = ''; state.tasks.clear(); if (search) search.value = '';
      selects.forEach(s => { s.value = ''; }); chips.forEach(c => c.setAttribute('aria-pressed', 'false')); apply();
    });
    apply();
  });

  /* ---------- back to top ---------- */
  const toTop = $('.to-top');
  if (toTop) {
    const onScroll = () => toTop.classList.toggle('show', window.scrollY > 600);
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll();
    toTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
  }

  /* ---------- external links ---------- */
  $$('a[href^="http"]').forEach(a => { if (a.host !== location.host) { a.rel = 'noopener'; if (!a.target) a.target = '_blank'; } });
})();
