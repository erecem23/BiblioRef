/* «Faltantes»: los párrafos que están en el PDF y no quedaron como referencia, de todo el proyecto
   en una sola lista. Cada uno se muestra con su recorte de página (/missing/<id>/band.png, con el
   párrafo marcado por el servidor) para decidir sin abrir la tesis. Las reglas de qué sigue abierto
   son las mismas de biblioref/review_problems.py y static/review-problems.js. */
(() => {
  const PAGE = 40;
  const fmt = n => Number(n || 0).toLocaleString('es-AR');
  const state = () => (S.missing = S.missing || {q: '', documentId: '', order: 'thesis', stage: 'merged', view: 'list', baseline: 0, groups: [], total: 0, loaded: 0, busy: false, docs: []});

  const style = document.createElement('style');
  style.id = 'project-missing-style';
  style.textContent = `
    .ms-step{display:flex;flex-direction:column;gap:11px;background:var(--surface);border:1px solid #f0d5ab;border-left:4px solid var(--warn);border-radius:var(--radius);padding:15px 18px;margin-top:14px}
    .ms-step.ms-done{border-color:#c9d8fb;border-left-color:var(--accent)}
    .ms-step h2{margin:0;font-size:15px;color:var(--warn)}
    .ms-step.ms-done h2{color:var(--accent-dark,#1f56c4)}
    .ms-step p{margin:0;font-size:13px;line-height:1.55;max-width:820px;color:var(--ink)}
    .ms-step .ms-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .ms-step .btn.big{font-size:13.5px;padding:10px 18px;border-radius:8px}
    .ms-step .btn.warnsolid{background:var(--warn);border-color:var(--warn);color:#fff}
    .ms-progress{flex:1 1 160px;max-width:300px;height:6px;border-radius:999px;background:#f0e3d0;overflow:hidden}
    .ms-progress i{display:block;height:100%;background:var(--warn)}
    .ms-hint{font-size:12px;color:var(--muted)}
    .ms-confirm li{margin-bottom:5px}
    .ms-bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:14px 0 12px}
    .ms-bar input,.ms-bar select{font:inherit;font-size:13px;padding:7px 10px;border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--surface);color:var(--ink)}
    .ms-bar input{flex:1 1 240px;max-width:330px}
    .ms-bar .btn{white-space:nowrap}
    .ms-sum{margin-left:auto;font-size:12.5px;color:var(--muted)}
    .ms-sum b{color:var(--ink)}
    .ms-list{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
    .ms-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:10px 16px;background:var(--canvas);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2}
    .ms-head b{font-size:13px}
    .ms-head .ms-meta{font-size:12px;color:var(--muted)}
    .ms-count{background:var(--warnbg);color:var(--warn);border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:600}
    .ms-open{background:none;border:0;font-size:12.5px;color:var(--accent);cursor:pointer;font-family:inherit;padding:0}
    .ms-head .ms-open:first-of-type{margin-left:auto}
    .ms-open:hover{text-decoration:underline}
    .ms-item{display:grid;grid-template-columns:minmax(0,1fr) 210px;gap:16px;padding:14px 16px;border-bottom:1px solid var(--line);align-items:start}
    .ms-item:last-child{border-bottom:0}
    .ms-item.ms-inside .ms-where{color:var(--warn)}
    .ms-where{font-size:11.5px;color:var(--muted);margin-bottom:6px}
    .ms-band{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--canvas);min-height:64px}
    .ms-band img{display:block;width:100%;height:auto}
    .ms-band.ms-wait{display:flex;align-items:center;justify-content:center;height:96px;font-size:12px;color:var(--muted)}
    .ms-acts{display:flex;flex-direction:column;gap:6px}
    .ms-item.ms-has-result{grid-template-columns:minmax(0,1fr) minmax(0,1fr) 230px}
    .ms-result{border:1px solid var(--line);border-radius:8px;background:#fff;padding:9px 11px;display:flex;flex-direction:column;gap:7px;min-width:0}
    .ms-result h4{margin:0;font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
    .ms-ref{font-size:12.5px;line-height:1.55;overflow-wrap:anywhere}
    .ms-ref b{color:var(--accent-dark,#1f56c4);font-variant-numeric:tabular-nums;margin-right:4px}
    .ms-from{background:var(--accent-bg);border-bottom:2px solid var(--accent);padding:0 1px}
    .ms-lost{background:var(--warnbg);border-bottom:2px dashed var(--warn);color:#8a4207;font-weight:600;padding:0 2px}
    .ms-verdict{font-size:12px;font-weight:600;color:var(--accent-dark,#1f56c4)}
    .ms-verdict.ms-warn{color:var(--warn)}
    .ms-edit{border:0;background:none;padding:0;font:inherit;font-size:12px;color:var(--accent);cursor:pointer;text-align:left}
    .ms-edit:hover{text-decoration:underline}
    @media(max-width:1100px){.ms-item.ms-has-result{grid-template-columns:minmax(0,1fr) 210px}.ms-item.ms-has-result .ms-result{grid-column:1}}
    .ms-acts .btn{justify-content:center}
    .ms-acts .btn.amber{border-color:var(--warn);color:var(--warn)}
    .ms-acts .btn.amber.solid{background:var(--warn);color:#fff}
    .ms-map{padding:14px 16px;display:flex;flex-direction:column;gap:10px}
    .ms-thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:12px}
    .ms-thumb{display:flex;flex-direction:column;gap:5px;background:none;border:0;padding:0;font:inherit;cursor:pointer;text-align:left}
    .ms-thumb .ms-page{position:relative;border:2px solid #d7dae1;border-radius:6px;overflow:hidden;background:var(--canvas);aspect-ratio:1/1.41}
    .ms-thumb .ms-page img{display:block;width:100%;height:auto}
    .ms-thumb .ms-page i{position:absolute;inset:0;display:block}
    .ms-thumb.ms-ok .ms-page{border-color:var(--accent)}
    .ms-thumb.ms-ok .ms-page i{background:rgba(47,111,235,.13)}
    .ms-thumb.ms-warn .ms-page{border-color:var(--warn)}
    .ms-thumb.ms-warn .ms-page i{background:rgba(180,83,9,.14)}
    .ms-thumb.ms-mixed .ms-page{border-color:#c8a97a}
    .ms-thumb.ms-mixed .ms-page i{background:rgba(180,83,9,.08)}
    .ms-thumb:hover .ms-page{outline:2px solid var(--accent);outline-offset:1px}
    .ms-thumb figcaption,.ms-thumb .ms-cap{font-size:11.5px;line-height:1.35}
    .ms-cap b{font-weight:600}
    .ms-cap .ms-n{color:var(--warn)}
    .ms-cap .ms-r{color:var(--muted)}
    .ms-strip{display:grid;grid-template-columns:repeat(auto-fill,minmax(34px,1fr));gap:6px}
    .ms-cell{height:34px;border-radius:4px;border:1px solid #d7dae1;background:var(--canvas);cursor:pointer;padding:0;font:inherit;font-size:9.5px;color:var(--muted)}
    .ms-cell.ms-ok{border-color:var(--accent);background:rgba(47,111,235,.16);color:var(--accent-dark,#1f56c4)}
    .ms-cell.ms-warn{border-color:var(--warn);border-style:dashed;background:rgba(180,83,9,.16);color:var(--warn)}
    .ms-cell.ms-mixed{border-color:#c8a97a;background:rgba(180,83,9,.08);color:var(--warn)}
    .ms-cell:hover{outline:2px solid var(--accent);outline-offset:1px}
    .ms-legend{display:flex;flex-wrap:wrap;align-items:center;gap:14px;font-size:11.5px;color:var(--muted)}
    .ms-legend i{width:11px;height:11px;border-radius:3px;display:inline-block;vertical-align:-1px;margin-right:5px}
    .ms-view{display:inline-flex;border:1px solid var(--line);border-radius:var(--radius-sm);overflow:hidden;background:var(--surface)}
    .ms-view button{font:inherit;font-size:12.5px;padding:7px 12px;border:0;background:none;color:var(--ink);cursor:pointer}
    .ms-view button.active{background:var(--accent);color:#fff}
    .ms-more{display:flex;justify-content:center;padding:14px}
    .ms-empty{padding:26px 16px;text-align:center;font-size:13px;color:var(--muted)}
    .ms-modalband{border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:10px}
    .ms-modalband img{display:block;width:100%;height:auto}
    .navcount{margin-left:auto;background:var(--warnbg);color:var(--warn);border-radius:999px;padding:1px 7px;font-size:10.5px;font-weight:700}
    .sidebar.collapsed .navcount{display:none}
  `;
  document.head.appendChild(style);

  // Las imágenes se piden cuando la fila se acerca a la pantalla: cada una es un render del PDF.
  const lazy = new IntersectionObserver(entries => {
    for(const entry of entries){
      if(!entry.isIntersecting) continue;
      const box = entry.target;
      lazy.unobserve(box);
      const img = new Image();
      img.alt = box.dataset.alt || 'Recorte de la página';
      img.onload = () => { box.classList.remove('ms-wait'); box.textContent = ''; box.appendChild(img); };
      img.onerror = () => { box.classList.add('ms-wait'); box.textContent = 'No se pudo dibujar el recorte'; };
      img.src = box.dataset.src;
    }
  }, {rootMargin: '400px 0px'});

  // Un párrafo que ya está adentro de una referencia no falta: extraerlo lo duplicaría.
  // Lo que corresponde es dividir la referencia que se lo tragó, justo donde el párrafo empieza.
  // Salvo que el párrafo fuera la segunda línea de esa misma referencia: ahí dividir la
  // partiría en dos, así que no hay nada que decidir.
  // The host reference, and the next one, as they are now: blue where the text came from the
  // outlined paragraph, amber for what the paragraph has and no reference kept.
  function refHtml(r){
    let html = '', at = 0;
    for(const [a, b] of (r.spans || []).slice().sort((x, y) => x[0] - y[0])){
      if(a < at) continue;
      html += esc(r.text.slice(at, a)) + `<span class="ms-from">${esc(r.text.slice(a, b))}</span>`;
      at = b;
    }
    html += esc(r.text.slice(at));
    return `<div class="ms-ref"><b>REF ${String(r.order).padStart(3, '0')}</b>${html}</div>`;
  }
  function resultHtml(item){
    const pv = item.preview;
    if(!pv || !pv.refs?.length) return '';
    const host = pv.refs[0];
    const lost = pv.leftover || [];
    const touched = pv.refs.filter(r => r.spans?.length).map(r => `REF ${String(r.order).padStart(3, '0')}`);
    const refs = pv.refs.map((r, i) => i === 0 && lost.length
      ? refHtml(r).replace(/<\/div>$/, ` <span class="ms-lost">${esc(lost.join(' … '))}</span></div>`)
      : refHtml(r)).join('');
    const verdict = lost.length
      ? `<div class="ms-verdict ms-warn">«${esc(lost.join(' … '))}» está en el recuadro pero no quedó en ninguna referencia.</div>`
      : `<div class="ms-verdict">Todo el recuadro ya está en ${touched.join(' y ') || 'las referencias'}.</div>`;
    return `<div class="ms-result"><h4>Cómo quedan las referencias</h4>${refs}${verdict}
      <button type="button" class="ms-edit" data-ms-edit="${esc(host.id)}">Editar el texto de REF ${String(host.order).padStart(3, '0')}</button></div>`;
  }

  function itemHtml(group, item){
    const inside = item.inside_ref;
    const lost = item.preview?.leftover || [];
    const hostOrder = inside ? String(inside.order).padStart(3, '0') : '';
    const ref = inside ? `REF ${String(inside.order).padStart(3, '0')}` : '';
    const where = inside
      ? (inside.continuation
          ? `pág. ${item.page} · el recuadro sigue a ${ref}`
          : `pág. ${item.page} · ya está adentro de ${ref} (${fmt(inside.length)} caracteres)`)
      : `pág. ${item.page}${item.best_existing_match == null ? '' : ` · el parecido con la referencia más cercana es ${String(item.best_existing_match).replace('.', ',')}`}`;
    let acts;
    if(inside && (inside.already_extracted || inside.continuation)){
      const label = inside.continuation ? 'Está bien · listo' : 'Ya está extraída · listo';
      acts = lost.length
        ? `<button type="button" class="btn xs amber solid" data-ms-append>Agregar al final de REF ${hostOrder}</button><button type="button" class="btn xs" data-ms-resolved>${label}</button>`
        : `<button type="button" class="btn xs amber solid" data-ms-resolved>${label}</button>`;
      if(inside.continuation) acts += '<button type="button" class="btn xs" data-ms-forcesplit>Es una referencia válida: separarla</button>';
    }else if(inside){
      acts = `<button type="button" class="btn xs amber solid" data-ms-split>Dividir ${ref} acá</button>`;
    }else{
      acts = `<button type="button" class="btn xs amber solid" data-ms-add>Extraer como referencia</button>`;
    }
    const result = resultHtml(item);
    return `<div class="ms-item${inside ? ' ms-inside' : ''}${result ? ' ms-has-result' : ''}" data-ms-doc="${esc(group.document_id)}" data-ms-id="${esc(item.id)}">
      <div>
        <div class="ms-where">${esc(where)}</div>
        <div class="ms-band ms-wait" data-src="/api/documents/${encodeURIComponent(group.document_id)}/missing/${encodeURIComponent(item.id)}/band.png?zoom=1.5" data-alt="Recorte de la página ${item.page}">recorte…</div>
      </div>
      ${result}
      <div class="ms-acts">
        ${acts}
        <button type="button" class="btn xs" data-ms-ignore>No es una referencia</button>
        <button type="button" class="btn xs" data-ms-open>Ver en la tesis</button>
      </div>
    </div>`;
  }

  function groupHtml(group){
    const who = [group.author, group.year].filter(Boolean).join(' · ');
    return `<div class="ms-head"><b>${esc(group.thesis_id || 'Tesis')}${who ? ' · ' + esc(who) : ''}</b>
      <span class="ms-meta">${fmt(group.page_count)} págs. · ${fmt(group.n_references)} referencias</span>
      <span class="ms-count">${fmt(group.n_missing)} faltante${group.n_missing === 1 ? '' : 's'}</span>
      <button type="button" class="ms-open" data-ms-zip="${esc(group.document_id)}" title="Un .zip con el informe de auditoría y el recorte de cada faltante">Exportar auditoría</button>
      <button type="button" class="ms-open ms-open-thesis" data-ms-thesis="${esc(group.document_id)}">Abrir la tesis ›</button></div>
      ${state().view === 'map' ? mapHtml(group) : group.items.map(x => itemHtml(group, x)).join('')}`;
  }

  // El mapa: una miniatura (o una casilla) por página de bibliografía, teñida según qué salió.
  function pageClass(page){
    if(page.merged || page.real) return page.references ? 'ms-mixed' : 'ms-warn';
    return page.references ? 'ms-ok' : '';
  }

  function pageTitle(page){
    const partes = [];
    if(page.references) partes.push(`${fmt(page.references)} referencia${page.references === 1 ? '' : 's'}`);
    if(page.merged) partes.push(`${fmt(page.merged)} pegada${page.merged === 1 ? '' : 's'}`);
    if(page.real) partes.push(`${fmt(page.real)} sin extraer`);
    return `pág. ${page.page}${partes.length ? ' · ' + partes.join(' · ') : ' · sin nada extraído'}`;
  }

  function mapHtml(group){
    const pages = group.pages || [];
    if(!pages.length) return '<div class="ms-map"><span class="ms-hint">Esta tesis no tiene una sección de bibliografía delimitada.</span></div>';
    const legend = `<div class="ms-legend">
      <span><i style="border:1px solid var(--accent);background:rgba(47,111,235,.16)"></i>salieron referencias</span>
      <span><i style="border:1px dashed var(--warn);background:rgba(180,83,9,.16)"></i>hay avisos</span>
      <span><i style="border:1px solid #c8a97a;background:rgba(180,83,9,.08)"></i>mezcla</span>
      <span><i style="border:1px solid #d7dae1"></i>nada</span>
      <span style="margin-left:auto">tocá una página para abrirla en la tesis</span></div>`;
    if(pages.length > 12){
      const cells = pages.map(page => `<button type="button" class="ms-cell ${pageClass(page)}" data-ms-page="${page.page}" data-ms-pagedoc="${esc(group.document_id)}" title="${esc(pageTitle(page))}">${page.page}</button>`).join('');
      return `<div class="ms-map">${legend}<div class="ms-strip">${cells}</div></div>`;
    }
    const thumbs = pages.map(page => `<button type="button" class="ms-thumb ${pageClass(page)}" data-ms-page="${page.page}" data-ms-pagedoc="${esc(group.document_id)}" title="${esc(pageTitle(page))}">
      <span class="ms-page"><span class="ms-band ms-wait" style="border:0;border-radius:0;min-height:0;height:100%" data-src="/api/documents/${encodeURIComponent(group.document_id)}/page/${page.page}.png?zoom=0.34" data-alt="Página ${page.page}"></span><i></i></span>
      <span class="ms-cap"><b>pág. ${page.page}</b>${page.merged || page.real ? ` <span class="ms-n">${fmt(page.merged + page.real)} aviso${page.merged + page.real === 1 ? '' : 's'}</span>` : ''}<br><span class="ms-r">${page.references ? `${fmt(page.references)} referencia${page.references === 1 ? '' : 's'}` : 'ninguna referencia'}</span></span>
    </button>`).join('');
    return `<div class="ms-map">${legend}<div class="ms-thumbs">${thumbs}</div></div>`;
  }

  function paint(){
    const st = state();
    const host = document.getElementById('missingList');
    if(!host) return;
    const summary = document.getElementById('missingSummary');
    if(summary) summary.innerHTML = st.total
      ? `<b>${fmt(st.total)} ${st.stage === 'merged' ? 'para dividir' : st.stage === 'real' ? 'sin extraer' : 'avisos'}</b> en ${fmt(st.nDocs)} tesis`
      : (st.stage === 'merged' ? 'no quedan pegadas por dividir' : 'sin faltantes pendientes');
    const badge = document.getElementById('navMissingCount');
    const pendientes = (st.nInside || 0) + (st.nReal || 0);
    if(badge){ badge.textContent = pendientes ? fmt(pendientes) : ''; badge.style.display = pendientes ? '' : 'none'; }
    const step = document.getElementById('missingStep');
    if(step) step.innerHTML = stepHtml();
    if(st.busy && !st.groups.length){ host.innerHTML = '<div class="ms-empty"><span class="loader"></span> buscando faltantes…</div>'; return; }
    if(!st.groups.length){
      host.innerHTML = `<div class="ms-list"><div class="ms-empty">${st.q || st.documentId ? 'No hay faltantes que coincidan con el filtro.' : 'No quedan faltantes por revisar en este proyecto.'}</div></div>`;
      return;
    }
    const toggle = document.getElementById('missingView');
    if(toggle) toggle.querySelectorAll('button').forEach(b => b.classList.toggle('active', b.dataset.msView === st.view));
    const more = st.view !== 'map' && st.loaded < st.total
      ? `<div class="ms-more"><button type="button" class="btn" data-ms-more ${st.busy ? 'disabled' : ''}>${st.busy ? 'cargando…' : `Ver ${fmt(Math.min(PAGE, st.total - st.loaded))} más (${fmt(st.total - st.loaded)} restantes)`}</button></div>`
      : '';
    host.innerHTML = `<div class="ms-list">${st.groups.map(groupHtml).join('')}${more}</div>`;
    host.querySelectorAll('.ms-band[data-src]').forEach(box => lazy.observe(box));
  }

  // Las tandas siguientes se pegan a la misma tesis si la última quedó cortada por la mitad.
  function mergeGroups(groups, incoming){
    for(const group of incoming){
      const last = groups[groups.length - 1];
      if(last && last.document_id === group.document_id) last.items.push(...group.items);
      else groups.push(group);
    }
    return groups;
  }

  async function load({append = false} = {}){
    const st = state();
    if(!S.project) return;
    st.busy = true;
    if(!append){ st.groups = []; st.loaded = 0; }
    paint();
    const qs = new URLSearchParams({order: st.order, stage: st.stage, offset: String(append ? st.loaded : 0), limit: String(PAGE)});
    if(st.q) qs.set('q', st.q);
    if(st.documentId) qs.set('document_id', st.documentId);
    try{
      const data = await api(`/api/projects/${encodeURIComponent(S.project.id)}/missing?${qs}`);
      st.total = data.total;
      st.nDocs = data.n_documents_with_missing;
      st.nInside = data.n_inside_reference;
      st.nReal = data.n_real;
      st.nMergedSuspects = data.n_merged_suspects || 0;
      st.nSplittable = data.n_splittable;
      st.baseline = Math.max(st.baseline || 0, data.n_inside_reference || 0);
      syncStageSelect();
      st.loaded = (append ? st.loaded : 0) + data.returned;
      st.groups = append ? mergeGroups(st.groups, data.documents) : data.documents;
    }catch(err){
      notify('No se pudieron cargar los faltantes: ' + err.message);
    }finally{
      st.busy = false;
      paint();
    }
  }

  // Paso 1 = las pegadas (extraerlas duplicaría texto); Paso 2 = las que faltan de verdad.
  function stepHtml(){
    const st = state();
    const pegadas = st.nInside;
    if(pegadas == null) return '';
    if(st.stage === 'real' || (!pegadas && st.stage !== 'all')){
      if(pegadas) return `<section class="ms-step ms-done"><h2>Paso 2 de 2 · ${fmt(st.nReal)} faltan de verdad</h2>
        <p>Estos párrafos no están en ninguna referencia: acá sí corresponde extraerlos. Todavía quedan <b>${fmt(pegadas)}</b> pegadas sin separar.</p>
        <div class="ms-row"><button type="button" class="btn" data-ms-goto="merged">Volver al Paso 1</button></div></section>`;
      const sospechas = st.nMergedSuspects || 0;
      return `<section class="ms-step ms-done"><h2>Paso 1 listo · no quedan párrafos pegados</h2>
        <p>Todo lo que estaba adentro de otra referencia quedó separado. Lo que sigue son los <b>${fmt(st.nReal)}</b> párrafos que faltan de verdad.</p>
        ${sospechas ? `<p class="ms-hint">Aparte, el texto de <b>${fmt(sospechas)}</b> referencia${sospechas === 1 ? '' : 's'} parece${sospechas === 1 ? '' : 'n'} contener más de una («posibles fusionadas»): se revisa${sospechas === 1 ? '' : 'n'} en la hoja de cada tesis.</p>` : ''}
        <div class="ms-row">${st.stage === 'real' ? '' : `<button type="button" class="btn primary big" data-ms-goto="real">Ir al Paso 2 · ${fmt(st.nReal)} faltantes</button>`}</div></section>`;
    }
    const base = Math.max(st.baseline || 0, pegadas);
    const hechas = Math.max(0, base - pegadas);
    return `<section class="ms-step"><h2>Paso 1 de 2 · ${fmt(pegadas)} referencias quedaron pegadas</h2>
      <p>Estos párrafos <b>ya están adentro</b> de otra referencia: el extractor pegó dos en una. Extraerlos ahora duplicaría el texto, así que primero se separan. Después queda el Paso 2, con los <b>${fmt(st.nReal)}</b> que faltan de verdad.</p>
      <div class="ms-row">
        ${st.nSplittable ? `<button type="button" class="btn big warnsolid" data-ms-splitall>Dividir las ${fmt(st.nSplittable)}</button>` : ''}
        <span class="ms-progress" aria-hidden="true"><i style="width:${base ? Math.round(100 * hechas / base) : 0}%"></i></span>
        <span class="ms-hint">${hechas ? `${fmt(hechas)} divididas · quedan ${fmt(pegadas)}` : 'o resolvelas de a una en la lista de abajo'}</span>
      </div>
      ${pegadas - (st.nSplittable || 0) > 0 ? `<p class="ms-hint">${fmt(pegadas - st.nSplittable)} de estas no se dividen: el párrafo ya está extraído y el aviso se cierra de a uno, con «Ya está extraída · listo».</p>` : ''}</section>`;
  }

  function syncStageSelect(){
    const select = document.getElementById('missingStage');
    if(!select) return;
    const st = state();
    select.innerHTML = `<option value="merged">Paso 1 · pegadas para dividir${st.nInside == null ? '' : ` (${fmt(st.nInside)})`}</option>`
      + `<option value="real">Paso 2 · faltan de verdad${st.nReal == null ? '' : ` (${fmt(st.nReal)})`}</option>`
      + '<option value="all">Todos los avisos</option>';
    select.value = st.stage;
  }

  function fillDocSelect(){
    const select = document.getElementById('missingDoc');
    if(!select) return;
    const st = state();
    const options = (S.docs || []).map(d => `<option value="${esc(d.id)}">${esc(d.thesis_id || d.title || d.filename || d.id)}</option>`).join('');
    select.innerHTML = `<option value="">Todas las tesis</option>${options}`;
    select.value = st.documentId || '';
  }

  const itemOf = el => {
    const row = el.closest('[data-ms-id]');
    if(!row) return null;
    const st = state();
    for(const group of st.groups){
      const item = group.items.find(x => x.id === row.dataset.msId);
      if(item && group.document_id === row.dataset.msDoc) return {group, item, row};
    }
    return null;
  };

  function drop(group, item){
    const st = state();
    group.items = group.items.filter(x => x.id !== item.id);
    group.n_missing = Math.max(0, (group.n_missing || 1) - 1);
    st.groups = st.groups.filter(g => g.items.length);
    st.total = Math.max(0, st.total - 1);
    st.loaded = Math.max(0, st.loaded - 1);
    // El mismo dato alimenta los chips del Resumen: se corrige sin recargar todas las tesis.
    const summary = (S.docs || []).find(d => d.id === group.document_id);
    if(summary?.problems) summary.problems = {...summary.problems, missing: Math.max(0, (summary.problems.missing || 1) - 1)};
    paint();
    if(typeof renderDashboard === 'function') renderDashboard();
  }

  const decide = (docId, checkId, decision, note) =>
    api(`/api/documents/${encodeURIComponent(docId)}/audit-checks/${encodeURIComponent(checkId)}/decision`,
        {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({decision, note})});

  async function close(group, item, decision, note){
    try{
      await decide(group.document_id, item.id, decision, note);
      drop(group, item);
    }catch(err){ notify('No se pudo guardar la decisión: ' + err.message); }
  }
  const ignore = (group, item) => close(group, item, 'ignore', 'missing_screen');

  // Una sola pasada para todo el proyecto: son cientos de referencias y el store se guarda entero.
  function confirmSplitAll(){
    const st = state();
    const n = st.nSplittable || 0;
    if(!n) return;
    modal(`Dividir ${fmt(n)} referencias pegadas`,
      `<ul class="ms-confirm">
        <li>Se van a separar <b>${fmt(n)}</b> párrafos que hoy están adentro de otra referencia, en ${fmt(st.nDocs)} tesis.</li>
        <li>Cada corte va <b>donde empieza el párrafo</b> detectado: el texto no se reescribe ni se pierde.</li>
        <li>Las dos partes quedan marcadas como revisadas y el aviso se cierra.</li>
        <li>Se deshace de a una con <b>«Unir con siguiente»</b> en Referencias por tesis.</li>
        <li>Tarda un rato: es un solo guardado al final.</li>
      </ul>`,
      `<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="msRunSplitAll">Dividir las ${fmt(n)}</button>`);
    document.getElementById('msRunSplitAll').onclick = runSplitAll;
  }

  async function runSplitAll(){
    const button = document.getElementById('msRunSplitAll');
    if(button){ button.disabled = true; button.textContent = 'dividiendo…'; }
    try{
      const result = await api(`/api/projects/${encodeURIComponent(S.project.id)}/missing/split-all`, {method: 'POST'});
      closeModal();
      await window.loadDocs?.(S.doc?.id);
      await load();
      notify(`Se separaron ${fmt(result.resolved)} pegadas en ${fmt(result.documents)} tesis · ${fmt(result.references_created)} referencias nuevas.`);
    }catch(err){
      closeModal();
      notify('No se pudieron dividir: ' + err.message);
    }
  }

  async function appendLost(group, item){
    const host = item.preview?.refs?.[0];
    const text = (item.preview?.leftover || []).join(' ');
    if(!host || !text) return;
    try{
      await api(`/api/documents/${encodeURIComponent(group.document_id)}/missing/${encodeURIComponent(item.id)}/append`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({reference_id: host.id, text}),
      });
      drop(group, item);
      if(S.doc?.id === group.document_id) await window.selectDoc(group.document_id);
    }catch(err){ notify('No se pudo agregar el texto: ' + err.message); }
  }

  function editHost(group, item, refId){
    const ref = (item.preview?.refs || []).find(r => r.id === refId);
    if(!ref) return;
    modal(`${group.thesis_id || 'Tesis'} · REF ${String(ref.order).padStart(3, '0')}`,
      `<div class="ms-modalband"><img alt="Recorte de la página ${item.page}" src="/api/documents/${encodeURIComponent(group.document_id)}/missing/${encodeURIComponent(item.id)}/band.png?zoom=1.6"></div>
       <p class="mini">Corregí el texto como aparece en el PDF. Al guardar se vuelve a leer autor, año y tipo.</p>
       <textarea id="modalText">${esc(ref.text)}</textarea>`,
      `<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="msSaveEdit">Guardar</button>`);
    document.getElementById('msSaveEdit').onclick = async () => {
      const text = document.getElementById('modalText')?.value.trim();
      if(!text) return modalWarn('La referencia no puede quedar vacía.');
      try{
        await api(`/api/documents/${encodeURIComponent(group.document_id)}/references/${encodeURIComponent(ref.id)}`, {
          method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text}),
        });
        closeModal();
        await load();
        if(S.doc?.id === group.document_id) await window.selectDoc(group.document_id);
      }catch(err){ modalWarn('No se pudo guardar: ' + err.message); }
    };
  }

  // El corte lo calcula el servidor: empieza donde empieza este párrafo.
  async function splitHost(group, item, force = false){
    try{
      const result = await api(`/api/documents/${encodeURIComponent(group.document_id)}/missing/${encodeURIComponent(item.id)}/split-host${force ? '?force=true' : ''}`, {method: 'POST'});
      drop(group, item);
      const summary = (S.docs || []).find(d => d.id === group.document_id);
      if(summary) summary.n_references = (summary.n_references || 0) + Math.max(0, (result.parts || []).length - 1);
      if(S.doc?.id === group.document_id) await window.selectDoc(group.document_id);
    }catch(err){ notify('No se pudo dividir la referencia: ' + err.message); }
  }

  // Extraer sin salir de la pantalla: el mismo candidato que arma un clic en el PDF.
  async function extract(group, item){
    const section = (group.sections || []).find(s => item.page >= (s.start_page || 1) && item.page <= (s.end_page || 1e9)) || (group.sections || [])[0];
    if(!section) return notify('Esta tesis no tiene una sección de referencias delimitada: abrila y marcala antes de extraer.');
    let candidate;
    try{
      candidate = await api(`/api/documents/${encodeURIComponent(group.document_id)}/references/candidate-from-point`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({page: item.page, y: item.y, end_page: section.end_page, end_y: section.end_y, section_label: section.label || 'Referencias', margin_pt: 42}),
      });
    }catch(err){ return notify('No se pudo formar una referencia desde ese párrafo: ' + err.message); }
    S.missingCandidate = {group, item, candidate};
    const warn = candidate.already_present_ref_id
      ? '<div class="candidatewarn">BiblioRef encontró una referencia muy parecida ya cargada. Revisá antes de duplicarla.</div>' : '';
    modal(`${group.thesis_id || 'Tesis'} · pág. ${candidate.start_page}`,
      `${warn}<div class="ms-modalband"><img alt="Recorte de la página ${item.page}" src="/api/documents/${encodeURIComponent(group.document_id)}/missing/${encodeURIComponent(item.id)}/band.png?zoom=1.6"></div>
       <p class="mini">Revisá el texto antes de agregarlo; sale del PDF tal cual está.</p>
       <textarea id="modalText">${esc(candidate.text)}</textarea>`,
      `<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="msSaveCandidate">Agregar referencia</button>`);
    document.getElementById('msSaveCandidate').onclick = saveCandidate;
  }

  async function saveCandidate(){
    const pending = S.missingCandidate;
    if(!pending) return;
    const text = document.getElementById('modalText')?.value.trim();
    if(!text) return modalWarn('La referencia no puede quedar vacía.');
    const {group, item, candidate} = pending;
    try{
      await api(`/api/documents/${encodeURIComponent(group.document_id)}/references`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text, start_page: candidate.start_page, end_page: candidate.end_page, start_y: candidate.start_y, before_ref_id: candidate.before_ref_id, source: 'human_pdf_click'}),
      });
      await decide(group.document_id, item.id, 'resolved', 'reference_added_from_missing_screen');
      S.missingCandidate = null;
      closeModal();
      drop(group, item);
    }catch(err){ modalWarn('No se pudo agregar la referencia: ' + err.message); }
  }

  document.addEventListener('click', async e => {
    if(e.target.closest('#revisionImport')){
      e.preventDefault();
      document.getElementById('revisionImportFile')?.click();
      return;
    }
    if(e.target.closest('#revisionXlsx')){
      e.preventDefault();
      const doc = state().documentId;
      download(`/api/projects/${encodeURIComponent(S.project.id)}/revision.xlsx${doc ? `?document_id=${encodeURIComponent(doc)}` : ''}`, 'la revisión');
      return;
    }
    if(e.target.closest('#missingXlsx')){
      e.preventDefault();
      download(`/api/projects/${encodeURIComponent(S.project.id)}/avisos.xlsx`, 'los avisos');
      return;
    }
    if(e.target.closest('#missingDataset')){
      e.preventDefault();
      location.href = `/api/projects/${encodeURIComponent(S.project.id)}/dataset.zip?_=${Date.now()}`;
      return;
    }
    const viewBtn = e.target.closest('[data-ms-view]');
    if(viewBtn){
      e.preventDefault();
      state().view = viewBtn.dataset.msView;
      paint();
      document.querySelectorAll('#missingList .ms-band[data-src]').forEach(box => lazy.observe(box));
      return;
    }
    const pageBtn = e.target.closest('[data-ms-page]');
    if(pageBtn){
      e.preventDefault();
      await window.openDoc(pageBtn.dataset.msPagedoc);
      if(S.doc?.id === pageBtn.dataset.msPagedoc){
        S.page = Number(pageBtn.dataset.msPage);
        await window.ensureSectionForPage(S.page);
        await window.renderSectionViewer({scrollPage: S.page});
      }
      return;
    }
    const goto = e.target.closest('[data-ms-goto]');
    if(goto){ e.preventDefault(); state().stage = goto.dataset.msGoto; return load(); }
    if(e.target.closest('[data-ms-splitall]')){ e.preventDefault(); return confirmSplitAll(); }
    const more = e.target.closest('[data-ms-more]');
    if(more){ e.preventDefault(); return load({append: true}); }
    const zip = e.target.closest('[data-ms-zip]');
    if(zip){ e.preventDefault(); location.href = `/api/documents/${encodeURIComponent(zip.dataset.msZip)}/audit-export.zip?_=${Date.now()}`; return; }
    const thesis = e.target.closest('[data-ms-thesis]');
    if(thesis){ e.preventDefault(); return window.openDoc(thesis.dataset.msThesis); }
    const found = e.target.closest('[data-ms-id]') ? itemOf(e.target) : null;
    if(!found) return;
    if(e.target.closest('[data-ms-ignore]')) return ignore(found.group, found.item);
    if(e.target.closest('[data-ms-split]')) return splitHost(found.group, found.item);
    if(e.target.closest('[data-ms-forcesplit]')) return splitHost(found.group, found.item, true);
    if(e.target.closest('[data-ms-append]')) return appendLost(found.group, found.item);
    if(e.target.closest('[data-ms-edit]')) return editHost(found.group, found.item, e.target.closest('[data-ms-edit]').dataset.msEdit);
    if(e.target.closest('[data-ms-resolved]')) return close(found.group, found.item, 'resolved', 'already_extracted');
    if(e.target.closest('[data-ms-add]')) return extract(found.group, found.item);
    if(e.target.closest('[data-ms-open]')){
      await window.openDoc(found.group.document_id);
      if(S.doc?.id === found.group.document_id) await window.focusMissing(found.item.id);
    }
  });

  // A project of a hundred theses takes a few seconds: the work panel says it is being built.
  async function download(url, what){
    const work = startWork(`Armando el Excel de ${what}`, 'Puede tardar unos segundos en un proyecto grande.');
    try{
      const response = await fetch(url, {cache: 'no-store'});
      if(!response.ok) throw new Error(`Error del servidor (código ${response.status}).`);
      const blob = await response.blob();
      const name = (response.headers.get('content-disposition') || '').match(/filename="([^"]+)"/)?.[1] || 'biblioref.xlsx';
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 10000);
      finishWork(work, 'Excel listo', name);
    }catch(err){
      finishWork(work, 'No se pudo armar el Excel', err.message, true);
    }
  }

  // The reviewed Excel comes back: «sí» applies the proposed correction, «no» closes the notice.
  document.addEventListener('change', async e => {
    if(e.target.id !== 'revisionImportFile' || !e.target.files?.length) return;
    const file = e.target.files[0];
    e.target.value = '';
    const body = new FormData();
    body.append('file', file);
    const work = startWork('Aplicando la revisión', file.name);
    let result;
    try{
      result = await api(`/api/projects/${encodeURIComponent(S.project.id)}/revision/import`, {method: 'POST', body});
    }catch(err){
      finishWork(work, 'No se pudo aplicar la revisión', err.message, true);
      return;
    }
    finishWork(work, 'Revisión aplicada', `${fmt(result.n_applied)} cambios.`);
    const labels = {divididas: 'referencias divididas', completadas: 'referencias completadas con el texto perdido',
      agregadas: 'referencias agregadas', 'cerrados sin cambios': 'avisos cerrados sin cambios'};
    const done = Object.entries(result.applied || {}).map(([k, n]) => `<li><b>${fmt(n)}</b> ${esc(labels[k] || k)}</li>`).join('');
    const skipped = (result.skipped || []).map(x => `<tr><td>${esc(x.fila)}</td><td>${esc(x.tesis || '')}</td><td>${esc(x.motivo)}</td></tr>`).join('');
    modal('Revisión aplicada',
      `${done ? `<ul>${done}</ul>` : '<p>No había filas con «sí» o «no» en la columna Decisión.</p>'}
       ${result.documents?.length ? `<p class="mini">Tesis modificadas: ${esc(result.documents.join(', '))}.</p>` : ''}
       ${skipped ? `<p><b>${fmt(result.skipped.length)} filas no se aplicaron</b></p><div class="org-dedupe-table"><table><thead><tr><th>Fila</th><th>Tesis</th><th>Motivo</th></tr></thead><tbody>${skipped}</tbody></table></div>` : ''}`,
      `<button class="btn primary" onclick="closeModal()">Listo</button>`);
    await load();
    if(typeof loadDocs === 'function') loadDocs().catch(() => {});
  });

  let typing = null;
  document.addEventListener('input', e => {
    if(e.target.id !== 'missingSearch') return;
    clearTimeout(typing);
    const value = e.target.value;
    typing = setTimeout(() => { Object.assign(state(), {q: value.trim(), baseline: 0}); load(); }, 300);
  });
  document.addEventListener('change', e => {
    if(e.target.id === 'missingStage'){ Object.assign(state(), {stage: e.target.value, baseline: 0}); load(); }
    else if(e.target.id === 'missingDoc'){ Object.assign(state(), {documentId: e.target.value, baseline: 0}); load(); }
    else if(e.target.id === 'missingOrder'){ state().order = e.target.value; load(); }
  });

  window.BiblioRefMissing = {
    render(){
      const st = state();
      syncStageSelect();
      if(st.projectId !== S.project?.id){ S.missing = null; state().projectId = S.project?.id; }
      fillDocSelect();
      load();
    },
    // Al cambiar de proyecto lo anterior ya no vale.
    reset(){ S.missing = null; const badge = document.getElementById('navMissingCount'); if(badge) badge.textContent = ''; },
  };
})();
