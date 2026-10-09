(() => {
  const originalRenderDocs = window.renderDocs;
  const originalSaveThesisMetadata = window.saveThesisMetadata;
  const originalSelectDoc = window.selectDoc;

  // Theses stored with an older title/front-matter revision are re-read by the
  // server in background processes (started by documents-index). Follow that
  // run and merge the refreshed summaries into the open project as they land.
  let refreshTimer = null;
  function followFrontmatterRefresh(projectId, pending){
    if(!pending || refreshTimer) return;
    let applied = 0;
    const tick = async () => {
      refreshTimer = null;
      if(window.S?.project?.id !== projectId) return;
      let status;
      try{ status = await api(`/api/projects/${encodeURIComponent(projectId)}/frontmatter-refresh`); }
      catch(err){ return; }
      if(status.done - applied >= 20 || (!status.running && status.done > applied)){
        applied = status.done;
        try{
          const d = await api(`/api/projects/${encodeURIComponent(projectId)}/documents-index`);
          if(window.S?.project?.id !== projectId) return;
          const fresh = new Map((d.documents||[]).map(x => [x.id, x]));
          S.docs = S.docs.map(x => fresh.has(x.id) ? {...x, ...fresh.get(x.id)} : x);
          renderCards();renderDashboard();renderProjectHeader();updateGlobal();
        }catch(err){}
      }
      if(status.running) refreshTimer = setTimeout(tick, 5000);
    };
    refreshTimer = setTimeout(tick, 5000);
  }

  // Opening a project must be an index read, not a hidden re-scan of every PDF.
  // Old title/front-matter revisions are re-read in the background (above) or
  // when a thesis is opened.
  window.loadDocs = async function loadDocsFromStoredIndex(selectId=null, importedDocs=null){
    const projectId = window.S?.project?.id;
    if(!projectId){
      S.docs=[];S.doc=null;renderCards();renderDocs();return;
    }
    const d = importedDocs
      ? {documents: importedDocs}
      : await api(`/api/projects/${encodeURIComponent(projectId)}/documents-index`);
    if(S.project?.id!==projectId)return;
    S.docs=d.documents||[];
    if(!S.exportTouched)S.exportIds=new Set(S.docs.filter(x=>x.status!=='uploaded'&&x.status!=='processing').map(x=>x.id));
    else S.exportIds=new Set([...S.exportIds].filter(id=>S.docs.some(d=>d.id===id)));
    renderCards();renderDocs();renderDashboard();updateHeroEmphasis();
    const id=selectId||(S.doc&&S.docs.some(x=>x.id===S.doc.id)&&S.doc.id);
    if(id){if(!importedDocs)await window.selectDoc(id)}else{S.doc=null;renderDocs()}
    await refreshProjectTree();renderProjectHeader();updateGlobal();
    if(!importedDocs) followFrontmatterRefresh(projectId, d.frontmatter_refresh_pending);
  };

  if(typeof originalSelectDoc === 'function'){
    window.selectDoc = async function selectDocWithLazyFrontmatter(id){
      const result = await originalSelectDoc(id);
      const d = window.S?.doc;
      if(d?.id===id){
        const i = S.docs.findIndex(x=>x.id===id);
        if(i>=0){
          S.docs[i] = {
            ...S.docs[i],
            title:d.title,
            title_source:d.title_source,
            title_confirmed:d.title_confirmed,
            metadata:d.metadata,
            metadata_detection:d.metadata_detection,
            cover_metadata_revision:d.cover_metadata_revision,
            title_reading_revision:d.title_reading_revision,
            frontmatter_refresh_pending:d.frontmatter_refresh_pending,
          };
          renderCards();renderDashboard();renderProjectHeader();updateGlobal();
          refreshProjectTree().catch(()=>{});
        }
      }
      return result;
    };
  }

  function augmentFrontmatterFields(){
    const d = window.S?.doc;
    const authorInput = document.querySelector('#meta-author');
    if(!d || !authorInput || document.querySelector('#frontmatterExtraFields')) return;
    const m = d.metadata || {};
    const detection = d.metadata_detection || {};
    const suggestions = detection.suggestions || {};
    const confidence = detection.confidence || {};
    const detected = ['director','codirector','institution'].filter(k => suggestions[k]);
    const hint = detected.length
      ? `Sugerido desde portada/front matter${detected.map(k => confidence[k] ? ` · ${k} ${Math.round(Number(confidence[k])*100)}%` : '').join('')}`
      : (d.frontmatter_refresh_pending
          ? 'Los metadatos de portada se actualizarán al abrir esta tesis.'
          : 'Estos campos se completan automáticamente cuando hay rótulos explícitos en la portada o páginas preliminares.');

    const block = document.createElement('div');
    block.id = 'frontmatterExtraFields';
    block.innerHTML = `
      <div class="thesisgrid">
        <div class="thesisfield"><label>Director/a</label><input id="meta-director" value="${esc(m.director||'')}"></div>
        <div class="thesisfield"><label>Codirector/a</label><input id="meta-codirector" value="${esc(m.codirector||'')}"></div>
      </div>
      <div class="thesisfield"><label>Institución</label><input id="meta-institution" value="${esc(m.institution||'')}"></div>
      <div class="mini" style="margin:-2px 0 8px">${esc(hint)}</div>`;
    authorInput.closest('.thesisfield')?.insertAdjacentElement('afterend', block);
  }

  if(typeof originalRenderDocs === 'function'){
    window.renderDocs = function renderDocsWithFrontmatter(){
      originalRenderDocs();
      augmentFrontmatterFields();
    };
  }

  if(typeof originalSaveThesisMetadata === 'function'){
    window.saveThesisMetadata = async function saveThesisMetadataWithFrontmatter(){
      const docId = window.S?.doc?.id;
      if(docId && document.querySelector('#meta-director')){
        const payload = {
          director: document.querySelector('#meta-director')?.value.trim() || '',
          codirector: document.querySelector('#meta-codirector')?.value.trim() || '',
          institution: document.querySelector('#meta-institution')?.value.trim() || '',
        };
        try{
          await api(`/api/documents/${encodeURIComponent(docId)}/frontmatter-metadata`, {
            method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
          });
        }catch(err){
          notify('No se pudieron guardar director/codirector/institución: ' + err.message);
        }
      }
      return originalSaveThesisMetadata();
    };
  }

  setTimeout(augmentFrontmatterFields, 0);
})();
