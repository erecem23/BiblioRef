/* Bibliography analysis screen.
   The report is never computed when the screen opens: it is a result the user
   asks for. What opens is the last stored one, with its date and whether the
   corpus moved since. Every figure is rendered beside the base it was computed
   over, because a median over 93,8 % of the corpus is a different claim from
   one over all of it. */
(() => {
  const fmt = n => Number(n || 0).toLocaleString('es-AR');
  const pct = n => `${Number(n || 0).toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  const $ = s => document.querySelector(s);

  const GROUPINGS = [
    ['university', 'Universidad'],
    ['program', 'Programa'],
    ['faculty', 'Facultad'],
    ['thesis_year', 'Año de la tesis'],
    ['director', 'Director'],
    ['degree_level', 'Nivel'],
  ];

  const state = { groupBy: 'university', busy: false, data: null, aliases: null };

  // The store holds several projects at once; a report that mixed them would
  // answer a question nobody asked.
  const projectId = () => (window.S && window.S.project && window.S.project.id) || '';

  const when = ts => {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
      ' ' + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
  };

  function metric(label, value, unit) {
    return `<div class="ancard"><div class="k">${esc(label)}</div><div class="v">${value}${unit ? `<small> ${esc(unit)}</small>` : ''}</div></div>`;
  }

  function row(label, value, base, tag) {
    return `<div class="anrow"><div><div class="lbl">${esc(label)}</div>` +
      `${base ? `<div class="base">${esc(base)}${tag ? `<span class="antag">${esc(tag)}</span>` : ''}</div>` : ''}</div>` +
      `<div class="val">${value}</div></div>`;
  }

  function warnings(report) {
    const cov = report.coverage || {};
    const tmp = report.temporal || {};
    const groups = report.groups || {};
    const bits = [];
    if (cov.documents_without_references) bits.push(`${fmt(cov.documents_without_references)} tesis sin ninguna referencia extraída`);
    if (cov.identifiable && cov.identifiable.excluded) bits.push(`${fmt(cov.identifiable.excluded)} referencias sin identificar como obra`);
    if (tmp.out_of_range) bits.push(`${fmt(tmp.out_of_range)} con año fuera de rango`);
    if (groups.ungrouped_documents) bits.push(`${fmt(groups.ungrouped_documents)} tesis sin el dato de agrupamiento`);
    if (!bits.length) return '';
    return `<div class="annote"><span>⚠</span><span><b>Tener en cuenta antes de citar estas cifras.</b> ${esc(bits.join(' · '))}.</span></div>`;
  }

  function cards(report) {
    const ident = report.identity_sensitivity || {};
    const obs = report.obsolescence || {};
    const cov = report.coverage || {};
    return `<div class="ancards">` +
      metric('Obras únicas', fmt(ident.works_with_year)) +
      metric('Mediana de edad', obs.median != null ? fmt(obs.median) : '—', obs.median != null ? 'años' : '') +
      metric('Índice de Price', obs.price_index_pct != null ? pct(obs.price_index_pct) : '—') +
      metric('Con DOI', cov.fields ? pct(cov.fields.doi.pct) : '—') +
      `</div>`;
  }

  function detail(report) {
    const cov = report.coverage || {};
    const obs = report.obsolescence || {};
    const ident = report.identity_sensitivity || {};
    const f = cov.fields || {};
    const out = [];

    if (obs.median != null) {
      out.push(row('Mediana de edad de las referencias', `${fmt(obs.median)} años`,
        `sobre ${fmt(obs.base)} de ${fmt(cov.references)} · media ${fmt(obs.mean)} · p25 ${fmt(obs.p25)} · p75 ${fmt(obs.p75)}`,
        obs.excluded ? `${fmt(obs.excluded)} sin año usable` : ''));
      out.push(row('Índice de Price', pct(obs.price_index_pct), `referencias de 5 años o menos, sobre ${fmt(obs.base)}`));
      out.push(row('Referencias de más de 20 años', pct(obs.over_20_pct), `sobre ${fmt(obs.base)}`));
    }
    if (cov.identifiable) {
      out.push(row('Obras únicas identificadas', fmt(ident.works_with_year),
        `desde ${fmt(cov.identifiable.n)} referencias identificables`,
        cov.identifiable.excluded ? `${fmt(cov.identifiable.excluded)} sin identificar` : ''));
      out.push(row('Obras que se fusionan si se ignora la edición', fmt(ident.works_merged_by_ignoring_year),
        'diferencia entre contar o no el año como parte de la obra'));
    }
    if (f.doi) {
      out.push(row('Referencias con DOI', pct(f.doi.pct), `${fmt(f.doi.n)} de ${fmt(cov.references)} · sin resolución externa`));
      out.push(row('Con revista identificada', pct(f.journal.pct), `${fmt(f.journal.n)} de ${fmt(cov.references)}`));
    }
    return `<div class="ansec"><h2>Cifras con su base</h2>${out.join('')}</div>`;
  }

  function types(report) {
    const t = report.document_types || {};
    if (!t.types || !t.types.length) return '';
    const items = t.types.slice(0, 8).map(x =>
      `<div class="anitem"><div class="top"><span class="name">${esc(x.type)}</span>` +
      `<span class="num">${fmt(x.n)} · ${pct(x.pct)}</span></div>` +
      `<div class="antrack"><i style="width:${Math.max(x.pct, 0.4)}%"></i></div></div>`).join('');
    return `<div class="ansec"><h2>Tipos documentales <span class="mini">sobre ${fmt(t.base)}</span></h2><div class="anbarlist">${items}</div></div>`;
  }

  function aliasSection() {
    const a = state.aliases;
    if (!a || !a.aliasable) return '';
    const activos = Object.entries(a.aliases || {});
    let html = '';

    if (a.suggestions && a.suggestions.length) {
      html += a.suggestions.map((s, i) => {
        const certeza = s.identical_once_normalised
          ? 'escritas distinto, mismo nombre'
          : `parecidas al ${pct(s.ratio * 100)}`;
        return `<div class="anitem"><div class="top"><span class="name">` +
          `${esc(s.a)} <span class="num">(${fmt(s.a_theses)})</span> ↔ ${esc(s.b)} <span class="num">(${fmt(s.b_theses)})</span>` +
          `</span></div>` +
          `<div class="base" style="margin-top:4px">${esc(certeza)} · si son la misma, se cuenta como ` +
          `<b>${esc(s.suggested_canonical)}</b></div>` +
          `<div style="margin-top:7px;display:flex;gap:8px;flex-wrap:wrap">` +
          `<button class="btn xs" data-alias-i="${i}" data-alias-dir="a">Unificar en «${esc(s.suggested_canonical)}»</button>` +
          `<button class="btn xs" data-alias-i="${i}" data-alias-dir="b">Unificar en «${esc(s.suggested_variant)}»</button>` +
          `</div></div>`;
      }).join('');
      html = `<h2>¿Son la misma? <span class="mini">se cuentan por separado hasta que lo decidas</span></h2>` +
        `<div class="anbarlist">${html}</div>`;
    }

    if (activos.length) {
      html += `<h2 style="margin-top:18px">Unificadas <span class="mini">decisión tuya, guardada en el proyecto</span></h2>` +
        `<div class="anpairs">` + activos.map(([v, c]) =>
          `<div>${esc(v)} → <b>${esc(c)}</b> <button class="btn xs" data-alias-undo="${esc(v)}" style="margin-left:8px">Deshacer</button></div>`
        ).join('') + `</div>`;
    }

    return html ? `<div class="ansec">${html}</div>` : '';
  }

  async function setAlias(variant, canonical) {
    try {
      await window.api('/api/analysis/aliases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId(), field: state.groupBy, variant, canonical }),
      });
    } catch (e) {
      const body = $('#anBody');
      if (body) body.insertAdjacentHTML('afterbegin', `<div class="annote"><span>⚠</span><span>${esc(e.message)}</span></div>`);
      return;
    }
    await loadAliases();
    await load();
  }

  function bindAliasButtons() {
    document.querySelectorAll('[data-alias-i]').forEach(btn => {
      btn.onclick = () => {
        const s = state.aliases.suggestions[Number(btn.dataset.aliasI)];
        if (!s) return;
        const canonical = btn.dataset.aliasDir === 'a' ? s.suggested_canonical : s.suggested_variant;
        const variant = btn.dataset.aliasDir === 'a' ? s.suggested_variant : s.suggested_canonical;
        setAlias(variant, canonical);
      };
    });
    document.querySelectorAll('[data-alias-undo]').forEach(btn => {
      btn.onclick = () => setAlias(btn.dataset.aliasUndo, '');
    });
  }

  async function loadAliases() {
    try {
      state.aliases = await window.api(
        `/api/analysis/alias-suggestions?group_by=${encodeURIComponent(state.groupBy)}&project_id=${encodeURIComponent(projectId())}`);
    } catch {
      state.aliases = null;
    }
  }

  function groupsSection(report) {
    const g = report.groups;
    if (!g || !g.groups || !g.groups.length) return '';
    const label = (GROUPINGS.find(x => x[0] === g.by) || ['', g.by])[1];
    const items = g.groups.map(x => {
      const med = x.obsolescence && x.obsolescence.median != null ? `${fmt(x.obsolescence.median)} a` : '—';
      return `<div class="anitem"><div class="top"><span class="name">${esc(x.group)}</span>` +
        `<span class="num">${fmt(x.theses)} tesis · ${fmt(x.references)} refs · ${fmt(x.refs_per_thesis)} por tesis · mediana ${med}</span></div>` +
        `<div class="antrack"><i style="width:${Math.max(x.doi_pct, 0.4)}%"></i></div>` +
        `<div class="base" style="margin-top:4px">DOI ${pct(x.doi_pct)} · ${fmt(x.works)} obras</div></div>`;
    }).join('');
    const overlaps = (g.overlaps || []).slice(0, 5).map(o =>
      `<div><span class="n">${fmt(o.shared_works)} obras</span>${esc(o.a)} ↔ ${esc(o.b)} <span class="n">J=${o.jaccard.toLocaleString('es-AR', { minimumFractionDigits: 4, maximumFractionDigits: 4 })}</span></div>`).join('');
    return `<div class="ansec"><h2>Comparación por ${esc(label.toLowerCase())} <span class="mini">${fmt(g.documents - g.ungrouped_documents)} de ${fmt(g.documents)} tesis agrupadas</span></h2>` +
      `<div class="anbarlist">${items}</div>` +
      (overlaps ? `<h2 style="margin-top:18px">Bibliografía compartida entre grupos</h2><div class="anpairs">${overlaps}</div>` : '') +
      `</div>`;
  }

  function works(report) {
    const w = (report.top_works || {}).works || [];
    const s = (report.top_sources || {}).sources || [];
    let html = '';
    if (w.length) {
      html += `<div class="ansec"><h2>Obras más citadas <span class="mini">por cantidad de tesis que la citan</span></h2><div class="anpairs">` +
        w.slice(0, 10).map(x => `<div><span class="n">${fmt(x.theses)} tesis</span>${esc((x.title || '').slice(0, 90))}</div>`).join('') +
        `</div></div>`;
    }
    if (s.length) {
      html += `<div class="ansec"><h2>Revistas más citadas <span class="mini">sobre ${fmt((report.top_sources || {}).base)} referencias con revista</span></h2><div class="anpairs">` +
        s.slice(0, 10).map(x => `<div><span class="n">${fmt(x.references)} refs</span>${esc((x.journal || '').slice(0, 80))} <span class="n">en ${fmt(x.theses)} tesis</span></div>`).join('') +
        `</div></div>`;
    }
    return html;
  }

  function network(report) {
    const c = report.coupling || {};
    const co = report.co_citation || {};
    let html = '';
    if ((c.pairs || []).length) {
      html += `<div class="ansec"><h2>Tesis que comparten bibliografía <span class="mini">desde ${fmt(c.min_shared)} obras en común</span></h2><div class="anpairs">` +
        c.pairs.slice(0, 8).map(p => `<div><span class="n">${fmt(p.shared_works)} obras</span>${esc((p.a_title || '').slice(0, 42))} ↔ ${esc((p.b_title || '').slice(0, 42))} <span class="n">J=${p.jaccard.toLocaleString('es-AR', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}</span></div>`).join('') +
        `</div></div>`;
    }
    if ((co.pairs || []).length) {
      html += `<div class="ansec"><h2>Obras citadas juntas <span class="mini">en ${fmt(co.min_theses)} tesis o más</span></h2><div class="anpairs">` +
        co.pairs.slice(0, 8).map(p => `<div><span class="n">${fmt(p.theses)} tesis</span>${esc((p.a_title || '').slice(0, 40))} ↔ ${esc((p.b_title || '').slice(0, 40))}</div>`).join('') +
        `</div></div>`;
    }
    return html;
  }

  function render() {
    const body = $('#anBody');
    const meta = $('#anMeta');
    const runBtn = $('#anRun');
    const exportBtn = $('#anExport');
    if (!body) return;

    const d = state.data;
    if (state.busy) {
      meta.textContent = 'Analizando la bibliografía…';
      runBtn.disabled = true;
      return;
    }
    runBtn.disabled = false;

    if (!d || d.status === 'never_run' || !d.report) {
      exportBtn.disabled = true;
      meta.textContent = '';
      body.innerHTML = `<div class="anempty"><h2>Todavía no analizaste la bibliografía</h2>` +
        `<p>El análisis no se calcula solo: recorre todas las referencias del proyecto y produce un reporte con su fecha. ` +
        `Cuando lo pidas, cada cifra va a venir con la base sobre la que se calculó.</p></div>`;
      return;
    }

    exportBtn.disabled = false;
    runBtn.textContent = 'Volver a analizar';
    
    meta.innerHTML = `Analizado el ${esc(when(d.generated_at))}` + (d.elapsed_s ? ` · ${fmt(d.elapsed_s)} s` : '');

    const stale = d.status === 'stale'
      ? `<div class="annote"><span>⚠</span><span><b>El corpus cambió desde este análisis.</b> Las cifras de abajo son las del ${esc(when(d.generated_at))}. Volvé a analizar para actualizarlas.</span></div>`
      : '';

    const r = d.report;
    body.innerHTML = stale + cards(r) + warnings(r) + detail(r) + types(r) + aliasSection() + groupsSection(r) + works(r) + network(r) +
      `<div class="anfoot">${esc(r.version || '')} · identidad de obra ${esc((r.coverage || {}).identity_version || '')} · ` +
      `sin resolución externa: las obras se agrupan por autor, año y título normalizados.</div>`;
    bindAliasButtons();
  }

  async function load() {
    try {
      state.data = await window.api(`/api/analysis?group_by=${encodeURIComponent(state.groupBy)}&project_id=${encodeURIComponent(projectId())}`);
    } catch (e) {
      state.data = null;
      const body = $('#anBody');
      if (body) body.innerHTML = `<div class="annote"><span>⚠</span><span>${esc(e.message)}</span></div>`;
      return;
    }
    render();
  }

  async function reload() {
    await loadAliases();
    await load();
  }

  async function run() {
    state.busy = true;
    render();
    try {
      state.data = await window.api('/api/analysis/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_by: state.groupBy, project_id: projectId() }),
      });
    } catch (e) {
      const body = $('#anBody');
      if (body) body.innerHTML = `<div class="annote"><span>⚠</span><span>${esc(e.message)}</span></div>`;
    } finally {
      state.busy = false;
      await loadAliases();
      render();
    }
  }

  function boot() {
    const select = $('#anGroupBy');
    if (select && !select.options.length) {
      select.innerHTML = GROUPINGS.map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('');
      select.value = state.groupBy;
      select.onchange = () => { state.groupBy = select.value; reload(); };
    }
    const runBtn = $('#anRun');
    if (runBtn && !runBtn.dataset.bound) { runBtn.dataset.bound = '1'; runBtn.onclick = run; }
    const exportBtn = $('#anExport');
    if (exportBtn && !exportBtn.dataset.bound) {
      exportBtn.dataset.bound = '1';
      exportBtn.onclick = () => { window.location.href = `/api/analysis/export.json?group_by=${encodeURIComponent(state.groupBy)}&project_id=${encodeURIComponent(projectId())}`; };
    }
    reload();
  }

  document.querySelectorAll('[data-screen="analysis"]').forEach(b => {
    b.addEventListener('click', boot);
  });
  if (document.readyState !== 'loading') {
    if (document.querySelector('#screen-analysis.active')) boot();
  } else {
    document.addEventListener('DOMContentLoaded', () => {
      if (document.querySelector('#screen-analysis.active')) boot();
    });
  }
})();
