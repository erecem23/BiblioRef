/* Possible problems per thesis: chips in every screen and a one-by-one queue in «Referencias por tesis».
   Counts come from the index (biblioref/review_problems.py); the items are rebuilt here from the open thesis
   with the same rules, so a decision taken in the queue removes the item from both. */
(() => {
  const KINDS = ['missing', 'merged', 'boundaries', 'type', 'author', 'year'];
  const LABELS = {
    missing: ['posible faltante', 'posibles faltantes', 'Posibles faltantes'],
    merged: ['posible fusionada', 'posibles fusionadas', 'Posibles fusionadas'],
    boundaries: ['borde de página', 'bordes de página', 'Bordes de página'],
    type: ['sin clasificar', 'sin clasificar', 'Sin clasificar'],
    author: ['sin autor', 'sin autor', 'Sin autor'],
    year: ['sin año', 'sin año', 'Sin año'],
  };
  // Two colors only: amber when something is missing, grey outline when it only needs a look.
  const REVIEW_ONLY = new Set(['merged', 'boundaries']);
  const REF_KINDS = new Set(['type', 'author', 'year']);
  const UNCLASSIFIED = new Set(['', 'sin_clasificar']);
  const TYPES = [['libro', 'Libro'], ['articulo_revista', 'Artículo de revista'], ['capitulo_libro', 'Capítulo de libro'], ['tesis', 'Tesis'], ['material_web', 'Material web'], ['conference_paper', 'Ponencia'], ['informe_documento', 'Informe o documento'], ['material_inedito', 'Material inédito'], ['documento_legal', 'Documento legal o normativo'], ['documento_guia_manual', 'Guía o manual']];
  const fmt = n => Number(n || 0).toLocaleString('es-AR');
  const label = (kind, n) => `${fmt(n)} ${LABELS[kind][n === 1 ? 0 : 1]}`;
  const text = v => String(v == null ? '' : Array.isArray(v) ? v.join('; ') : v).replace(/\s+/g, ' ').trim();

  const style = document.createElement('style');
  style.id = 'review-problems-style';
  style.textContent = `
    .pb-chips{display:flex;flex-wrap:wrap;gap:5px;align-items:center}
    .pb-chip{display:inline-flex;align-items:center;gap:3px;padding:1px 8px;border-radius:999px;font:600 11px/1.5 inherit;font-family:inherit;white-space:nowrap;cursor:pointer;border:1px solid transparent;background:var(--warnbg);color:var(--warn)}
    .pb-chip.pb-review{background:#fff;border-color:#c9ced8;color:#374151}
    .pb-chip:hover{text-decoration:underline}
    .pb-chip:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
    .pb-more{font-size:11px;color:var(--muted)}
    .card .pb-chips{margin-top:7px}
    .pb-panel{border:1px solid var(--line);border-radius:var(--radius-sm);background:#fff;margin-bottom:10px;overflow:hidden}
    .pb-head{display:flex;align-items:center;gap:8px;padding:8px 10px;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
    .pb-cats{display:grid;grid-template-columns:1fr 1fr;gap:2px;padding:0 6px 6px}
    .pb-cat{display:flex;align-items:center;gap:7px;border:1px solid transparent;background:none;border-radius:6px;padding:5px 6px;font:inherit;font-size:12.5px;color:var(--ink);text-align:left;cursor:pointer;min-width:0}
    .pb-cat:hover:not(:disabled){background:var(--canvas)}
    .pb-cat:disabled{color:#9aa1ad;cursor:default}
    .pb-cat[aria-pressed="true"]{border-color:#a9c3f7;background:var(--accent-bg)}
    .pb-cat span.pb-n{margin-left:auto;font-variant-numeric:tabular-nums;color:var(--muted);font-size:12px}
    .pb-dot{width:8px;height:8px;border-radius:50%;flex:none;background:var(--warn)}
    .pb-dot.pb-review{background:#fff;border:1.5px solid #8b93a1}
    .pb-cat:disabled .pb-dot{opacity:.35}
    .pb-queue{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;padding:8px 10px;background:var(--accent-bg);border-top:1px solid #c9d8fb;font-size:12.5px}
    .pb-queue b{color:var(--accent-dark,#1f56c4)}
    .pb-queue .pb-sp{flex:1}
    .pb-progress{flex:1 1 60px;max-width:120px;height:5px;border-radius:999px;background:#d6def0;overflow:hidden}
    .pb-progress i{display:block;height:100%;background:var(--accent)}
    .pb-item{display:grid;gap:7px;padding:9px 10px;border-top:1px solid var(--line);font-size:12.5px}
    .pb-item .pb-where{font-size:11px;color:var(--muted)}
    .pb-item .pb-preview{color:#374151;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
    .pb-item .pb-acts{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
    .pb-item select,.pb-item input{font:inherit;font-size:12.5px;border:1px solid var(--line);border-radius:6px;padding:4px 6px;min-width:0;flex:1 1 150px;background:#fff;color:var(--ink)}
    .pb-done{padding:10px;border-top:1px solid var(--line);font-size:12.5px;color:#374151}
    .pb-keys{font-size:11px;color:var(--muted)}
    .slottype{margin:8px 0;border:1.5px solid #e9b877;background:var(--warnbg);border-radius:8px;padding:8px 10px;display:grid;gap:7px}
    .slottype-head{display:flex;align-items:center;flex-wrap:wrap;gap:6px 10px;font-size:12.5px;font-weight:700;color:var(--warn)}
    .slottype-head small{font-weight:400;font-size:11.5px;color:var(--muted)}
    .slottype-head .btn{margin-left:auto}
    .slottype-btns{display:flex;flex-wrap:wrap;gap:5px;align-items:center}
    .slottype-btns .btn{background:#fff}
    .slottype-btns .btn:hover{border-color:var(--accent);color:var(--accent-dark,#1f56c4)}
    .slottype-btns kbd{font:600 10px/1 inherit;font-family:inherit;color:var(--muted);border:1px solid #d4d8e0;border-radius:3px;padding:1px 3px;margin-left:2px}
    .slottype-btns select{font:inherit;font-size:12px;border:1px solid #d4d8e0;border-radius:6px;padding:3px 6px;background:#fff;color:var(--ink);max-width:190px}
  `;
  document.head.appendChild(style);

  // ---- Chips (Tesis del proyecto, Resumen) --------------------------------------
  function counts(d){ return d?.problems || {}; }
  // Page boundaries are only worth a look inside «Referencias por tesis»; everywhere else they were noise.
  const LIST_KINDS = KINDS.filter(k => k !== 'boundaries');
  function total(d){ return LIST_KINDS.reduce((n, k) => n + (counts(d)[k] || 0), 0); }
  function chips(d, {max = 6, arrow = false} = {}){
    const c = counts(d);
    const present = LIST_KINDS.filter(k => c[k]);
    if(!present.length) return '';
    const shown = present.slice(0, max);
    const rest = present.length - shown.length;
    return `<span class="pb-chips">${shown.map(k => `<button type="button" class="pb-chip ${REVIEW_ONLY.has(k) ? 'pb-review' : ''}" data-problem-doc="${esc(d.id)}" data-problem-kind="${k}" title="${REF_KINDS.has(k) ? 'Completarlas acá' : 'Abrir en el PDF y recorrerlos de a uno'}">${esc(label(k, c[k]))}${arrow ? ' ›' : ''}</button>`).join('')}${rest > 0 ? `<span class="pb-more">+${rest}</span>` : ''}</span>`;
  }
  document.addEventListener('click', e => {
    const chip = e.target.closest('[data-problem-kind][data-problem-doc]');
    if(!chip) return;
    e.preventDefault();
    e.stopPropagation();
    // Missing data is completed in place; extraction checks need the PDF.
    const kind = chip.dataset.problemKind;
    if(REF_KINDS.has(kind) && !chip.closest('#screen-review')) fix(chip.dataset.problemDoc, kind);
    else open(chip.dataset.problemDoc, kind);
  }, true);

  // ---- Items of the open thesis -------------------------------------------------
  const decision = id => S.doc?.audit_decisions?.[id]?.decision || null;
  const parsedOf = r => r.effective_parsed || r.parsed || {};
  function refForMerged(x){
    const head = text(x.text).slice(0, 60);
    const refs = (S.doc.references || []).filter(r => !r.deleted);
    return refs.find(r => text(r.text).startsWith(head)) || refs.find(r => r.start_page === x.page && text(r.text).includes(head.slice(0, 30)));
  }
  function items(kind){
    if(!S.doc) return [];
    const cov = S.doc.analysis?.coverage || {};
    let out = [];
    if(kind === 'missing'){
      out = (cov.possible_missing || []).filter(x => !['ignore', 'resolved', 'accepted_missing'].includes(decision(x.id)))
        .map(x => ({key: x.id, checkId: x.id, page: x.page, preview: x.first_line || x.text}));
    }else if(kind === 'merged'){
      out = (cov.merged_suspects || []).map(x => ({x, checkId: `merged_${x.page || 0}_${x.record_index || 0}`}))
        .filter(({checkId}) => !['ignore', 'resolved'].includes(decision(checkId)))
        .map(({x, checkId}) => { const r = refForMerged(x); return {key: checkId, checkId, page: x.page, preview: r?.text || x.text, refId: r?.id, order: r?.order}; });
    }else if(kind === 'boundaries'){
      out = (cov.page_boundaries || []).filter(x => ['review', 'pending'].includes(decision(x.id) || x.verdict))
        .map(x => ({key: x.id, checkId: x.id, page: x.page_before, pageAfter: x.page_after, preview: (x.previous_tail || []).slice(-1)[0] || ''}));
    }else if(REF_KINDS.has(kind)){
      out = (S.doc.references || []).filter(r => !r.deleted).filter(r => {
        const p = parsedOf(r);
        const open = kind === 'type' ? UNCLASSIFIED.has(text(p.publication_type)) : !text(p[kind]);
        return open && !['ignore', 'resolved'].includes(decision(`data_${kind}_${r.id}`));
      }).map(r => ({key: r.id, checkId: `data_${kind}_${r.id}`, page: r.start_page, preview: r.text, refId: r.id, order: r.order}));
    }
    return out.sort((a, b) => (a.page || 0) - (b.page || 0) || (a.order || 0) - (b.order || 0));
  }
  const docCounts = () => Object.fromEntries(KINDS.map(k => [k, items(k).length]));

  // ---- Queue -----------------------------------------------------------------------
  const queue = () => (S.problemQueue && S.doc && S.problemQueue.docId === S.doc.id) ? S.problemQueue : null;

  async function open(docId, kind){
    S.problemQueue = {docId, kind, index: 0};
    const search = document.getElementById('searchRefs');
    if(search) search.value = '';
    if(S.doc?.id === docId){
      show('review');
      await go(0);
    }else{
      await window.openDoc(docId); // the selectDoc hook below moves to the first item
    }
    if(!document.getElementById('reviewWorkspace')?.classList.contains('drawer-open')) document.getElementById('refTab')?.click();
  }

  async function go(index){
    const q = queue();
    if(!q) return;
    const list = items(q.kind);
    q.index = Math.max(0, Math.min(index, list.length - 1));
    const item = list[q.index];
    if(!item){ renderRefs(); return; }
    if(item.refId){
      S.selectedRef = null;
      await window.pickRef(item.refId);
      document.querySelector(`#refList .refitem[data-id="${item.refId}"]`)?.scrollIntoView({block: 'nearest'});
    }else if(q.kind === 'missing'){
      renderRefs();
      await window.focusMissing(item.checkId);
    }else{
      renderRefs();
      S.page = item.page;
      await ensureSectionForPage(item.page);
      await renderSectionViewer({scrollPage: item.page});
    }
    document.querySelector('.pb-panel')?.scrollIntoView({block: 'nearest'});
  }

  function syncIndexSummary(){
    const i = S.docs?.findIndex(d => d.id === S.doc?.id);
    if(i >= 0) S.docs[i] = {...S.docs[i], problems: docCounts()};
  }

  async function reloadAndStay(){
    // selectDoc re-renders; the hook below keeps the same position, which now holds the next item.
    await window.selectDoc(S.doc.id);
    syncIndexSummary();
  }

  async function dismiss(checkId){
    try{
      await api(`/api/documents/${S.doc.id}/audit-checks/${encodeURIComponent(checkId)}/decision`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({decision: 'ignore'})});
      await reloadAndStay();
    }catch(err){ notify('No se pudo guardar la decisión: ' + err.message); }
  }

  async function saveField(refId, field, value){
    value = text(value);
    if(!value) return notify('Completá el dato o usá «Está bien» si la referencia no lo tiene.');
    try{
      const updated = await api(`/api/documents/${S.doc.id}/references/${refId}/parsed-review`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({overrides: {[field]: value}})});
      const i = S.doc.references.findIndex(r => r.id === refId);
      if(i >= 0 && updated && updated.id === refId) S.doc.references[i] = updated;
      else return reloadAndStay();
      syncIndexSummary();
      await go(queue()?.index || 0);
    }catch(err){ notify('No se pudo guardar el dato: ' + err.message); }
  }

  function currentItemHtml(q, item){
    const where = item.pageAfter ? `Páginas ${item.page} → ${item.pageAfter}` : `${item.order ? `REF ${String(item.order).padStart(3, '0')} · ` : ''}pág. ${item.page || '?'}`;
    const preview = item.preview ? `<div class="pb-preview">${esc(item.preview)}</div>` : '';
    let acts = '';
    if(q.kind === 'type'){
      acts = `<select id="pbType" aria-label="Tipo documental"><option value="">Elegí el tipo…</option>${TYPES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select><button type="button" class="btn xs primary" data-pb-save="publication_type">Guardar</button><button type="button" class="btn xs" data-pb-ok>Está bien</button>`;
    }else if(q.kind === 'author' || q.kind === 'year'){
      acts = `<input id="pbField" ${q.kind === 'year' ? 'inputmode="numeric" maxlength="12" placeholder="Año"' : 'placeholder="Autor principal"'} aria-label="${q.kind === 'year' ? 'Año' : 'Autor'}"><button type="button" class="btn xs primary" data-pb-save="${q.kind}">Guardar</button><button type="button" class="btn xs" data-pb-ok title="La referencia realmente no tiene este dato">Está bien</button>`;
    }else if(q.kind === 'merged'){
      acts = `${item.refId ? '<button type="button" class="btn xs primary" data-pb-split>Dividir…</button>' : ''}<button type="button" class="btn xs" data-pb-ok>Es una sola referencia</button>`;
    }else if(q.kind === 'missing'){
      acts = `<button type="button" class="btn xs primary" data-pb-add>Extraer como referencia</button><button type="button" class="btn xs" data-pb-ignore>No es una referencia</button>`;
    }else if(q.kind === 'boundaries'){
      acts = `<button type="button" class="btn xs primary" data-pb-boundary>Revisar el borde…</button>`;
    }
    return `<div class="pb-item"><div class="pb-where">${esc(where)}</div>${preview}<div class="pb-acts">${acts}</div></div>`;
  }

  function panel(){
    if(!S.doc || !(S.doc.references || S.doc.analysis)) return '';
    const c = docCounts();
    const q = queue();
    const cats = KINDS.map(k => `<button type="button" class="pb-cat" data-pb-kind="${k}" aria-pressed="${q?.kind === k}" ${c[k] ? '' : 'disabled'}><span class="pb-dot ${REVIEW_ONLY.has(k) ? 'pb-review' : ''}"></span>${LABELS[k][2]}<span class="pb-n">${fmt(c[k])}</span></button>`).join('');
    let body = '';
    if(q){
      const list = items(q.kind);
      if(!list.length){
        body = `<div class="pb-queue"><b>${LABELS[q.kind][2]}</b><span class="pb-sp"></span><button type="button" class="btn xs" data-pb-exit>Salir</button></div><div class="pb-done">No quedan ${esc(LABELS[q.kind][1])} para revisar en esta tesis.</div>`;
      }else{
        const i = Math.min(q.index, list.length - 1);
        body = `<div class="pb-queue"><b>${LABELS[q.kind][2]} · ${fmt(i + 1)} de ${fmt(list.length)}</b><span class="pb-progress" aria-hidden="true"><i style="width:${Math.round(100 * (i + 1) / list.length)}%"></i></span><span class="pb-sp"></span><button type="button" class="btn xs" data-pb-step="-1" ${i ? '' : 'disabled'} aria-label="Anterior">‹</button><button type="button" class="btn xs" data-pb-step="1" ${i < list.length - 1 ? '' : 'disabled'} aria-label="Siguiente">›</button><button type="button" class="btn xs" data-pb-exit>Salir</button></div>${currentItemHtml(q, list[i])}<div class="pb-keys" style="padding:0 10px 8px">← → para moverte · ${REF_KINDS.has(q.kind) || q.kind === 'merged' ? 'la lista muestra solo estas referencias' : 'la lista muestra todas las referencias'}</div>`;
      }
    }
    return `<section class="pb-panel" aria-label="Para revisar"><div class="pb-head">Para revisar en ${esc(S.doc.thesis_id || 'esta tesis')}</div><div class="pb-cats">${cats}</div>${body}</section>`;
  }

  document.addEventListener('click', async e => {
    const host = e.target.closest('.pb-panel');
    if(!host) return;
    const q = queue();
    const kindBtn = e.target.closest('[data-pb-kind]');
    if(kindBtn){
      if(q?.kind === kindBtn.dataset.pbKind){ S.problemQueue = null; renderRefs(); return; }
      S.problemQueue = {docId: S.doc.id, kind: kindBtn.dataset.pbKind, index: 0};
      return go(0);
    }
    if(!q) return;
    const item = items(q.kind)[Math.min(q.index, items(q.kind).length - 1)];
    if(e.target.closest('[data-pb-exit]')){ S.problemQueue = null; renderRefs(); return; }
    const step = e.target.closest('[data-pb-step]');
    if(step) return go(q.index + Number(step.dataset.pbStep));
    if(!item) return;
    if(e.target.closest('[data-pb-ok]')) return dismiss(item.checkId);
    const save = e.target.closest('[data-pb-save]');
    if(save){
      const value = save.dataset.pbSave === 'publication_type' ? document.getElementById('pbType')?.value : document.getElementById('pbField')?.value;
      return saveField(item.refId, save.dataset.pbSave, value);
    }
    if(e.target.closest('[data-pb-split]')) return window.splitRef(item.refId);
    if(e.target.closest('[data-pb-add]')) return window.addMissing(item.checkId);
    if(e.target.closest('[data-pb-ignore]')) return window.ignoreAudit(item.checkId);
    if(e.target.closest('[data-pb-boundary]')) return window.reviewBoundary(item.checkId);
  });
  document.addEventListener('keydown', e => {
    const q = queue();
    if(!document.getElementById('screen-review')?.classList.contains('active')) return;
    const typing = e.target instanceof Element && e.target.closest('input,textarea,select,[contenteditable]');
    if(!typing && /^[1-6]$/.test(e.key) && !e.ctrlKey && !e.altKey && !e.metaKey && !document.querySelector('#modalHost .modal, #modalHost [role="dialog"]')){
      const btn = document.querySelectorAll('.slottype [data-slot-type]')[Number(e.key) - 1];
      if(btn && !btn.disabled){ e.preventDefault(); btn.click(); return; }
    }
    if(!q) return;
    if(typing || document.querySelector('#modalHost .modal, #modalHost [role="dialog"]')) {
      if(e.key === 'Enter' && e.target.id === 'pbField'){ e.preventDefault(); document.querySelector('[data-pb-save]')?.click(); }
      return;
    }
    if(e.key === 'ArrowRight'){ e.preventDefault(); go(q.index + 1); }
    else if(e.key === 'ArrowLeft'){ e.preventDefault(); go(q.index - 1); }
  });

  // After a thesis is (re)loaded, stay on the same position of the queue.
  const originalSelectDoc = window.selectDoc;
  window.selectDoc = async function selectDocKeepingQueue(id){
    const result = await originalSelectDoc(id);
    if(S.problemQueue && S.problemQueue.docId === id && S.doc?.id === id) await go(S.problemQueue.index);
    else if(S.problemQueue && S.problemQueue.docId !== id) S.problemQueue = null;
    return result;
  };

  // Dividir desde la cola también cierra el aviso: si no, la fusionada sigue contando como pendiente
  // y no hay forma de saber si la división se tomó.
  const originalSaveSplit = window.saveSplit;
  window.saveSplit = async function saveSplitClosingMergedItem(refId){
    const q = queue();
    const list = q && q.kind === 'merged' ? items('merged') : [];
    const item = list[Math.min(q?.index ?? 0, list.length - 1)] || null;
    const before = (S.doc?.references || []).filter(r => !r.deleted).length;
    const result = await originalSaveSplit(refId);
    // Con el modal todavía abierto (texto sin «---», error del servidor) no se dividió nada.
    if(!item || item.refId !== refId || !S.doc) return result;
    if((S.doc.references || []).filter(r => !r.deleted).length <= before) return result;
    try{
      await api(`/api/documents/${S.doc.id}/audit-checks/${encodeURIComponent(item.checkId)}/decision`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({decision: 'resolved', note: 'split_from_queue'})});
      S.doc.audit_decisions = {...(S.doc.audit_decisions || {}), [item.checkId]: {decision: 'resolved', note: 'split_from_queue'}};
    }catch(err){ notify('La referencia se dividió, pero no se pudo marcar el aviso como resuelto: ' + err.message); }
    syncIndexSummary();
    await go(queue()?.index || 0);
    return result;
  };

  // Used by renderRefs in app.js.
  let matchCache = null;
  window.BiblioRefRefFilter = {
    matches(r){
      const q = queue();
      if(!q || !(REF_KINDS.has(q.kind) || q.kind === 'merged')) return true;
      // renderRefs calls this once per reference in one synchronous pass: build the set once.
      if(!matchCache){
        matchCache = new Set(items(q.kind).map(x => x.refId));
        queueMicrotask(() => { matchCache = null; });
      }
      return matchCache.has(r.id);
    },
    notice(){ return panel(); },
    clear(){ S.problemQueue = null; renderRefs(); },
  };

  // Tipo faltante en la tarjeta sobre el PDF (app.js): botones que guardan al tocarlos; 1–6 desde el teclado.
  const QUICK_TYPES = TYPES.slice(0, 6);
  function typeBox(r){
    if(!S.doc || !r) return '';
    const open = UNCLASSIFIED.has(text(parsedOf(r).publication_type)) && !['ignore', 'resolved'].includes(decision(`data_type_${r.id}`));
    if(!open) return '';
    const q = queue();
    let where = 'se guarda al tocarlo';
    if(q?.kind === 'type'){
      const list = items('type');
      const i = list.findIndex(x => x.refId === r.id);
      if(i >= 0) where = `${fmt(i + 1)} de ${fmt(list.length)} sin clasificar · se guarda y pasa a la siguiente`;
    }
    const id = esc(r.id);
    return `<div class="slottype" role="group" aria-label="Tipo de la referencia">
      <div class="slottype-head">Falta el tipo <small>${where}</small><button type="button" class="btn xs" data-slot-type-leave="${id}" title="La referencia no encaja en ningún tipo: sale de la lista sin clasificar">Dejar así</button></div>
      <div class="slottype-btns">${QUICK_TYPES.map(([v, l], i) => `<button type="button" class="btn xs" data-slot-type="${v}" data-slot-ref="${id}">${esc(l)}<kbd>${i + 1}</kbd></button>`).join('')}
        <select data-slot-type-other="${id}" aria-label="Otro tipo"><option value="">Otro…</option>${TYPES.slice(6).map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}</select></div>
    </div>`;
  }
  async function classify(refId, value){
    if(queue()?.kind === 'type') return saveField(refId, 'publication_type', value);
    try{
      const updated = await api(`/api/documents/${S.doc.id}/references/${refId}/parsed-review`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({overrides: {publication_type: value}})});
      const i = S.doc.references.findIndex(r => r.id === refId);
      if(i >= 0 && updated && updated.id === refId) S.doc.references[i] = updated;
      syncIndexSummary();
      S.selectedRef = null;
      await window.pickRef(refId);
    }catch(err){ notify('No se pudo guardar el tipo: ' + err.message); }
  }
  document.addEventListener('click', e => {
    const pick = e.target.closest('[data-slot-type]');
    if(pick){ pick.disabled = true; return classify(pick.dataset.slotRef, pick.dataset.slotType); }
    const leave = e.target.closest('[data-slot-type-leave]');
    if(leave) return dismiss(`data_type_${leave.dataset.slotTypeLeave}`);
  });
  document.addEventListener('change', e => {
    const other = e.target.closest('[data-slot-type-other]');
    if(other && other.value) classify(other.dataset.slotTypeOther, other.value);
  });

  // Para la tarjeta sobre el PDF (app.js): ¿esta referencia es una posible fusionada todavía abierta?
  const mergedFor = refId => S.doc ? (items('merged').find(x => x.refId === refId) || null) : null;

  // ---- Fix dialog: missing type, author or year, completed where the chip was clicked ----
  const FIELD = {type: 'publication_type', author: 'author', year: 'year'};
  const PLACEHOLDER = {author: 'Apellido, N.', year: 'Año, p. ej. 2019 o s.f.'};

  async function fix(docId, kind, only = null){
    if(!REF_KINDS.has(kind)) return open(docId, kind);
    let doc;
    try{ doc = await api('/api/documents/' + encodeURIComponent(docId)); }
    catch(err){ return notify('No se pudo abrir la tesis: ' + err.message); }
    const decisions = doc.audit_decisions || {};
    const refs = (doc.references || []).filter(r => !r.deleted).filter(r => {
      if(only) return only.includes(r.id);
      const p = parsedOf(r);
      const missing = kind === 'type' ? UNCLASSIFIED.has(text(p.publication_type)) : !text(p[kind]);
      return missing && !['ignore', 'resolved'].includes(decisions[`data_${kind}_${r.id}`]?.decision);
    }).sort((a, b) => (a.start_page || 0) - (b.start_page || 0) || (a.order || 0) - (b.order || 0));
    if(!refs.length) return notify('No quedan referencias para completar en esta tesis.');
    const control = r => kind === 'type'
      ? `<select data-fix-value aria-label="Tipo de la referencia ${esc(r.order)}"><option value="">Elegir tipo…</option>${TYPES.map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}</select>`
      : `<input data-fix-value type="text" placeholder="${PLACEHOLDER[kind]}" aria-label="${kind === 'author' ? 'Autor' : 'Año'} de la referencia ${esc(r.order)}">`;
    const rows = refs.map(r => `<div class="pb-fix-row" data-fix-ref="${esc(r.id)}">
        <div class="pb-fix-text"><b>${esc(r.order)}.</b> ${esc(r.text)}
          <div class="pb-fix-links"><button type="button" class="text-btn" data-fix-pdf="${esc(r.id)}">Ver en el PDF${r.start_page ? ` · p. ${esc(r.start_page)}` : ''}</button></div></div>
        <div class="pb-fix-ctl">${control(r)}<label><input type="checkbox" data-fix-leave> Dejar así</label></div>
      </div>`).join('');
    const title = displayTitle(doc);
    modal(`${label(kind, refs.length)}`,
      `<p class="mini" style="margin-top:0">${esc(doc.thesis_id || '')} · ${esc(title)}. Lo que completes se guarda como corrección manual; el texto original no cambia. «Dejar así» lo saca de la lista sin completarlo.</p>
       <div class="pb-fix-list">${rows}</div>`,
      `<span class="mini" id="pbFixCount" style="margin-right:auto"></span><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="pbFixSave">Guardar</button>`);
    document.querySelector('#modalHost .modal')?.classList.add('org-wide');
    const host = document.querySelector('#modalHost');
    const pending = () => [...host.querySelectorAll('.pb-fix-row')].map(row => ({
      id: row.dataset.fixRef,
      value: text(row.querySelector('[data-fix-value]').value),
      leave: row.querySelector('[data-fix-leave]').checked,
    })).filter(x => x.value || x.leave);
    const update = () => {
      const n = pending().length;
      $('#pbFixCount').textContent = `${fmt(n)} de ${fmt(refs.length)} con algo elegido`;
      $('#pbFixSave').disabled = !n;
      $('#pbFixSave').textContent = n ? `Guardar ${fmt(n)}` : 'Guardar';
    };
    host.querySelectorAll('.pb-fix-row').forEach(row => {
      const input = row.querySelector('[data-fix-value]');
      const leave = row.querySelector('[data-fix-leave]');
      input.addEventListener('input', update);
      input.addEventListener('change', update);
      leave.addEventListener('change', () => { input.disabled = leave.checked; update(); });
    });
    host.querySelectorAll('[data-fix-pdf]').forEach(b => b.addEventListener('click', async () => {
      closeModal();
      await open(docId, kind);
      const at = items(kind).findIndex(x => x.refId === b.dataset.fixPdf);
      if(at >= 0) await go(at);
    }));
    update();
    host.querySelector('[data-fix-value]')?.focus();
    $('#pbFixSave').onclick = async () => {
      const work = pending();
      $('#pbFixSave').disabled = true;
      let failed = 0;
      for(const x of work){
        try{
          if(x.leave){
            await api(`/api/documents/${encodeURIComponent(docId)}/audit-checks/${encodeURIComponent(`data_${kind}_${x.id}`)}/decision`,
              {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({decision: 'ignore', note: 'Dejar así (desde el aviso)'})});
          }else{
            await api(`/api/documents/${encodeURIComponent(docId)}/references/${encodeURIComponent(x.id)}/parsed-review`,
              {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({overrides: {[FIELD[kind]]: x.value}})});
          }
        }catch(err){ failed++; console.error(err); }
      }
      closeModal();
      if(S.doc?.id === docId){
        try{ S.doc = await api('/api/documents/' + encodeURIComponent(docId)); renderRefs(); }catch(err){ /* the review screen reloads on open */ }
      }
      window.dispatchEvent(new CustomEvent('biblioref:refs-changed', {detail: {docId}}));
      if(failed) notify(`${fmt(work.length - failed)} guardadas; ${fmt(failed)} no se pudieron guardar.`);
    };
  }

  const fixStyle = document.createElement('style');
  fixStyle.textContent = `
    .pb-fix-list{max-height:min(60vh,560px);overflow:auto;border-top:1px solid var(--line)}
    .pb-fix-row{display:flex;gap:14px;align-items:flex-start;padding:12px 2px;border-bottom:1px solid #edeef2}
    .pb-fix-text{flex:1;min-width:0;font-size:13.5px;line-height:1.5}
    .pb-fix-links{margin-top:3px}
    .pb-fix-links .text-btn{font-size:12.5px;color:var(--accent);min-height:0;padding:0}
    .pb-fix-ctl{display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex:0 0 230px}
    .pb-fix-ctl select,.pb-fix-ctl input[type=text]{width:100%;font:inherit;font-size:13px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink)}
    .pb-fix-ctl label{font-size:12.5px;color:var(--muted);display:flex;gap:6px;align-items:center;cursor:pointer}
  `;
  document.head.appendChild(fixStyle);

  window.BiblioRefProblems = {KINDS, LABELS, chips, total, open, counts, mergedFor, dismiss, fix, typeBox};
})();
