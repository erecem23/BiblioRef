(() => {
  const originalRenderDashboard = window.renderDashboard;
  const state = {
    projectId: undefined,
    view: 'tesis',
    search: '',
    rowsByDoc: new Map(),
    expanded: new Set(),
    loading: new Map(),
    requestSeq: 0,
    docKeys: new Map(),
    ocrOnly: false,
    infField: '',
    sortProblems: false,
    filters: new Set(),
    filterMode: 'any',
    filterOpen: false,
    ocr: {projectId: null, available: null, reason: '', jobs: {}, timer: null, finished: -1},
    focus: null,
    focusMode: 'all',
  };

  // Thesis-level columns, read straight from each document's metadata.
  const THESIS_FIELDS = [
    {key:'author', label:'Autor/a', cls:'rs-w-person'},
    {key:'year', label:'Año', cls:'rs-w-year'},
    {key:'degree_level', label:'Nivel', cls:'rs-w-level'},
    {key:'program', label:'Programa', cls:'rs-w-program'},
    {key:'faculty', label:'Facultad', cls:'rs-w-faculty'},
    {key:'university', label:'Universidad', cls:'rs-w-university'},
    {key:'director', label:'Director/a', cls:'rs-w-person'},
    {key:'codirector', label:'Codirector/a', cls:'rs-w-person', optional:true},
  ];
  const TYPE_LABELS = {
    articulo_revista:'Artículo', libro:'Libro', capitulo_libro:'Capítulo', material_web:'Web',
    conference_paper:'Ponencia', informe_documento:'Informe', tesis:'Tesis', material_inedito:'Inédito', documento_legal:'Legal', documento_guia_manual:'Guía o manual',
  };
  const LEVEL_LABELS = {doctorado:'Doctorado', maestria:'Maestría', especializacion:'Especialización', grado:'Grado', licenciatura:'Licenciatura'};
  const UNCLASSIFIED = new Set(['', 'sin_clasificar']);
  const REF_COLS = 9;
  const DASH = '<span class="rs-dash">—</span>';
  const CARET = '<svg class="rs-caret" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>';

  const stylesheet = `
    #screen-project .content{max-width:none;padding:18px 20px 28px}
    #screen-project .h1{font-size:21px;margin-bottom:4px}
    #screen-project .lead{max-width:none;margin-bottom:12px}
    #screen-project #projectStats,#screen-project .projectbar{display:none}
    #dashboardTable.rs-host{overflow:visible;border:0;background:transparent;box-shadow:none;display:flex;flex-direction:column;gap:10px}
    .rs-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .rs-seg{display:inline-flex;gap:2px;padding:3px;border-radius:9px;background:#e6e8ee}
    .rs-seg button{display:flex;align-items:baseline;gap:8px;border:0;border-radius:7px;background:transparent;padding:7px 14px;font-family:inherit;font-size:13px;font-weight:600;color:var(--muted);cursor:pointer}
    .rs-seg button span{font-size:12px;font-weight:500;font-variant-numeric:tabular-nums}
    .rs-seg button[aria-selected="true"]{background:#fff;color:var(--ink);box-shadow:var(--shadow)}
    .rs-search{height:34px;width:min(360px,100%);border:1px solid var(--line);border-radius:8px;background:#fff;padding:0 10px;font-family:inherit;font-size:13px;color:var(--ink)}
    .rs-summary{margin-left:auto;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
    .rs-note{font-size:12px;color:var(--muted)}
    .rs-scroll{overflow:auto;max-height:calc(100vh - 250px);border:1px solid var(--line);border-radius:var(--radius);background:#fff;box-shadow:var(--shadow)}
    .rs-empty{padding:24px;text-align:center;color:var(--muted)}
    .rs-table{width:100%;border-collapse:separate;border-spacing:0;font-size:12px;line-height:1.4}
    .rs-table th{position:sticky;top:0;z-index:2;background:#f6f7f9;padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:bottom;white-space:nowrap;font-size:10.5px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#4b5563}
    .rs-cov{display:block;margin-top:2px;font-size:10.5px;font-weight:500;letter-spacing:0;text-transform:none;color:var(--muted);font-variant-numeric:tabular-nums}
    .rs-table td{padding:8px 10px;border-bottom:1px solid #edeef2;vertical-align:top;background:#fff;color:var(--ink)}
    .rs-table tbody tr:hover td{background:#f8fbff}
    .rs-num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
    .rs-code{font-weight:600;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
    .rs-clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
    .rs-miss{display:inline-block;padding:1px 7px;border-radius:999px;background:var(--warnbg);color:var(--warn);font-size:10.5px;font-weight:600;line-height:1.5;white-space:nowrap}
    .rs-dash{color:#a0a6b0}
    .rs-mono{font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-size:11px;color:#374151}

    /* Tesis: code and title stay visible while metadata columns scroll. */
    .rs-thesis{min-width:1560px}
    .rs-thesis .rs-st1{position:sticky;left:0;z-index:1;width:74px;min-width:74px}
    .rs-thesis .rs-st2{position:sticky;left:74px;z-index:1;width:300px;min-width:300px;box-shadow:inset -2px 0 0 #d6dae2}
    .rs-thesis th.rs-st1,.rs-thesis th.rs-st2{z-index:3}
    .rs-thesis td.rs-st2{font-weight:600}
    .rs-w-person{min-width:170px}.rs-w-year{min-width:56px}.rs-w-level{min-width:96px}.rs-w-program{min-width:190px}.rs-w-faculty{min-width:180px}.rs-w-university{min-width:210px}

    /* Referencias: one collapsible block per thesis. */
    .rs-refs{min-width:1480px}
    .rs-w-n{width:46px}.rs-w-author{min-width:160px}.rs-w-type{min-width:96px}.rs-w-title{min-width:320px}.rs-w-venue{min-width:210px}.rs-w-doi{min-width:190px}.rs-w-page{width:58px}.rs-w-raw{min-width:380px}
    .rs-table tr.rs-group td{padding:0;background:#f6f7f9;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
    .rs-table tbody tr.rs-group:hover td{background:#eff1f5}
    .rs-group-row{position:sticky;left:0;box-sizing:border-box;display:flex;align-items:center;gap:10px;width:var(--rs-vw,100%);min-width:0;padding-right:12px}
    .rs-group-head{flex:1;display:flex;align-items:center;gap:10px;min-width:0;padding:9px 0 9px 12px;border:0;background:transparent;font-family:inherit;font-size:12.5px;color:var(--ink);text-align:left;cursor:pointer}
    .rs-w-problems{min-width:250px}
    .rs-table tr.rs-group td.rs-gcell{padding:9px 10px;vertical-align:middle;white-space:nowrap}
    .rs-table tr.rs-group td.rs-gcell .rs-group-head{padding:0;gap:6px}
    .rs-gtail{display:flex;align-items:center;gap:10px;min-width:0}
    .rs-gtail .rs-gtitle{flex:1 1 auto}
    .rs-focus{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap;padding:12px 14px;border:1px solid var(--line);border-radius:var(--radius);background:#fff}
    .rs-focus-main{flex:1 1 420px;min-width:0}
    .rs-crumb{font-size:12.5px;color:var(--muted)}
    .rs-crumb button{border:0;background:none;padding:0;font:inherit;color:var(--accent);cursor:pointer}
    .rs-focus h2{margin:3px 0 2px;font-size:18px;line-height:1.35}
    .rs-focus-meta{font-size:13px;color:#374151}
    .rs-focus-acts{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
    .rs-fix{border:0;background:none;padding:0;font:inherit;cursor:pointer;text-decoration:underline dotted;text-underline-offset:3px}
    .rs-fix:hover .rs-miss{text-decoration:underline}
    .rs-extract{border:1px solid #c9ced8;background:#fff;border-radius:999px;padding:3px 10px;font:600 12.5px/1.5 inherit;font-family:inherit;color:#374151;cursor:pointer}
    .rs-filterwrap{position:relative;display:inline-flex}
    .rs-filterbtn[aria-pressed="true"]{border-color:#a9c3f7;background:var(--accent-bg);color:var(--accent-dark,#1f56c4)}
    .rs-fchip{display:inline-flex;align-items:center;gap:6px;padding:2px 4px 2px 10px;border-radius:999px;background:var(--sidebar,#101a30);color:#fff;font-size:12px;font-weight:600;white-space:nowrap}
    .rs-fchip button{border:0;background:rgba(255,255,255,.18);color:#fff;border-radius:999px;width:18px;height:18px;font:inherit;line-height:1;cursor:pointer}
    .rs-fpanel{position:absolute;top:calc(100% + 6px);left:0;z-index:30;width:min(660px,calc(100vw - 40px));background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow-md);font-size:13px;color:var(--ink);text-transform:none;letter-spacing:0;font-weight:400}
    .rs-fgroups{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}
    .rs-fg{padding:10px 12px;display:grid;gap:2px;align-content:start}
    .rs-fg+.rs-fg{border-left:1px solid var(--line)}
    .rs-fg h4{margin:0 0 4px;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
    .rs-fg label{display:flex;align-items:center;gap:7px;padding:3px 0;cursor:pointer;white-space:nowrap}
    .rs-fg label small{margin-left:auto;padding-left:8px;color:var(--muted);font-variant-numeric:tabular-nums}
    .rs-fpanel input{accent-color:var(--accent);margin:0}
    .rs-fdot{width:8px;height:8px;border-radius:50%;flex:none;background:var(--warn)}
    .rs-fdot-review{background:#fff;border:1.5px solid #8b93a1}
    .rs-fdot-state{background:#c7ccd6}
    .rs-ffoot{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 12px;border-top:1px solid var(--line);font-size:12.5px}
    .rs-ffoot label{display:inline-flex;align-items:center;gap:4px;margin-left:8px;cursor:pointer}
    .rs-flink{border:0;background:none;padding:0;color:var(--accent);font:inherit;font-weight:600;cursor:pointer}
    .rs-covmiss{display:inline-block;margin-top:3px;border:0;border-radius:999px;padding:0 7px;background:var(--warnbg);color:var(--warn);font-family:inherit;font-size:10.5px;font-weight:600;letter-spacing:0;text-transform:none;cursor:pointer}
    .rs-covmiss[aria-pressed="true"]{background:var(--warn);color:#fff}
    @media(max-width:760px){.rs-fgroups{grid-template-columns:1fr}.rs-fg+.rs-fg{border-left:0;border-top:1px solid var(--line)}}
    .rs-sortbtn{border:0;background:none;padding:0;font:inherit;letter-spacing:inherit;text-transform:inherit;color:inherit;cursor:pointer}
    .rs-sortbtn[aria-pressed="true"]{color:var(--accent)}
    .rs-thesis{min-width:1810px!important}
    .rs-chipbtn{border:0;font-family:inherit;cursor:pointer}
    .rs-chipbtn:hover{text-decoration:underline}
    .rs-chipbtn:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
    .rs-reffilter{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:10px;padding:7px 10px;border:1px solid var(--line);border-radius:var(--radius-sm);background:#f6f7f9;font-size:12px;color:#374151}
    .rs-reffilter b{color:var(--ink)}
    .rs-reffilter button{margin-left:auto}
    .rs-group-head:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
    .rs-caret{flex:none;width:14px;height:14px;color:var(--muted);transition:transform .15s}
    .rs-group-head[aria-expanded="false"] .rs-caret{transform:rotate(-90deg)}
    .rs-who{font-size:13px;font-weight:700;white-space:nowrap}
    .rs-gtitle{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#374151}
    .rs-chips{display:flex;gap:5px;flex:none}
    .rs-count{flex:none;font-size:12px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
    .rs-table tr.rs-note-row td{padding:0}
    .rs-table tbody tr.rs-note-row:hover td{background:#fff}
    .rs-sticky{position:sticky;left:0;box-sizing:border-box;width:var(--rs-vw,100%);display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:6px 12px 10px 58px;font-size:12px;color:var(--muted)}
    /* OCR: the reason is grey; missing data keeps the amber "falta". */
    .rs-ocrbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px 16px;padding:10px 12px;border:1px solid var(--line);border-radius:var(--radius);background:#fafbfc}
    .rs-ocrbar b{font-size:13px}
    .rs-ocrfacts{display:flex;flex-wrap:wrap;gap:4px 14px;flex:1 1 360px;font-size:12.5px;color:#374151}
    .rs-ocrfacts strong{font-variant-numeric:tabular-nums}
    .rs-ocrerr{flex-basis:100%;font-size:12px;color:var(--muted)}
    .rs-ocrtag{display:inline-block;margin-top:5px;padding:1px 7px;border:1px solid var(--line);border-radius:999px;background:#eef0f3;color:#374151;font-size:10.5px;font-weight:600;line-height:1.5;white-space:nowrap}
    .rs-miss small{font-size:inherit;font-weight:500;opacity:.85}
    /* Inference: grey dashed tag, never a third color. */
    .rs-inf{display:inline-block;margin-top:3px;padding:0 6px;border:1px dashed #b8bec9;border-radius:999px;background:transparent;color:#4b5563;font:650 10px/1.5 inherit;font-family:inherit;letter-spacing:.02em;white-space:nowrap;cursor:pointer}
    .rs-inf:hover,.rs-inf[aria-expanded="true"]{border-color:#6b7280;color:var(--ink)}
    .rs-inf:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
    .rs-infpop{position:fixed;z-index:60;width:min(340px,calc(100vw - 24px));padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;box-shadow:var(--shadow-md);font-size:12px;display:grid;gap:6px}
    .rs-infpop b{font-size:12.5px}
    .rs-infpop .rs-infev{color:#374151}
    .rs-infpop .rs-infrow{display:flex;gap:6px;flex-wrap:wrap;margin-top:2px}
    .rs-infcallout{border:1px solid var(--line);background:#fafbfc;border-radius:8px;padding:10px 12px;font-size:13px;color:#374151}
    .rs-infrule{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:start;padding:10px 12px;border:1px solid var(--line);border-radius:8px;margin-top:8px;cursor:pointer}
    .rs-infrule input{margin-top:3px}
    .rs-infrule .rs-infn{font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
    .rs-infrule .rs-infd{font-size:12px;color:var(--muted)}
    .rs-infrule .rs-infex{font-size:12px;color:#374151;margin-top:3px}
    .rs-infrule.rs-off{cursor:default;opacity:.7}
    .rs-chipf{font-family:inherit;font-size:12px;font-weight:600;border:1px solid var(--line);background:#fff;border-radius:999px;padding:4px 11px;color:#374151;cursor:pointer}
    .rs-chipf[aria-pressed="true"]{background:var(--sidebar,#101a30);border-color:var(--sidebar,#101a30);color:#fff}
    .rs-audit{min-width:980px}
    @media(max-width:900px){#screen-project .content{padding:14px}.rs-summary{width:100%;margin-left:0}.rs-scroll{max-height:none}.rs-chips{display:none}}
    @media(prefers-reduced-motion:reduce){.rs-caret{transition:none}}
  `;
  const style = document.createElement('style');
  style.id = 'reference-sheet-style';
  style.textContent = stylesheet;
  document.head.appendChild(style);

  const asText = value => {
    if (value == null || value === '') return '';
    if (Array.isArray(value)) return value.map(asText).filter(Boolean).join('; ');
    if (typeof value === 'object') {
      if (value.name) return asText(value.name);
      return Object.values(value).map(asText).filter(Boolean).join('; ');
    }
    return String(value);
  };
  const miss = label => `<span class="rs-miss">${esc(label)}</span>`;
  const val = value => value ? esc(value) : miss('falta');
  const missOcr = label => `<span class="rs-miss" title="El dato está en páginas escaneadas: el OCR puede completarlo">${esc(label)} <small>· OCR</small></span>`;
  const pageList = pages => pages.length === 1 ? `p. ${pages[0]}` : `págs. ${pages.slice(0, 3).join(', ')}${pages.length > 3 ? '…' : ''}`;

  // What OCR would unlock, as computed by the server (ocr_need); loose scanned figures are not listed.
  function ocrTag(d){
    const job = state.ocr.jobs[d.id];
    if(job?.state === 'queued') return 'OCR en cola';
    if(job?.state === 'running') return `OCR ${fmt(job.done)} de ${fmt(job.total)} págs.`;
    if(job?.state === 'extracting') return 'OCR hecho · extrayendo bibliografía';
    if(job?.state === 'error') return 'OCR con error';
    const need = d.ocr_need;
    if(need){
      if(need.kind === 'document') return need.unreadable ? 'OCR · texto ilegible' : 'OCR · tesis completa';
      if(need.kind === 'cover') return 'OCR · portada';
      if(need.kind === 'bibliography') return `OCR · bibliografía ${pageList(need.bibliography_pages)}`;
      return `OCR · portada y bibliografía ${pageList(need.bibliography_pages)}`;
    }
    if(d.ocr?.reprocess_suggested) return 'OCR hecho · falta reprocesar';
    return '';
  }
  const FIELD_LABELS = {author:'Autor/a', year:'Año', degree_level:'Nivel', program:'Programa', faculty:'Facultad', university:'Universidad', director:'Director/a', codirector:'Codirector/a'};
  const inferenceOf = (d, key) => (d.metadata_inference || {})[key] || null;
  const infTag = (d, key) => {
    const inf = inferenceOf(d, key);
    return `<button type="button" class="rs-inf" data-inf="${esc(d.id)}" data-field="${esc(key)}" aria-expanded="false" title="${esc(inf.rule_title + ': ' + inf.evidence)}">inferido</button>`;
  };
  // ---- Filters by reason («Filtrar ▾» and the «N faltan» shortcut under each column) ----
  const FILTER_GROUPS = [
    {title: 'Faltan datos de la tesis', items: THESIS_FIELDS.filter(f => !f.optional).map(f => ({
      key: `meta:${f.key}`, label: f.label, chip: `Falta ${f.label.toLowerCase()}`, tone: 'miss',
      test: d => !asText((d.metadata || {})[f.key]).trim(),
    }))},
    {title: 'Problemas en las referencias', items: [
      ['missing', 'Posibles faltantes', 'miss'], ['merged', 'Posibles fusionadas', 'review'],
      ['type', 'Sin clasificar', 'miss'], ['author', 'Sin autor', 'miss'], ['year', 'Sin año', 'miss'],
    ].map(([k, label, tone]) => ({key: `prob:${k}`, label, chip: label, tone, test: d => (d.problems || {})[k] > 0}))},
    {title: 'Estado', items: [
      {key: 'state:review', label: 'Por revisar', test: d => statusText(d) === 'revisar'},
      {key: 'state:ready', label: 'Listas', test: d => statusText(d) === 'lista'},
      {key: 'state:norefs', label: 'Sin referencias', test: d => isProcessed(d) && !d.n_references},
      {key: 'state:ocr', label: 'Necesitan OCR', test: d => !!d.ocr_need},
      {key: 'state:inferred', label: 'Con datos inferidos', test: d => Object.keys(d.metadata_inference || {}).length > 0},
    ].map(x => ({...x, chip: x.label, tone: 'state'}))},
  ];
  const FILTERS = new Map(FILTER_GROUPS.flatMap(g => g.items).map(x => [x.key, x]));
  function passesFilters(d){
    const active = [...state.filters].map(k => FILTERS.get(k)).filter(Boolean);
    if(!active.length) return true;
    return state.filterMode === 'all' ? active.every(f => f.test(d)) : active.some(f => f.test(d));
  }
  function filterButton(){
    const n = state.filters.size;
    const chips = [...state.filters].map(k => FILTERS.get(k)).filter(Boolean).map(f =>
      `<span class="rs-fchip">${esc(f.chip)}<button type="button" data-filter-remove="${esc(f.key)}" aria-label="Quitar el filtro ${esc(f.chip)}">×</button></span>`).join('');
    return `<span class="rs-filterwrap"><button type="button" class="btn xs rs-filterbtn" data-filter-toggle aria-expanded="${state.filterOpen}" aria-pressed="${n > 0}">Filtrar${n ? ` · ${n}` : ''} ▾</button>${state.filterOpen ? filterPanel() : ''}</span>${chips}`;
  }
  function filterPanel(){
    const docs = sortedDocs();
    const groups = FILTER_GROUPS.map(g => `<div class="rs-fg"><h4>${esc(g.title)}</h4>${g.items.map(f => {
      const count = docs.filter(f.test).length;
      return `<label><input type="checkbox" data-filter-key="${esc(f.key)}" ${state.filters.has(f.key) ? 'checked' : ''}><span class="rs-fdot rs-fdot-${f.tone}"></span>${esc(f.label)}<small>${fmt(count)}</small></label>`;
    }).join('')}</div>`).join('');
    return `<div class="rs-fpanel" role="dialog" aria-label="Filtrar tesis por motivo"><div class="rs-fgroups">${groups}</div>
      <div class="rs-ffoot"><span>Que tengan <label><input type="radio" name="rsFilterMode" value="any" ${state.filterMode === 'any' ? 'checked' : ''}> alguno</label> <label><input type="radio" name="rsFilterMode" value="all" ${state.filterMode === 'all' ? 'checked' : ''}> todos</label></span><button type="button" class="rs-flink" data-filter-clear>Limpiar filtros</button></div></div>`;
  }
  const ocrFillsCover = d => ['document', 'cover', 'cover_bibliography'].includes(d.ocr_need?.kind);
  const fmt = n => Number(n || 0).toLocaleString('es-AR');
  const norm = value => String(value || '').toLocaleLowerCase('es');
  const isProcessed = d => d.status !== 'uploaded' && d.status !== 'processing';
  const levelLabel = value => LEVEL_LABELS[norm(value)] || value;
  const typeLabel = value => TYPE_LABELS[value] || String(value).replace(/_/g, ' ');

  const thesisSortKey = d => {
    const n = Number(thesisNumber(d));
    return Number.isFinite(n) && n > 0 ? n : Number.MAX_SAFE_INTEGER;
  };
  const sortedDocs = () => [...S.docs].sort((a,b) => thesisSortKey(a)-thesisSortKey(b) || displayTitle(a).localeCompare(displayTitle(b), 'es'));
  // What invalidates one thesis' loaded references: only changes to that thesis.
  const docKey = d => `${d.updated_at||0}:${d.n_references||0}:${d.status||''}`;

  function thesisMeta(doc){
    const metadata = doc.metadata || {};
    const out = {};
    THESIS_FIELDS.forEach(f => { out[f.key] = asText(metadata[f.key]).trim(); });
    return out;
  }
  function thesisMatches(doc, q){
    return [doc.thesis_id, displayTitle(doc), doc.filename, ...Object.values(thesisMeta(doc))].some(v => norm(v).includes(q));
  }
  function refMatches(r, q){
    return [r.author, r.authors, r.year, r.publicationType, r.title, r.journal, r.publisher, r.doi, r.raw].some(v => norm(v).includes(q));
  }

  function resetIfNeeded(){
    const projectId = S.project?.id || null;
    if(state.projectId !== projectId){
      state.projectId = projectId;
      state.rowsByDoc.clear();
      state.loading.clear();
      state.docKeys = new Map();
      state.requestSeq += 1;
      state.view = 'tesis';
      state.search = '';
      state.ocrOnly = false;
      state.filters.clear();
      state.filterMode = 'any';
      state.filterOpen = false;
      state.expanded.clear();
      state.focus = null;
      state.focusMode = 'all';
      pollOcr(projectId);
    }
    // Background work (OCR, front-matter re-reading) refreshes the index every few seconds;
    // dropping every thesis' references then kept the open ones stuck in «Cargando referencias».
    const keys = new Map(S.docs.map(d => [d.id, docKey(d)]));
    for(const id of [...state.rowsByDoc.keys(), ...state.loading.keys()]){
      if(state.docKeys.get(id) !== keys.get(id)){
        state.rowsByDoc.delete(id);
        state.loading.delete(id);
      }
    }
    state.docKeys = keys;
    [...state.expanded].forEach(id => { if(!keys.has(id)) state.expanded.delete(id); });
  }

  function rowsFromDocument(doc){
    const decisions = doc.audit_decisions || {};
    const open = (kind, id) => !['ignore', 'resolved'].includes(decisions[`data_${kind}_${id}`]?.decision);
    return (doc.references || []).filter(r => !r.deleted).map((r, i) => {
      const p = r.effective_parsed || r.parsed || {};
      const start = r.start_page || '';
      const end = r.end_page || start;
      const missing = [
        UNCLASSIFIED.has(asText(p.publication_type)) && open('type', r.id) && 'type',
        !asText(p.author).trim() && open('author', r.id) && 'author',
        !asText(p.year).trim() && open('year', r.id) && 'year',
      ].filter(Boolean);
      return {
        id: r.id,
        missing,
        order: r.order || i + 1,
        author: asText(p.author),
        authors: asText(p.authors),
        year: asText(p.year),
        publicationType: asText(p.publication_type),
        title: asText(p.title),
        journal: asText(p.journal),
        publisher: asText(p.publisher || p.publisher_observed || p.source_publisher),
        doi: asText(p.doi),
        raw: r.text || r.reference_text || '',
        page: start ? (end && end !== start ? `${start}–${end}` : String(start)) : '',
      };
    });
  }

  async function loadDoc(docId, seq, key){
    if(state.rowsByDoc.has(docId)) return;
    const doc = await api('/api/documents/' + encodeURIComponent(docId));
    // Discard only if the project changed or this thesis changed while loading.
    if(seq !== state.requestSeq || state.docKeys.get(docId) !== key) return;
    state.rowsByDoc.set(docId, rowsFromDocument(doc));
    const index = S.docs.findIndex(d => d.id === docId);
    if(index >= 0){
      S.docs[index] = {
        ...S.docs[index],
        title: doc.title,
        title_source: doc.title_source,
        title_confirmed: doc.title_confirmed,
        metadata: doc.metadata,
        metadata_detection: doc.metadata_detection,
        cover_metadata_revision: doc.cover_metadata_revision,
        title_reading_revision: doc.title_reading_revision,
        frontmatter_refresh_pending: doc.frontmatter_refresh_pending,
      };
    }
  }

  // References are fetched per thesis, only when its block is expanded.
  async function ensureExpanded(){
    const seq = state.requestSeq;
    const pending = [...state.expanded].filter(id => !state.rowsByDoc.has(id) && !state.loading.has(id));
    for(const id of pending){
      const key = state.docKeys.get(id);
      state.loading.set(id, key);
      try{
        await loadDoc(id, seq, key);
      }catch(err){
        state.expanded.delete(id);
        notify('No se pudieron cargar las referencias de la tesis: ' + err.message);
      }finally{
        if(state.loading.get(id) === key) state.loading.delete(id);
      }
      if(seq !== state.requestSeq) return;
      draw();
    }
    // A thesis invalidated while this loop ran is loaded again.
    if([...state.expanded].some(id => !state.rowsByDoc.has(id) && !state.loading.has(id))) ensureExpanded();
  }

  function thesisView(docs, q){
    const metas = new Map(docs.map(d => [d.id, thesisMeta(d)]));
    const problemTotal = d => window.BiblioRefProblems ? BiblioRefProblems.total(d) : 0;
    const byText = (q ? docs.filter(d => thesisMatches(d, q)) : docs).slice();
    if(state.sortProblems) byText.sort((a, b) => problemTotal(b) - problemTotal(a));
    const list = (state.ocrOnly ? byText.filter(d => ocrTag(d)) : byText).filter(passesFilters);
    const coverage = key => docs.filter(d => metas.get(d.id)[key]).length;
    const inferredCount = key => docs.filter(d => inferenceOf(d, key)).length;
    const covText = key => `${fmt(coverage(key))} de ${fmt(docs.length)}${inferredCount(key) ? ` · ${fmt(inferredCount(key))} inferidos` : ''}`;
    const missingButton = key => {
      const n = docs.length - coverage(key);
      if(!n) return '';
      const on = state.filters.has(`meta:${key}`);
      return `<button type="button" class="rs-covmiss" data-filter-quick="meta:${key}" aria-pressed="${on}" title="${on ? 'Quitar este filtro' : 'Ver solo las tesis a las que les falta este dato'}">${fmt(n)} ${n === 1 ? 'falta' : 'faltan'}${on ? ' ✓' : ''}</button>`;
    };
    const head = THESIS_FIELDS.map(f => `<th class="${f.cls}${f.key==='year' ? ' rs-num' : ''}">${f.label}${f.optional ? '' : `<span class="rs-cov">${covText(f.key)}</span>${missingButton(f.key)}`}</th>`).join('');
    const rows = list.map(d => {
      const m = metas.get(d.id);
      const title = displayTitle(d);
      const cells = THESIS_FIELDS.map(f => {
        const value = f.key === 'degree_level' && m[f.key] ? levelLabel(m[f.key]) : m[f.key];
        const empty = f.optional ? DASH : (ocrFillsCover(d) ? missOcr('falta') : miss('falta'));
        const inferred = value && inferenceOf(d, f.key) ? `<br>${infTag(d, f.key)}` : '';
        return `<td class="${f.key==='year' ? 'rs-num' : ''}">${value ? esc(value) + inferred : empty}</td>`;
      }).join('');
      const done = isProcessed(d);
      const tag = ocrTag(d);
      const refs = !done ? DASH : (d.ocr_need?.kind === 'document' && !d.n_references ? missOcr('0') : fmt(d.n_references));
      return `<tr>
        <td class="rs-st1 rs-code">${esc(d.thesis_id || '')}${tag ? `<br><span class="rs-ocrtag">${esc(tag)}</span>` : ''}</td>
        <td class="rs-st2"><div class="rs-clamp" title="${esc(title)}">${val(title)}</div></td>
        <td class="rs-w-problems">${window.BiblioRefProblems ? (BiblioRefProblems.chips(d, {max: 3}) || DASH) : DASH}</td>
        ${cells}
        <td class="rs-num">${refs}</td>
        <td>${done ? `<button type="button" class="btn xs" data-show-refs="${esc(d.id)}">Ver referencias</button>` : '<span class="rs-dash">sin procesar</span>'}</td>
      </tr>`;
    }).join('');
    const empty = docs.length ? (state.filters.size ? 'Ninguna tesis cumple los filtros elegidos.' : 'Ninguna tesis coincide con la búsqueda.') : 'Todavía no hay tesis en el proyecto.';
    return {
      summary: q || state.ocrOnly || state.filters.size ? `Mostrando ${fmt(list.length)} de ${fmt(docs.length)} tesis` : `${fmt(docs.length)} tesis`,
      note: 'Una fila por tesis. Bajo cada columna, cuántas tesis del proyecto tienen ese dato; el codirector es opcional y no se marca como faltante.',
      table: `<table class="rs-table rs-thesis"><thead><tr>
        <th class="rs-st1">Código</th><th class="rs-st2">Título de la tesis</th><th class="rs-w-problems"><button type="button" class="rs-sortbtn" data-sort-problems aria-pressed="${!!state.sortProblems}" title="Ordenar por cantidad de problemas">Problemas ${state.sortProblems ? '↓' : '↕'}</button><span class="rs-cov">${fmt(docs.filter(d => problemTotal(d)).length)} tesis con algo para revisar</span></th>${head}<th class="rs-num">Refs.</th><th></th>
      </tr></thead><tbody>${rows || `<tr><td colspan="${THESIS_FIELDS.length + 5}">${empty}</td></tr>`}</tbody></table>`,
    };
  }

  // ---- Inference: explained before applying, marked in each cell, auditable ----
  async function refreshDocsFromIndex(){
    const projectId = S.project?.id;
    if(!projectId) return;
    const d = await api(`/api/projects/${encodeURIComponent(projectId)}/documents-index`);
    if(S.project?.id !== projectId) return;
    const fresh = new Map((d.documents || []).map(x => [x.id, x]));
    S.docs = S.docs.map(x => fresh.has(x.id) ? {...x, ...fresh.get(x.id)} : x);
    renderCards(); renderProjectHeader(); updateGlobal();
    draw();
  }

  function closeInferencePopover(){
    document.querySelector('.rs-infpop')?.remove();
    document.querySelectorAll('.rs-inf[aria-expanded="true"]').forEach(b => b.setAttribute('aria-expanded', 'false'));
  }

  function toggleInferencePopover(btn){
    const open = btn.getAttribute('aria-expanded') === 'true';
    closeInferencePopover();
    if(open) return;
    const d = S.docs.find(x => x.id === btn.dataset.inf);
    const inf = d && inferenceOf(d, btn.dataset.field);
    if(!inf) return;
    const pop = document.createElement('div');
    pop.className = 'rs-infpop';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'Dato inferido');
    pop.innerHTML = `<b>Inferido: ${esc(inf.rule_title)}</b>
      <span class="rs-infev">${esc(inf.evidence)}</span>
      <span class="rs-note">No figura en el PDF de esta tesis. Confirmar lo guarda como dato revisado a mano; deshacer vuelve a dejarlo como faltante.</span>
      <div class="rs-infrow"><button type="button" class="btn xs" data-inf-act="confirm" data-doc="${esc(d.id)}" data-field="${esc(btn.dataset.field)}">Confirmar</button><button type="button" class="btn xs" data-inf-act="undo" data-doc="${esc(d.id)}" data-field="${esc(btn.dataset.field)}">Deshacer</button></div>`;
    document.body.appendChild(pop);
    pop.addEventListener('click', e => {
      const act = e.target.closest('[data-inf-act]');
      if(act) inferenceAction(act.dataset.doc, act.dataset.field, act.dataset.infAct);
    });
    const r = btn.getBoundingClientRect();
    const w = pop.offsetWidth, h = pop.offsetHeight;
    pop.style.left = Math.max(12, Math.min(r.left, window.innerWidth - w - 12)) + 'px';
    pop.style.top = (r.bottom + 6 + h > window.innerHeight ? Math.max(12, r.top - h - 6) : r.bottom + 6) + 'px';
    btn.setAttribute('aria-expanded', 'true');
  }
  document.addEventListener('click', e => {
    if(!e.target.closest('.rs-infpop') && !e.target.closest('[data-inf]')) closeInferencePopover();
  });
  document.addEventListener('keydown', e => { if(e.key === 'Escape') closeInferencePopover(); });
  document.addEventListener('scroll', closeInferencePopover, true);

  async function inferenceAction(docId, field, action){
    // Saving the project can take a couple of seconds; show it on the pressed controls.
    document.querySelectorAll(`[data-inf-act][data-doc="${CSS.escape(docId)}"][data-field="${CSS.escape(field)}"]`).forEach(b => {
      b.disabled = true;
      if(b.dataset.infAct === action) b.textContent = 'Guardando…';
    });
    closeInferencePopover();
    try{
      const doc = await api(`/api/documents/${encodeURIComponent(docId)}/inference/${encodeURIComponent(field)}/${action === 'confirm' ? 'confirm' : 'undo'}`, {method:'POST'});
      // The route returns the updated summary: merge just this thesis instead of reloading the index.
      S.docs = S.docs.map(x => x.id === docId ? {...x, ...doc} : x);
      renderCards(); updateGlobal();
      draw();
    }catch(err){
      notify('No se pudo ' + (action === 'confirm' ? 'confirmar' : 'deshacer') + ' el dato inferido: ' + err.message);
    }
  }

  async function undoAllInferences(){
    const projectId = S.project?.id;
    if(!projectId) return;
    const label = state.infField ? FIELD_LABELS[state.infField].toLowerCase() : 'todos los campos';
    if(!window.confirm(`¿Deshacer los datos inferidos de ${label}? Vuelven a quedar como faltantes.`)) return;
    try{
      await api(`/api/projects/${encodeURIComponent(projectId)}/inference/undo-all`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(state.infField ? {field: state.infField} : {})});
      state.infField = '';
      await refreshDocsFromIndex();
    }catch(err){
      notify('No se pudieron deshacer las inferencias: ' + err.message);
    }
  }

  async function openInferenceModal(){
    const projectId = S.project?.id;
    if(!projectId) return;
    modal('Inferir datos faltantes', '<p><span class="loader"></span> Revisando qué se puede inferir…</p>', '<button class="btn" onclick="closeModal()">Cancelar</button>');
    let preview;
    try{
      preview = await api(`/api/projects/${encodeURIComponent(projectId)}/inference/preview`);
    }catch(err){
      modalWarn('No se pudo calcular la inferencia: ' + err.message);
      return;
    }
    const rules = preview.rules.map(r => {
      const ex = r.example ? `<div class="rs-infex">Ej.: ${esc(r.example.thesis_id || '')} → ${esc(r.example.value)} · ${esc(r.example.evidence)}</div>` : '';
      return `<label class="rs-infrule"><input type="checkbox" class="rs-infcheck" value="${esc(r.id)}" data-count="${r.count}" ${r.count ? 'checked' : 'disabled'}>
        <span><b>${esc(r.title)}</b><div class="rs-infd">${esc(r.description)}</div>${ex}</span>
        <span class="rs-infn">${fmt(r.count)} ${r.count === 1 ? 'dato' : 'datos'}</span></label>`;
    }).join('');
    const body = `<div class="rs-infcallout"><b>Inferir no es extraer.</b> El dato no está escrito en el PDF: se deduce de otros datos de la misma tesis o de otras tesis del proyecto. Por eso cada valor queda marcado <span class="rs-inf" style="cursor:default">inferido</span> con su regla y evidencia, se puede revisar en la pestaña «Inferidos» y se puede deshacer. Solo se completan celdas vacías: nunca se cambia un dato leído del PDF ni uno editado a mano.</div>
      ${rules}
      <div class="rs-infrule rs-off"><span></span><span><b>${esc(preview.not_inferred.title)}</b><div class="rs-infd">${esc(preview.not_inferred.description)}</div></span><span class="rs-infn">—</span></div>`;
    modal('Inferir datos faltantes', body,
      `<span class="rs-note" id="rsInfTotal" style="margin-right:auto"></span><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="rsInfApply" onclick="BiblioRefApplyInference()">Inferir</button>`);
    const update = () => {
      const n = [...document.querySelectorAll('.rs-infcheck:checked')].reduce((a, c) => a + Number(c.dataset.count), 0);
      const total = document.getElementById('rsInfTotal');
      const apply = document.getElementById('rsInfApply');
      if(total) total.textContent = n ? `${fmt(n)} datos · se pueden deshacer` : 'Nada para inferir';
      if(apply){ apply.textContent = `Inferir ${fmt(n)} datos`; apply.disabled = !n; }
    };
    document.querySelectorAll('.rs-infcheck').forEach(c => c.addEventListener('change', update));
    update();
  }

  window.BiblioRefApplyInference = async function(){
    const projectId = S.project?.id;
    const rules = [...document.querySelectorAll('.rs-infcheck:checked')].map(c => c.value);
    if(!projectId || !rules.length) return;
    try{
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/inference`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({rules})});
      closeModal();
      await refreshDocsFromIndex();
      if(!res.applied) notify('No quedaba ningún dato para inferir.');
    }catch(err){
      modalWarn('No se pudo aplicar la inferencia: ' + err.message);
    }
  };

  function inferenceAuditView(docs, q){
    const items = [];
    for(const d of docs){
      for(const [field, inf] of Object.entries(d.metadata_inference || {})){
        items.push({d, field, inf});
      }
    }
    const byField = f => items.filter(i => i.field === f).length;
    const fields = [...new Set(items.map(i => i.field))];
    const shown = items.filter(i => (!state.infField || i.field === state.infField)
      && (!q || [i.d.thesis_id, displayTitle(i.d), i.inf.value, i.inf.evidence, i.inf.rule_title].some(v => norm(v).includes(q))));
    const chips = `<div class="rs-toolbar" style="padding:10px 12px;border-bottom:1px solid var(--line);position:sticky;left:0">
      <button type="button" class="rs-chipf" data-inf-field="" aria-pressed="${!state.infField}">Todos ${fmt(items.length)}</button>
      ${fields.map(f => `<button type="button" class="rs-chipf" data-inf-field="${esc(f)}" aria-pressed="${state.infField === f}">${esc(FIELD_LABELS[f] || f)} ${fmt(byField(f))}</button>`).join('')}
      <span style="flex:1"></span>
      <button type="button" class="btn xs" data-inf-undo-all>${state.infField ? 'Deshacer los de ' + esc((FIELD_LABELS[state.infField] || '').toLowerCase()) : 'Deshacer todos'}</button>
    </div>`;
    const rows = shown.map(({d, field, inf}) => `<tr>
      <td class="rs-code">${esc(d.thesis_id || '')}</td>
      <td><div class="rs-clamp" title="${esc(displayTitle(d))}">${esc(displayTitle(d))}</div></td>
      <td>${esc(FIELD_LABELS[field] || field)}</td>
      <td>${esc(inf.value)}</td>
      <td>${esc(inf.rule_title)}</td>
      <td>${esc(inf.evidence)}</td>
      <td style="white-space:nowrap"><button type="button" class="btn xs" data-inf-act="confirm" data-doc="${esc(d.id)}" data-field="${esc(field)}">Confirmar</button> <button type="button" class="btn xs" data-inf-act="undo" data-doc="${esc(d.id)}" data-field="${esc(field)}">Deshacer</button></td>
    </tr>`).join('');
    return {
      summary: `${fmt(shown.length)} de ${fmt(items.length)} datos inferidos`,
      note: 'Confirmar guarda el valor como revisado a mano y quita la etiqueta; deshacer lo vuelve a dejar como faltante. Las exportaciones indican el origen de cada dato (PDF, inferido o manual).',
      table: `${chips}<table class="rs-table rs-audit"><thead><tr>
        <th>Código</th><th style="min-width:240px">Tesis</th><th>Campo</th><th style="min-width:180px">Valor inferido</th><th style="min-width:170px">Regla</th><th style="min-width:280px">Evidencia</th><th></th>
      </tr></thead><tbody>${rows || '<tr><td colspan="7">Ningún dato inferido coincide.</td></tr>'}</tbody></table>`,
    };
  }

  function ocrBanner(docs){
    const needs = docs.filter(d => d.ocr_need);
    const count = kinds => needs.filter(d => kinds.includes(d.ocr_need.kind)).length;
    const jobs = Object.values(state.ocr.jobs);
    const active = jobs.filter(j => ['queued', 'running', 'extracting'].includes(j.state)).length;
    const reprocess = docs.filter(d => !d.ocr_need && d.ocr?.reprocess_suggested).length;
    if(!needs.length && !active && !reprocess) return '';
    const whole = count(['document']);
    const covers = count(['cover', 'cover_bibliography']);
    const bibs = count(['bibliography', 'cover_bibliography']);
    const facts = [
      whole && `<span><strong>${fmt(whole)}</strong> tesis escaneadas completas (sin referencias hasta el OCR)</span>`,
      covers && `<span><strong>${fmt(covers)}</strong> portadas escaneadas con datos faltantes</span>`,
      bibs && `<span><strong>${fmt(bibs)}</strong> bibliografías con páginas escaneadas</span>`,
      active && `<span><strong>${fmt(active)}</strong> tesis en curso</span>`,
      reprocess && `<span><strong>${fmt(reprocess)}</strong> con OCR hecho que falta reprocesar</span>`,
    ].filter(Boolean).join('');
    const unavailable = state.ocr.available === false;
    const failed = jobs.filter(j => j.state === 'error');
    return `<div class="rs-ocrbar" role="status">
      <b>${active ? 'OCR en curso' : 'OCR pendiente'}</b>
      <div class="rs-ocrfacts">${facts}</div>
      <button type="button" class="btn xs" data-ocr-filter aria-pressed="${state.ocrOnly}">${state.ocrOnly ? 'Ver todas' : 'Ver cuáles'}</button>
      ${needs.length ? `<button type="button" class="btn xs primary" data-ocr-run ${unavailable || active ? 'disabled' : ''}>Aplicar OCR…</button>` : ''}
      ${unavailable ? `<span class="rs-ocrerr">${esc(state.ocr.reason || 'El OCR no está disponible en este equipo.')}</span>` : ''}
      ${failed.length ? `<span class="rs-ocrerr">${fmt(failed.length)} con error: ${esc(failed[0].error || '')}</span>` : ''}
    </div>`;
  }

  function confirmProjectOcr(){
    const needs = sortedDocs().filter(d => d.ocr_need);
    const pages = needs.reduce((n, d) => n + d.ocr_need.pages.length, 0);
    const minutes = Math.max(1, Math.round(pages / 60));
    const whole = needs.filter(d => d.ocr_need.kind === 'document').length;
    modal('Aplicar OCR',
      `<p>Se van a reconocer <b>${fmt(pages)} páginas</b> de <b>${fmt(needs.length)} tesis</b>: portadas escaneadas con datos faltantes, páginas escaneadas de la bibliografía y tesis escaneadas completas. Las figuras sueltas no se tocan.</p>
       <p>Tarda alrededor de ${fmt(minutes)} min y sigue en segundo plano. El PDF original se conserva: se trabaja sobre una copia con la capa de texto. Al terminar se vuelven a leer los metadatos, sin cambiar lo que editaste a mano.</p>
       ${whole ? `<p>En las ${fmt(whole)} tesis escaneadas completas la bibliografía se extrae sola al terminar el OCR, salvo que ya tengan correcciones hechas a mano: esas quedan marcadas «falta reprocesar».</p>` : ''}`,
      `<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="BiblioRefRunProjectOcr()">Aplicar OCR</button>`);
  }

  window.BiblioRefRunProjectOcr = async function(){
    const projectId = S.project?.id;
    if(!projectId) return;
    try{
      await api(`/api/projects/${encodeURIComponent(projectId)}/ocr`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({scope:'needed'})});
      closeModal();
      pollOcr(projectId, true);
      window.BiblioRefPollOcr?.();
    }catch(err){
      modalWarn('No se pudo iniciar el OCR: ' + err.message);
    }
  };

  // OCR runs on the server; follow it and merge refreshed theses as each one finishes.
  async function pollOcr(projectId, force = false){
    const ocr = state.ocr;
    if(!projectId) return;
    if(ocr.projectId !== projectId){
      clearTimeout(ocr.timer);
      Object.assign(ocr, {projectId, available: null, reason: '', jobs: {}, timer: null, finished: -1});
    }else if(ocr.timer && !force){
      return;
    }
    clearTimeout(ocr.timer);
    ocr.timer = null;
    let status;
    try{
      status = await api(`/api/projects/${encodeURIComponent(projectId)}/ocr`);
      if(status.available === false && !ocr.reason){
        const info = await api('/api/ocr/status').catch(() => ({}));
        ocr.reason = info.reason || '';
      }
    }catch(err){ return; }
    if(S.project?.id !== projectId) return;
    ocr.available = status.available;
    ocr.jobs = status.jobs || {};
    const jobs = Object.values(ocr.jobs);
    const finished = jobs.filter(j => j.state === 'done' || j.state === 'error').length;
    const active = jobs.some(j => ['queued', 'running', 'extracting'].includes(j.state));
    if(ocr.finished >= 0 && finished > ocr.finished){
      try{
        const d = await api(`/api/projects/${encodeURIComponent(projectId)}/documents-index`);
        if(S.project?.id !== projectId) return;
        const fresh = new Map((d.documents || []).map(x => [x.id, x]));
        S.docs = S.docs.map(x => fresh.has(x.id) ? {...x, ...fresh.get(x.id)} : x);
        renderCards(); renderProjectHeader(); updateGlobal();
      }catch(err){}
    }
    ocr.finished = finished;
    if(document.querySelector('#dashboardTable .rs-toolbar')) draw();
    if(active) ocr.timer = setTimeout(() => { ocr.timer = null; pollOcr(projectId); }, 4000);
  }

  function refCells(r, docId = null){
    const venue = r.journal || r.publisher;
    const fix = (kind, label) => docId && r.missing?.includes(kind)
      ? `<button type="button" class="rs-fix" data-fix-kind="${kind}" data-fix-doc="${esc(docId)}" data-fix-ref="${esc(r.id)}" title="Completar">${miss(label)}</button>`
      : miss(label);
    const type = UNCLASSIFIED.has(r.publicationType) ? fix('type', 'sin clasificar') : esc(typeLabel(r.publicationType));
    return `<td class="rs-num">${esc(r.order)}</td>
      <td>${r.author ? esc(r.author) : fix('author', 'falta')}</td>
      <td class="rs-num">${r.year ? esc(r.year) : fix('year', 'falta')}</td>
      <td>${type}</td>
      <td><div class="rs-clamp" title="${esc(r.title)}">${val(r.title)}</div></td>
      <td>${venue ? esc(venue) : DASH}</td>
      <td class="rs-mono">${r.doi ? esc(r.doi) : DASH}</td>
      <td class="rs-num">${r.page ? esc(r.page) : DASH}</td>
      <td class="rs-mono"><div class="rs-clamp" title="${esc(r.raw)}">${esc(r.raw)}</div></td>`;
  }
  const noteRow = html => `<tr class="rs-note-row"><td colspan="${REF_COLS}"><div class="rs-sticky">${html}</div></td></tr>`;

  function groupHead(d, rows, open){
    const m = thesisMeta(d);
    const title = displayTitle(d);
    // Counted for every thesis in the index, so they show without expanding.
    const chips = window.BiblioRefProblems ? BiblioRefProblems.chips(d, {arrow: true}) : '';
    return `<tr class="rs-group" data-group="${esc(d.id)}">
      <td class="rs-gcell"><button type="button" class="rs-group-head" data-toggle="${esc(d.id)}" aria-expanded="${open}" aria-label="Desplegar ${esc(d.thesis_id || title)}">${CARET}<span class="rs-code">${esc(d.thesis_id || '')}</span></button></td>
      <td class="rs-gcell rs-who">${m.author ? esc(m.author) : miss('falta autor/a')}</td>
      <td class="rs-gcell rs-num rs-who">${m.year ? esc(m.year) : miss('falta')}</td>
      <td class="rs-gcell" colspan="${REF_COLS - 3}"><div class="rs-gtail" style="max-width:var(--rs-tail,900px)">
        <span class="rs-gtitle" title="${esc(title)}">${esc(title)}</span>
        ${chips ? `<span class="rs-chips">${chips}</span>` : ''}
        <span class="rs-count">${fmt(d.n_references)} refs.</span>
        <button type="button" class="btn xs" data-focus="${esc(d.id)}">Abrir</button>
      </div></td></tr>`;
  }

  function referenceView(docs, q){
    let shownRefs = 0;
    const groups = [];
    for(const d of docs){
      if(!passesFilters(d)) continue;
      const rows = state.rowsByDoc.get(d.id);
      const thesisHit = !q || thesisMatches(d, q);
      const refRows = rows ? (thesisHit ? rows : rows.filter(r => refMatches(r, q))) : null;
      if(!thesisHit && !(refRows && refRows.length)) continue;
      const open = state.expanded.has(d.id);
      let html = groupHead(d, rows, open);
      if(open){
        if(!refRows){
          html += noteRow('<span class="loader"></span> Cargando referencias…');
        }else{
          shownRefs += refRows.length;
          html += refRows.map(r => `<tr>${refCells(r)}</tr>`).join('');
          const emptyText = rows.length ? 'Ninguna referencia de esta tesis coincide con la búsqueda.' : 'Esta tesis no tiene referencias extraídas.';
          html += noteRow(`${refRows.length ? '' : emptyText + ' '}<button type="button" class="btn xs" data-open-doc="${esc(d.id)}">Abrir en Referencias por tesis</button>`);
        }
      }
      groups.push(html);
    }
    const empty = docs.length ? 'Ninguna tesis coincide con la búsqueda.' : 'Todavía no hay tesis procesadas.';
    return {
      summary: `${state.filters.size ? `Mostrando ${fmt(groups.length)} de ${fmt(docs.length)}` : fmt(groups.length)} tesis · ${fmt(shownRefs)} referencias desplegadas`,
      note: 'Desplegá una tesis para ver sus referencias. Los datos de la tesis van una sola vez, en el encabezado; los chips ámbar cuentan referencias con datos faltantes. Exportar sigue sacando todas las referencias completas.',
      table: `<table class="rs-table rs-refs"><thead><tr>
        <th class="rs-num rs-w-n">N.º</th><th class="rs-w-author">Autor</th><th class="rs-num rs-w-year">Año</th><th class="rs-w-type">Tipo</th><th class="rs-w-title">Título</th><th class="rs-w-venue">Revista / editorial</th><th class="rs-w-doi">DOI</th><th class="rs-num rs-w-page">Pág.</th><th class="rs-w-raw">Referencia original</th>
      </tr></thead><tbody>${groups.join('') || `<tr><td colspan="${REF_COLS}">${empty}</td></tr>`}</tbody></table>`,
    };
  }

  function focusView(d, q){
    const rows = state.rowsByDoc.get(d.id);
    const c = d.problems || {};
    const missingCount = rows ? rows.filter(r => r.missing.length).length : (c.type || 0) + (c.author || 0) + (c.year || 0);
    if(state.focusMode === 'missing' && rows && !missingCount) state.focusMode = 'all';
    const base = rows ? (state.focusMode === 'missing' ? rows.filter(r => r.missing.length) : rows) : null;
    const shown = base ? (q ? base.filter(r => refMatches(r, q)) : base) : null;
    const body = !shown
      ? noteRow('<span class="loader"></span> Cargando referencias…')
      : shown.length
        ? shown.map(r => `<tr>${refCells(r, d.id)}</tr>`).join('')
        : noteRow(rows.length ? 'Ninguna referencia coincide.' : 'Esta tesis no tiene referencias extraídas.');
    return {
      summary: shown ? `${fmt(shown.length)} de ${fmt(rows.length)} referencias` : '',
      note: state.focusMode === 'missing'
        ? 'Referencias sin tipo, autor o año leídos. Tocá el dato en ámbar para completarlo.'
        : 'Todas las referencias de la tesis. Los datos en ámbar faltan: tocalos para completarlos.',
      missingCount,
      table: `<table class="rs-table rs-refs"><thead><tr>
        <th class="rs-num rs-w-n">N.º</th><th class="rs-w-author">Autor</th><th class="rs-num rs-w-year">Año</th><th class="rs-w-type">Tipo</th><th class="rs-w-title">Título</th><th class="rs-w-venue">Revista / editorial</th><th class="rs-w-doi">DOI</th><th class="rs-num rs-w-page">Pág.</th><th class="rs-w-raw">Referencia original</th>
      </tr></thead><tbody>${body}</tbody></table>`,
    };
  }

  function focusHeader(d, missingCount){
    const m = thesisMeta(d);
    const docs = sortedDocs().filter(isProcessed);
    const at = docs.findIndex(x => x.id === d.id);
    const prev = docs[at - 1], next = docs[at + 1];
    const c = d.problems || {};
    const extraction = (c.missing || 0) + (c.merged || 0);
    const kind = ['missing', 'merged'].find(k => c[k]);
    const meta = [m.author || miss('falta autor/a'), m.year, m.university, m.degree_level && levelLabel(m.degree_level), `${fmt(d.n_references)} referencias`]
      .filter(Boolean).map(x => x.startsWith?.('<span') ? x : esc(x)).join(' · ');
    return `<div class="rs-focus">
      <div class="rs-focus-main">
        <div class="rs-crumb"><button type="button" data-focus-exit>← Todas las tesis</button> › ${esc(d.thesis_id || '')}</div>
        <h2>${esc(displayTitle(d))}</h2>
        <div class="rs-focus-meta">${meta}</div>
      </div>
      <div class="rs-focus-acts">
        <button type="button" class="btn xs" data-focus-go="${esc(prev?.id || '')}" ${prev ? '' : 'disabled'}>‹ Anterior</button>
        <button type="button" class="btn xs" data-focus-go="${esc(next?.id || '')}" ${next ? '' : 'disabled'}>Siguiente ›</button>
        <button type="button" class="btn xs" data-open-doc="${esc(d.id)}">Ver en el PDF</button>
      </div>
    </div>
    <div class="rs-toolbar">
      <div class="rs-seg" role="tablist" aria-label="Qué referencias mostrar">
        <button type="button" role="tab" data-focus-mode="all" aria-selected="${state.focusMode === 'all'}">Todas <span>${fmt(d.n_references)}</span></button>
        <button type="button" role="tab" data-focus-mode="missing" aria-selected="${state.focusMode === 'missing'}" ${missingCount ? '' : 'disabled'}>Faltan datos <span>${fmt(missingCount)}</span></button>
      </div>
      ${extraction ? `<button type="button" class="rs-extract" data-problem-doc="${esc(d.id)}" data-problem-kind="${kind}" title="Recorrerlos de a uno en el PDF">Extracción a revisar ${fmt(extraction)} ›</button>` : ''}
      <input id="rsSearch" class="rs-search" type="search" value="${esc(state.search)}" placeholder="Buscar en las referencias de esta tesis…" aria-label="Buscar en las referencias">
      <span class="rs-summary"></span>
    </div>`;
  }

  function focusThesis(id, mode = 'all'){
    state.focus = id;
    state.focusMode = mode;
    state.view = 'refs';
    state.search = '';
    state.expanded.add(id);
  }

  function sizeSticky(){
    const scroll = document.querySelector('#dashboardTable .rs-scroll');
    if(scroll) scroll.style.setProperty('--rs-vw', scroll.clientWidth + 'px');
  }

  function scrollToGroup(id){
    const scroll = document.querySelector('#dashboardTable .rs-scroll');
    const row = scroll && [...scroll.querySelectorAll('tr.rs-group')].find(tr => tr.dataset.group === id);
    if(!row) return;
    const head = scroll.querySelector('thead');
    scroll.scrollTop = Math.max(0, row.offsetTop - (head ? head.offsetHeight : 0));
  }

  function draw(keepScroll = true){
    const host = $('#dashboardTable');
    if(!host) return;
    bindHost(host);
    host.classList.add('rs-host');
    const prev = host.querySelector('.rs-scroll');
    const scrollPos = keepScroll && prev ? [prev.scrollTop, prev.scrollLeft] : [0, 0];
    const searchFocused = document.activeElement?.id === 'rsSearch';
    const lead = document.querySelector('#screen-project .lead');
    if(lead) lead.textContent = state.view === 'tesis'
      ? 'Una fila por tesis, solo con sus metadatos, para ver de un vistazo qué datos de portada faltan.'
      : state.view === 'inferidos'
        ? 'Cada dato completado por inferencia, con su regla y evidencia, para confirmarlo o deshacerlo.'
        : 'El parseo de cada referencia, agrupado bajo su tesis.';

    const docs = sortedDocs();
    const processed = docs.filter(isProcessed);
    const totalRefs = processed.reduce((n,d) => n + (d.n_references || 0), 0);
    const q = norm(state.search.trim());
    const inferredTotal = docs.reduce((n, d) => n + Object.keys(d.metadata_inference || {}).length, 0);
    if(state.view === 'inferidos' && !inferredTotal) state.view = 'tesis';
    const focused = state.view === 'refs' && state.focus ? S.docs.find(d => d.id === state.focus) : null;
    if(state.focus && !focused) state.focus = null;
    if(focused){
      if(lead) lead.textContent = 'Las referencias de una tesis, en tabla.';
      const fv = focusView(focused, q);
      host.innerHTML = `${focusHeader(focused, fv.missingCount)}
        <div class="rs-note">${esc(fv.note)}</div>
        <div class="rs-scroll">${fv.table}</div>`;
      host.querySelector('.rs-summary').textContent = fv.summary;
      sizeSticky();
      const scroll = host.querySelector('.rs-scroll');
      if(scroll){ scroll.scrollTop = scrollPos[0]; scroll.scrollLeft = scrollPos[1]; }
      if(searchFocused){
        const input = $('#rsSearch');
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      }
      return;
    }
    const view = state.view === 'tesis' ? thesisView(docs, q) : state.view === 'inferidos' ? inferenceAuditView(docs, q) : referenceView(processed, q);

    host.innerHTML = `<div class="rs-toolbar">
      <div class="rs-seg" role="tablist" aria-label="Vista del resumen">
        <button type="button" role="tab" data-view="tesis" aria-selected="${state.view === 'tesis'}">Tesis <span>${fmt(docs.length)}</span></button>
        <button type="button" role="tab" data-view="refs" aria-selected="${state.view === 'refs'}">Referencias <span>${fmt(totalRefs)}</span></button>
        ${inferredTotal ? `<button type="button" role="tab" data-view="inferidos" aria-selected="${state.view === 'inferidos'}">Inferidos <span>${fmt(inferredTotal)}</span></button>` : ''}
      </div>
      <input id="rsSearch" class="rs-search" type="search" value="${esc(state.search)}" placeholder="${state.view === 'refs' ? 'Buscar tesis o en las referencias desplegadas…' : 'Buscar tesis, autor/a, director/a, universidad…'}" aria-label="Buscar en la vista">
      ${state.view === 'inferidos' ? '' : filterButton()}
      ${state.view === 'refs' && state.expanded.size ? '<button type="button" class="btn xs" data-collapse-all>Plegar todas</button>' : ''}
      ${state.view === 'tesis' ? '<button type="button" class="btn xs" data-infer-open>Inferir faltantes…</button>' : ''}
      <span class="rs-summary">${view.summary}${state.filters.size && state.view !== 'inferidos' ? ' · <button type="button" class="rs-flink" data-filter-clear>Limpiar</button>' : ''}</span>
    </div>
    ${state.view === 'tesis' ? ocrBanner(docs) : ''}
    <div class="rs-note">${esc(view.note)}</div>
    <div class="rs-scroll">${view.table}</div>`;

    sizeSticky();
    // Keep the filter panel inside the window when the button sits far to the right.
    const panel = host.querySelector('.rs-fpanel');
    if(panel){
      const overflow = panel.getBoundingClientRect().right - (document.documentElement.clientWidth - 12);
      if(overflow > 0) panel.style.left = `${-overflow}px`;
    }
    const scroll = host.querySelector('.rs-scroll');
    if(scroll){ scroll.scrollTop = scrollPos[0]; scroll.scrollLeft = scrollPos[1]; }
    if(searchFocused){
      const input = $('#rsSearch');
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  }

  function bindHost(host){
    if(host.dataset.rsBound) return;
    host.dataset.rsBound = '1';
    host.addEventListener('click', e => {
      const viewBtn = e.target.closest('[data-view]');
      const toggle = e.target.closest('[data-toggle]');
      const showRefs = e.target.closest('[data-show-refs]');
      const openDocBtn = e.target.closest('[data-open-doc]');
      const focusBtn = e.target.closest('[data-focus],[data-focus-go]');
      const modeBtn = e.target.closest('[data-focus-mode]');
      const fixBtn = e.target.closest('[data-fix-kind]');
      if(fixBtn){
        window.BiblioRefProblems?.fix(fixBtn.dataset.fixDoc, fixBtn.dataset.fixKind, [fixBtn.dataset.fixRef]);
      }else if(focusBtn){
        const id = focusBtn.dataset.focus || focusBtn.dataset.focusGo;
        if(id){ focusThesis(id, state.focus ? state.focusMode : 'all'); draw(false); ensureExpanded(); }
      }else if(modeBtn){
        if(state.focusMode !== modeBtn.dataset.focusMode){ state.focusMode = modeBtn.dataset.focusMode; draw(false); }
      }else if(e.target.closest('[data-focus-exit]')){
        const id = state.focus;
        state.focus = null;
        state.search = '';
        draw(false);
        if(id) scrollToGroup(id);
      }else if(viewBtn){
        if(state.view !== viewBtn.dataset.view){ state.view = viewBtn.dataset.view; state.focus = null; state.search = ''; state.infField = ''; draw(false); }
      }else if(toggle){
        const id = toggle.dataset.toggle;
        if(state.expanded.has(id)) state.expanded.delete(id); else state.expanded.add(id);
        draw();
        ensureExpanded();
      }else if(showRefs){
        focusThesis(showRefs.dataset.showRefs);
        draw(false);
        ensureExpanded();
      }else if(openDocBtn){
        window.openDoc(openDocBtn.dataset.openDoc);
      }else if(e.target.closest('[data-filter-toggle]')){
        state.filterOpen = !state.filterOpen;
        draw();
      }else if(e.target.closest('[data-filter-remove]')){
        state.filters.delete(e.target.closest('[data-filter-remove]').dataset.filterRemove);
        draw(false);
      }else if(e.target.closest('[data-filter-quick]')){
        const key = e.target.closest('[data-filter-quick]').dataset.filterQuick;
        if(state.filters.has(key)) state.filters.delete(key); else state.filters.add(key);
        draw(false);
      }else if(e.target.closest('[data-filter-clear]')){
        state.filters.clear();
        draw(false);
      }else if(e.target.closest('[data-sort-problems]')){
        state.sortProblems = !state.sortProblems;
        draw(false);
      }else if(e.target.closest('[data-inf]')){
        toggleInferencePopover(e.target.closest('[data-inf]'));
      }else if(e.target.closest('[data-infer-open]')){
        openInferenceModal();
      }else if(e.target.closest('[data-inf-field]')){
        state.infField = e.target.closest('[data-inf-field]').dataset.infField;
        draw(false);
      }else if(e.target.closest('[data-inf-act]')){
        const btn = e.target.closest('[data-inf-act]');
        inferenceAction(btn.dataset.doc, btn.dataset.field, btn.dataset.infAct);
      }else if(e.target.closest('[data-inf-undo-all]')){
        undoAllInferences();
      }else if(e.target.closest('[data-ocr-filter]')){
        state.ocrOnly = !state.ocrOnly;
        draw(false);
      }else if(e.target.closest('[data-ocr-run]')){
        confirmProjectOcr();
      }else if(e.target.closest('[data-collapse-all]')){
        state.expanded.clear();
        draw();
      }
    });
    host.addEventListener('change', e => {
      const box = e.target.closest('[data-filter-key]');
      if(box){
        if(box.checked) state.filters.add(box.dataset.filterKey); else state.filters.delete(box.dataset.filterKey);
        draw(false);
      }else if(e.target.name === 'rsFilterMode'){
        state.filterMode = e.target.value;
        draw(false);
      }
    });
    document.addEventListener('click', e => {
      if(state.filterOpen && !e.target.closest('.rs-filterwrap') && e.target.isConnected){
        state.filterOpen = false;
        draw();
      }
    });
    document.addEventListener('keydown', e => {
      if(e.key === 'Escape' && state.filterOpen){ state.filterOpen = false; draw(); }
    });
    host.addEventListener('input', e => {
      if(e.target.id !== 'rsSearch') return;
      state.search = e.target.value;
      draw(false);
    });
  }
  window.addEventListener('resize', sizeSticky);

  window.BiblioRefOpenThesisTable = function(id, mode = 'all'){
    resetIfNeeded();
    focusThesis(id, mode);
    show('project');
    renderDashboard();
  };

  // A correction made in the fix dialog: reload that thesis's rows and the index counts.
  window.addEventListener('biblioref:refs-changed', async e => {
    const id = e.detail?.docId;
    if(id) state.rowsByDoc.delete(id);
    try{ await refreshDocsFromIndex(); }catch(err){ /* the next open refreshes it */ }
    ensureExpanded();
  });

  window.renderDashboard = function renderDashboardSummaryViews(){
    resetIfNeeded();
    const heading = document.querySelector('#screen-project .h1');
    if(heading) heading.textContent = 'Resumen';
    draw();
    ensureExpanded();
  };

  window.BiblioRefOriginalRenderDashboard = originalRenderDashboard;
})();
