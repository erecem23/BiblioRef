/* Organizing «Tesis del proyecto»: editable folders, checkboxes, selection by reason and saved selections.
   Moving a thesis only changes where it is shown; PDFs and references are untouched. */
(() => {
  const originalMatches = window.matchesCollectionSearch;
  const COVER_FIELDS = ['author', 'year', 'degree_level', 'program', 'faculty', 'university', 'director'];
  const org = {selected: new Set(), view: null, lastClicked: null, folderOf: new Map(), renaming: null, toastTimer: null};
  S.org = org;

  const style = document.createElement('style');
  style.id = 'project-organize-style';
  style.textContent = `
    .collection-documents .card.org-card{grid-template-columns:auto minmax(0,1fr) auto}
    .org-check{display:flex;align-items:flex-start;padding-top:3px;cursor:pointer}
    .org-check input{width:17px;height:17px;margin:0;accent-color:var(--accent);cursor:pointer}
    .collection-documents .card.org-on{border-color:#a9c3f7;background:#f6f9ff}
    .card.org-dragging{opacity:.55}
    .org-pill{display:inline-block;margin:6px 0 0 6px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);background:#eef0f3;color:#374151;font-size:11px;font-weight:600}
    .org-bar{position:sticky;top:0;z-index:4;display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px;padding:9px 12px;border:1px solid #c9d8fb;border-radius:9px;background:var(--accent-bg)}
    .org-bar[hidden]{display:none}
    .org-bar b{font-size:13px;color:var(--accent-dark,#1f56c4)}
    .org-bar .org-sp{flex:1}
    .org-bar input{width:17px;height:17px;accent-color:var(--accent);margin:0}
    .org-tools{grid-column:1/-1;display:flex;flex-wrap:wrap;align-items:center;gap:8px}
    .org-viewchip{display:inline-flex;align-items:center;gap:6px;padding:3px 4px 3px 10px;border-radius:999px;background:var(--sidebar,#101a30);color:#fff;font-size:12px;font-weight:600}
    .org-viewchip button{border:0;background:rgba(255,255,255,.15);color:#fff;border-radius:999px;width:20px;height:20px;cursor:pointer;font:inherit;line-height:1}
    .org-menu{position:fixed;z-index:70;min-width:250px;max-height:min(70vh,560px);overflow:auto;background:#fff;border:1px solid var(--line);border-radius:9px;box-shadow:var(--shadow-md);padding:6px;font-size:13px}
    .org-menu h4{margin:6px 8px 3px;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
    .org-menu button{display:flex;width:100%;justify-content:space-between;gap:12px;border:0;background:none;padding:7px 9px;border-radius:6px;font:inherit;color:var(--ink);text-align:left;cursor:pointer}
    .org-menu button:hover,.org-menu button:focus-visible{background:var(--canvas);outline:none}
    .org-menu button span:last-child{color:var(--muted);font-variant-numeric:tabular-nums}
    .org-menu button.org-danger{color:var(--danger)}
    .org-menu hr{border:0;border-top:1px solid var(--line);margin:4px 0}
    .tree-folder>summary.org-drop,.tree-root.org-drop{outline:2px dashed var(--accent);outline-offset:-2px;background:#f3f7ff}
    .tree-folder>summary .org-more{margin-left:4px;border:0;background:none;color:var(--muted);border-radius:4px;padding:0 5px;font:inherit;font-size:15px;line-height:1.2;cursor:pointer;opacity:0}
    .tree-folder>summary:hover .org-more,.tree-folder>summary .org-more:focus-visible{opacity:1}
    .tree-folder>summary input.org-rename{flex:1;min-width:0;font:inherit;font-weight:600;border:1px solid var(--accent);border-radius:5px;padding:1px 6px}
    .org-newfolder{border:0;background:none;color:var(--accent);font:inherit;font-size:13px;font-weight:600;cursor:pointer;padding:4px 2px}
    .org-sel{display:flex;align-items:center;gap:8px;width:100%;border:0;background:none;border-radius:6px;padding:7px 6px;font:inherit;font-size:13.5px;color:var(--ink);text-align:left;cursor:pointer}
    .org-sel:hover{background:var(--canvas)}
    .org-sel[aria-pressed="true"]{background:var(--accent-bg);color:var(--accent-dark,#1f56c4);font-weight:600}
    .org-sel span.org-n{flex:1;min-width:0}
    .org-sel small{color:var(--muted);font-variant-numeric:tabular-nums;font-size:12px}
    .org-sel .org-x{border:0;background:none;color:var(--muted);cursor:pointer;font:inherit;padding:0 4px}
    .org-sel svg{width:15px;height:15px;flex:none;color:var(--muted)}
    .org-save{border:0;background:none;color:var(--muted);font:inherit;font-size:13px;cursor:pointer;padding:6px 6px 2px 29px}
    .org-save:hover{color:var(--accent)}
    .org-folderpick{display:grid;gap:2px;max-height:48vh;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:6px}
    .org-folderpick label{display:flex;align-items:center;gap:8px;padding:5px 6px;border-radius:6px;cursor:pointer;font-size:13.5px}
    .org-folderpick label:hover{background:var(--canvas)}
    .org-folderpick small{color:var(--muted);margin-left:auto}
    .org-toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:80;display:flex;align-items:center;gap:12px;padding:10px 14px;border-radius:9px;background:var(--sidebar,#101a30);color:#fff;font-size:13.5px;box-shadow:var(--shadow-md)}
    #modalHost .modal.org-wide{width:min(980px,calc(100vw - 32px));max-width:none}
    .org-dedupe-table{max-height:55vh;overflow:auto;border:1px solid var(--line);border-radius:8px;margin-top:10px}
    .org-dedupe-table table{border-collapse:collapse;width:100%;font-size:12.5px;min-width:680px}
    .org-dedupe-table th{position:sticky;top:0;background:#f6f7f9;text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;color:#4b5563;padding:7px 9px;border-bottom:1px solid var(--line)}
    .org-dedupe-table td{padding:7px 9px;border-bottom:1px solid #edeef2;vertical-align:top}
    .org-dedupe-table input{width:16px;height:16px;accent-color:var(--accent)}
    .org-src{font-size:11px;color:var(--muted);overflow-wrap:anywhere}
    .org-rm{color:#6b7280}
    .org-toast button{border:1px solid rgba(255,255,255,.35);background:none;color:#fff;border-radius:6px;padding:4px 10px;font:inherit;font-weight:600;cursor:pointer}
    #uploadCards.org-table-host{display:flex;flex-direction:column;flex:1;min-height:0;height:auto!important;max-height:none!important;overflow:hidden;padding:0;margin-top:10px}
    #uploadCards.org-table-host+.cards-resizer{display:none}
    .org-scroll{flex:1;min-height:0;overflow:auto;border:1px solid var(--line);border-radius:8px;overscroll-behavior:contain}
    .org-table{width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed;font-size:13px;line-height:1.4}
    .org-table th{position:sticky;top:0;z-index:2;background:#f6f7f9;padding:8px 8px;border-bottom:1px solid var(--line);text-align:left;font-size:10.5px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#4b5563;white-space:nowrap}
    .org-table td{padding:8px;border-bottom:1px solid #edeef2;vertical-align:top;overflow:hidden}
    .org-table tr[data-card-id]:hover td{background:#fafbfc}
    .org-table tr.org-on td{background:#f6f9ff}
    .org-table tr.selected td{background:var(--accent-bg)}
    .org-table tr.selected td:first-child{box-shadow:inset 3px 0 var(--accent)}
    .org-table tr.org-dragging{opacity:.55}
    .org-table{min-width:880px}
    .org-c-check{width:32px}
    .org-c-check input{width:16px;height:16px;margin:2px 0 0;accent-color:var(--accent);cursor:pointer}
    .org-c-code{width:60px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
    .org-c-author{width:150px}
    .org-table .org-c-num{width:48px;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
    .org-c-problems{width:210px}
    .org-c-status{width:84px}
    .org-c-acts{width:132px;text-align:right;white-space:nowrap}
    .org-c-acts .btn{margin-left:4px}
    .org-c-acts .org-more{min-width:34px;padding:0 8px}
    .org-title{font-weight:600;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
    .org-file{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
    .org-miss{color:var(--warn);font-weight:600;font-size:12px}
    .org-table .pill{margin:0}
    .org-table .org-pill{margin-top:4px}
    .org-add{position:relative}
    .org-add>summary{list-style:none;cursor:pointer}
    .org-add>summary::-webkit-details-marker{display:none}
    .org-add .org-add-menu{position:absolute;right:0;top:calc(100% + 6px);z-index:40;min-width:260px;padding:6px;background:#fff;border:1px solid var(--line);border-radius:9px;box-shadow:var(--shadow-md);display:flex;flex-direction:column}
    .org-add .org-add-menu button{justify-content:flex-start;text-align:left;border:0;background:none;padding:9px 10px;border-radius:6px;font:inherit;font-size:14px;color:var(--ink);cursor:pointer;min-height:0}
    .org-add .org-add-menu button:hover{background:var(--canvas)}
    .org-add .org-add-menu button[hidden]{display:none}
    .org-add .org-add-menu p{margin:4px 10px 6px;font-size:12px;color:var(--muted)}
    #screen-collection .import-toolbar.org-compact{padding:0;border:0;background:none}
    #screen-collection .import-toolbar.org-compact .import-toolbar-row{display:none}
    #screen-collection .collection-grid{height:calc(100dvh - 215px)}
    #screen-collection .collection-heading{margin-bottom:8px}
    #screen-collection .collection-workspace-tools{margin:6px 0}
    #screen-collection .collection-documents .documents-heading p{display:none}
    #screen-collection .collection-documents .collection-search{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px}
    #screen-collection .collection-documents .collection-search>label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
    #screen-collection .collection-documents .collection-search>input{flex:1 1 260px;min-width:0}
    #screen-collection .collection-documents .collection-search .org-tools{grid-column:auto;flex:0 1 auto}
    @container orgmain (max-width:1000px){.org-c-status{display:none}}
    #screen-collection .collection-main{container:orgmain/inline-size}
    #projectExplorer .project-tree{flex:1 1 auto;min-height:120px;height:auto!important}
    #projectExplorer .explorer-help,#projectExplorer .organization-option{display:none}
    /* «Selecciones» es una sola línea al pie del explorador; la lista se abre flotando encima de las carpetas. */
    #projectExplorer .org-selections{flex:none;position:relative;border-top:1px solid var(--line);margin:0;padding:0}
    #projectExplorer.org-sel-menu #orgSelections{display:none}
    .org-selbar{display:flex;align-items:center;gap:8px;width:100%;border:0;background:#fafbfc;padding:8px 12px;font:inherit;cursor:pointer;text-align:left}
    .org-selbar:hover{background:var(--canvas)}
    .org-selbar svg{width:14px;height:14px;flex:none;color:var(--muted)}
    .org-selbar h3{margin:0;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
    .org-selbar .org-selnow{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;font-weight:600;color:var(--accent-dark,#1f56c4)}
    .org-selbar .org-selbadge{margin-left:auto;font-size:11.5px;font-weight:600;color:var(--warn);background:var(--warnbg);border-radius:999px;padding:1px 8px;white-space:nowrap}
    .org-selbar .org-caret{margin-left:auto;color:var(--muted);font-size:11px}
    .org-selbar .org-selbadge+.org-caret{margin-left:0}
    .org-selpop{position:absolute;left:8px;right:8px;bottom:calc(100% + 4px);z-index:30;max-height:min(60vh,460px);overflow:auto;background:#fff;border:1px solid var(--line);border-radius:9px;box-shadow:var(--shadow-md);padding:6px}
    .org-selpop[hidden]{display:none}
    .org-selpop .org-sel{font-size:13px;padding:6px 6px}
    .org-selpop .org-save{padding-left:29px}
    .org-status{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-top:10px;padding:8px 12px;border:1px solid var(--line);border-radius:9px;background:#fff;font-size:13px}
    .org-status[hidden]{display:none}
    .org-status .org-stg{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
    .org-status .org-stsep{width:1px;align-self:stretch;background:var(--line)}
    .org-status .org-dot{width:8px;height:8px;border-radius:50%;flex:none;background:var(--warn)}
    .org-status .org-dot.org-rv{background:#fff;border:1.5px solid #8b93a1}
    .org-status .org-dot.org-run{background:var(--accent)}
    .org-status .btn[aria-pressed="true"]{background:var(--accent-bg);border-color:#a9c3f7;color:var(--accent-dark,#1f56c4)}
    .org-pill.org-warn{background:var(--warnbg);border-color:transparent;color:var(--warn)}
    .org-menu button[aria-checked]::before{content:'';display:inline-block;width:14px;flex:none}
    .org-menu button[aria-checked="true"]::before{content:'✓';color:var(--accent)}
    .org-bar .org-links{display:flex;align-items:center;gap:6px;font-size:13.5px}
    .org-bar .org-links button{border:0;background:none;padding:2px;font:inherit;font-weight:600;color:var(--accent-dark,#1f56c4);cursor:pointer;text-decoration:underline;text-underline-offset:2px}
    #collectionWorkspace.org-dropping .collection-main{outline:2px dashed var(--accent);outline-offset:-4px;background:var(--accent-bg)}
    .org-ocr{margin-top:7px;max-width:360px;font-size:12.5px;color:#374151}
    .org-ocr.err{color:var(--muted)}
    .org-ocrbar{height:6px;margin-top:4px;border-radius:3px;background:var(--line);overflow:hidden}
    .org-ocrbar span{display:block;height:100%;background:var(--accent);transition:width .4s}
    .org-ocrbar.wait span{width:100%;opacity:.35}
    .org-ocr-table select{font:inherit;font-size:12.5px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;background:#fff;max-width:230px}
    .org-ocr-table td.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
    .org-ocr-foot{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:10px;font-size:13px;color:var(--muted)}
  `;
  document.head.appendChild(style);

  const BOLT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M13 3 5 14h6l-1 7 8-11h-6Z"/></svg>';
  const SAVED = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4Z"/></svg>';
  const projectId = () => S.project?.id;
  const jsonBody = body => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const fmt = n => Number(n || 0).toLocaleString('es-AR');
  const normTitle = d => String(displayTitle(d) || '').toLocaleLowerCase('es').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9ñ]+/g, ' ').trim();
  const codeNum = d => Number(thesisNumber(d)) || Number.MAX_SAFE_INTEGER;

  // ---- Reasons to select ----------------------------------------------------
  // Repeated theses come from the server: same PDF bytes, with the copy to keep already chosen.
  function duplicateInfo(){
    const copies = new Set(), all = new Set(), originalOf = new Map();
    const byId = new Map(S.docs.map(d => [d.id, d]));
    for(const g of org.duplicates?.groups || []){
      all.add(g.keep.id);
      for(const r of g.remove){
        all.add(r.id);
        copies.add(r.id);
        originalOf.set(r.id, byId.get(g.keep.id) || {thesis_id: g.keep.thesis_id});
      }
    }
    return {pairs: (org.duplicates?.groups || []).length, copies, all, originalOf, loading: !org.duplicates};
  }
  async function loadDuplicates(){
    const pid = projectId();
    if(!pid) return;
    try{
      const data = await api(`/api/projects/${encodeURIComponent(pid)}/duplicates`);
      if(projectId() !== pid) return;
      org.duplicates = data;
      rerender();
    }catch(err){ console.warn('duplicates', err); }
  }
  window.BiblioRefLoadDuplicates = loadDuplicates;

  const processed = d => d.status !== 'uploaded' && d.status !== 'processing';
  // Extracted with an older engine, or OCR finished on a thesis whose bibliography was kept.
  const needsReprocess = d => processed(d) && !d.ocr_need && (!!d.analysis_stale || !!d.ocr?.reprocess_suggested);
  const REASONS = [
    {id: 'duplicates', label: 'Repetidas (mismo archivo)', group: 'Datos', sidebar: true},
    {id: 'review', label: 'Por revisar', group: 'Estado', sidebar: true, test: d => statusText(d) === 'revisar'},
    {id: 'ready', label: 'Listas', group: 'Estado', test: d => statusText(d) === 'lista'},
    {id: 'unprocessed', label: 'Sin procesar', group: 'Estado', test: d => !processed(d)},
    {id: 'stale', label: 'Para reprocesar', group: 'Estado', test: d => needsReprocess(d)},
    {id: 'norefs', label: 'Sin referencias', group: 'Estado', sidebar: true, test: d => processed(d) && !d.n_references},
    {id: 'ocr', label: 'Escaneadas', group: 'Datos', sidebar: true, test: d => !!d.ocr_need},
    {id: 'missing', label: 'Faltan metadatos de portada', group: 'Datos', sidebar: true, test: d => COVER_FIELDS.some(k => !String((d.metadata || {})[k] || '').trim())},
    {id: 'inferred', label: 'Con datos inferidos', group: 'Datos', sidebar: true, test: d => Object.keys(d.metadata_inference || {}).length > 0},
  ];
  const reason = id => REASONS.find(r => r.id === id);

  // Which theses a reason shows, and which of them it marks (duplicates mark only the later copies).
  function reasonSets(id){
    if(id === 'duplicates'){
      const info = duplicateInfo();
      return {show: info.all, mark: info.copies, count: info.pairs, unit: info.pairs === 1 ? 'par' : 'pares'};
    }
    const r = reason(id);
    const ids = new Set(S.docs.filter(r.test).map(d => d.id));
    return {show: ids, mark: ids, count: ids.size, unit: ''};
  }

  function folderDocs(path){
    const key = JSON.stringify(path);
    return new Set(S.docs.filter(d => {
      const p = org.folderOf.get(d.id) || [];
      return JSON.stringify(p.slice(0, path.length)) === key;
    }).map(d => d.id));
  }

  function viewIds(){
    const v = org.view;
    if(!v) return null;
    if(v.kind === 'reason') return reasonSets(v.id).show;
    if(v.kind === 'folder') return folderDocs(v.path);
    if(v.kind === 'value') return new Set(S.docs.filter(v.test).map(d => d.id));
    return null;
  }

  window.matchesCollectionSearch = function matchesWithView(doc){
    if(!originalMatches(doc)) return false;
    const ids = viewIds();
    return !ids || ids.has(doc.id);
  };
  const visibleDocs = () => S.docs.filter(window.matchesCollectionSearch);

  function setView(view, markIds){
    org.view = view;
    if(markIds){ org.selected = new Set(markIds); }
    rerender();
  }

  function rerender(){
    renderCards();
    renderProjectTree();
  }

  // ---- Theses as a table with checkboxes -------------------------------------
  // One row per thesis and fixed columns, so the list reads like «Resumen» and uses the whole height.
  const MISS = label => `<span class="org-miss">${label}</span>`;
  function thesisRow(d, dup, busy){
    const id = d.id;
    const m = d.metadata || {};
    const on = org.selected.has(id);
    const focused = S.collectionFocusedId === id;
    const pills = [];
    const original = dup.originalOf.get(id);
    if(original) pills.push(`<span class="org-pill" style="margin-left:0">repetida de ${esc(original.thesis_id || displayTitle(original))}</span>`);
    if(d.analysis_stale) pills.push(`<span class="org-pill" style="margin-left:0">extraída con ${esc(d.analysis_versions?.software_version || 'una versión anterior')}</span>`);
    const scan = ocrCardHtml(d);
    const processedDoc = processed(d);
    const unprocessed = d.status === 'uploaded';
    return `<tr data-card-id="${esc(id)}" class="${on ? 'org-on' : ''} ${focused ? 'selected' : ''}" draggable="true" tabindex="-1">
      <td class="org-c-check"><input type="checkbox" data-org-check="${esc(id)}" ${on ? 'checked' : ''} aria-label="Seleccionar ${esc(displayTitle(d))}"></td>
      <td class="org-c-code">${esc(d.thesis_id || '')}</td>
      <td class="org-c-title"><div class="org-title" title="${esc(displayTitle(d))}">${esc(displayTitle(d))}</div><div class="org-file" title="${esc(d.filename || '')}">${esc(d.filename || '')}</div>${pills.join('')}${scan ? `<div data-org-ocr="${esc(id)}">${scan}</div>` : ''}</td>
      <td class="org-c-author">${m.author ? esc(m.author) : MISS('falta')}</td>
      <td class="org-c-num">${m.year ? esc(m.year) : MISS('falta')}</td>
      <td class="org-c-num">${processedDoc ? fmt(d.n_references) : '—'}</td>
      <td class="org-c-problems">${window.BiblioRefProblems ? BiblioRefProblems.chips(d) : ''}</td>
      <td class="org-c-status"><span class="pill ${pillClass(d)}">${statusText(d)}</span></td>
      <td class="org-c-acts">${unprocessed ? `<button type="button" class="btn xs primary" data-org-row="process" ${busy ? 'disabled' : ''}>Procesar</button>` : '<button type="button" class="btn xs" data-org-row="open">Revisar</button>'}<button type="button" class="btn xs org-more" data-org-row="more" aria-haspopup="menu" aria-label="Más acciones">⋯</button></td>
    </tr>`;
  }

  window.renderCards = function renderThesisTable(){
    const host = $('#uploadCards');
    if(!host) return;
    $('#collectionCount').textContent = S.docs.length;
    $('#analyzeAll').disabled = S.importBusy || S.analysisBusy || !S.docs.length;
    const ids = new Set(S.docs.map(d => d.id));
    org.selected = new Set([...org.selected].filter(id => ids.has(id)));
    const visible = S.docs.filter(matchesCollectionSearch);
    const query = $('#collectionSearch').value.trim();
    $('#collectionSearchCount').textContent = query ? `${visible.length} de ${S.docs.length} tesis` : '';
    host.classList.add('org-table-host');
    if(!visible.length){
      host.innerHTML = S.docs.length
        ? '<div class="projects-empty"><b>No se encontraron tesis</b><p>Probá con otro título, archivo o universidad.</p></div>'
        : '<div class="projects-empty"><b>El proyecto está listo para recibir tesis</b><p>Usá «Agregar tesis» o arrastrá PDF, ZIP o carpetas.</p></div>';
    }else{
      const dup = duplicateInfo();
      const busy = S.importBusy || S.analysisBusy;
      const scroll = host.querySelector('.org-scroll');
      const pos = scroll ? [scroll.scrollTop, scroll.scrollLeft] : [0, 0];
      host.innerHTML = `<div class="org-scroll"><table class="org-table"><thead><tr>
          <th class="org-c-check"><input type="checkbox" data-org-all aria-label="Seleccionar todas las tesis visibles" title="Todas las visibles (Ctrl+A)"></th><th class="org-c-code">Código</th><th>Título de la tesis</th><th class="org-c-author">Autor/a</th>
          <th class="org-c-num">Año</th><th class="org-c-num">Refs</th><th class="org-c-problems">Problemas</th><th class="org-c-status">Estado</th><th class="org-c-acts"></th>
        </tr></thead><tbody>${visible.map(d => thesisRow(d, dup, busy)).join('')}</tbody></table></div>`;
      const next = host.querySelector('.org-scroll');
      next.scrollTop = pos[0];
      next.scrollLeft = pos[1];
    }
    if(typeof updateHeroEmphasis === 'function') updateHeroEmphasis();
    renderStatusBar();
    renderSelectionBar();
    renderTools();
  };

  // What the project still needs, with the action for all of them: OCR (amber, something is missing)
  // and reprocessing (grey outline, worth doing).
  function renderStatusBar(){
    const cards = $('#uploadCards');
    if(!cards) return;
    let bar = document.getElementById('orgStatus');
    if(!bar){
      bar = document.createElement('div');
      bar.id = 'orgStatus';
      bar.className = 'org-status';
      bar.setAttribute('role', 'status');
      cards.parentNode.insertBefore(bar, document.getElementById('orgBar') || cards);
    }
    const running = S.docs.filter(d => OCR_ACTIVE.includes(org.ocr.jobs[d.id]?.state));
    const ocr = reasonSets('ocr').show;
    const waiting = [...ocr].filter(id => !OCR_ACTIVE.includes(org.ocr.jobs[id]?.state));
    const stale = reasonSets('stale').show;
    const busy = S.importBusy || S.analysisBusy;
    const on = id => org.view?.kind === 'reason' && org.view.id === id;
    const plural = (n, one, many) => `${fmt(n)} ${n === 1 ? one : many}`;
    const groups = [
      running.length && `<div class="org-stg"><span class="org-dot org-run"></span><span>OCR en curso en <b>${plural(running.length, 'tesis', 'tesis')}</b></span></div>`,
      waiting.length && `<div class="org-stg"><span class="org-dot"></span><span><b>${fmt(waiting.length)}</b> ${waiting.length === 1 ? 'necesita' : 'necesitan'} OCR</span>
        <button type="button" class="btn xs" data-org-status-view="ocr" aria-pressed="${on('ocr')}">${on('ocr') ? 'Ver todas' : 'Ver cuáles'}</button>
        <button type="button" class="btn xs primary" data-org-status-run="ocr">${waiting.length === 1 ? 'Aplicar OCR…' : `Aplicar OCR a las ${fmt(waiting.length)}…`}</button></div>`,
      stale.size && `<div class="org-stg"><span class="org-dot org-rv"></span><span><b>${fmt(stale.size)}</b> para reprocesar</span>
        <button type="button" class="btn xs" data-org-status-view="stale" aria-pressed="${on('stale')}" title="Extraídas con una versión anterior del motor, o con el OCR hecho después de procesarlas">${on('stale') ? 'Ver todas' : 'Ver cuáles'}</button>
        <button type="button" class="btn xs" data-org-status-run="stale" ${busy ? 'disabled' : ''}>${stale.size === 1 ? 'Reprocesar' : `Reprocesar las ${fmt(stale.size)}`}</button></div>`,
    ].filter(Boolean);
    bar.hidden = !groups.length;
    bar.innerHTML = groups.join('<span class="org-stsep" aria-hidden="true"></span>');
  }
  document.querySelector('.collection-documents')?.addEventListener('click', e => {
    const view = e.target.closest('[data-org-status-view]');
    if(view){
      const id = view.dataset.orgStatusView;
      if(org.view?.kind === 'reason' && org.view.id === id) return setView(null);
      return setView({kind: 'reason', id}, reasonSets(id).mark);
    }
    const run = e.target.closest('[data-org-status-run]');
    if(!run) return;
    const id = run.dataset.orgStatusRun;
    const ids = id === 'ocr'
      ? [...reasonSets('ocr').show].filter(x => !OCR_ACTIVE.includes(org.ocr.jobs[x]?.state))
      : [...reasonSets('stale').show];
    org.selected = new Set(ids);
    renderCards();
    if(id === 'ocr') openOcrDialog(); else processSelection();
  });

  // Starts again from the PDF as imported; the bibliography is extracted again unless it has manual work.
  async function redoOcr(d){
    const pages = d.ocr.pages.length;
    if(!await confirmModal(`¿Rehacer el OCR de ${d.thesis_id || 'esta tesis'}? Se vuelven a reconocer ${fmt(pages)} ${pages === 1 ? 'página' : 'páginas'} desde el PDF original (${minutesLabel(pages)}).`)) return;
    try{
      const res = await api(`/api/documents/${encodeURIComponent(d.id)}/ocr`, jsonBody({scope: 'redo'}));
      if(res.job) org.ocr.jobs[d.id] = res.job;
      if(res.message) return notify(res.message);
      renderCards();
      pollProjectOcr(true);
    }catch(err){ notify('No se pudo rehacer el OCR: ' + err.message); }
  }

  // «Revisar» opens the thesis's references as a table; without references there is only the PDF to look at.
  function reviewThesis(id){
    const d = S.docs.find(x => x.id === id);
    if(d && processed(d) && d.n_references && window.BiblioRefOpenThesisTable) window.BiblioRefOpenThesisTable(id);
    else openDoc(id);
  }
  window.BiblioRefReviewThesis = reviewThesis;

  function rowAction(action, id, anchor){
    const d = S.docs.find(x => x.id === id);
    if(!d) return;
    if(action === 'open') reviewThesis(id);
    else if(action === 'process') analyzeOne(id, 'stable', true);
    else if(action === 'more'){
      const busy = S.importBusy || S.analysisBusy;
      showMenu(anchor, `<button type="button" role="menuitem" data-item="pdf"><span>Ver en el PDF</span><span></span></button>
        ${processed(d) && !busy ? `<button type="button" role="menuitem" data-item="reprocess"><span>${d.analysis_stale ? `Actualizar a v${esc(d.current_versions?.software_version || 'actual')}` : 'Reprocesar referencias'}</span><span></span></button>` : ''}
        ${scannedPages(d).length ? '<button type="button" role="menuitem" data-item="ocr"><span>Aplicar OCR…</span><span></span></button>' : ''}
        ${d.ocr?.pages?.length ? '<button type="button" role="menuitem" data-item="redo-ocr"><span>Rehacer OCR</span><span></span></button>' : ''}
        ${busy ? '' : '<button type="button" role="menuitem" data-item="remove"><span>Quitar del proyecto…</span><span></span></button>'}`, item => {
        if(item === 'pdf') openDoc(id);
        else if(item === 'reprocess') analyzeOne(id, 'stable', true);
        else if(item === 'ocr'){ org.selected = new Set([id]); renderCards(); openOcrDialog(); }
        else if(item === 'redo-ocr') redoOcr(d);
        else if(item === 'remove') removeDoc(id);
      });
    }
  }

  function renderTools(){
    const search = document.querySelector('.collection-search');
    if(!search) return;
    let tools = search.querySelector('.org-tools');
    if(!tools){
      tools = document.createElement('div');
      tools.className = 'org-tools';
      search.appendChild(tools);
    }
    const v = org.view;
    const label = v ? (v.kind === 'reason' ? reason(v.id).label : v.label) : '';
    tools.innerHTML = `<button type="button" class="btn" data-org-menu aria-haspopup="menu">Seleccionar por… ▾</button>
      ${v ? `<span class="org-viewchip">Mostrando: ${esc(label)} · ${fmt(visibleDocs().length)}<button type="button" data-org-clear-view aria-label="Mostrar todas las tesis">×</button></span>` : ''}`;
  }

  function renderSelectionBar(){
    const cards = $('#uploadCards');
    if(!cards) return;
    let bar = document.getElementById('orgBar');
    if(!bar){
      bar = document.createElement('div');
      bar.id = 'orgBar';
      bar.className = 'org-bar';
      bar.setAttribute('role', 'region');
      bar.setAttribute('aria-label', 'Acciones sobre las tesis seleccionadas');
      cards.parentNode.insertBefore(bar, cards);
    }
    const n = org.selected.size;
    const visible = visibleDocs();
    const allVisible = visible.length && visible.every(d => org.selected.has(d.id));
    // The header checkbox mirrors the visible rows: checked, empty or half.
    const head = document.querySelector('#uploadCards .org-table th [data-org-all]');
    if(head){ head.checked = !!allVisible; head.indeterminate = !allVisible && visible.some(d => org.selected.has(d.id)); }
    bar.hidden = !n;
    if(!n){ bar.innerHTML = ''; return; }
    const busy = S.importBusy || S.analysisBusy;
    bar.innerHTML = `<input type="checkbox" data-org-all ${allVisible ? 'checked' : ''} aria-label="Seleccionar todas las visibles">
      <b>${allVisible || n > visible.length ? fmt(n) : `${fmt(n)} de ${fmt(visible.length)}`} ${n === 1 ? 'seleccionada' : 'seleccionadas'}</b>
      <span class="org-links">${allVisible ? '' : `<button type="button" data-org-pick="all">Seleccionar ${visible.length === 1 ? 'la visible' : `las ${fmt(visible.length)}`}</button><span aria-hidden="true">·</span>`}<button type="button" data-org-pick="none">Ninguna</button></span>
      <span class="org-sp"></span>
      ${org.view?.kind === 'reason' && org.view.id === 'duplicates' && org.duplicates?.groups?.length ? '<button type="button" class="btn primary" data-org-act="dedupe">Revisar y quitar copias…</button>' : ''}
      ${S.docs.some(d => org.selected.has(d.id) && scannedPages(d).length) ? `<button type="button" class="btn ${org.view?.kind === 'reason' && org.view.id === 'ocr' ? 'primary' : ''}" data-org-act="ocr">Aplicar OCR…</button>` : ''}
      <button type="button" class="btn" data-org-act="move">Mover a…</button>
      <button type="button" class="btn" data-org-act="process" ${busy ? 'disabled' : ''}>Procesar</button>
      <button type="button" class="btn" data-org-act="export">Exportar</button>
      <button type="button" class="btn warn" data-org-act="remove" ${busy ? 'disabled' : ''}>Quitar…</button>
      <button type="button" class="text-btn" data-org-act="clear">Cancelar</button>`;
    const all = bar.querySelector('[data-org-all]');
    if(all) all.indeterminate = !allVisible && visible.some(d => org.selected.has(d.id));
  }

  function toggleOne(id, on, shift){
    const visible = visibleDocs().map(d => d.id);
    if(shift && org.lastClicked && visible.includes(org.lastClicked)){
      const [a, b] = [visible.indexOf(org.lastClicked), visible.indexOf(id)].sort((x, y) => x - y);
      visible.slice(a, b + 1).forEach(x => on ? org.selected.add(x) : org.selected.delete(x));
    }else if(on){
      org.selected.add(id);
    }else{
      org.selected.delete(id);
    }
    org.lastClicked = id;
    document.querySelectorAll('#uploadCards [data-card-id]').forEach(card => {
      const selected = org.selected.has(card.dataset.cardId);
      card.classList.toggle('org-on', selected);
      const box = card.querySelector('[data-org-check]');
      if(box) box.checked = selected;
    });
    renderSelectionBar();
  }

  const cardsHost = $('#uploadCards');
  cardsHost?.addEventListener('click', e => {
    const box = e.target.closest('[data-org-check]');
    if(box){ e.stopPropagation(); toggleOne(box.dataset.orgCheck, box.checked, e.shiftKey); return; }
    const row = e.target.closest('[data-card-id]');
    if(!row) return;
    const act = e.target.closest('[data-org-row]');
    if(act){ e.stopPropagation(); rowAction(act.dataset.orgRow, row.dataset.cardId, act); return; }
    if(!e.target.closest('button,a,input,select')) focusCollectionDocument(row.dataset.cardId);
  });
  cardsHost?.addEventListener('dblclick', e => {
    const row = e.target.closest('[data-card-id]');
    if(row && !e.target.closest('button,a,input,select')) reviewThesis(row.dataset.cardId);
  });
  cardsHost?.addEventListener('dragstart', e => {
    const card = e.target.closest?.('[data-card-id]');
    if(card) startDrag(e, card.dataset.cardId, card);
  });
  cardsHost?.addEventListener('dragend', e => e.target.closest?.('[data-card-id]')?.classList.remove('org-dragging'));

  document.querySelector('.collection-documents')?.addEventListener('click', e => {
    if(e.target.closest('[data-org-all]')){
      const on = e.target.checked;
      visibleDocs().forEach(d => on ? org.selected.add(d.id) : org.selected.delete(d.id));
      renderCards();
    }else if(e.target.closest('[data-org-pick]')){
      if(e.target.closest('[data-org-pick]').dataset.orgPick === 'all') visibleDocs().forEach(d => org.selected.add(d.id));
      else org.selected.clear();
      renderCards();
    }else if(e.target.closest('[data-org-act]')){
      runAction(e.target.closest('[data-org-act]').dataset.orgAct);
    }else if(e.target.closest('[data-org-menu]')){
      openReasonMenu(e.target.closest('[data-org-menu]'));
    }else if(e.target.closest('[data-org-clear-view]')){
      setView(null);
    }
  });

  document.addEventListener('keydown', e => {
    if(!$('#screen-collection')?.classList.contains('active')) return;
    if((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a' && !e.target.closest('input,textarea,select,[contenteditable]')){
      e.preventDefault();
      visibleDocs().forEach(d => org.selected.add(d.id));
      renderCards();
    }
  });

  // ---- "Seleccionar por…" menu -------------------------------------------------
  function closeMenu(){ document.querySelector('.org-menu')?.remove(); }
  document.addEventListener('click', e => { if(!e.target.closest('.org-menu') && !e.target.closest('[data-org-menu]') && !e.target.closest('.org-more')) closeMenu(); });
  document.addEventListener('keydown', e => { if(e.key === 'Escape') closeMenu(); });

  function showMenu(anchor, html, onClick){
    closeMenu();
    const menu = document.createElement('div');
    menu.className = 'org-menu';
    menu.setAttribute('role', 'menu');
    menu.innerHTML = html;
    document.body.appendChild(menu);
    const r = anchor.getBoundingClientRect();
    menu.style.left = Math.max(8, Math.min(r.left, innerWidth - menu.offsetWidth - 8)) + 'px';
    menu.style.top = (r.bottom + 4 + menu.offsetHeight > innerHeight ? Math.max(8, r.top - menu.offsetHeight - 4) : r.bottom + 4) + 'px';
    menu.addEventListener('click', e => {
      const item = e.target.closest('[data-item]');
      if(!item) return;
      closeMenu();
      onClick(item.dataset.item);
    });
    menu.querySelector('button')?.focus();
  }

  function openReasonMenu(anchor){
    const groups = ['Estado', 'Datos'];
    const savedList = S.project?.saved_selections || [];
    const inSidebar = selectionsPlace() === 'sidebar';
    const univ = $('#groupUniversity');
    const html = `<h4>Rápido</h4>
      <button type="button" role="menuitem" data-item="all"><span>Todas (${fmt(visibleDocs().length)})</span><span>Ctrl+A</span></button>
      <button type="button" role="menuitem" data-item="invert"><span>Invertir selección</span><span></span></button>
      <button type="button" role="menuitem" data-item="none"><span>Ninguna</span><span></span></button>` +
      groups.map(g => `<h4>${g}</h4>` + REASONS.filter(r => r.group === g).map(r => {
      const sets = reasonSets(r.id);
      return `<button type="button" role="menuitem" data-item="reason:${r.id}"><span>${esc(r.label)}</span><span>${fmt(sets.count)}${sets.unit ? ' ' + sets.unit : ''}</span></button>`;
    }).join('')).join('') + `<h4>Valor</h4>
      <button type="button" role="menuitem" data-item="value:university"><span>Universidad…</span><span>›</span></button>
      <button type="button" role="menuitem" data-item="value:degree_level"><span>Nivel…</span><span>›</span></button>
      <button type="button" role="menuitem" data-item="value:year"><span>Año o rango de años…</span><span>›</span></button>
      <h4>Guardadas</h4>
      ${savedList.map(s => `<button type="button" role="menuitem" data-item="saved:${esc(s.id)}"><span>${esc(s.name)}</span><span></span></button>`).join('')}
      <button type="button" role="menuitem" data-item="save-search"><span>＋ Guardar búsqueda actual</span><span></span></button>
      <h4>Opciones</h4>
      <button type="button" role="menuitemcheckbox" aria-checked="${inSidebar}" data-item="place"><span>Mostrar las selecciones en el explorador</span><span></span></button>
      ${univ ? `<button type="button" role="menuitemcheckbox" aria-checked="${univ.checked}" data-item="group-university"><span>Agrupar sueltas por universidad</span><span>experimental</span></button>` : ''}`;
    showMenu(anchor, html, item => {
      if(item.startsWith('saved:')) return applySaved(item.slice(6));
      if(item === 'save-search') return saveSearch();
      if(item === 'place') return setSelectionsPlace(inSidebar ? 'menu' : 'sidebar');
      if(item === 'group-university'){ univ.checked = !univ.checked; univ.dispatchEvent(new Event('change', {bubbles: true})); return; }
      if(item.startsWith('reason:')){
        const id = item.slice(7);
        setView({kind: 'reason', id}, reasonSets(id).mark);
      }else if(item.startsWith('value:')){
        chooseValue(item.slice(6));
      }else if(item === 'all'){
        visibleDocs().forEach(d => org.selected.add(d.id)); renderCards();
      }else if(item === 'invert'){
        visibleDocs().forEach(d => org.selected.has(d.id) ? org.selected.delete(d.id) : org.selected.add(d.id)); renderCards();
      }else if(item === 'none'){
        org.selected.clear(); renderCards();
      }
    });
  }

  function chooseValue(field){
    const labels = {university: 'Universidad', degree_level: 'Nivel', year: 'Año'};
    if(field === 'year'){
      const years = S.docs.map(d => Number((d.metadata || {}).year)).filter(Boolean);
      const min = years.length ? Math.min(...years) : 2000, max = years.length ? Math.max(...years) : new Date().getFullYear();
      modal('Seleccionar por año', `<form class="project-form" id="orgYearForm"><label>Desde<input id="orgYearFrom" type="number" value="${min}" min="1900" max="2100"></label><label>Hasta<input id="orgYearTo" type="number" value="${max}" min="1900" max="2100"></label></form><p class="mini">Las tesis sin año no se seleccionan.</p>`,
        `<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="orgYearOk">Seleccionar</button>`);
      $('#orgYearOk').onclick = () => {
        const from = Number($('#orgYearFrom').value), to = Number($('#orgYearTo').value);
        const test = d => { const y = Number((d.metadata || {}).year); return y && y >= from && y <= to; };
        closeModal();
        setView({kind: 'value', label: `Año ${from}–${to}`, test}, S.docs.filter(test).map(d => d.id));
      };
      return;
    }
    const counts = new Map();
    S.docs.forEach(d => { const v = String((d.metadata || {})[field] || '').trim(); if(v) counts.set(v, (counts.get(v) || 0) + 1); });
    const options = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    modal(`Seleccionar por ${labels[field].toLowerCase()}`, options.length
      ? `<div class="org-folderpick">${options.map(([v, n], i) => `<label><input type="radio" name="orgValue" value="${esc(v)}" ${i ? '' : 'checked'}><span>${esc(v)}</span><small>${fmt(n)}</small></label>`).join('')}</div>`
      : '<p>Ninguna tesis tiene ese dato.</p>',
      `<button class="btn" onclick="closeModal()">Cancelar</button>${options.length ? '<button class="btn primary" id="orgValueOk">Seleccionar</button>' : ''}`);
    const ok = $('#orgValueOk');
    if(ok) ok.onclick = () => {
      const value = document.querySelector('input[name="orgValue"]:checked')?.value;
      const test = d => String((d.metadata || {})[field] || '').trim() === value;
      closeModal();
      setView({kind: 'value', label: `${labels[field]}: ${field === 'degree_level' ? value : value}`, test}, S.docs.filter(test).map(d => d.id));
    };
  }

  // ---- Explorer: editable folders and saved selections ---------------------------
  window.renderProjectTree = function renderEditableTree(){
    const tree = $('#projectTree');
    if(!tree) return;
    const query = collectionQuery();
    const matching = new Set(S.docs.filter(originalMatches).map(d => d.id));
    org.folderOf = new Map();
    (function index(items, parents){
      for(const n of items){
        if(n.kind === 'folder') index(n.children, [...parents, n.name]);
        else org.folderOf.set(n.id, parents);
      }
    })(S.projectTree || [], []);
    function filtered(items, parentMatch = false){
      return items.flatMap(n => {
        const match = parentMatch || n.name.toLocaleLowerCase('es').includes(query);
        if(n.kind === 'document') return match || matching.has(n.id) ? [n] : [];
        const children = filtered(n.children, match);
        return children.length || (!query && n.kind === 'folder') ? [{...n, children}] : [];
      });
    }
    function nodes(items, parents = []){
      return items.map(n => {
        if(n.kind === 'folder'){
          const pathArr = [...parents, n.name];
          const path = JSON.stringify(pathArr);
          const open = !query && (S.treeCollapsed || S.treeClosed.has(path)) ? '' : 'open';
          const renaming = org.renaming === path;
          const name = renaming
            ? `<input class="org-rename" data-org-rename="${esc(path)}" value="${esc(n.name)}" aria-label="Nuevo nombre de la carpeta" maxlength="120">`
            : `<span>${esc(n.name)}</span>`;
          return `<details class="tree-folder" data-tree-path="${esc(path)}" ${open}><summary title="${esc(n.name)}" data-org-folder="${esc(path)}">${folderIcon}${name}<small>${n.count}</small><button type="button" class="org-more" data-org-folder-menu="${esc(path)}" aria-label="Opciones de la carpeta ${esc(n.name)}">⋯</button></summary><div class="tree-children">${nodes(n.children, pathArr)}</div></details>`;
        }
        return `<button class="tree-file ${(S.collectionFocusedId || S.doc?.id) === n.id ? 'selected' : ''}" draggable="true" data-doc-id="${esc(n.id)}" title="${esc(n.name)} · ${esc(n.title)}${n.university_suggested ? ' · Universidad sugerida en portada' : ''}">${fileIcon}<span>${esc(n.name)}</span>${n.university_suggested ? '<small>por revisar</small>' : ''}</button>`;
      }).join('');
    }
    tree.innerHTML = nodes(query ? filtered(S.projectTree || []) : (S.projectTree || []))
      || (query ? '<div class="tree-empty">No hay archivos que coincidan.</div>' : '<div class="tree-empty">Tu estructura aparecerá aquí<br>cuando incorpores las tesis.</div>');
    if(!query) tree.querySelectorAll('details').forEach(d => d.addEventListener('toggle', () => {
      if(d.open) S.treeClosed.delete(d.dataset.treePath); else S.treeClosed.add(d.dataset.treePath);
    }));
    const input = tree.querySelector('[data-org-rename]');
    if(input){ input.focus(); input.select(); }
    renderExplorerExtras();
    renderSelections();
  };

  function renderExplorerExtras(){
    const sub = document.querySelector('.explorer-subhead');
    if(sub && !sub.querySelector('[data-org-newfolder]')){
      sub.querySelector('#toggleTree')?.insertAdjacentHTML('beforebegin', '<button type="button" class="org-newfolder" data-org-newfolder>＋ Nueva carpeta</button>');
    }
    const help = document.querySelector('.explorer-help');
    if(help) help.textContent = 'Un clic ubica la tesis · doble clic abre la revisión · arrastrá tesis a una carpeta · clic derecho o ⋯ en una carpeta para más opciones.';
    const root = document.querySelector('.tree-root');
    if(root) root.dataset.orgFolder = '[]';
  }

  function renderSelections(){
    const tree = $('#projectTree');
    if(!tree) return;
    let box = document.getElementById('orgSelections');
    if(!box){
      box = document.createElement('section');
      box.id = 'orgSelections';
      box.className = 'org-selections';
      box.setAttribute('aria-label', 'Selecciones');
      tree.insertAdjacentElement('afterend', box);
    }
    const v = org.view;
    const items = REASONS.filter(r => r.sidebar).map(r => {
      const sets = reasonSets(r.id);
      if(r.id === 'inferred' && !sets.count) return '';
      if(r.id === 'duplicates' && !org.duplicates) return `<button type="button" class="org-sel" disabled>${BOLT}<span class="org-n">${esc(r.label)}</span><small>calculando…</small></button>`;
      const on = v?.kind === 'reason' && v.id === r.id;
      return `<button type="button" class="org-sel" data-org-reason="${r.id}" aria-pressed="${on}">${BOLT}<span class="org-n">${esc(r.label)}</span><small>${fmt(sets.count)}${sets.unit ? ' ' + sets.unit : ''}</small></button>`;
    }).join('');
    const saved = (S.project?.saved_selections || []).map(s => {
      const on = v?.kind === 'saved' && v.id === s.id;
      return `<div class="org-sel" role="button" tabindex="0" data-org-saved="${esc(s.id)}" aria-pressed="${on}">${SAVED}<span class="org-n">${esc(s.name)}</span><button type="button" class="org-x" data-org-saved-del="${esc(s.id)}" aria-label="Borrar la selección ${esc(s.name)}">×</button></div>`;
    }).join('');
    const pending = reasonSets('review').count;
    const now = v ? (v.kind === 'reason' ? reason(v.id)?.label : v.label) : '';
    const open = !!org.selOpen;
    box.innerHTML = `<button type="button" class="org-selbar" data-org-selbar aria-expanded="${open}" aria-controls="orgSelPop">${BOLT}<h3>Selecciones</h3>${now ? `<span class="org-selnow">· ${esc(now)}</span>` : ''}${pending ? `<span class="org-selbadge">${fmt(pending)} por revisar</span>` : ''}<span class="org-caret" aria-hidden="true">${open ? '▾' : '▴'}</span></button>
      <div class="org-selpop" id="orgSelPop" ${open ? '' : 'hidden'}>${items}${saved}<button type="button" class="org-save" data-org-save-search>＋ Guardar búsqueda actual</button><button type="button" class="org-tomenu" data-org-place="menu" title="Quitar esta línea del explorador; siguen en «Seleccionar por…»">Mostrar solo en «Seleccionar por…»</button></div>`;
    applySelectionsPlace();
  }
  function setSelectionsOpen(open){
    org.selOpen = open;
    const box = document.getElementById('orgSelections');
    if(!box) return;
    box.querySelector('#orgSelPop').hidden = !open;
    const bar = box.querySelector('[data-org-selbar]');
    bar.setAttribute('aria-expanded', String(open));
    bar.querySelector('.org-caret').textContent = open ? '▾' : '▴';
  }
  document.addEventListener('click', e => { if(org.selOpen && !e.target.closest('#orgSelections')) setSelectionsOpen(false); });
  document.addEventListener('keydown', e => { if(e.key === 'Escape' && org.selOpen) setSelectionsOpen(false); });

  // Where «Selecciones» lives is a browser preference: in the sidebar (folds to one row) or only in the menu.
  const PLACE_KEY = 'biblioref.selections-place';
  function selectionsPlace(){ try{ return localStorage.getItem(PLACE_KEY) === 'menu' ? 'menu' : 'sidebar'; }catch{ return 'sidebar'; } }
  function setSelectionsPlace(place){
    const before = selectionsPlace();
    try{ localStorage.setItem(PLACE_KEY, place); }catch{}
    applySelectionsPlace();
    if(place === 'menu') toast('Las selecciones quedan en «Seleccionar por…»; desde ese menú se vuelven a mostrar acá.', () => setSelectionsPlace(before));
  }
  function applySelectionsPlace(){
    const explorer = $('#projectExplorer');
    if(!explorer) return;
    const menu = selectionsPlace() === 'menu';
    explorer.classList.toggle('org-sel-menu', menu);
  }

  const explorer = $('#projectExplorer');
  explorer?.addEventListener('click', e => {
    const more = e.target.closest('[data-org-folder-menu]');
    if(more){ e.preventDefault(); e.stopPropagation(); openFolderMenu(more, JSON.parse(more.dataset.orgFolderMenu)); return; }
    if(e.target.closest('[data-org-rename]')){ e.preventDefault(); return; }
    if(e.target.closest('[data-org-newfolder]')) return newFolder([]);
    if(e.target.closest('[data-org-selbar]')) return setSelectionsOpen(!org.selOpen);
    const r = e.target.closest('[data-org-reason]');
    if(r){
      const id = r.dataset.orgReason;
      org.selOpen = false;
      if(org.view?.kind === 'reason' && org.view.id === id) return setView(null);
      return setView({kind: 'reason', id}, reasonSets(id).mark);
    }
    const del = e.target.closest('[data-org-saved-del]');
    if(del){ e.stopPropagation(); return deleteSaved(del.dataset.orgSavedDel); }
    const saved = e.target.closest('[data-org-saved]');
    if(saved){ setSelectionsOpen(false); return applySaved(saved.dataset.orgSaved); }
    if(e.target.closest('[data-org-save-search]')){ setSelectionsOpen(false); return saveSearch(); }
    const place = e.target.closest('[data-org-place]');
    if(place){ setSelectionsOpen(false); return setSelectionsPlace(place.dataset.orgPlace); }
  });
  explorer?.addEventListener('keydown', e => {
    const input = e.target.closest('[data-org-rename]');
    if(input){
      if(e.key === 'Enter'){ e.preventDefault(); commitRename(input); }
      else if(e.key === 'Escape'){ org.renaming = null; renderProjectTree(); }
      else if(e.key === ' '){ e.stopPropagation(); }
      return;
    }
    const saved = e.target.closest('[data-org-saved]');
    if(saved && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); applySaved(saved.dataset.orgSaved); }
    const summary = e.target.closest('summary[data-org-folder]');
    if(summary && e.key === 'F2'){ e.preventDefault(); org.renaming = summary.dataset.orgFolder; renderProjectTree(); }
  });
  explorer?.addEventListener('focusout', e => {
    const input = e.target.closest?.('[data-org-rename]');
    if(input && org.renaming) commitRename(input);
  });
  explorer?.addEventListener('contextmenu', e => {
    const summary = e.target.closest('summary[data-org-folder]');
    if(!summary) return;
    e.preventDefault();
    openFolderMenu(summary, JSON.parse(summary.dataset.orgFolder));
  });

  function openFolderMenu(anchor, path){
    showMenu(anchor, `<button type="button" role="menuitem" data-item="sub"><span>Nueva subcarpeta</span><span></span></button>
      <button type="button" role="menuitem" data-item="rename"><span>Renombrar</span><span>F2</span></button>
      <button type="button" role="menuitem" data-item="select"><span>Seleccionar su contenido</span><span>${fmt(folderDocs(path).size)}</span></button>
      <hr><button type="button" role="menuitem" class="org-danger" data-item="delete"><span>Eliminar carpeta…</span><span></span></button>`, item => {
      if(item === 'sub') newFolder(path);
      else if(item === 'rename'){ org.renaming = JSON.stringify(path); renderProjectTree(); }
      else if(item === 'select') setView({kind: 'folder', path, label: `Carpeta ${path.join(' › ')}`}, folderDocs(path));
      else if(item === 'delete') deleteFolder(path);
    });
  }

  async function reloadTree(){
    await refreshProjectTree();
    renderCards();
  }

  async function commitRename(input){
    const path = JSON.parse(input.dataset.orgRename);
    const name = input.value.trim();
    org.renaming = null;
    if(!name || name === path[path.length - 1]){ renderProjectTree(); return; }
    try{
      await api(`/api/projects/${encodeURIComponent(projectId())}/folders`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path, name})});
      const oldKey = JSON.stringify(path);
      if(S.treeClosed.delete(oldKey)) S.treeClosed.add(JSON.stringify([...path.slice(0, -1), name]));
      $('#projectSaved').textContent = 'Carpeta renombrada';
      await reloadTree();
    }catch(err){
      renderProjectTree();
      notify('No se pudo renombrar la carpeta: ' + err.message);
    }
  }

  function newFolder(parent){
    const where = parent.length ? `dentro de «${esc(parent.join(' › '))}»` : 'en la raíz del proyecto';
    modal('Nueva carpeta', `<form class="project-form" id="orgNewFolder"><label>Nombre de la carpeta <span class="mini">${where}</span><input id="orgNewFolderName" maxlength="120" required placeholder="Por ejemplo: Duplicadas para revisar"></label></form>`,
      `<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="orgNewFolderOk">Crear carpeta</button>`);
    const submit = async () => {
      const name = $('#orgNewFolderName').value.trim();
      if(!name) return $('#orgNewFolderName').focus();
      try{
        await api(`/api/projects/${encodeURIComponent(projectId())}/folders`, jsonBody({path: [...parent, name]}));
        closeModal();
        $('#projectSaved').textContent = 'Carpeta creada';
        await reloadTree();
      }catch(err){ modalWarn('No se pudo crear la carpeta: ' + err.message); }
    };
    $('#orgNewFolderOk').onclick = submit;
    $('#orgNewFolder').onsubmit = e => { e.preventDefault(); submit(); };
    $('#orgNewFolderName').focus();
  }

  async function deleteFolder(path){
    const n = folderDocs(path).size;
    const parent = path.length > 1 ? `«${path.slice(0, -1).join(' › ')}»` : 'la raíz del proyecto';
    const message = n
      ? `¿Eliminar la carpeta «${path[path.length - 1]}»? Sus ${n} tesis y subcarpetas pasan a ${parent}. No se borra ninguna tesis.`
      : `¿Eliminar la carpeta vacía «${path[path.length - 1]}»?`;
    if(!await confirmModal(message)) return;
    try{
      await api(`/api/projects/${encodeURIComponent(projectId())}/folders/delete`, jsonBody({path}));
      if(org.view?.kind === 'folder') org.view = null;
      $('#projectSaved').textContent = 'Carpeta eliminada';
      await reloadTree();
    }catch(err){ notify('No se pudo eliminar la carpeta: ' + err.message); }
  }

  // ---- Drag and drop ------------------------------------------------------------
  function startDrag(e, id, el){
    const ids = org.selected.has(id) ? [...org.selected] : [id];
    e.dataTransfer.setData('application/x-biblioref-docs', JSON.stringify(ids));
    e.dataTransfer.setData('text/plain', `${ids.length} tesis`);
    e.dataTransfer.effectAllowed = 'move';
    el?.classList.add('org-dragging');
  }
  explorer?.addEventListener('dragstart', e => {
    const file = e.target.closest?.('.tree-file[data-doc-id]');
    if(file) startDrag(e, file.dataset.docId, null);
  });
  const dropTarget = e => e.target.closest?.('summary[data-org-folder], .tree-root[data-org-folder]');
  explorer?.addEventListener('dragover', e => {
    const target = dropTarget(e);
    if(!target || !e.dataTransfer.types.includes('application/x-biblioref-docs')) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    explorer.querySelectorAll('.org-drop').forEach(x => x !== target && x.classList.remove('org-drop'));
    target.classList.add('org-drop');
  });
  explorer?.addEventListener('dragleave', e => {
    const target = dropTarget(e);
    if(target && !target.contains(e.relatedTarget)) target.classList.remove('org-drop');
  });
  explorer?.addEventListener('drop', e => {
    const target = dropTarget(e);
    explorer.querySelectorAll('.org-drop').forEach(x => x.classList.remove('org-drop'));
    if(!target) return;
    const raw = e.dataTransfer.getData('application/x-biblioref-docs');
    if(!raw) return;
    e.preventDefault();
    moveTo(JSON.parse(raw), JSON.parse(target.dataset.orgFolder));
  });

  // ---- Actions on the selection ---------------------------------------------------
  function toast(message, undo){
    document.querySelector('.org-toast')?.remove();
    clearTimeout(org.toastTimer);
    const el = document.createElement('div');
    el.className = 'org-toast';
    el.setAttribute('role', 'status');
    el.innerHTML = `<span>${esc(message)}</span>${undo ? '<button type="button">Deshacer</button>' : ''}`;
    document.body.appendChild(el);
    if(undo) el.querySelector('button').onclick = () => { el.remove(); undo(); };
    org.toastTimer = setTimeout(() => el.remove(), 9000);
  }

  async function moveTo(ids, path, {silent = false} = {}){
    try{
      const res = await api(`/api/projects/${encodeURIComponent(projectId())}/move`, jsonBody({document_ids: ids, path}));
      $('#projectSaved').textContent = 'Tesis movidas';
      await reloadTree();
      if(!silent) toast(`${ids.length} ${ids.length === 1 ? 'tesis movida' : 'tesis movidas'} a ${path.length ? path.join(' › ') : 'la raíz'}`, async () => {
        try{
          await api(`/api/projects/${encodeURIComponent(projectId())}/move`, jsonBody({moves: res.previous}));
          await reloadTree();
          toast('Movimiento deshecho');
        }catch(err){ notify('No se pudo deshacer: ' + err.message); }
      });
    }catch(err){ notify('No se pudieron mover las tesis: ' + err.message); }
  }

  function folderPaths(items = S.projectTree || [], parents = []){
    return items.filter(n => n.kind === 'folder').flatMap(n => [{path: [...parents, n.name], count: n.count}, ...folderPaths(n.children, [...parents, n.name])]);
  }

  function openMoveDialog(){
    const ids = [...org.selected];
    const folders = folderPaths();
    const row = (path, count, checked) => `<label style="padding-left:${6 + path.length * 16}px"><input type="radio" name="orgDest" value="${esc(JSON.stringify(path))}" ${checked ? 'checked' : ''}>${folderIcon.replace('<svg', '<svg width="16" height="16"')}<span>${esc(path.length ? path[path.length - 1] : (S.project?.name || 'Proyecto') + ' (raíz)')}</span>${count != null ? `<small>${fmt(count)}</small>` : ''}</label>`;
    modal(`Mover ${fmt(ids.length)} ${ids.length === 1 ? 'tesis' : 'tesis'} a…`,
      `<div class="org-folderpick">${row([], null, !folders.length)}${folders.map((f, i) => row(f.path, f.count, i === 0)).join('')}</div>
       <form class="project-form" id="orgMoveNew" style="margin-top:10px"><label>O crear una carpeta nueva dentro de la elegida <span class="mini">Opcional</span><input id="orgMoveNewName" maxlength="120" placeholder="Nombre de la carpeta nueva"></label></form>
       <p class="mini">Mover no cambia el PDF ni las referencias: solo dónde se ve la tesis en el proyecto. Se puede deshacer.</p>`,
      `<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="orgMoveOk">Mover aquí</button>`);
    const submit = () => {
      const picked = document.querySelector('input[name="orgDest"]:checked');
      let path = picked ? JSON.parse(picked.value) : [];
      const extra = $('#orgMoveNewName').value.trim();
      if(extra) path = [...path, extra];
      closeModal();
      moveTo(ids, path);
    };
    $('#orgMoveOk').onclick = submit;
    $('#orgMoveNew').onsubmit = e => { e.preventDefault(); submit(); };
  }

  async function processSelection(){
    const ids = [...org.selected];
    const done = S.docs.filter(d => ids.includes(d.id) && processed(d)).length;
    if(!await confirmModal(`¿Procesar las referencias de ${ids.length} ${ids.length === 1 ? 'tesis' : 'tesis'}?${done ? ` ${done} ya estaban procesadas: se vuelven a procesar y la versión anterior queda guardada como instantánea.` : ''}`)) return;
    if(S.analysisBusy || S.importBusy) return;
    const pid = projectId();
    const work = startWork('Procesando las referencias', `0 de ${ids.length} tesis terminadas.`);
    S.analysisBusy = true; renderCards();
    let completed = 0, failed = 0, next = 0;
    const capacity = Math.max(1, Math.min(ids.length, S.capabilities?.processing?.max_workers || 1));
    const consume = async () => {
      while(next < ids.length && S.project?.id === pid){
        const id = ids[next++];
        try{
          const doc = await api(`/api/documents/${id}/analyze`, jsonBody({rescue_profile: 'stable', worker: true}));
          const i = S.docs.findIndex(d => d.id === id);
          if(i >= 0) S.docs[i] = {...S.docs[i], ...doc};
        }catch(err){ failed++; console.error(err); }
        finally{
          completed++;
          updateWork(work, {title: 'Procesando las referencias', detail: `${completed} de ${ids.length} terminadas · hasta ${capacity} en paralelo.`, percent: Math.min(99, 100 * completed / ids.length)});
        }
      }
    };
    try{
      await Promise.all(Array.from({length: capacity}, consume));
      await loadDocs();
      finishWork(work, failed ? 'Procesamiento terminado con avisos' : 'Referencias procesadas', `${ids.length - failed} de ${ids.length} tesis procesadas.`, failed === ids.length);
    }catch(err){ finishWork(work, 'No se pudo completar el procesamiento', err.message, true); }
    finally{ S.analysisBusy = false; renderCards(); updateGlobal(); }
  }

  async function removeSelection(){
    const ids = [...org.selected];
    if(!await confirmModal(`¿Quitar ${ids.length} ${ids.length === 1 ? 'tesis' : 'tesis'} del proyecto? Se eliminan sus PDF guardados en BiblioRef, sus referencias y correcciones. No se puede deshacer.`)) return;
    try{
      const res = await api(`/api/projects/${encodeURIComponent(projectId())}/documents/remove`, jsonBody({document_ids: ids}));
      org.selected.clear();
      if(S.doc && res.removed.includes(S.doc.id)) S.doc = null;
      await loadDocs();
      await loadProjects();
      toast(`${res.removed.length} ${res.removed.length === 1 ? 'tesis quitada' : 'tesis quitadas'} del proyecto`);
    }catch(err){ notify('No se pudieron quitar las tesis: ' + err.message); }
  }

  function runAction(action){
    if(action === 'clear'){ org.selected.clear(); renderCards(); }
    else if(action === 'move') openMoveDialog();
    else if(action === 'dedupe') openDedupeDialog();
    else if(action === 'ocr') openOcrDialog();
    else if(action === 'process') processSelection();
    else if(action === 'remove') removeSelection();
    else if(action === 'export'){
      S.exportIds = new Set(org.selected);
      S.exportTouched = true;
      show('export');
      if(typeof renderExport === 'function') renderExport();
    }
  }

  // ---- OCR on the selection ------------------------------------------------------------
  // Measured on T0038 at 300 dpi: 0.5–1 s per page; one second keeps the estimate honest.
  const OCR_SECONDS_PER_PAGE = 1;
  const OCR_ACTIVE = ['queued', 'running', 'extracting'];
  org.ocr = {jobs: {}, timer: null, projectId: null};
  const scannedPages = d => (d?.ocr_scan?.pages || []).map(Number);
  const pagesLabel = n => `${fmt(n)} ${n === 1 ? 'pág.' : 'págs.'}`;
  const minutesLabel = pages => {
    const min = Math.round(pages * OCR_SECONDS_PER_PAGE / 60);
    return min < 1 ? 'menos de 1 min' : `unos ${fmt(min)} min`;
  };
  const NEED_LABEL = {
    document: 'Escaneada completa',
    cover: 'Portada escaneada',
    bibliography: 'Bibliografía escaneada',
    cover_bibliography: 'Portada y bibliografía escaneadas',
  };

  function ocrCardHtml(d){
    const job = org.ocr.jobs[d?.id];
    if(job && OCR_ACTIVE.includes(job.state)){
      if(job.state === 'queued') return `<div class="org-ocr">OCR en cola · ${pagesLabel(job.total)}<div class="org-ocrbar wait"><span></span></div></div>`;
      if(job.state === 'extracting') return `<div class="org-ocr">OCR hecho · extrayendo la bibliografía<div class="org-ocrbar wait"><span></span></div></div>`;
      const pct = job.total ? Math.round(100 * job.done / job.total) : 0;
      return `<div class="org-ocr">OCR · página ${fmt(job.done)} de ${fmt(job.total)}<div class="org-ocrbar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><span style="width:${pct}%"></span></div></div>`;
    }
    if(job?.state === 'error') return `<div class="org-ocr err">OCR con error: ${esc(job.error || '')}</div>`;
    const need = d?.ocr_need;
    if(need) return `<span class="org-pill org-warn" style="margin-left:0" ${need.unreadable ? 'title="El PDF tiene texto pero no se puede leer: se convierte en imagen y se le aplica OCR"' : ''}>${need.unreadable && need.kind === 'document' ? 'Texto ilegible' : NEED_LABEL[need.kind] || 'Escaneada'} · ${pagesLabel(need.pages.length)}</span>`;
    if(d?.ocr?.reprocess_suggested) return '<span class="org-pill" style="margin-left:0">OCR hecho · falta reprocesar</span>';
    return '';
  }

  // Scopes the server understands, and the pages each one would recognise in this thesis.
  function ocrScopes(d){
    const need = d.ocr_need;
    const all = scannedPages(d);
    if(need?.kind === 'document') return [{id: 'all', label: 'Tesis completa', pages: all.length}];
    const scopes = [];
    if(need) scopes.push({id: 'needed', label: `Lo que falta (${need.kind === 'cover' ? 'portada' : need.kind === 'bibliography' ? 'bibliografía' : 'portada y bibliografía'})`, pages: need.pages.length});
    const front = (d.ocr_scan?.frontmatter_pages || []).length;
    if(front && need?.kind !== 'cover') scopes.push({id: 'frontmatter', label: 'Solo portada', pages: front});
    if(all.length && all.length !== need?.pages.length) scopes.push({id: 'all', label: 'Todas las páginas escaneadas', pages: all.length});
    return scopes;
  }

  function openOcrDialog(){
    const docs = S.docs.filter(d => org.selected.has(d.id));
    const busy = docs.filter(d => OCR_ACTIVE.includes(org.ocr.jobs[d.id]?.state));
    const rows = docs.filter(d => scannedPages(d).length && !busy.includes(d));
    const skipped = docs.length - rows.length - busy.length;
    if(!rows.length) return notify(busy.length ? 'Las tesis seleccionadas ya tienen el OCR en curso.' : 'Ninguna de las tesis seleccionadas tiene páginas escaneadas.');
    const body = rows.map(d => {
      const scopes = ocrScopes(d);
      // Only what fills a gap is proposed; loose scanned figures start unticked.
      const pick = d.ocr_need ? scopes[0].id : 'none';
      const options = scopes.map(s => `<option value="${s.id}" data-pages="${s.pages}" ${s.id === pick ? 'selected' : ''}>${esc(s.label)}</option>`).join('')
        + `<option value="none" data-pages="0" ${pick === 'none' ? 'selected' : ''}>No aplicar${d.ocr_need ? '' : ' (solo figuras o anexos)'}</option>`;
      return `<tr><td><b>${esc(d.thesis_id || '')}</b> ${esc(displayTitle(d))}</td>
        <td><select data-ocr-doc="${esc(d.id)}" aria-label="Qué reconocer en ${esc(d.thesis_id || displayTitle(d))}">${options}</select></td>
        <td class="n" data-ocr-pages></td><td class="n" data-ocr-time></td></tr>`;
    }).join('');
    const notes = [
      busy.length && `${fmt(busy.length)} ya ${busy.length === 1 ? 'tiene' : 'tienen'} el OCR en curso`,
      skipped && `${fmt(skipped)} sin páginas escaneadas: no se ${skipped === 1 ? 'toca' : 'tocan'}`,
    ].filter(Boolean).map(t => `<span>${t}</span>`).join('');
    modal(`Aplicar OCR a ${fmt(rows.length)} ${rows.length === 1 ? 'tesis' : 'tesis'}`,
      `<p>Para cada tesis se propone lo mínimo que completa lo que falta; podés cambiarlo. Corre en segundo plano y el PDF original se conserva: se trabaja sobre una copia con la capa de texto.</p>
       <div class="org-dedupe-table org-ocr-table"><table><thead><tr><th>Tesis</th><th>Qué reconocer</th><th style="text-align:right">Págs.</th><th style="text-align:right">Tiempo</th></tr></thead><tbody>${body}</tbody></table></div>
       <p class="mini">Al terminar se vuelven a leer los datos de portada. Si se reconocen páginas después de la portada, la bibliografía se extrae de nuevo, salvo en tesis con correcciones hechas a mano.</p>
       ${notes ? `<div class="org-ocr-foot">${notes}</div>` : ''}`,
      `<span class="mini" id="orgOcrTotal" style="margin-right:auto"></span><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="orgOcrOk">Aplicar OCR</button>`);
    document.querySelector('#modalHost .modal')?.classList.add('org-wide');
    const selects = [...document.querySelectorAll('select[data-ocr-doc]')];
    const update = () => {
      let pages = 0, count = 0;
      selects.forEach(sel => {
        const n = Number(sel.selectedOptions[0]?.dataset.pages || 0);
        const row = sel.closest('tr');
        row.querySelector('[data-ocr-pages]').textContent = n ? fmt(n) : '—';
        row.querySelector('[data-ocr-time]').textContent = n ? minutesLabel(n) : '—';
        pages += n; count += n ? 1 : 0;
      });
      $('#orgOcrTotal').textContent = count ? `${fmt(count)} tesis · ${pagesLabel(pages)} · ${minutesLabel(pages)}` : 'Nada para aplicar';
      $('#orgOcrOk').disabled = !count;
    };
    selects.forEach(sel => sel.addEventListener('change', update));
    update();
    $('#orgOcrOk').onclick = async () => {
      const picks = selects.filter(sel => sel.value !== 'none').map(sel => ({id: sel.dataset.ocrDoc, scope: sel.value}));
      $('#orgOcrOk').disabled = true;
      const failed = [];
      for(const p of picks){
        try{
          const res = await api(`/api/documents/${encodeURIComponent(p.id)}/ocr`, jsonBody({scope: p.scope}));
          if(res.job) org.ocr.jobs[p.id] = res.job;
        }catch(err){
          failed.push(err.message);
          if(/tesseract|spa\.traineddata|disponible/i.test(err.message)) break;
        }
      }
      closeModal();
      renderCards();
      if(failed.length) notify(`No se pudo iniciar el OCR${failed.length < picks.length ? ` en ${fmt(failed.length)} tesis` : ''}: ${failed[0]}`);
      else toast(`OCR en cola para ${fmt(picks.length)} ${picks.length === 1 ? 'tesis' : 'tesis'}`);
      pollProjectOcr(true);
    };
  }

  // The server runs one OCR at a time; follow the project's jobs and refresh a thesis when it finishes.
  async function pollProjectOcr(force = false){
    const pid = projectId();
    const ocr = org.ocr;
    if(!pid) return;
    if(ocr.projectId !== pid){
      clearTimeout(ocr.timer);
      Object.assign(ocr, {projectId: pid, jobs: {}, timer: null});
    }else if(ocr.timer && !force){
      return;
    }
    clearTimeout(ocr.timer);
    ocr.timer = null;
    let status;
    try{ status = await api(`/api/projects/${encodeURIComponent(pid)}/ocr`); }catch(err){ return; }
    if(projectId() !== pid) return;
    const before = ocr.jobs;
    ocr.jobs = status.jobs || {};
    const settled = Object.keys(ocr.jobs).some(id => OCR_ACTIVE.includes(before[id]?.state) && !OCR_ACTIVE.includes(ocr.jobs[id].state));
    if(settled){
      try{ await loadDocs(); }catch(err){}
      renderCards();
    }else{
      let missing = false;
      for(const [id, job] of Object.entries(ocr.jobs)){
        const node = document.querySelector(`[data-org-ocr="${CSS.escape(id)}"]`);
        if(node) node.innerHTML = ocrCardHtml({...S.docs.find(d => d.id === id), id});
        else if(OCR_ACTIVE.includes(job.state) && S.docs.some(d => d.id === id)) missing = true;
      }
      if(missing) renderCards(); else renderStatusBar();
    }
    showOcrWork();
    if(Object.values(ocr.jobs).some(j => OCR_ACTIVE.includes(j.state))){
      ocr.timer = setTimeout(() => { ocr.timer = null; pollProjectOcr(); }, 3000);
    }
  }
  window.BiblioRefPollOcr = () => pollProjectOcr(true);

  // The shared progress panel follows the whole batch, whatever screen launched it.
  function showOcrWork(){
    const ocr = org.ocr;
    const active = Object.keys(ocr.jobs).filter(id => OCR_ACTIVE.includes(ocr.jobs[id].state));
    if(active.length && !ocr.work){
      ocr.batch = new Set();
      ocr.work = startWork('OCR en curso', '', {announceDone: true});
    }
    if(!ocr.work) return;
    active.forEach(id => ocr.batch.add(id));
    const batch = [...ocr.batch].map(id => [id, ocr.jobs[id]]).filter(([, j]) => j);
    const name = id => S.docs.find(d => d.id === id)?.thesis_id || 'tesis';
    const done = batch.filter(([, j]) => !OCR_ACTIVE.includes(j.state));
    const failed = done.filter(([, j]) => j.state === 'error').length;
    if(!active.length){
      finishWork(ocr.work, failed ? 'OCR terminado con errores' : 'OCR terminado',
        `${fmt(done.length - failed)} de ${fmt(batch.length)} tesis reconocidas.${failed ? ` ${fmt(failed)} con error.` : ''}`, failed === batch.length && failed > 0);
      ocr.work = null;
      return;
    }
    const pages = batch.reduce((n, [, j]) => n + (j.total || 0), 0);
    const read = batch.reduce((n, [, j]) => n + (OCR_ACTIVE.includes(j.state) ? (j.done || 0) : (j.total || 0)), 0);
    const [curId, cur] = batch.find(([, j]) => j.state === 'running' || j.state === 'extracting') || [];
    const now = !cur ? 'En cola' : cur.state === 'extracting'
      ? `${name(curId)}: extrayendo la bibliografía`
      : `${name(curId)}: página ${fmt(cur.done)} de ${fmt(cur.total)}`;
    updateWork(ocr.work, {
      title: 'OCR en curso',
      detail: `${now} · ${fmt(done.length)} de ${fmt(batch.length)} tesis terminadas · ${minutesLabel(Math.max(0, pages - read))} restantes`,
      percent: pages ? Math.min(99, 100 * read / pages) : null,
    });
  }

  // ---- Repeated copies ----------------------------------------------------------------
  function openDedupeDialog(){
    const groups = org.duplicates?.groups || [];
    if(!groups.length) return notify('No hay tesis repetidas en el proyecto.');
    const where = f => f && f.length ? f.join(' › ') : 'raíz del proyecto';
    const refs = x => x.n_references ? ` · ${fmt(x.n_references)} refs` : '';
    const rows = groups.map((g, i) => `<tr>
      <td><input type="checkbox" class="org-dedupe" value="${esc(g.sha256)}" data-n="${g.remove.length}" checked aria-label="Quitar las copias de ${esc(g.keep.thesis_id || '')}"></td>
      <td><b>${esc(g.keep.thesis_id || '')}</b> · ${esc(g.keep.title || '')}<div class="org-src">${esc(where(g.target_folder))}${refs(g.keep)}${g.moves_folder ? ' · pasa a esta carpeta' : ''}</div></td>
      <td class="org-rm">${g.remove.map(r => `${esc(r.thesis_id || '')}${refs(r)}<div class="org-src">${esc(r.source || '')}</div>`).join('')}</td>
      <td class="org-src">${esc(g.reason)}</td></tr>`).join('');
    modal('Quitar copias repetidas',
      `<p>${fmt(groups.length)} ${groups.length === 1 ? 'grupo' : 'grupos'} del mismo archivo PDF. Se quitan las copias de la columna «Se quita» con sus PDF guardados en BiblioRef, sus referencias y correcciones: <b>no se puede deshacer</b>. Las que se conservan no cambian.</p>
       <div class="org-dedupe-table"><table><thead><tr><th><input type="checkbox" id="orgDedupeAll" checked aria-label="Todos los grupos"></th><th>Se conserva</th><th>Se quita</th><th>Por qué</th></tr></thead><tbody>${rows}</tbody></table></div>`,
      `<span class="mini" id="orgDedupeCount" style="margin-right:auto"></span><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn warn" id="orgDedupeOk">Quitar copias</button>`);
    document.querySelector('#modalHost .modal')?.classList.add('org-wide');
    const boxes = [...document.querySelectorAll('.org-dedupe')];
    const update = () => {
      const chosen = boxes.filter(b => b.checked);
      const n = chosen.reduce((sum, b) => sum + Number(b.dataset.n), 0);
      $('#orgDedupeCount').textContent = `${fmt(chosen.length)} de ${fmt(boxes.length)} grupos elegidos`;
      $('#orgDedupeOk').textContent = `Quitar ${fmt(n)} ${n === 1 ? 'copia' : 'copias'}`;
      $('#orgDedupeOk').disabled = !n;
      $('#orgDedupeAll').checked = chosen.length === boxes.length;
      $('#orgDedupeAll').indeterminate = chosen.length > 0 && chosen.length < boxes.length;
    };
    boxes.forEach(b => b.addEventListener('change', update));
    $('#orgDedupeAll').addEventListener('change', e => { boxes.forEach(b => { b.checked = e.target.checked; }); update(); });
    $('#orgDedupeOk').onclick = async () => {
      const sha256 = boxes.filter(b => b.checked).map(b => b.value);
      if(!sha256.length) return;
      const button = $('#orgDedupeOk');
      button.disabled = true;
      button.textContent = 'Quitando…';
      try{
        const res = await api(`/api/projects/${encodeURIComponent(projectId())}/duplicates/resolve`, jsonBody({sha256}));
        closeModal();
        org.selected.clear();
        org.view = null;
        await loadDocs();
        await loadProjects();
        await loadDuplicates();
        toast(`${fmt(res.removed.length)} ${res.removed.length === 1 ? 'copia repetida quitada' : 'copias repetidas quitadas'}`);
      }catch(err){
        button.disabled = false;
        update();
        modalWarn('No se pudieron quitar las copias: ' + err.message);
      }
    };
    update();
  }

  // ---- Saved selections -------------------------------------------------------------
  function saveSearch(){
    const query = $('#collectionSearch').value.trim();
    const base = org.view?.kind === 'reason' ? org.view.id : '';
    if(!query && !base) return notify('Escribí una búsqueda o elegí una selección antes de guardarla.');
    const suggestion = [base ? reason(base).label : '', query ? `«${query}»` : ''].filter(Boolean).join(' · ');
    modal('Guardar selección', `<form class="project-form" id="orgSaveForm"><label>Nombre<input id="orgSaveName" maxlength="80" value="${esc(suggestion)}"></label></form><p class="mini">Guarda el criterio, no la lista: al abrirla vuelve a buscar con los datos actuales.</p>`,
      `<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="orgSaveOk">Guardar</button>`);
    const submit = async () => {
      const name = $('#orgSaveName').value.trim();
      if(!name) return $('#orgSaveName').focus();
      try{
        const entry = await api(`/api/projects/${encodeURIComponent(projectId())}/selections`, jsonBody({name, query, base}));
        S.project.saved_selections = [...(S.project.saved_selections || []), entry];
        closeModal();
        renderSelections();
      }catch(err){ modalWarn('No se pudo guardar la selección: ' + err.message); }
    };
    $('#orgSaveOk').onclick = submit;
    $('#orgSaveForm').onsubmit = e => { e.preventDefault(); submit(); };
  }

  function applySaved(id){
    const saved = (S.project?.saved_selections || []).find(s => s.id === id);
    if(!saved) return;
    if(org.view?.kind === 'saved' && org.view.id === id){
      $('#collectionSearch').value = '';
      return setView(null);
    }
    $('#collectionSearch').value = saved.query || '';
    org.view = saved.base ? {kind: 'reason', id: saved.base} : null;
    const marked = visibleDocs().map(d => d.id);
    const baseMark = saved.base ? reasonSets(saved.base).mark : null;
    org.selected = new Set(baseMark ? marked.filter(x => baseMark.has(x)) : marked);
    org.view = {kind: 'saved', id, label: saved.name, baseId: saved.base};
    rerender();
  }

  async function deleteSaved(id){
    const saved = (S.project?.saved_selections || []).find(s => s.id === id);
    if(!saved || !await confirmModal(`¿Borrar la selección guardada «${saved.name}»? Las tesis no cambian.`)) return;
    try{
      await api(`/api/projects/${encodeURIComponent(projectId())}/selections/${encodeURIComponent(id)}`, {method: 'DELETE'});
      S.project.saved_selections = S.project.saved_selections.filter(s => s.id !== id);
      if(org.view?.kind === 'saved' && org.view.id === id) setView(null); else renderSelections();
    }catch(err){ notify('No se pudo borrar la selección: ' + err.message); }
  }

  // A saved selection keeps its base reason as the visible filter.
  const baseViewIds = viewIds;
  window.matchesCollectionSearch = function matchesWithSavedView(doc){
    if(!originalMatches(doc)) return false;
    if(org.view?.kind === 'saved'){
      return !org.view.baseId || reasonSets(org.view.baseId).show.has(doc.id);
    }
    const ids = baseViewIds();
    return !ids || ids.has(doc.id);
  };

  // ---- «Agregar tesis» as a menu in the heading; files can be dropped on the whole workspace ----
  (function compactImport(){
    const toolbar = document.querySelector('#screen-collection .import-toolbar');
    const save = document.querySelector('#screen-collection .collection-save');
    const buttons = ['#chooseFiles', '#chooseFolder', '#chooseDrive'].map(s => $(s)).filter(Boolean);
    if(!toolbar || !save || !buttons.length) return;
    const menu = document.createElement('details');
    menu.className = 'org-add';
    menu.innerHTML = '<summary class="btn primary">+ Agregar tesis ▾</summary><div class="org-add-menu" role="menu"></div>';
    const list = menu.querySelector('.org-add-menu');
    buttons.forEach(b => { b.classList.remove('text-btn'); b.setAttribute('role', 'menuitem'); list.appendChild(b); });
    list.insertAdjacentHTML('beforeend', '<p>También podés arrastrar PDF, ZIP o carpetas sobre la lista.</p>');
    save.prepend(menu);
    list.addEventListener('click', e => { if(e.target.closest('button')) menu.open = false; });
    document.addEventListener('click', e => { if(menu.open && !menu.contains(e.target)) menu.open = false; });
    toolbar.classList.add('org-compact');

    const grid = $('#collectionWorkspace');
    const external = e => [...(e.dataTransfer?.types || [])].includes('Files');
    grid?.addEventListener('dragover', e => {
      if(!external(e) || S.importBusy) return;
      e.preventDefault();
      grid.classList.add('org-dropping');
    });
    grid?.addEventListener('dragleave', e => { if(!grid.contains(e.relatedTarget)) grid.classList.remove('org-dropping'); });
    grid?.addEventListener('drop', e => {
      grid.classList.remove('org-dropping');
      if(!external(e) || S.importBusy) return;
      e.preventDefault();
      importDroppedFiles(e.dataTransfer);
    });
  })();

  // A different project starts with nothing selected.
  const originalOpenProject = window.openProject;
  window.openProject = async function openProjectClearingSelection(id){
    org.selected.clear();
    org.view = null;
    org.renaming = null;
    org.duplicates = null;
    const result = await originalOpenProject(id);
    loadDuplicates();
    pollProjectOcr(true);
    return result;
  };
})();
