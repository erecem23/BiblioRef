/* «Referencias por tesis»: moving between theses and through the whole PDF.

   - Between theses, two layouts the reader picks (a browser preference, never thesis data):
     «list»: a column with every thesis of the project and its open problems;
     «header»: ‹ T0145 ▾ › in the toolbar, with the same list in a menu.
     Alt+↑/↓ and Alt+←/→ move to the previous or next thesis in both.
   - Through the PDF: a vertical rail beside the pages, one mark per page. Blue is the bibliography,
     amber a possible bibliography or a paragraph still missing. A page outside the bibliography opens
     the whole PDF, page by page, until «Volver a la bibliografía». */
(() => {
  const NAV_KEY = 'biblioref.review-nav';
  const style = document.createElement('style');
  style.id = 'review-navigation-style';
  style.textContent = `
    /* thesis list (layout «list») */
    .workspace.nav-list{grid-template-columns:250px minmax(0,1fr) 0 34px;grid-template-areas:'list viewer refs tab'}
    .workspace.nav-list.drawer-open{grid-template-columns:250px minmax(0,1fr) 360px 34px}
    .workspace .rn-list{grid-area:list;display:none;flex-direction:column;min-width:0;background:var(--surface);border-right:1px solid var(--line);max-height:calc(100vh - 106px);position:sticky;top:0}
    .workspace.nav-list .rn-list{display:flex}
    .rn-listhead{padding:12px 14px 6px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
    .rn-listhint{padding:0 14px 8px;font-size:11.5px;color:var(--muted)}
    .rn-items{overflow:auto;flex:1;min-height:0;border-top:1px solid var(--line);overscroll-behavior:contain}
    .rn-item{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);background:none;padding:10px 14px;font:inherit;color:var(--ink);cursor:pointer}
    .rn-item:hover{background:var(--canvas)}
    .rn-item[aria-current="true"]{background:var(--accent-bg);box-shadow:inset 4px 0 var(--accent)}
    .rn-item b{font-size:13.5px}
    .rn-item .rn-who{font-size:13px;color:var(--muted)}
    .rn-item .rn-pb{display:block;margin-top:3px;font-size:12px;color:var(--warn)}
    .rn-item .rn-pb.ok{color:var(--muted)}
    /* thesis switch (layout «header») */
    .rn-switch{display:none;align-items:center;gap:6px;position:relative}
    #screen-review.nav-header .rn-switch{display:flex}
    /* The old «select ← anterior siguiente →» stays in the DOM for the code that updates it, hidden. */
    #screen-review .review-toolbar>.toolbar-group[aria-label="Tesis"]{display:none}
    .rn-switch .rn-step{min-width:38px;font-size:16px}
    .rn-current{display:flex;flex-direction:column;align-items:flex-start;border:1px solid var(--accent);border-radius:8px;background:var(--surface);padding:3px 12px;font:inherit;color:var(--ink);cursor:pointer;min-width:280px;max-width:520px;text-align:left}
    .rn-current small{font-size:11.5px;color:var(--muted)}
    .rn-current b{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
    .rn-pop{position:absolute;left:44px;top:calc(100% + 6px);z-index:60;width:440px;max-height:60vh;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow-md,0 10px 28px rgba(20,24,36,.16))}
    .rn-pop[hidden]{display:none}
    .rn-pop .rn-items{border-top:0}
    .rn-mode{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
    .rn-mode .viewtoggle button{padding:4px 10px}
    /* page rail beside the PDF */
    .rn-body{display:flex;gap:8px;min-height:0;align-items:stretch}
    .rn-body>#pageWrap{flex:1;min-width:0}
    .rn-rail{display:flex;flex-direction:column;align-items:center;gap:4px;width:34px;flex:none;max-height:calc(100vh - 128px);font-size:10.5px;color:var(--muted);font-variant-numeric:tabular-nums}
    #screen-review.nav-header .rn-rail{order:2}
    .rn-strip{position:relative;flex:1;width:20px;display:flex;flex-direction:column;gap:1px;border-radius:6px;cursor:pointer;touch-action:none;outline-offset:2px;min-height:120px}
    .rn-strip:focus-visible{outline:2px solid var(--accent)}
    .rn-tick{flex:1;min-height:1px;background:#e3e6ec;border-radius:1px;position:relative}
    .rn-tick.sec{background:var(--accent)}
    .rn-tick.cand{background:var(--warn)}
    .rn-tick.off{background:repeating-linear-gradient(135deg,#9aa1ad 0 2px,#d6dae2 2px 4px)}
    .rn-tick.miss::after{content:'';position:absolute;inset:0 0 0 55%;background:var(--warn)}
    .rn-tick.cur{outline:2px solid var(--ink);outline-offset:1px;z-index:1}
    .rn-tip{position:absolute;right:calc(100% + 6px);transform:translateY(-50%);padding:2px 7px;border-radius:5px;background:var(--ink);color:#fff;font-size:11px;white-space:nowrap;pointer-events:none;z-index:5}
    #screen-review.nav-header .rn-tip{right:auto;left:calc(100% + 6px)}
    #screen-review .viewerbar{flex-wrap:nowrap}
    #screen-review .viewercontext{flex:1 1 auto;min-width:0}
    #screen-review .viewerbar .toolbar{flex:none;flex-wrap:nowrap}
    .rn-pagelabel{font-size:12px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
    /* section tools grouped in one menu */
    .rn-limits>summary{white-space:nowrap}
    .rn-limits .toolmorepop{min-width:250px;display:flex;flex-direction:column;align-items:stretch;gap:4px}
    .rn-limits .toolmorepop .btn{justify-content:flex-start;text-align:left}
    /* whole PDF */
    .rn-whole{position:sticky;top:-12px;z-index:6;display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:-12px -20px 12px -78px;padding:10px 14px;background:#fff;border-bottom:1px solid var(--line);font-size:13px}
    .rn-whole b{font-size:13.5px}
    .rn-page{position:relative;width:min(96%,900px);margin:0 auto 12px;background:#fff;border-radius:var(--radius-sm);box-shadow:0 3px 12px rgba(16,24,40,.16);overflow:hidden}
    .rn-page img{display:block;width:100%;height:auto}
    .rn-page.sec{box-shadow:0 0 0 3px var(--accent),0 3px 12px rgba(16,24,40,.16);cursor:pointer}
    .rn-page .pagebadge.sec{background:var(--accent-bg);color:var(--accent-dark,#1f56c4);border-color:#a9c3f7}
  `;
  document.head.appendChild(style);

  const screen = document.getElementById('screen-review');
  const workspace = document.getElementById('reviewWorkspace');
  const toolbar = screen?.querySelector('.review-toolbar');
  const wrap = document.getElementById('pageWrap');
  if(!screen || !workspace || !toolbar || !wrap) return;

  const fmt = n => Number(n || 0).toLocaleString('es-AR');
  const pref = () => { try{ return localStorage.getItem(NAV_KEY) === 'header' ? 'header' : 'list'; }catch{ return 'list'; } };

  // ---- Between theses ------------------------------------------------------------------
  const PB_ORDER = ['missing', 'merged', 'boundaries', 'type', 'author', 'year'];
  function problemLine(d){
    const P = window.BiblioRefProblems;
    if(!P) return '';
    const c = P.counts(d) || {};
    const parts = PB_ORDER.filter(k => c[k]).map(k => `${fmt(c[k])} ${P.LABELS[k][c[k] === 1 ? 0 : 1]}`);
    return parts.slice(0, 2).join(' · ');
  }
  const surname = d => String((d.metadata || {}).author || '').split(/[,;]| y /)[0].trim().split(/\s+/).slice(-1)[0] || '';
  function itemsHtml(){
    const current = S.doc?.id;
    return S.docs.map(d => {
      const pb = problemLine(d);
      const who = surname(d);
      return `<button type="button" class="rn-item" data-rn-doc="${esc(d.id)}" aria-current="${d.id === current}" title="${esc(displayTitle(d))}">
        <b>${esc(d.thesis_id || '')}</b>${who ? ` <span class="rn-who">· ${esc(who)}</span>` : ''}
        <span class="rn-pb ${pb ? '' : 'ok'}">${pb ? esc(pb) : (d.n_references ? `${fmt(d.n_references)} referencias · sin avisos` : 'sin referencias')}</span></button>`;
    }).join('');
  }

  const list = document.createElement('aside');
  list.className = 'rn-list';
  list.setAttribute('aria-label', 'Tesis del proyecto');
  workspace.insertBefore(list, workspace.firstChild);

  const sw = document.createElement('div');
  sw.className = 'rn-switch';
  sw.innerHTML = `<button type="button" class="btn xs rn-step" data-rn-step="-1" aria-label="Tesis anterior" title="Tesis anterior (Alt+←)">‹</button>
    <button type="button" class="rn-current" aria-haspopup="listbox" aria-expanded="false"><small></small><b></b></button>
    <button type="button" class="btn xs rn-step" data-rn-step="1" aria-label="Tesis siguiente" title="Tesis siguiente (Alt+→)">›</button>
    <div class="rn-pop" hidden><div class="rn-listhead">Tesis del proyecto</div><div class="rn-items"></div></div>`;
  const firstGroup = toolbar.querySelector('.toolbar-group');
  (firstGroup || toolbar).insertAdjacentElement(firstGroup ? 'afterend' : 'afterbegin', sw);

  const mode = document.createElement('div');
  mode.className = 'rn-mode';
  mode.innerHTML = `<span>Tesis:</span><span class="viewtoggle" role="group" aria-label="Cómo cambiar de tesis">
    <button type="button" data-rn-mode="list" title="Una columna con todas las tesis a la izquierda">Lista</button>
    <button type="button" data-rn-mode="header" title="La tesis actual arriba, con ‹ ›  y un menú">Encabezado</button></span>`;
  const more = toolbar.querySelector('#reviewMoreMenu');
  toolbar.insertBefore(mode, more || null);

  function renderTheses(){
    const i = Math.max(0, S.docs.findIndex(d => d.id === S.doc?.id));
    const d = S.docs[i];
    list.innerHTML = `<div class="rn-listhead">Tesis del proyecto · ${fmt(S.docs.length)}</div><div class="rn-listhint">Alt+↑ / Alt+↓ cambia de tesis</div><div class="rn-items">${itemsHtml()}</div>`;
    list.querySelector('[aria-current="true"]')?.scrollIntoView({block: 'nearest'});
    sw.querySelector('.rn-current small').textContent = S.docs.length ? `Tesis ${i + 1} de ${S.docs.length} · ${problemLine(d || {}) || 'sin avisos'}` : '';
    sw.querySelector('.rn-current b').textContent = d ? `${d.thesis_id || ''} · ${displayTitle(d)}` : 'Elegí una tesis';
    const pop = sw.querySelector('.rn-pop');
    if(!pop.hidden) pop.querySelector('.rn-items').innerHTML = itemsHtml();
  }
  function applyMode(){
    const m = pref();
    setTimeout(fit, 0);
    workspace.classList.toggle('nav-list', m === 'list');
    screen.classList.toggle('nav-header', m === 'header');
    mode.querySelectorAll('[data-rn-mode]').forEach(b => b.classList.toggle('active', b.dataset.rnMode === m));
    setTimeout(() => window.renderMargin?.(), 260);
  }
  async function step(delta){
    if(!S.docs.length) return;
    let i = Math.max(0, S.docs.findIndex(d => d.id === S.doc?.id));
    i = (i + delta + S.docs.length) % S.docs.length;
    await selectDoc(S.docs[i].id);
  }
  const closePop = () => { const pop = sw.querySelector('.rn-pop'); pop.hidden = true; sw.querySelector('.rn-current').setAttribute('aria-expanded', 'false'); };

  mode.addEventListener('click', e => {
    const b = e.target.closest('[data-rn-mode]');
    if(!b) return;
    try{ localStorage.setItem(NAV_KEY, b.dataset.rnMode); }catch{ /* only this session */ }
    applyMode();
  });
  const pick = e => { const b = e.target.closest('[data-rn-doc]'); if(b){ closePop(); selectDoc(b.dataset.rnDoc); } };
  list.addEventListener('click', pick);
  sw.addEventListener('click', e => {
    const s = e.target.closest('[data-rn-step]');
    if(s) return step(Number(s.dataset.rnStep));
    if(e.target.closest('.rn-current')){
      const pop = sw.querySelector('.rn-pop');
      pop.hidden = !pop.hidden;
      sw.querySelector('.rn-current').setAttribute('aria-expanded', String(!pop.hidden));
      if(!pop.hidden){ pop.querySelector('.rn-items').innerHTML = itemsHtml(); pop.querySelector('[aria-current="true"]')?.scrollIntoView({block: 'nearest'}); }
      return;
    }
    pick(e);
  });
  document.addEventListener('click', e => { if(!e.target.closest('.rn-switch')) closePop(); });
  document.addEventListener('keydown', e => {
    if(!screen.classList.contains('active')) return;
    if(e.key === 'Escape') closePop();
    if(!e.altKey || e.ctrlKey || e.metaKey) return;
    const delta = {ArrowUp: -1, ArrowLeft: -1, ArrowDown: 1, ArrowRight: 1}[e.key];
    if(!delta || e.target.closest?.('input,textarea,select,[contenteditable="true"]')) return;
    e.preventDefault();
    step(delta);
  });

  // ---- Section tools in one menu --------------------------------------------------------
  const limits = document.querySelector('.viewerbar .toolbar-group[aria-label="Límites de la sección"]');
  if(limits){
    const menu = limits.querySelector('details.toolmore');
    const pop = menu?.querySelector('.toolmorepop');
    if(menu && pop){
      menu.classList.add('rn-limits');
      const summary = menu.querySelector('summary');
      summary.textContent = 'Límites de la sección ▾';
      summary.title = 'Marcar inicio o final, aplicar, editar o agregar secciones';
      const relabel = (id, text) => { const b = document.getElementById(id); if(b){ b.textContent = text; pop.appendChild(b); } };
      relabel('visibleStart', 'Marcar el inicio en el PDF');
      relabel('visibleEnd', 'Marcar el final en el PDF');
      relabel('applySectionLimits', 'Aplicar límites y volver a extraer…');
      relabel('editSection', 'Editar límites por número…');
      relabel('addSection', '＋ Agregar sección');
      document.getElementById('applySectionLimits')?.classList.remove('primary');
    }
  }

  // ---- Page rail ---------------------------------------------------------------------
  const body = document.createElement('div');
  body.className = 'rn-body';
  wrap.parentNode.insertBefore(body, wrap);
  body.appendChild(wrap);
  const rail = document.createElement('div');
  rail.className = 'rn-rail';
  rail.innerHTML = '<span class="rn-first">1</span><div class="rn-strip" role="slider" tabindex="0" aria-label="Página del PDF" aria-orientation="vertical" aria-valuemin="1"></div><span class="rn-last"></span>';
  body.insertBefore(rail, wrap);
  const strip = rail.querySelector('.rn-strip');
  const label = document.createElement('span');
  label.className = 'rn-pagelabel';
  document.querySelector('.viewercontext')?.appendChild(label);

  let drawnKey = '', dragging = false;
  const mapFor = () => S.doc ? S.docMaps?.[`${S.doc.id}|${S.doc.updated_at || ''}`] : null;
  async function docMap(){
    const pending = mapFor();
    if(!pending) return {candidates: []};
    try{ const m = await pending; return m && !m.error ? m : {candidates: []}; }catch{ return {candidates: []}; }
  }
  const inSection = page => (S.doc?.sections || []).some(s => page >= (+s.start_page || 1) && page <= (+s.end_page || S.doc.page_count));
  const missingPages = () => { try{ return new Set((window.activeMissing?.() || []).map(x => +x.page)); }catch{ return new Set(); } };

  async function draw(){
    if(!S.doc){ strip.innerHTML = ''; label.textContent = ''; drawnKey = ''; return; }
    const count = S.doc.page_count || 1;
    const secs = S.doc.sections || [];
    const cands = (await docMap()).candidates || [];
    const miss = missingPages();
    const key = `${S.doc.id}|${S.doc.updated_at}|${secs.map(s => `${s.start_page}-${s.end_page}`).join(',')}|${(S.doc.discarded_sections || []).length}|${cands.length}|${[...miss].join(',')}|${count}`;
    if(key !== drawnKey){
      drawnKey = key;
      const off = S.doc.discarded_sections || [];
      const kind = p => inSection(p) ? 'sec'
        : off.some(d => p >= d.section.start_page && p <= d.section.end_page) ? 'off'
        : cands.some(c => p >= c.start_page && p <= c.end_page) ? 'cand' : '';
      strip.innerHTML = Array.from({length: count}, (_, i) => `<span class="rn-tick ${kind(i + 1)}${miss.has(i + 1) ? ' miss' : ''}" data-p="${i + 1}"></span>`).join('');
      strip.setAttribute('aria-valuemax', String(count));
      rail.querySelector('.rn-last').textContent = String(count);
    }
    mark();
  }
  function mark(){
    if(!S.doc) return;
    const page = S.page || 1;
    strip.querySelector('.rn-tick.cur')?.classList.remove('cur');
    strip.querySelector(`.rn-tick[data-p="${page}"]`)?.classList.add('cur');
    strip.setAttribute('aria-valuenow', String(page));
    label.textContent = `p. ${page} de ${S.doc.page_count || 1}`;
  }
  const pageAt = e => {
    const r = strip.getBoundingClientRect();
    const count = S.doc?.page_count || 1;
    return Math.max(1, Math.min(count, Math.floor(((e.clientY - r.top) / r.height) * count) + 1));
  };
  function tip(page, e){
    strip.querySelector('.rn-tip')?.remove();
    if(page == null || !S.doc) return;
    const r = strip.getBoundingClientRect();
    const t = document.createElement('span');
    t.className = 'rn-tip';
    const sec = (S.doc.sections || []).find(s => page >= s.start_page && page <= s.end_page);
    t.textContent = `p. ${page}${sec ? ` · ${sec.label}` : ''}`;
    t.style.top = `${Math.max(8, Math.min(r.height - 8, e.clientY - r.top))}px`;
    strip.appendChild(t);
  }
  async function go(page){
    if(!S.doc) return;
    page = Math.max(1, Math.min(S.doc.page_count || 1, page));
    if(S.wholePdf){ scrollWhole(page); }
    else if(inSection(page)){ await originalGoTo(page, await docMap()); }
    else{ await showWhole(page); }
    S.page = page;
    mark();
  }
  strip.addEventListener('pointerdown', e => { dragging = true; strip.setPointerCapture(e.pointerId); tip(pageAt(e), e); });
  strip.addEventListener('pointermove', e => tip(pageAt(e), e));
  strip.addEventListener('pointerup', e => { if(!dragging) return; dragging = false; tip(null); go(pageAt(e)); });
  strip.addEventListener('pointerleave', () => { if(!dragging) tip(null); });
  strip.addEventListener('keydown', e => {
    const d = {ArrowUp: -1, ArrowDown: 1, PageUp: -10, PageDown: 10}[e.key];
    if(d){ e.preventDefault(); go((S.page || 1) + d); }
    else if(e.key === 'Home'){ e.preventDefault(); go(1); }
    else if(e.key === 'End'){ e.preventDefault(); go(S.doc?.page_count || 1); }
  });

  // ---- Whole PDF: every page, loaded as it comes into view ------------------------------
  let observer = null;
  function loadPage(el){
    if(!el || el.querySelector('img') || !S.doc) return;
    const img = new Image();
    img.alt = `Página ${el.dataset.page}`;
    img.onload = () => { el.style.aspectRatio = ''; };
    img.src = `/api/documents/${S.doc.id}/page/${el.dataset.page}.png?zoom=${S.zoom || 1.5}`;
    el.appendChild(img);
  }
  // The observer only fires once the view moves: the page jumped to and its neighbours load right away.
  function scrollWhole(page){
    for(let p = page - 1; p <= page + 2; p++) loadPage(wrap.querySelector(`.rn-page[data-page="${p}"]`));
    wrap.querySelector(`.rn-page[data-page="${page}"]`)?.scrollIntoView({block: 'start'});
  }
  async function showWhole(page){
    if(!S.doc) return;
    const doc = S.doc, count = doc.page_count || 1;
    S.renderSeq = (S.renderSeq || 0) + 1;   // a section render still in flight must not overwrite this view
    S.wholePdf = true;
    S.openState = null;
    const first = S.sectionPreview?.pages?.[0];
    const ratio = first ? `${first.width}/${first.height}` : '210/297';
    const m = await docMap();
    const cand = (m.candidates || []).find(c => page >= c.start_page && page <= c.end_page);
    wrap.innerHTML = `<div class="rn-whole" role="status"><b>PDF completo</b><span>Las páginas con borde azul son la bibliografía; un clic en ellas vuelve a la revisión.</span>
      <span style="flex:1"></span>${cand ? `<button type="button" class="btn xs" data-rn-cand="${cand.start_page}">Agregar pp. ${cand.start_page}–${cand.end_page} como zona</button>` : ''}
      <button type="button" class="btn primary xs" data-rn-back>Volver a la bibliografía</button></div>` +
      Array.from({length: count}, (_, i) => {
        const p = i + 1, sec = inSection(p);
        return `<div class="rn-page${sec ? ' sec' : ''}" data-page="${p}" style="aspect-ratio:${ratio}"><div class="pagebadge${sec ? ' sec' : ''}">p. ${p}${sec ? ' · bibliografía' : ''}</div></div>`;
      }).join('');
    observer?.disconnect();
    observer = new IntersectionObserver(entries => entries.forEach(en => { if(en.isIntersecting) loadPage(en.target); }), {root: wrap, rootMargin: '900px 0px'});
    wrap.querySelectorAll('.rn-page').forEach(el => observer.observe(el));
    for(let p = page - 1; p <= page + 2; p++) loadPage(wrap.querySelector(`.rn-page[data-page="${p}"]`));
    // A frame may never come while the window is hidden: a timer does the jump too.
    let jumped = false;
    const jump = () => { if(jumped || !S.wholePdf) return; jumped = true; wrap.style.scrollBehavior = 'auto'; scrollWhole(page); wrap.style.scrollBehavior = ''; };
    requestAnimationFrame(jump);
    setTimeout(jump, 60);
    S.page = page;
    mark();
    window.showViewerToast?.(`p. ${page} está fuera de la bibliografía: se muestra el PDF completo`, 2400);
  }
  async function leaveWhole(page){
    S.wholePdf = false;
    observer?.disconnect();
    const start = +((S.doc?.sections || [])[S.activeSection || 0]?.start_page) || 1;
    S.page = page || start;
    await window.renderSectionViewer({scrollPage: S.page});
    mark();
  }
  wrap.addEventListener('click', async e => {
    if(!S.wholePdf) return;
    if(e.target.closest('[data-rn-back]')) return leaveWhole(null);
    const c = e.target.closest('[data-rn-cand]');
    if(c){
      const m = await docMap();
      const cand = (m.candidates || []).find(x => x.start_page === +c.dataset.rnCand);
      S.wholePdf = false;
      if(cand) return window.addCandidateSection?.(cand);
      return;
    }
    const pg = e.target.closest('.rn-page.sec');
    if(pg) return leaveWhole(+pg.dataset.page);
  });

  // ---- Hooks into the viewer --------------------------------------------------------------
  const originalGoTo = window.goToDocPage;
  // Any page of the document can be looked at: outside the bibliography it opens the whole PDF.
  window.goToDocPage = async function goToAnyPage(page, m){
    if(S.wholePdf && inSection(page)) return leaveWhole(page);
    if(S.wholePdf) return scrollWhole(page);
    if(inSection(page)) return originalGoTo(page, m || await docMap());
    return showWhole(page);
  };
  const originalRenderSection = window.renderSectionViewer;
  window.renderSectionViewer = function renderSectionLeavingWhole(){
    S.wholePdf = false;
    observer?.disconnect();
    return originalRenderSection.apply(this, arguments);
  };
  const originalScrollToPage = window.scrollToPage;
  window.scrollToPage = function scrollToPageAndMark(page){ originalScrollToPage(page); mark(); };
  const originalRenderDoc = window.renderDoc;
  window.renderDoc = function renderDocWithRail(){ const r = originalRenderDoc.apply(this, arguments); draw(); renderTheses(); fit(); return r; };
  const originalRenderDocMap = window.renderDocMap;
  window.renderDocMap = async function renderDocMapAndRail(){ const r = await originalRenderDocMap.apply(this, arguments); draw(); return r; };
  const originalRenderDocs = window.renderDocs;
  window.renderDocs = function renderDocsAndTheses(){ const r = originalRenderDocs.apply(this, arguments); renderTheses(); return r; };
  const originalMargin = window.renderMargin;
  if(typeof originalMargin === 'function'){
    window.renderMargin = async function renderMarginAndRail(){ const r = await originalMargin.apply(this, arguments); draw(); return r; };
  }

  // Follow the page the reader is looking at, in the bibliography or in the whole PDF.
  let scrollTimer;
  wrap.addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      const top = wrap.getBoundingClientRect().top + 60;
      const pages = [...wrap.querySelectorAll('[data-page]')];
      const current = pages.filter(el => el.getBoundingClientRect().top <= top).pop() || pages[0];
      if(current){ S.page = +current.dataset.page; mark(); }
    }, 80);
  }, {passive: true});

  // The PDF and the rail fill the window below the bars, whatever their height.
  function fit(){
    if(!screen.classList.contains('active')) return;
    const top = wrap.getBoundingClientRect().top + window.scrollY;
    const h = Math.max(320, Math.round(window.innerHeight - top - 14));
    wrap.style.maxHeight = rail.style.maxHeight = `${h}px`;
    rail.style.height = `${h}px`;
  }
  let fitTimer;
  window.addEventListener('resize', () => { clearTimeout(fitTimer); fitTimer = setTimeout(fit, 120); });
  new MutationObserver(() => setTimeout(fit, 0)).observe(screen, {attributes: true, attributeFilter: ['class']});

  applyMode();
  if(S.docs?.length) renderTheses();
  draw();
})();
