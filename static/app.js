const S={
  projects:[],project:null,projectTree:[],importBusy:false,treeClosed:new Set(),
  docs:[],doc:null,page:1,selectedRef:null,origin:null,zoom:1.10,token:null,
  markMode:null,addFromPdfMode:false,activeSection:0,sectionPreview:null,renderSeq:0,
  exportIds:new Set(),exportTouched:false,pdfCandidate:null,previewTimer:null,pendingMissingId:null,
  autoUpdating:new Set(),viewerToastTimer:null,dashboardIds:new Set(),dashboardTouched:false,cleanVisualText:true,driveStack:[],driveStatus:null,
  dashboardView:'table',dashboardGroupBy:'university',refView:'cards',capabilities:null,parsedSaving:new Set(),pipelineLayers:new Set(),pipelineTouched:false,resolutionRunning:new Set(),
  originCache:{},hoverRefId:null,hoverTimer:null
};
window.S=S;
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];

async function api(url,opt={}){
  opt={...opt,headers:{...(opt.headers||{})}};
  if((opt.method||'GET').toUpperCase()!=='GET'&&S.token)opt.headers['X-BiblioRef-Token']=S.token;
  opt.cache='no-store';const sep=url.includes('?')?'&':'?';const target=(opt.method||'GET').toUpperCase()==='GET'?url+sep+'_nocache='+Date.now():url;const r=await fetch(target,opt);
  if(!r.ok){let m=await r.text();try{m=JSON.parse(m).detail||m}catch{if(/^\s*</.test(m))m=`Error del servidor (código ${r.status}).`}throw new Error(m)}
  const ct=r.headers.get('content-type')||'';
  return ct.includes('json')?r.json():r.text();
}
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function titleOf(d){return d?.title||d?.filename||'Tesis'}

const VISUAL_FUNCTION_WORDS=new Set([
  'a','al','as','and','at','con','da','das','de','del','do','dos','e','el','en','for','from','in','la','las','los','of','on','or','para','por','the','to','un','una','y'
]);
const VISUAL_A_WORDS=new Set([
  'case','critical','guide','history','method','model','new','note','perspective','proposal','qualitative','quantitative','report','review','study','survey','systematic','theoretical',
  'modo','nivel','partir','pesar','propósito','través','vez'
]);
function visualText(value){
  let t=String(value??'');
  try{t=t.normalize('NFC')}catch(e){}
  t=t.replace(/[\u00ad\u200b\u2060\ufffe\uffff]/g,'').replace(/\s+/g,' ').trim();
  t=t.replace(/\s+([,.;:!?%\)\]\}])/g,'$1').replace(/([\(\[\{¿¡])\s+/g,'$1');
  // PDF antiguos suelen separar un apellido por cambios de span: "Sevilla G uzmán".
  // Sólo se repara cuando hay contexto lexical a la izquierda, para no convertir
  // títulos normales como "A study" en "Astudy".
  for(let pass=0;pass<2;pass++){
    t=t.replace(/\b([A-ZÁÉÍÓÚÜÑÀ-Þ])\s+([a-záéíóúüñà-ÿ]{2,})\b/g,(m,a,b,offset,src)=>{
      const prev=src.slice(Math.max(0,offset-30),offset);
      const prevWord=(prev.match(/([A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ]{2,})[\s,;:&.-]*$/)||[])[1]||'';
      const low=b.toLowerCase();
      if((a==='A'||a==='I')&&VISUAL_A_WORDS.has(low))return m;
      if(VISUAL_FUNCTION_WORDS.has(low))return m;
      return prevWord?a+b:m;
    });
  }
  // Completa apellidos/nombres partidos por más de un cambio de span: Guzm án -> Guzmán.
  for(let pass=0;pass<2;pass++){
    t=t.replace(/\b([A-ZÁÉÍÓÚÜÑÀ-Þ][a-záéíóúüñà-ÿ]{2,})\s+([a-záéíóúüñà-ÿ]{1,3})(?=[,.;:)\s])/g,(m,a,b)=>VISUAL_FUNCTION_WORDS.has(b.toLowerCase())?m:a+b);
  }
  t=t.replace(/(^|[.;]\s+)([A-ZÁÉÍÓÚÜÑ])\s+([a-záéíóúüñà-ÿ]{2,4})\s+([a-záéíóúüñà-ÿ]{2,4})(?=[,;])/g,(m,p,a,b,c)=>p+a+b+c);
  // Corrige secuencias inequívocamente letter-spaced (tres o más letras sueltas).
  t=t.replace(/\b(?:[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ]\s+){2,}[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ]\b/g,m=>m.replace(/\s+/g,''));
  // Fragmentaciones frecuentes de palabras funcionales producidas por PDFs con
  // kerning/encoding defectuoso. Son deliberadamente pocas y conservadoras.
  const repairs=[
    [/\bL a\b/g,'La'],[/\bE l\b/g,'El'],[/\bU n\b/g,'Un'],[/\bU na\b/g,'Una'],
    [/\bd e\b/gi,'de'],[/\be l\b/gi,'el'],[/\be n\b/gi,'en'],[/\bc o n\b/gi,'con'],
    [/\bco m o\b/gi,'como'],[/\bp o r\b/gi,'por'],[/\bp a ra\b/gi,'para'],[/\bq u e\b/gi,'que']
  ];
  repairs.forEach(([rx,repl])=>{t=t.replace(rx,repl)});
  return t.replace(/\s{2,}/g,' ').trim();
}
function displayTitle(d){return visualText(titleOf(d))}
function displayRefText(r){return S.cleanVisualText?visualText(r?.text||''):(r?.text||'')}
function thesisNumber(d){const m=String(d?.thesis_id||'').match(/(\d+)$/);return m?String(parseInt(m[1],10)):''}
function thesisLabel(d){const n=thesisNumber(d);return `${n?n+' — ':''}${displayTitle(d)}`}
function metaOf(d){return d?.metadata||{}}
function statusText(d){if(d.analysis_stale)return 'actualizar';return d.status==='uploaded'?'sin procesar':d.status==='processing'?'procesando':(d.status==='review'||d.status==='error')?'revisar':'lista'}
function pillClass(d){if(d.analysis_stale||d.status==='review'||d.status==='error')return 'warn';if(d.status==='uploaded'||d.status==='processing')return 'neutral';return 'ok'}
function processableDocs(){return S.docs.filter(d=>d.status==='uploaded'||(d.analysis_stale&&!d.has_manual_work))}
function updateHeroEmphasis(){const pending=processableDocs().length,load=$('#loadMenu>summary'),go=$('#analyzeAll');if(!load||!go)return;load.classList.toggle('primary',pending===0);go.classList.toggle('primary',pending>0);go.textContent=pending?`Procesar${pending>1?' '+pending:''}`:'Procesar'}
function refStatusLabel(s){return ({reviewed:'revisada',extracted:'extraída',truncated:'truncada',possibly_merged:'pegadas'})[s]||s||'extraída'}
function refSourceLabel(s){return ({automatic:'auto',manual:'delimitada',human_insert:'manual',human_pdf_click:'desde PDF',human_paste:'pegada'})[s]||s||'auto'}

const SCREEN_LABELS={new:'Inicio',collection:'Tesis del proyecto',project:'Resumen',missing:'Faltantes',review:'Referencias por tesis',export:'Exportar'};
function show(name){
  if(name!=='new'&&!S.project)name='new';
  if(name==='review'&&!S.doc){
    if(S.docs.length){selectDoc(S.docs[0].id).then(()=>{if(S.doc)show('review')}).catch(e=>notify(e.message));return}
    name='collection';
  }
  $$('.screen').forEach(x=>x.classList.remove('active'));$('#screen-'+name).classList.add('active');
  $$('.nav button').forEach(x=>x.classList.toggle('active',x.dataset.screen===name));
  const label=$('#topbarLabel');if(label)label.textContent=SCREEN_LABELS[name]||'BiblioRef';
  if(name==='new'){loadProjects().catch(e=>notify('No se pudieron cargar los proyectos: '+e.message));$('#globalStatus').textContent='Proyectos guardados en este equipo'}
  else updateGlobal();
  if(name==='export')renderExport();
  if(name==='project')renderDashboard();
  if(name==='missing')window.BiblioRefMissing?.render();
  if(name==='review'&&S.doc)renderSectionViewer({scrollPage:S.page});
}
$$('[data-screen]').forEach(b=>b.onclick=()=>show(b.dataset.screen));

async function health(){const h=await api('/api/health');S.token=h.session_token;$('#version').textContent='v'+h.software_version;$('#globalStatus').textContent='local · algoritmo '+h.algorithm_version;try{S.capabilities=await api('/api/capabilities')}catch(e){console.warn('capabilities',e)}renderLayerOptions()}
async function loadDocs(selectId=null,importedDocs=null){
  const projectId=S.project?.id;if(!projectId){S.docs=[];S.doc=null;renderCards();renderDocs();return}
  const d=importedDocs?{documents:importedDocs}:await api('/api/documents?project_id='+encodeURIComponent(projectId));if(S.project?.id!==projectId)return;S.docs=d.documents;
  if(!S.exportTouched)S.exportIds=new Set(S.docs.filter(x=>x.status!=='uploaded'&&x.status!=='processing').map(x=>x.id));
  else S.exportIds=new Set([...S.exportIds].filter(id=>S.docs.some(d=>d.id===id)));
  renderCards();renderDocs();renderDashboard();updateHeroEmphasis();
  const id=selectId||(S.doc&&S.docs.some(x=>x.id===S.doc.id)&&S.doc.id);
  if(id){if(!importedDocs)await selectDoc(id)}else{S.doc=null;renderDocs()}
  await refreshProjectTree();renderProjectHeader();updateGlobal();
}
function updateGlobal(){if($('#screen-new').classList.contains('active')){$('#globalStatus').textContent='Proyectos guardados en este equipo';return}const n=S.docs.length,r=S.docs.reduce((a,d)=>a+(d.n_references||0),0);$('#globalStatus').textContent=`${n} tesis · ${r} referencias · local`}
function renderCards(){
  const el=$('#uploadCards');if(!el)return;$('#collectionCount').textContent=S.docs.length;$('#analyzeAll').disabled=S.importBusy||S.analysisBusy||!S.docs.length;
  const visibleDocs=S.docs.filter(matchesCollectionSearch);
  $('#collectionSearchCount').textContent=$('#collectionSearch').value.trim()?`${visibleDocs.length} de ${S.docs.length} tesis`:'';
  el.innerHTML=visibleDocs.map(d=>{const warn=d.status==='review'||d.status==='error'||d.analysis_stale;const stale=d.analysis_stale?`<div class="mini" style="color:var(--warn);margin-top:5px">Extracción guardada con ${esc(d.analysis_versions?.software_version||'una versión anterior')}; motor actual ${esc(d.current_versions?.software_version||'')}</div>`:'';return `<div class="card ${S.collectionFocusedId===d.id?'selected':''}" data-card-id="${esc(d.id)}" tabindex="-1"><div><div class="cardtitle">${esc(displayTitle(d))}</div><div class="cardfile">${esc(thesisNumber(d)||'')} · ${esc(d.filename)}</div><div class="mini" style="margin-top:4px">${d.page_count} páginas · ${d.size_mb} MB · ${d.n_references||0} refs</div>${d.preflight?.predominantly_scanned?'<span class="pill warn">parece escaneado</span>':''}<span class="pill ${pillClass(d)}">${statusText(d)}</span>${stale}</div><div class="actions"><button class="btn ${(d.status==='uploaded'||d.analysis_stale)?'primary':''}" ${S.importBusy||S.analysisBusy?'disabled':''} onclick="analyzeOne('${d.id}','stable',true)">${d.status==='uploaded'?'Procesar':d.analysis_stale?'Actualizar a v'+(d.current_versions?.software_version||'actual'):'Reprocesar'}</button><button class="btn" onclick="openDoc('${d.id}')">Revisar</button><button class="btn warn" ${S.importBusy||S.analysisBusy?'disabled':''} onclick="removeDoc('${d.id}')">Quitar</button></div></div>`}).join('')||(S.docs.length?'<div class="projects-empty"><b>No se encontraron tesis</b><p>Probá con otro título, archivo o universidad.</p></div>':'<div class="projects-empty"><b>El proyecto está listo para recibir tesis</b><p>Cargá archivos para comenzar.</p></div>');
}
function processedDocs(){return S.docs.filter(d=>d.status!=='uploaded'&&d.status!=='processing')}
function syncDashboardSelection(){
  if(!S.dashboardTouched&&S.dashboardIds.size===0)S.dashboardIds=new Set(processedDocs().map(d=>d.id));
  S.dashboardIds=new Set([...S.dashboardIds].filter(id=>S.docs.some(d=>d.id===id)));
}
function renderDashboard(){
  const stats=$('#projectStats'),table=$('#dashboardTable');if(!stats||!table)return;syncDashboardSelection();
  const done=processedDocs(),counts=done.map(d=>d.n_references||0),total=counts.reduce((a,b)=>a+b,0),min=counts.length?Math.min(...counts):0,max=counts.length?Math.max(...counts):0;
  stats.innerHTML=`<div class="statbox"><div class="value">${S.docs.length}</div><div class="label">tesis</div></div><div class="statbox"><div class="value">${done.length}</div><div class="label">procesadas</div></div><div class="statbox"><div class="value">${total}</div><div class="label">referencias</div></div><div class="statbox"><div class="value">${min}</div><div class="label">mínimo por tesis</div></div><div class="statbox"><div class="value">${max}</div><div class="label">máximo por tesis</div></div>`;
  table.innerHTML=S.dashboardView==='grouped'?renderDashboardGroups():`<table class="dashtable"><thead><tr><th></th><th>ID</th><th>Tesis</th><th>Universidad / área</th><th>Estado</th><th style="text-align:right">Referencias</th><th></th></tr></thead><tbody>${S.docs.map(d=>{const m=metaOf(d),sel=S.dashboardIds.has(d.id);return `<tr><td><input type="checkbox" ${sel?'checked':''} onchange="toggleDashboard('${d.id}',this.checked)"></td><td>${esc(thesisNumber(d)||'—')}</td><td><div class="dash-title">${esc(displayTitle(d))}</div><div class="dash-sub">${esc(d.filename)}</div></td><td><div>${esc(m.university||'—')}</div><div class="dash-sub">${esc(m.area||'')}</div></td><td><span class="pill ${pillClass(d)}">${statusText(d)}</span></td><td class="numcol"><b>${d.n_references||0}</b></td><td><button class="btn xs" onclick="openDoc('${d.id}')">Abrir</button></td></tr>`}).join('')||'<tr><td colspan="7">Todavía no hay tesis en el proyecto.</td></tr>'}</tbody></table>`;
  const selected=S.docs.filter(d=>S.dashboardIds.has(d.id));$('#dashSelectionSummary').textContent=`${selected.length} seleccionada(s) · ${selected.reduce((n,d)=>n+(d.n_references||0),0)} referencias`;
}
function groupKeyFor(d,by){
  const m=metaOf(d);
  if(by==='university')return m.university||'Sin universidad';
  if(by==='area')return m.area||'Sin área / disciplina';
  if(by==='status')return statusText(d);
  return 'Todas';
}
function renderDashboardGroups(){
  const by=S.dashboardGroupBy,groups=new Map();
  S.docs.forEach(d=>{const key=groupKeyFor(d,by);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(d)});
  if(!groups.size)return '<div class="mini" style="padding:14px">Todavía no hay tesis en el proyecto.</div>';
  const keys=[...groups.keys()].sort((a,b)=>a.localeCompare(b,'es'));
  return `<div class="groupedlist">${keys.map(key=>{
    const docs=groups.get(key),refs=docs.reduce((n,d)=>n+(d.n_references||0),0);
    return `<details class="groupbox" open><summary><span class="groupname">${esc(key)}</span><span class="groupmeta">${docs.length} tesis · ${refs} referencias</span></summary><div class="groupdocs">${docs.map(d=>{const sel=S.dashboardIds.has(d.id);return `<div class="grouprow"><input type="checkbox" ${sel?'checked':''} onchange="toggleDashboard('${d.id}',this.checked)"><div class="grouprow-title" title="${esc(displayTitle(d))}">${esc(displayTitle(d))}</div><span class="pill ${pillClass(d)}">${statusText(d)}</span><span class="numcol">${d.n_references||0} refs</span><button class="btn xs" onclick="openDoc('${d.id}')">Abrir</button></div>`}).join('')}</div></details>`;
  }).join('')}</div>`;
}
$$('#dashViewToggle button').forEach(b=>b.onclick=()=>{S.dashboardView=b.dataset.view;$$('#dashViewToggle button').forEach(x=>x.classList.toggle('active',x===b));$('#dashGroupBy').classList.toggle('hidden',S.dashboardView!=='grouped');renderDashboard()});
$('#dashGroupBy').onchange=e=>{S.dashboardGroupBy=e.target.value;renderDashboard()};
window.toggleDashboard=(id,on)=>{S.dashboardTouched=true;if(on)S.dashboardIds.add(id);else S.dashboardIds.delete(id);renderDashboard()};
function selectedDashboardIds(){return [...S.dashboardIds]}
function openExportModal(ids,title='Exportar'){
  const valid=ids.filter(id=>S.docs.some(d=>d.id===id&&d.status!=='uploaded'&&d.status!=='processing'));if(!valid.length)return notify('Seleccioná al menos una tesis procesada.');
  const q=encodeURIComponent(valid.join(','));modal(title,`<div class="candidateinfo">${valid.length} tesis · ${valid.reduce((n,id)=>n+(S.docs.find(d=>d.id===id)?.n_references||0),0)} referencias</div><div class="exportpop"><button class="btn primary" onclick="downloadSelection('xlsx','${q}')">Excel</button><button class="btn" onclick="downloadSelection('csv','${q}')">CSV</button><button class="btn" onclick="downloadSelection('json','${q}')">JSON</button>${valid.length===1?`<button class="btn" title="Informe de auditoría con los recortes de cada faltante" onclick="downloadAudit('${valid[0]}')">Auditoría (.zip)</button>`:''}</div>`,`<button class="btn" onclick="closeModal()">Cerrar</button>`)
}
window.downloadAudit=id=>{location.href=`/api/documents/${id}/audit-export.zip?_nocache=${Date.now()}`};
window.downloadSelection=(fmt,q)=>{location.href=`/api/project/export/selection/${fmt}?documents=${q}&_nocache=${Date.now()}`};
function bulkMetadataModal(initialIds=[]){
  const checked=new Set(initialIds.length?initialIds:S.docs.map(d=>d.id));
  const docs=S.docs.map(d=>`<label><input type="checkbox" class="bulk-doc" value="${d.id}" ${checked.has(d.id)?'checked':''}> ${esc(thesisLabel(d))}</label>`).join('');
  const body=`<div class="mini">Elegí varias tesis y completá sólo los campos comunes que quieras aplicar. Los campos vacíos no modifican nada.</div><div class="bulkdocs">${docs}</div><div class="bulkbox"><div class="thesisgrid"><div class="thesisfield"><label>Universidad</label><input id="bulk-university"></div><div class="thesisfield"><label>País</label><input id="bulk-country"></div></div><div class="thesisfield"><label>Facultad / unidad académica</label><input id="bulk-faculty"></div><div class="thesisfield"><label>Programa / carrera</label><input id="bulk-program"></div><div class="thesisfield"><label>Repositorio</label><input id="bulk-repository"></div><div class="thesisfield"><label>URL del repositorio</label><input id="bulk-repository_url"></div><div class="thesisfield"><label>Área / disciplina</label><input id="bulk-area"></div></div>`;
  modal('Editar datos comunes',body,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="saveBulkMetadata()">Aplicar a seleccionadas</button>`)
}
window.saveBulkMetadata=async()=>{const document_ids=$$('.bulk-doc:checked').map(x=>x.value);if(!document_ids.length)return modalWarn('Elegí al menos una tesis.');const fields={};for(const k of ['university','country','faculty','program','repository','repository_url','area']){const v=$('#bulk-'+k).value.trim();if(v)fields[k]=v}if(!Object.keys(fields).length)return modalWarn('Completá al menos un dato común.');try{await api('/api/documents/bulk-metadata',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({document_ids,fields})});closeModal();await loadDocs(S.doc?.id);renderDashboard()}catch(e){modalWarn('No se pudo guardar: '+e.message)}};
function renderDocs(){
  const detailSummary=document.querySelector('.thesisdetails>summary');if(detailSummary)detailSummary.textContent='Datos de la tesis';
  const sel=$('#thesisSelect');if(!sel)return;const current=S.doc?.id||'';
  sel.innerHTML='<option value="">Elegí una tesis</option>'+S.docs.map(d=>`<option value="${d.id}" ${d.id===current?'selected':''}>${esc(thesisLabel(d))}</option>`).join('');
  const d=S.doc,sum=$('#docSummary');if(!d){sum.innerHTML='<div class="mini">No hay tesis seleccionada.</div>';return}
  const m=metaOf(d),n=thesisNumber(d);
  sum.innerHTML=`<div class="thesisdata"><div class="thesisdata-head"><span class="mini">${n?'ID '+esc(n):''}</span></div>
    <div class="thesisfield"><label>Título</label><textarea id="meta-title">${esc(displayTitle(d))}</textarea></div>
    <div class="thesisfield"><label>Autor/a</label><input id="meta-author" value="${esc(m.author||'')}"></div>
    <div class="thesisgrid"><div class="thesisfield"><label>Año</label><input id="meta-year" value="${esc(m.year||'')}"></div><div class="thesisfield"><label>País</label><input id="meta-country" value="${esc(m.country||'')}"></div></div>
    <div class="thesisfield"><label>Universidad</label><input id="meta-university" value="${esc(m.university||'')}"></div>
    <div class="thesisfield"><label>Facultad / unidad académica</label><input id="meta-faculty" value="${esc(m.faculty||'')}"></div>
    <div class="thesisfield"><label>Programa / carrera</label><input id="meta-program" value="${esc(m.program||'')}"></div>
    <div class="thesisfield"><label>Repositorio</label><input id="meta-repository" value="${esc(m.repository||'')}"></div>
    <div class="thesisfield"><label>URL del registro</label><input id="meta-repository_url" value="${esc(m.repository_url||'')}"></div>
    <div class="thesisfield"><label>Área / disciplina</label><input id="meta-area" value="${esc(m.area||'')}"></div>
    <div class="actions"><button class="btn primary xs" onclick="saveThesisMetadata()">Guardar datos</button></div>
    <div class="thesisfile">archivo · ${esc(d.filename)}</div></div>`;
}
window.saveThesisMetadata=async()=>{if(!S.doc)return;const payload={title:$('#meta-title').value.trim(),author:$('#meta-author').value.trim(),year:$('#meta-year').value.trim(),country:$('#meta-country').value.trim(),university:$('#meta-university').value.trim(),faculty:$('#meta-faculty').value.trim(),program:$('#meta-program').value.trim(),repository:$('#meta-repository').value.trim(),repository_url:$('#meta-repository_url').value.trim(),area:$('#meta-area').value.trim()};if(!payload.title)return notify('El título no puede quedar vacío.');try{S.doc=await api(`/api/documents/${S.doc.id}/metadata`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});await loadDocs(S.doc.id)}catch(e){notify('No se pudieron guardar los datos: '+e.message)}};
$('#thesisSelect').onchange=async e=>{if(e.target.value)await selectDoc(e.target.value)};
$('#prevThesis').onclick=()=>moveThesis(-1);$('#nextThesis').onclick=()=>moveThesis(1);
async function moveThesis(delta){if(!S.docs.length)return;let i=Math.max(0,S.docs.findIndex(d=>d.id===S.doc?.id));i=(i+delta+S.docs.length)%S.docs.length;await selectDoc(S.docs[i].id)}
async function selectDoc(id){
  const projectId=S.project?.id,sequence=(S.docSelectSequence||0)+1;S.docSelectSequence=sequence;
  const isCurrent=()=>S.docSelectSequence===sequence&&S.project?.id===projectId;
  const loaded=await api('/api/documents/'+id);if(!isCurrent())return;if(projectId&&loaded.project_id!==projectId)return;S.doc=loaded;S.activeSection=0;S.selectedRef=null;S.origin=null;S.markMode=null;S.addFromPdfMode=false;S.originCache={};S.pageOriginsCache={};S.spansCache={};S.openState=null;
  if(S.doc.analysis_stale&&!S.doc.has_manual_work&&!S.autoUpdating.has(id)){
    S.autoUpdating.add(id);
    $('#globalStatus').innerHTML='<span class="loader"></span> actualizando extracción a v'+esc(S.doc.current_versions?.software_version||'actual');
    try{
      await api(`/api/documents/${id}/analyze`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rescue_profile:'stable',worker:true})});
      const refreshed=await api('/api/documents/'+id);if(!isCurrent())return;S.doc=refreshed;
      const summary=S.docs.find(x=>x.id===id);if(summary){summary.analysis_stale=false;summary.n_references=S.doc.n_references;summary.status=S.doc.status;summary.analysis_versions=S.doc.analysis_versions;summary.has_manual_work=S.doc.has_manual_work}renderCards();renderDashboard();updateHeroEmphasis()
    }catch(e){console.error('No se pudo actualizar automáticamente',e)}finally{S.autoUpdating.delete(id)}
  }
  if(!isCurrent())return;
  S.page=Math.min(Math.max(S.doc.sections?.[0]?.start_page||1,1),S.doc.page_count);
  renderDocs();renderDoc();if($('#screen-review').classList.contains('active'))await renderSectionViewer({scrollPage:S.page});updateGlobal();
}
window.selectDoc=selectDoc;window.openDoc=async id=>{try{await selectDoc(id);if(S.doc?.id===id)show('review')}catch(e){notify('No se pudo abrir la tesis: '+e.message)}};
window.removeDoc=async id=>{if(!await confirmModal('¿Quitar esta tesis del proyecto? El PDF y sus correcciones locales se eliminarán del proyecto de BiblioRef.'))return;try{await api('/api/documents/'+id,{method:'DELETE'});if(S.doc?.id===id)S.doc=null;await loadDocs()}catch(e){notify('No se pudo quitar la tesis: '+e.message)}};

function renderLayerOptions(){
  const el=$('#layerOptions');if(!el)return;const layers=(S.capabilities?.layers||[]).filter(x=>x.mode!=='deferred_local');
  if(!layers.length){el.innerHTML='<div class="layerlegend">No se pudo leer el manifiesto de capas.</div>';return}
  if(!S.pipelineTouched&&S.pipelineLayers.size===0)layers.filter(x=>x.default_enabled&&['crossref','openalex','consensus','decision'].includes(x.id)).forEach(x=>S.pipelineLayers.add(x.id));
  const selectableIds=new Set(['crossref','openalex','consensus','decision']);
  el.innerHTML=layers.map(layer=>{
    const selectable=Boolean(layer.interactive_execution)&&selectableIds.has(layer.id);
    const checked=selectable?S.pipelineLayers.has(layer.id):Boolean(layer.interactive_execution);
    const dot=checked&&layer.interactive_execution?'on':layer.available?'ready':'',state=selectable?(checked?'seleccionada':'opcional'):(layer.interactive_execution?'activa':layer.available?'disponible':'no disponible');
    const control=selectable?`<input class="layercheck" type="checkbox" ${checked?'checked':''} onchange="togglePipelineLayer('${layer.id}',this.checked)" aria-label="${esc(layer.label)}">`:`<span class="layerdot ${dot}"></span>`;
    return `<div class="layerrow ${selectable?'selectable':''}" title="${esc(layer.version||'')}">${control}<div><div class="layername">${esc(layer.label)}</div><div class="layerdesc">${esc(layer.description||'')}</div></div><span class="layerstate">${state}</span></div>`;
  }).join('')+`<div class="layerlegend">Marcá las capas externas/determinísticas que querés ejecutar sobre la referencia seleccionada. El runtime local está desactivado en esta versión. Ninguna capa reescribe el parser.</div><div class="layeractions"><button class="btn primary xs" onclick="runSelectedResolution()">Ejecutar en REF seleccionada</button></div>`;
}
window.togglePipelineLayer=(id,on)=>{S.pipelineTouched=true;if(on)S.pipelineLayers.add(id);else S.pipelineLayers.delete(id);if(on&&id==='decision')S.pipelineLayers.add('consensus');renderLayerOptions()};
function renderDoc(){if(!S.doc)return;$('#pageInput').value=S.page;renderSections();renderAnalysis();renderRefs();renderDocs();renderLayerOptions();renderDocMap()}
function renderSections(){
  const sel=$('#sectionSelect'),secs=S.doc?.sections||[];if(!sel)return;
  if(!secs.length){sel.innerHTML='<option value="">Sin sección</option>';sel.disabled=true;return}
  sel.disabled=false;sel.innerHTML=secs.map((sec,i)=>`<option value="${i}" ${i===S.activeSection?'selected':''}>${esc(sec.label||'Referencias')}${secs.length>1?' '+(i+1):''}</option>`).join('');
}
function readSections(){return (S.doc?.sections||[]).map(s=>({label:s.label||'Referencias',start_page:+s.start_page||1,start_y:+(s.start_y||0),end_page:+s.end_page||S.doc.page_count,end_y:s.end_y==null||s.end_y===''?null:+s.end_y}))}
function syncSectionDrafts(){}
window.scheduleSectionPreview=()=>{clearTimeout(S.previewTimer);S.previewTimer=setTimeout(()=>renderSectionViewer({scrollPage:S.page}),250)};
window.setActiveSection=async i=>{S.activeSection=+i||0;const sec=S.doc.sections[S.activeSection];if(sec?.start_page)S.page=sec.start_page;S.origin=null;renderSections();await renderSectionViewer({scrollPage:S.page})};
$('#sectionSelect').onchange=e=>setActiveSection(+e.target.value);
window.removeSection=async i=>{if(!S.doc)return;if(!await confirmModal('¿Quitar esta sección bibliográfica?'))return;S.doc.sections.splice(i,1);S.activeSection=Math.max(0,Math.min(S.activeSection,S.doc.sections.length-1));renderSections();renderSectionViewer()};
$('#addSection').onclick=()=>{if(!S.doc)return;S.doc.sections.push({label:'Referencias',start_page:S.page,start_y:0,end_page:S.page,end_y:null,source:'manual'});S.activeSection=S.doc.sections.length-1;renderSections();renderSectionViewer({scrollPage:S.page})};
window.editActiveSection=()=>{if(!S.doc)return;const sec=S.doc.sections[S.activeSection];if(!sec)return notify('Agregá una sección primero.');modal('Límites de la sección',`<div class="thesisfield"><label>Nombre</label><input id="secModalLabel" value="${esc(sec.label||'Referencias')}"></div><div class="fields"><div class="field"><label>Inicio · página</label><input id="secModalSP" type="number" min="1" value="${sec.start_page||1}"></div><div class="field"><label>Inicio · posición</label><input id="secModalSY" type="number" step="0.1" value="${sec.start_y??0}"></div><div class="field"><label>Fin · página</label><input id="secModalEP" type="number" min="1" value="${sec.end_page||S.doc.page_count}"></div><div class="field"><label>Fin · posición</label><input id="secModalEY" type="number" step="0.1" value="${sec.end_y??''}"></div></div>`,`<button class="btn warn" onclick="removeActiveSectionFromModal()">Eliminar sección</button><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="saveSectionDraftFromModal()">Guardar</button>`)};
window.saveSectionDraftFromModal=()=>{const sec=S.doc.sections[S.activeSection];sec.label=$('#secModalLabel').value.trim()||'Referencias';sec.start_page=+$('#secModalSP').value||1;sec.start_y=+($('#secModalSY').value||0);sec.end_page=+$('#secModalEP').value||sec.start_page;sec.end_y=$('#secModalEY').value===''?null:+$('#secModalEY').value;closeModal();renderSections();renderSectionViewer({scrollPage:sec.start_page})};
window.removeActiveSectionFromModal=()=>{const i=S.activeSection;closeModal();removeSection(i)};
$('#editSection').onclick=()=>editActiveSection();
window.applySectionLimits=async()=>{if(!S.doc)return;const sections=readSections();if(!sections.length)return notify('Agregá al menos una sección.');if(!await confirmModal('Esto volverá a segmentar esta tesis usando estos límites y reemplazará la lista actual de referencias. La corrección quedará registrada.'))return;try{S.doc=await api(`/api/documents/${S.doc.id}/manual-sections`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sections})});renderDoc();await renderSectionViewer({scrollPage:sections[Math.min(S.activeSection,sections.length-1)]?.start_page||1});await loadDocs(S.doc.id)}catch(e){notify(e.message)}};
$('#applySectionLimits').onclick=()=>applySectionLimits();

$('#visibleStart').onclick=()=>beginMark('start');$('#visibleEnd').onclick=()=>beginMark('end');
function beginMark(mode){
  if(!S.doc)return;if(!S.doc.sections.length){S.doc.sections.push({label:'Referencias',start_page:S.page,start_y:0,end_page:S.page,end_y:null});S.activeSection=0;renderSections()}
  S.addFromPdfMode=false;S.markMode=mode;updateViewerMode();renderSectionViewer({scrollPage:S.page});
}
function updateViewerMode(){
  const b=$('#addFromPdf');if(!b)return;
  b.textContent=S.addFromPdfMode?'Cancelar agregado':'＋ desde PDF';b.classList.toggle('warn',S.addFromPdfMode);b.classList.toggle('primary',!S.addFromPdfMode);
  $$('#pageWrap .pdfcrop').forEach(c=>c.classList.toggle('clickable',Boolean(S.markMode||S.addFromPdfMode)));
  if(S.markMode)$('#viewerTitle').textContent=S.markMode==='start'?'Clic en el punto exacto donde EMPIEZA la sección':'Clic en el punto exacto donde TERMINA la sección';
}
function activeSection(){syncSectionDrafts();return S.doc?.sections?.[S.activeSection]||S.doc?.sections?.[0]||null}

function auditDecision(id){return S.doc?.audit_decisions?.[id]?.decision||null}
function renderAnalysis(){
  if(!S.doc)return;const a=S.doc.analysis||{},msgs=a.messages||[];
  const stale=S.doc.analysis_stale;
  const staleNotice=stale?`<div class="notice warn"><b>Esta lista fue extraída con una versión anterior.</b><br>El PDF del visor es actual, pero las referencias guardadas corresponden a ${esc(S.doc.analysis_versions?.software_version||'una versión anterior')}. El motor actual es ${esc(S.doc.current_versions?.software_version||'')}. ${S.doc.has_manual_work?'Hay correcciones en referencias o límites: se guardará una instantánea antes de actualizar.':''}<div class="actions"><button class="btn primary xs" onclick="updateCurrentExtraction()">Actualizar extracción a v${esc(S.doc.current_versions?.software_version||'actual')}</button></div></div>`:'';
  const baseNotice=msgs.length?`<div class="notice ${a.needs_review?'warn':''}"><b>${a.needs_review?'Conviene revisar esta tesis':'Extracción consistente'}</b><br>${msgs.map(esc).join('<br>')}</div>`:(S.doc.status==='uploaded'?'<div class="notice">Esta tesis todavía no fue procesada.</div>':'');
  $('#analysisNotice').innerHTML=staleNotice+baseNotice;
  const cov=a.coverage||{},sum=cov.summary||{},missing=(cov.possible_missing||[]).filter(x=>auditDecision(x.id)!=='ignore'&&auditDecision(x.id)!=='resolved'&&auditDecision(x.id)!=='accepted_missing'),bounds=cov.page_boundaries||[],merged=cov.merged_suspects||[];
  const nReview=bounds.filter(x=>(auditDecision(x.id)||x.verdict)==='review'||(auditDecision(x.id)||x.verdict)==='pending').length;
  const headline=(!missing.length&&!nReview&&!merged.length&&cov.status!=='unavailable')?'<span class="checkok">✓ Control sin alertas activas</span>':`<span class="checkwarn">${missing.length+nReview+merged.length} punto(s) para revisar</span>`;
  const missHtml=missing.length?`<div class="auditgroup"><b>Posibles referencias faltantes</b>${missing.slice(0,12).map(x=>`<div class="auditrow warn"><div><span class="auditico">?</span> pág. ${x.page}<div class="auditpreview">${esc(x.first_line||x.text||'')}</div></div><div class="auditactions"><button class="btn xs" onclick="focusMissing('${x.id}')">Ver</button><button class="btn xs primary" onclick="addMissing('${x.id}')">＋</button><button class="btn xs" onclick="ignoreAudit('${x.id}')">Ignorar</button></div></div>`).join('')}</div>`:'';
  const boundHtml=bounds.length?`<div class="auditgroup"><details class="auditdetails" ${nReview?'open':''}><summary><b>Bordes de página</b> · ${bounds.length}${nReview?' · '+nReview+' revisar':''}</summary>${bounds.map(x=>{const d=auditDecision(x.id)||x.verdict,label=d==='split'?'✓ nueva referencia':d==='continue'?'✓ continúa':d==='review'||d==='pending'?'⚠ revisar':'✓ resuelto',klass=d==='review'||d==='pending'?'warn':'ok';return `<button class="boundaryrow ${klass}" onclick="reviewBoundary('${x.id}')"><span>${x.page_before} → ${x.page_after}</span><span>${label}</span></button>`}).join('')}</details></div>`:'';
  const mergedHtml=merged.length?`<div class="auditgroup"><b>Posibles referencias pegadas</b>${merged.slice(0,8).map(x=>`<div class="auditrow warn"><span>REF ${String(x.record_index||'').padStart(3,'0')} · pág. ${x.page||'?'}</span><span class="mini">revisar</span></div>`).join('')}</div>`:'';
  let legacy='';if(cov.possible_incomplete_coverage)legacy='<div class="mini">La auditoría general también detecta posible cobertura incompleta.</div>';
  $('#coverage').innerHTML=`<div class="auditheadline">${headline}</div>${missHtml}${boundHtml}${mergedHtml}${legacy}`+(a.recommendations?.length?`<div class="actions">${a.recommendations.map(r=>`<button class="btn xs" onclick="reanalyzeRescue('${esc(r.profile||r)}')">probar ${esc(r.label||r.profile||r)}</button>`).join('')}</div>`:'');
}
window.focusMissing=async id=>{const x=(S.doc.analysis?.coverage?.possible_missing||[]).find(v=>v.id===id);if(!x)return;S.page=x.page;await ensureSectionForPage(x.page);await renderSectionViewer({scrollPage:x.page})};
window.addMissing=async id=>{const x=(S.doc.analysis?.coverage?.possible_missing||[]).find(v=>v.id===id);if(!x)return;S.pendingMissingId=id;S.page=x.page;await ensureSectionForPage(x.page);S.markMode=null;S.addFromPdfMode=true;updateViewerMode();await renderSectionViewer({scrollPage:x.page});setTimeout(()=>candidateFromPoint(x.page,x.y),80)};
window.ignoreAudit=async id=>{try{await api(`/api/documents/${S.doc.id}/audit-checks/${id}/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision:'ignore'})});await selectDoc(S.doc.id)}catch(e){notify('No se pudo ignorar el aviso: '+e.message)}};
function boundaryCropMarkup(info,mode,page){
  const lines=info?.lines||[],h=+info?.height||842,w=+info?.width||595;
  let anchor=mode==='bottom'?Math.max(0,h-90):90;
  if(lines.length){const line=mode==='bottom'?lines[lines.length-1]:lines[0];anchor=mode==='bottom'?+line.y1:+line.y0}
  const top=Math.max(0,anchor-85),bottom=Math.min(h,anchor+85),ch=Math.max(60,bottom-top);
  const ratio=`${w}/${ch}`;
  const shift=(top/h)*100;
  return `<div class="boundaryimage" style="aspect-ratio:${ratio}"><img alt="Página ${page}" src="/api/documents/${S.doc.id}/page/${page}.png?zoom=1.25&_nocache=${Date.now()}" style="transform:translateY(-${shift}%);width:100%;height:auto"></div>`;
}
window.reviewBoundary=async id=>{
  const x=(S.doc.analysis?.coverage?.page_boundaries||[]).find(v=>v.id===id);if(!x)return;
  const ev=(x.evidence||[]).map(e=>`<li>${esc(e.signal.replaceAll('_',' '))}</li>`).join('');
  let left=null,right=null;try{[left,right]=await Promise.all([api(`/api/documents/${S.doc.id}/page/${x.page_before}/lines`),api(`/api/documents/${S.doc.id}/page/${x.page_after}/lines`)])}catch(e){console.warn('boundary lines',e)}
  const lCrop=left?boundaryCropMarkup(left,'bottom',x.page_before):`<div class="boundaryimage" style="height:220px"><img src="/api/documents/${S.doc.id}/page/${x.page_before}.png?zoom=1.25&_nocache=${Date.now()}"></div>`;
  const rCrop=right?boundaryCropMarkup(right,'top',x.page_after):`<div class="boundaryimage" style="height:220px"><img src="/api/documents/${S.doc.id}/page/${x.page_after}.png?zoom=1.25&_nocache=${Date.now()}"></div>`;
  const body=`<div class="boundarycompare"><div><div class="mini">final de página ${x.page_before}</div>${lCrop}<div class="auditpreview">${esc((x.previous_tail||[]).join(' · '))}</div></div><div><div class="mini">inicio de página ${x.page_after}</div>${rCrop}<div class="auditpreview">${esc((x.next_head||[]).join(' · '))}</div></div></div><div class="candidateinfo"><b>Sugerencia de BiblioRef:</b> ${x.verdict==='split'?'probable nueva referencia':x.verdict==='continue'?'probable continuación':'requiere revisión'}<ul>${ev}</ul></div>`;
  modal(`Borde ${x.page_before} → ${x.page_after}`,body,`<button class="btn" onclick="saveBoundaryDecision('${id}','pending')">Dejar pendiente</button><button class="btn" onclick="saveBoundaryDecision('${id}','continue')">Continúa anterior</button><button class="btn primary" onclick="saveBoundaryDecision('${id}','split')">Nueva referencia</button>`)
};
window.saveBoundaryDecision=async(id,decision)=>{try{await api(`/api/documents/${S.doc.id}/audit-checks/${id}/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})});closeModal();await selectDoc(S.doc.id)}catch(e){notify('No se pudo guardar la decisión: '+e.message)}};
window.reanalyzeRescue=async profile=>{if(!S.doc)return;await analyzeOne(S.doc.id,profile,false);await selectDoc(S.doc.id)};
window.updateCurrentExtraction=async()=>{if(!S.doc)return;const msg=S.doc.has_manual_work?'La extracción actual tiene correcciones en referencias o límites. BiblioRef guardará una instantánea completa y luego volverá a extraer con v'+(S.doc.current_versions?.software_version||'actual')+'. ¿Continuar?':'Volver a extraer esta tesis con v'+(S.doc.current_versions?.software_version||'actual')+'?';if(!await confirmModal(msg))return;await analyzeOne(S.doc.id,'stable',false);await selectDoc(S.doc.id)};
$('#reextract').onclick=()=>updateCurrentExtraction();

function renderRefs(){
  if(!S.doc)return;
  const workspace=$('#screen-review .workspace');if(workspace)workspace.classList.toggle('sheet-mode',S.refView==='table');
  const q=$('#searchRefs').value.toLowerCase();
  const refs=(S.doc.references||[]).filter(r=>{
    if(r.deleted)return false;
    if(window.BiblioRefRefFilter&&!BiblioRefRefFilter.matches(r))return false;
    if(!q)return true;
    const p=r.effective_parsed||r.parsed||{};
    const hay=[r.text,p.author,p.authors,p.year,p.publication_type,p.title,p.journal,p.publisher,p.publisher_observed,p.source_publisher,p.doi].filter(Boolean).join(' ').toLowerCase();
    return hay.includes(q);
  });
  $('#refCount').textContent=`${S.doc.n_references||0} referencias`;
  const missing=(S.doc.analysis?.coverage?.possible_missing||[]).filter(x=>auditDecision(x.id)!=='ignore'&&auditDecision(x.id)!=='resolved'&&auditDecision(x.id)!=='accepted_missing');
  $('#missingIndicator').innerHTML=(window.BiblioRefRefFilter?BiblioRefRefFilter.notice(refs.length,(S.doc.references||[]).filter(r=>!r.deleted).length):'')+(missing.length?`<div class="missingcount">⚠ ${missing.length} posible${missing.length===1?'':'s'} referencia${missing.length===1?'':'s'} sin extraer · pág. ${[...new Set(missing.map(x=>x.page))].slice(0,4).join(', ')}</div>`:'');
  $('#tabCount').textContent=S.doc.n_references||0;
  const tabMissing=$('#tabMissing');tabMissing.hidden=!missing.length;tabMissing.textContent='⚠ '+missing.length;
  if(S.refView==='table'){$('#refList').innerHTML=renderRefsTable(refs);return}
  $('#refList').innerHTML=refs.map(r=>{
    const problem=['truncated','possibly_merged'].includes(r.status)||Boolean(r.audit_flags);
    const p=r.effective_parsed||r.parsed||{};
    const parsedBits=[];
    if(p.author)parsedBits.push(`autor: ${p.author}`);
    if(p.journal)parsedBits.push(`revista: ${p.journal}`);
    if(p.publisher)parsedBits.push(`editorial: ${p.publisher}`);
    if(p.doi)parsedBits.push(`DOI: ${p.doi}`);
    const parsedSummary=parsedBits.length?parsedBits.join(' · '):'parseo v0.2: sin campos firmes adicionales';
    const parsedHtml=`<div class="refparsed" title="${esc(parsedSummary)}">${esc(parsedSummary)}</div>`;
    const typeChip=p.publication_type&&p.publication_type!=='sin_clasificar'?`<span class="tag type">${esc(p.publication_type.replaceAll('_',' '))}</span>`:'';
    const yearChip=p.year?`<span class="tag">${esc(p.year)}</span>`:'';
    return `<div class="refitem ${S.selectedRef===r.id?'current':''} ${problem?'problem':''}" data-id="${r.id}" role="button" tabindex="0" aria-current="${S.selectedRef===r.id?'true':'false'}" onclick="pickRef('${r.id}')" onkeydown="if(event.target===event.currentTarget&&(event.key==='Enter'||event.key===' ')){event.preventDefault();pickRef('${r.id}')}" onmouseenter="hoverRefStart('${r.id}')" onmouseleave="hoverRefEnd('${r.id}')" onfocus="hoverRefStart('${r.id}')" onblur="hoverRefEnd('${r.id}')"><div class="num">REF ${String(r.order).padStart(3,'0')} · ${r.start_page?`pág${r.start_page!==r.end_page?'s':''}. ${r.start_page}${r.end_page&&r.end_page!==r.start_page?'–'+r.end_page:''}`:'ubicación manual'}<button class="refcopy" title="Copiar referencia" onclick="event.stopPropagation();copyRef('${r.id}',this)"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="5.5" y="5.5" width="8" height="8" rx="1"/><path d="M3 10.5V3a1 1 0 0 1 1-1h7.5"/></svg></button></div><div class="reftext" title="Vista visual; el texto original se conserva">${esc(displayRefText(r))}</div>${parsedHtml}<div class="refmeta">${yearChip}${typeChip}<span class="tag ${r.status==='reviewed'?'ok':problem?'warn':''}">${esc(refStatusLabel(r.status))}</span><span class="tag">${esc(refSourceLabel(r.source))}</span>${r.edited?'<span class="tag warn">editada</span>':''}</div><div class="refquick"><button class="btn xs" onclick="event.stopPropagation();editRef('${r.id}')">Editar</button><button class="btn xs" onclick="event.stopPropagation();showParsed('${r.id}')">Campos</button><button class="btn xs" onclick="event.stopPropagation();runSelectedResolution('${r.id}')">Resolver</button><button class="btn xs ok" title="Marcar revisada" onclick="event.stopPropagation();markRef('${r.id}','reviewed')">✓</button><details class="refmore" onclick="event.stopPropagation()"><summary title="Más opciones">⋯</summary><div class="refmoremenu"><button class="btn xs" onclick="originRef('${r.id}')">Ubicación</button><button class="btn xs" onclick="pasteRef('${r.id}')">Pegar reemplazo</button><button class="btn xs" onclick="splitRef('${r.id}')">Dividir</button><button class="btn xs" onclick="mergeNext('${r.id}')">Unir con siguiente</button><button class="btn xs" onclick="markRef('${r.id}','truncated')">Marcar truncada</button><button class="btn xs" onclick="markRef('${r.id}','possibly_merged')">Marcar pegadas</button><button class="btn xs warn" onclick="deleteRef('${r.id}')">Eliminar</button></div></details></div></div>`;
  }).join('')||'<div class="mini">No hay referencias para mostrar.</div>';
}
function parserScalar(v){return Array.isArray(v)?v.join('; '):(v==null?'':String(v))}
function hasParsedOverride(r,field){return Object.prototype.hasOwnProperty.call(r.parsed_review?.overrides||{},field)}
function sheetInput(r,field,size=''){
  const p=r.effective_parsed||r.parsed||{},base=r.parsed||{},manual=hasParsedOverride(r,field),value=parserScalar(p[field]),original=parserScalar(base[field]);
  return `<div class="sheetcell ${size}"><input class="sheetinput ${manual?'manual':''}" value="${esc(value)}" title="Parser: ${esc(original||'—')}" data-ref="${r.id}" data-field="${field}" onchange="saveParsedCell('${r.id}','${field}',this.value)" onkeydown="sheetKey(event,this)">${manual?`<button class="sheetundo" title="Volver al valor del parser" onclick="event.stopPropagation();revertParsedCell('${r.id}','${field}')">↶</button>`:''}</div>`;
}
function sidecarStatus(r,keys){for(const key of keys){const value=r?.[key];if(value){if(typeof value==='string')return value;if(value.status)return value.status;if(value.decision)return value.decision;if(value.version)return value.version}}return ''}
function sheetStatus(value){return value?`<span class="tag sheetstatus">${esc(value)}</span>`:'<span class="sheetstatus empty">no ejecutado</span>'}
function renderRefsTable(refs){
  if(!refs.length)return '<div class="mini">No hay referencias para mostrar.</div>';
  const rows=refs.map(r=>{
    const problem=['truncated','possibly_merged'].includes(r.status)||Boolean(r.audit_flags),reviewN=Object.keys(r.parsed_review?.overrides||{}).length;
    const resolution=sidecarStatus(r,['resolution_decision','resolution','resolver_decision']);
    return `<tr class="${S.selectedRef===r.id?'current':''}" onclick="if(!event.target.closest('input,button,textarea'))pickRef('${r.id}')"><td class="numcol sheet-index">${String(r.order).padStart(3,'0')}</td><td class="sheet-raw-cell"><textarea class="sheet-raw" readonly title="Texto crudo extraído; editarlo usa la acción Editar de la tarjeta">${esc(r.text||'')}</textarea><span class="sheetparserhint">raw · ${esc(refSourceLabel(r.source))}</span></td><td>${sheetInput(r,'author','medium')}</td><td>${sheetInput(r,'year')}</td><td>${sheetInput(r,'publication_type','medium')}</td><td>${sheetInput(r,'title','wide')}</td><td>${sheetInput(r,'journal','medium')}</td><td>${sheetInput(r,'publisher','medium')}</td><td>${sheetInput(r,'publisher_observed','medium')}</td><td>${sheetInput(r,'doi','medium')}</td><td>${sheetStatus(resolution)}</td><td><span class="tag ${r.status==='reviewed'?'ok':problem?'warn':''}">${esc(refStatusLabel(r.status))}</span>${reviewN?`<span class="sheetparserhint">${reviewN} campo(s) corregido(s)</span>`:'<span class="sheetparserhint">parser original</span>'}<button class="btn xs" style="margin-top:5px" onclick="event.stopPropagation();runSelectedResolution('${r.id}')">Resolver</button></td></tr>`;
  }).join('');
  return `<div class="sheetnote"><b>Planilla de auditoría.</b> El texto crudo y <code>parsed</code> permanecen intactos. Las celdas editadas se guardan como <code>parsed_review.overrides</code>; amarillo = corrección humana. Tab recorre celdas, Enter guarda la celda activa y Esc descarta el cambio local.</div><div class="reftablewrap workbook"><table class="dashtable reftable workbook"><thead><tr><th class="sheet-index">#</th><th class="sheet-raw-cell">Referencia cruda</th><th>Autor</th><th>Año</th><th>Tipo</th><th>Título</th><th>Revista</th><th>Editorial</th><th>Editorial observada</th><th>DOI</th><th>Resolución</th><th>Revisión</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
window.sheetKey=(event,input)=>{if(event.key==='Enter'){event.preventDefault();input.blur()}else if(event.key==='Escape'){event.preventDefault();const r=refBy(input.dataset.ref),p=r?.effective_parsed||r?.parsed||{};input.value=parserScalar(p[input.dataset.field]);input.blur()}};
window.saveParsedCell=async(refId,field,value)=>{
  const key=`${refId}:${field}`;if(S.parsedSaving.has(key)||!S.doc)return;S.parsedSaving.add(key);
  try{const updated=await api(`/api/documents/${S.doc.id}/references/${refId}/parsed-review`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({overrides:{[field]:value}})});const idx=S.doc.references.findIndex(r=>r.id===refId);if(idx>=0)S.doc.references[idx]=updated;renderRefs();}
  catch(e){notify('No se pudo guardar la corrección de '+field+': '+e.message)}finally{S.parsedSaving.delete(key)}
};
window.revertParsedCell=async(refId,field)=>{if(!S.doc)return;try{const updated=await api(`/api/documents/${S.doc.id}/references/${refId}/parsed-review`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({unset_fields:[field]})});const idx=S.doc.references.findIndex(r=>r.id===refId);if(idx>=0)S.doc.references[idx]=updated;renderRefs()}catch(e){notify('No se pudo revertir la corrección: '+e.message)}};
$$('#refViewToggle button').forEach(b=>b.onclick=()=>{S.refView=b.dataset.refview;$$('#refViewToggle button').forEach(x=>x.classList.toggle('active',x===b));renderRefs()});

/* ---- Dónde está cada referencia en el PDF: una sola pasada para toda la sección ---- */
async function ensureSpans(){
  const sec=activeSection();if(!S.doc||!sec)return {};
  const sp=Math.max(1,+sec.start_page||1),ep=Math.min(S.doc.page_count,+sec.end_page||sp);
  const key=`${S.doc.id}|${sp}-${ep}`;
  if(!S.spansCache)S.spansCache={};
  if(!S.spansCache[key])S.spansCache[key]=api(`/api/documents/${S.doc.id}/reference-spans?start_page=${sp}&end_page=${ep}`).then(r=>r.spans||{}).catch(()=>({}));
  return S.spansCache[key];
}
/* Las cajas azules se calculan sobre el PDF y se cachean por sección: toda edición que
   mueva, parta o una referencias las deja viejas, así que hay que tirar el caché y repintar. */
function invalidateRefGeometry(){S.originCache={};S.pageOriginsCache={};S.spansCache={};S.origin=null}
async function refreshAfterRefChange(page=null){
  invalidateRefGeometry();
  renderDoc();
  if($('#screen-review')?.classList.contains('active'))await renderSectionViewer({scrollPage:page||S.page});
}
const normRefText=t=>String(t||'').replace(/\s+/g,' ').trim();
const refByText=t=>(S.doc?.references||[]).find(r=>!r.deleted&&normRefText(r.text)===normRefText(t));
const refLabel=r=>'REF '+String(r.order).padStart(3,'0');
function activeMissing(){return (S.doc?.analysis?.coverage?.possible_missing||[]).filter(x=>!['ignore','resolved','accepted_missing'].includes(auditDecision(x.id)))}
// Con una referencia abierta la página queda partida en dos recortes: vale el que contiene esa altura.
function cropAt(page,y){
  const crops=$$(`#pageWrap .pdfcrop[data-page="${page}"]`);
  return crops.find(c=>y>=+c.dataset.cropTop&&y<=+c.dataset.cropBottom)||crops[0]||null;
}

/* ---- Margen: el número de cada referencia y las que faltan ---- */
window.renderMargin=async()=>{
  const wrap=$('#pageWrap');if(!wrap||!S.doc)return;
  const seq=S.marginSeq=(S.marginSeq||0)+1;
  const spans=await ensureSpans();
  if(seq!==S.marginSeq||!S.doc)return;
  wrap.querySelectorAll('.refbadge,.gapbadge').forEach(x=>x.remove());
  // Van en el visor y no en el recorte: el recorte oculta todo lo que se sale de la página.
  const place=(el,page,y)=>{
    const crop=cropAt(page,y);if(!crop)return;
    const top=+crop.dataset.cropTop,bottom=+crop.dataset.cropBottom;
    const frac=Math.max(0,Math.min(1,(y-top)/Math.max(1,bottom-top)));
    el.style.top=(crop.offsetTop+frac*crop.offsetHeight)+'px';
    el.style.left=Math.max(4,crop.offsetLeft-66)+'px';
    wrap.appendChild(el);
  };
  (S.doc.references||[]).filter(r=>!r.deleted).forEach(r=>{
    const span=spans[r.id];if(!span)return;
    const b=document.createElement('button');b.className='refbadge';b.dataset.ref=r.id;
    b.textContent='REF '+String(r.order).padStart(3,'0');
    b.onclick=e=>{e.stopPropagation();togglePdfRef(r.id)};
    place(b,span[0].page,span[0].y0);
  });
  activeMissing().forEach(x=>{
    const b=document.createElement('button');b.className='gapbadge';b.textContent='falta';
    b.onclick=e=>{e.stopPropagation();toggleOpenMissing(x.id)};
    place(b,x.page,x.y);
  });
};

/* ---- Abrir debajo: la página se corta bajo el párrafo y aparece su versión digital ---- */
function buildCrop(p,part=''){
  const crop=document.createElement('div');
  crop.className='pdfcrop'+(part?' '+part:'')+((S.markMode||S.addFromPdfMode)?' clickable':'');
  crop.dataset.page=p.page;crop.dataset.width=p.width;crop.dataset.height=p.height;crop.dataset.cropTop=p.crop_top;crop.dataset.cropBottom=p.crop_bottom;
  crop.style.aspectRatio=`${p.width}/${Math.max(1,p.crop_bottom-p.crop_top)}`;
  if(part!=='cut-bottom'){const badge=document.createElement('div');badge.className='pagebadge';badge.textContent=`p. ${p.page}`;crop.appendChild(badge)}
  const img=new Image();img.loading='lazy';img.alt=`Página ${p.page}`;
  img.style.transform=`translateY(-${(p.crop_top/p.height)*100}%)`;
  img.onclick=ev=>viewerClick(ev,crop,cropParams(crop));
  // El mismo token en toda la sección: al partir una página se reusa la imagen ya cargada.
  img.src=`/api/documents/${S.doc.id}/page/${p.page}.png?zoom=${S.zoom}&t=${S.imgToken||0}`;
  crop.appendChild(img);return crop;
}
const SLOT_ARROW='<svg class="slotarrow" viewBox="0 0 52 46" aria-hidden="true"><path d="M20 0 V26 Q20 34 28 34 H46"/><path d="M40 28 L46 34 L40 40"/></svg>';
function openSlotHTML(kind,id){
  if(kind==='missing'){
    const x=activeMissing().find(m=>m.id===id)||{};const line=x.first_line||x.text||'';
    return `${SLOT_ARROW}<div class="slotcard"><div class="slothead">Falta la referencia digital<span>pág. ${x.page||'—'}</span><button class="slotclose" title="Cerrar" onclick="clearRefSelection()">×</button></div>
      <div class="slottext">Este párrafo está en el PDF pero no se generó una referencia${line?`: “${esc(line.slice(0,180))}”`:''}.</div>
      <div class="actions"><button class="btn xs amber" onclick="addMissing('${esc(id)}')">Extraer acá</button><button class="btn xs" onclick="ignoreAudit('${esc(id)}')">No es una referencia</button></div></div>`;
  }
  const r=refBy(id);if(!r)return '';
  const p=r.effective_parsed||r.parsed||{};
  const field=(label,key)=>`<label class="slotfield"><span>${label}</span><input value="${esc(parserScalar(p[key]))}" onchange="saveParsedCell('${id}','${key}',this.value)"></label>`;
  // Una fusionada muestra los campos de la primera nada más: la tarjeta lo dice antes de que se lean.
  const merged=window.BiblioRefProblems?.mergedFor?.(id)||(r.status==='possibly_merged'?{}:null);
  const typeBox=window.BiblioRefProblems?.typeBox?.(r)||'';
  const mergedWarn=merged?`<div class="slotwarn"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2.6 18 17H2z"/><path d="M10 8v3.6"/><path d="M10 14.1v.1"/></svg><b>Esto parece contener más de una referencia · los campos de abajo son de la primera nada más</b><button class="btn xs amber solid" onclick="splitRef('${id}')">Dividir…</button><button class="btn xs amber" onclick="${merged.checkId?`BiblioRefProblems.dismiss('${esc(merged.checkId)}')`:`markRef('${id}','reviewed')`}">Es una sola</button></div>`:'';
  return `${SLOT_ARROW}<div class="slotcard${merged?' merged':''}">${mergedWarn}<div class="slothead">Referencia digital extraída · REF ${String(r.order).padStart(3,'0')}<span>pág. ${r.start_page||'—'}</span><button class="slotclose" title="Cerrar" onclick="clearRefSelection()">×</button></div>
    <div class="slottext">${esc(displayRefText(r))}</div>${typeBox}
    <div class="slotfields">${field('autor','author')}${field('año','year')}${typeBox?'':field('tipo','publication_type')}${field('revista','journal')}${field('editorial','publisher')}${field('DOI','doi')}</div>
    <div class="actions"><button class="btn xs" onclick="copyRef('${id}',this)">Copiar</button><button class="btn xs" onclick="editRef('${id}')">Editar texto</button><button class="btn xs ok" onclick="markRef('${id}','reviewed')">✓ Revisada</button></div></div>`;
}
// Viewport position of a point of the PDF, to keep what the reader touched in place.
function pdfPointTop(page,y){
  const crop=cropAt(page,y);if(!crop||!crop.isConnected)return null;
  const p=cropParams(crop),r=crop.getBoundingClientRect();
  return r.top+((y-p.crop_top)/Math.max(1,p.crop_bottom-p.crop_top))*r.height;
}
async function openBelow(kind,id,scroll='nearest'){
  // With scroll 'keep' (a click on the PDF) the touched reference must not move on screen.
  let anchor=null;
  if(kind==='ref'&&scroll==='keep'){
    const spans=await ensureSpans();const first=(spans[id]||[])[0];
    if(first){const top=pdfPointTop(first.page,first.y0);if(top!=null)anchor={page:first.page,y:first.y0,top}}
  }
  closeBelow();
  // Las posiciones de una sección larga tardan la primera vez: si mientras tanto se eligió otra o se cerró, esta apertura ya no vale.
  const seq=S.openSeq;
  let page,y1;
  if(kind==='ref'){
    const spans=await ensureSpans();
    const boxes=spans[id]||(await fetchOrigin(id))?.span||[];
    if(seq!==S.openSeq||!boxes.length)return;
    const last=boxes[boxes.length-1];page=last.page;y1=last.y1;
  }else{
    const x=activeMissing().find(m=>m.id===id);if(!x)return;page=x.page;y1=x.y+14;
  }
  const crop=cropAt(page,y1);if(!crop||!crop.isConnected)return;
  const p=cropParams(crop),cut=Math.min(p.crop_bottom,y1+5);
  const slot=document.createElement('div');slot.className='openslot'+(kind==='missing'?' miss':'');slot.innerHTML=openSlotHTML(kind,id);
  const parts=[buildCrop({...p,crop_bottom:cut},'cut-top'),slot];
  if(p.crop_bottom-cut>2)parts.push(buildCrop({...p,crop_top:cut},'cut-bottom'));
  crop.replaceWith(...parts);
  S.openState={kind,id,original:crop,parts};
  refreshPdfMarks();renderMargin();paintOrigin();
  if(anchor){
    const now=pdfPointTop(anchor.page,anchor.y),wrap=$('#pageWrap');
    if(now!=null&&wrap)wrap.scrollTop+=now-anchor.top;
    return;
  }
  slot.scrollIntoView({block:scroll,behavior:'smooth'});
}
function closeBelow(){
  S.openSeq=(S.openSeq||0)+1;
  const st=S.openState;if(!st)return;S.openState=null;
  const[first,...rest]=st.parts;
  if(first?.isConnected){first.replaceWith(st.original);rest.forEach(x=>x.remove())}
  refreshPdfMarks();renderMargin();paintOrigin();
}
async function selectOnPdf(id,scroll='nearest'){
  await openBelow('ref',id,scroll);
  const spans=await ensureSpans();
  S.origin=spans[id]?{span:spans[id]}:await fetchOrigin(id);
  if(S.selectedRef===id)paintOrigin();
}
// Desde el PDF: abre o cierra la referencia tocada sin mover la página.
window.togglePdfRef=async id=>{
  if(S.selectedRef===id)return clearRefSelection();
  S.selectedRef=id;renderRefs();await selectOnPdf(id,'keep');
  $(`#refList .refitem[data-id="${id}"]`)?.scrollIntoView({block:'nearest'});
};
window.toggleOpenMissing=async id=>{
  if(S.openState?.kind==='missing'&&S.openState.id===id)return clearRefSelection();
  S.selectedRef=null;S.origin=null;renderRefs();paintOrigin();
  await openBelow('missing',id);
};

/* ---- Mapa del documento: dónde puede haber bibliografía además de las secciones ---- */
window.renderDocMap=async()=>{
  const host=$('#docMap');if(!host||!S.doc)return;
  // Leer el documento entero cuesta: solo cuando la solapa está abierta.
  if(!$('#reviewWorkspace')?.classList.contains('drawer-open'))return;
  const docId=S.doc.id,key=`${docId}|${S.doc.updated_at||''}`;
  if(!S.docMaps)S.docMaps={};
  if(!S.docMaps[key]){host.innerHTML='<p class="mapnote">Leyendo el documento completo…</p>';S.docMaps[key]=api(`/api/documents/${docId}/document-map`).catch(e=>({error:e.message}))}
  const m=await S.docMaps[key];
  if(S.doc?.id!==docId)return;
  if(m.error){host.innerHTML=`<p class="mapnote">No se pudo leer el documento: ${esc(m.error)}</p>`;return}
  const secPages=new Set(),candPages=new Set(),tocPages=new Set(m.toc.map(t=>t.target_page));
  m.sections.forEach(s=>{for(let p=s.start_page;p<=s.end_page;p++)secPages.add(p)});
  m.candidates.forEach(c=>{for(let p=c.start_page;p<=c.end_page;p++)candPages.add(p)});
  const offPages=new Set();(S.doc.discarded_sections||[]).forEach(d=>{for(let p=d.section.start_page;p<=d.section.end_page;p++)offPages.add(p)});
  const ticks=Array.from({length:m.page_count},(_,i)=>{
    const p=i+1,kind=secPages.has(p)?'sec':offPages.has(p)?'off':candPages.has(p)?'cand':'';
    const what=kind==='sec'?' · zona incluida':kind==='off'?' · zona excluida':kind==='cand'?' · posible bibliografía':'';
    return `<button class="maptick ${kind}${tocPages.has(p)?' toc':''}" data-page="${p}" title="p. ${p}${what}${tocPages.has(p)?' · el índice apunta acá':''}"></button>`;
  }).join('');
  const count=m.page_count||1,pct=p=>((p-1)/count*100).toFixed(3),wid=(a,b)=>((b-a+1)/count*100).toFixed(3);
  const discarded=S.doc.discarded_sections||[];
  const blocks=[
    ...m.sections.map((s,i)=>({kind:'sec',i,a:s.start_page,b:s.end_page,label:s.label})),
    ...discarded.map((d,i)=>({kind:'off',i,a:d.section.start_page,b:d.section.end_page,label:d.section.label})),
    // A possible bibliography that overlaps a zone would hide it; the zone already covers those pages.
    ...m.candidates.map((c,i)=>({kind:'cand',i,a:c.start_page,b:c.end_page,label:'Posible bibliografía'}))
      .filter(c=>![...m.sections,...discarded.map(d=>d.section)].some(s=>c.a<=s.end_page&&c.b>=s.start_page)),
  ].sort((x,y)=>x.a-y.a);
  const blockHtml=blocks.map(z=>{
    const state=z.kind==='sec'?'incluida':z.kind==='off'?'excluida':'sin sección';
    const open=S.mapPop&&S.mapPop.kind===z.kind&&S.mapPop.i===z.i;
    const w=+wid(z.a,z.b),narrow=w<9;
    return `<button class="mapblock ${z.kind}${open?' open':''}${narrow?' narrow':''}" style="left:min(${pct(z.a)}%, calc(100% - 22px));width:${w}%" data-zone="${z.kind}:${z.i}" aria-expanded="${open}" title="${esc(z.label)} · pp. ${z.a}–${z.b} · ${state}" aria-label="${esc(z.label)}, páginas ${z.a} a ${z.b}, ${state}"><span>${z.kind==='off'?'✕ ':''}${esc(z.label)}</span></button>`;
  }).join('');
  const refsOf=(ids,zone,a,b,deleted)=>(S.doc.references||[]).filter(r=>(!!r.deleted)===deleted&&(ids?ids.includes(r.id):(r.zone_id===zone||(r.start_page>=a&&r.start_page<=b))));
  const sample=list=>list.slice(0,3).map(r=>`<span>${esc(String(r.text||'').slice(0,90))}${String(r.text||'').length>90?'…':''}</span>`).join('');
  let pop='';
  if(S.mapPop){
    const {kind,i}=S.mapPop,toc=(a,b)=>m.toc.some(t=>t.target_page>=a&&t.target_page<=b)?'<span class="maphint">el índice apunta acá</span>':'';
    if(kind==='sec'&&m.sections[i]){
      const s=m.sections[i],sec=(S.doc.sections||[])[i]||s,list=refsOf(null,sec.zone_id,s.start_page,s.end_page,false),only=m.sections.length<2;
      pop=`<div class="mappop"><div><b>«${esc(s.label)}»</b> <span class="mapmeta">pp. ${s.start_page}–${s.end_page} · ${list.length} referencia${list.length===1?'':'s'} · incluida</span> ${toc(s.start_page,s.end_page)}</div><div class="mapsample">${sample(list)||'<span>Sin referencias extraídas</span>'}</div><div class="mappopacts"><button class="btn xs" data-zoneact="exclude" ${only?'disabled title="Tiene que quedar al menos una zona de bibliografía"':''}>Excluir: no es bibliografía de la tesis</button><button class="btn xs" data-zoneact="view">Ver en el PDF</button><button class="btn xs" data-zoneact="close">Cerrar</button></div>${only?'<p class="mapnote">Es la única zona incluida: no se puede excluir.</p>':''}</div>`;
    }else if(kind==='off'&&discarded[i]){
      const d=discarded[i],s=d.section,list=refsOf(d.reference_ids||[],null,0,0,true);
      pop=`<div class="mappop off"><div><b>«${esc(s.label)}»</b> <span class="mapmeta">pp. ${s.start_page}–${s.end_page} · ${list.length} referencia${list.length===1?'':'s'} · excluida</span></div><div class="mapsample">${sample(list)||'<span>Sin referencias</span>'}</div><div class="mappopacts"><button class="btn xs primary" data-zoneact="include">Incluir de nuevo en la bibliografía</button><button class="btn xs" data-zoneact="view">Ver en el PDF</button><button class="btn xs" data-zoneact="close">Cerrar</button></div></div>`;
    }else if(kind==='cand'&&m.candidates[i]){
      const c=m.candidates[i];
      pop=`<div class="mappop cand"><div><b>Posible bibliografía sin zona</b> <span class="mapmeta">pp. ${c.start_page}–${c.end_page} · todavía no se extrajo</span> ${toc(c.start_page,c.end_page)}</div><div class="mappopacts"><button class="btn xs primary" data-zoneact="addcand">Ver y agregar como zona</button><button class="btn xs" data-zoneact="close">Cerrar</button></div></div>`;
    }else S.mapPop=null;
  }
  const tocItems=m.toc.map(t=>`<button class="mapitem" data-goto="${t.target_page}"><b>Índice, p. ${t.page}: ${esc(t.label)}</b><span>→ p. ${t.target_page}</span></button>`).join('');
  const discardedNote=m.discarded.length?` Se descartaron ${m.discarded.length} zona${m.discarded.length===1?'':'s'} con forma de lista pero sin años ni editoriales (p. ${m.discarded.map(d=>d.start_page).join(', ')}).`:'';
  const help=blocks.length>1||discarded.length?'Tocá una zona para ver qué tiene e incluirla o excluirla de la bibliografía.':'Tocá la zona para ver qué tiene.';
  host.innerHTML=`<div class="maphead"><b>Mapa del documento</b><span>${m.page_count} páginas</span></div><p class="mapnote">${help}</p><div class="mapblocks">${blockHtml}</div><div class="mapstrip">${ticks}</div><div class="maplegend"><span><i class="sec"></i>incluida</span><span><i class="off"></i>excluida</span><span><i class="cand"></i>posible bibliografía</span><span><i class="toc"></i>el índice apunta acá</span></div>${pop}${tocItems?`<div class="mapitems">${tocItems}</div>`:''}${m.candidates.length?'':`<p class="mapnote">No hay otras zonas con bibliografía.${discardedNote}</p>`}`;
  host.onclick=e=>{
    const z=e.target.closest('[data-zone]');
    if(z){const [kind,i]=z.dataset.zone.split(':');S.mapPop=S.mapPop&&S.mapPop.kind===kind&&S.mapPop.i===+i?null:{kind,i:+i};return renderDocMap()}
    const act=e.target.closest('[data-zoneact]');
    if(act&&S.mapPop){
      const {kind,i}=S.mapPop,a=act.dataset.zoneact;
      if(a==='close'){S.mapPop=null;return renderDocMap()}
      if(a==='exclude')return discardSections([i]);
      if(a==='include')return restoreSection(i);
      if(a==='addcand')return addCandidateSection(m.candidates[i]);
      if(a==='view'){const page=kind==='sec'?m.sections[i].start_page:discarded[i].section.start_page;if(kind==='sec')return setActiveSection(i);return goToDocPage(page,m)}
    }
    const t=e.target.closest('[data-page],[data-goto]');if(!t)return;
    goToDocPage(+(t.dataset.goto||t.dataset.page),m);
  };
};
// Sections of the map are the document's sections in the same order.
async function discardSections(indices){
  if(!S.doc||!indices.length)return;
  const before=(S.doc.discarded_sections||[]).length;
  try{
    const doc=await api(`/api/documents/${S.doc.id}/sections/discard`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices})});
    S.activeSection=0;S.docMaps={};S.mapPop={kind:'off',i:before};
    await selectDoc(doc.id);
    const n=((doc.discarded_sections||[])[before]?.reference_ids||[]).length;
    showViewerToast(`Zona excluida · ${n} referencia${n===1?'':'s'} dejan de contar · se puede incluir de nuevo desde el mapa`,3200);
  }catch(e){notify('No se pudo excluir la zona: '+e.message)}
}
async function restoreSection(index){
  if(!S.doc)return;
  try{
    const doc=await api(`/api/documents/${S.doc.id}/sections/restore`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index})});
    S.activeSection=0;S.docMaps={};S.mapPop=null;
    await selectDoc(doc.id);
    showViewerToast('Zona incluida de nuevo en la bibliografía',2400);
  }catch(e){notify('No se pudo incluir la zona: '+e.message)}
}
async function goToDocPage(page,m){
  const inSection=(S.doc.sections||[]).some(s=>page>=(s.start_page||1)&&page<=(s.end_page||S.doc.page_count));
  if(inSection){await ensureSectionForPage(page);scrollToPage(page);return}
  const cand=m.candidates.find(c=>page>=c.start_page&&page<=c.end_page);
  if(cand)return addCandidateSection(cand);
  showViewerToast(`La p. ${page} no está en ninguna sección. Usá “＋ sección” si querés revisarla.`,2800);
}
function addCandidateSection(c){
  S.doc.sections.push({label:'Referencias',start_page:c.start_page,start_y:Math.max(0,Math.floor((c.start_y||0)-4)),end_page:c.end_page,end_y:null,source:'manual'});
  S.activeSection=S.doc.sections.length-1;renderSections();renderSectionViewer({scrollPage:c.start_page});
  showViewerToast('Sección agregada sin guardar · “Aplicar” la extrae',3200);
}
function resolutionAssessment(r,index){return (r.consensus?.assessments||[]).find(x=>x.candidate_index===index)||null}
function semanticScore(r,index){return (r.semantic?.scores||[]).find(x=>x.candidate_index===index)?.similarity}
window.runSelectedResolution=async(refId=null)=>{
  if(!S.doc)return;const id=refId||S.selectedRef;if(!id)return notify('Seleccioná una referencia primero.');
  S.selectedRef=id;const layers=[...S.pipelineLayers];if(!layers.length)return notify('Seleccioná al menos una capa downstream.');
  if(S.resolutionRunning.has(id))return;S.resolutionRunning.add(id);
  try{
    const updated=await api(`/api/documents/${S.doc.id}/references/${id}/resolve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({layers})});
    const idx=S.doc.references.findIndex(x=>x.id===id);if(idx>=0)S.doc.references[idx]=updated;renderRefs();showResolutionResult(id);
  }catch(e){notify('No se pudieron ejecutar las capas: '+e.message)}finally{S.resolutionRunning.delete(id)}
};
window.showResolutionResult=id=>{
  const r=refBy(id);if(!r)return;const candidates=r.resolver_candidates||[],human=r.human_resolution||null,errors=r.resolution_run?.layer_errors||{};
  const status=`<div class="candidateinfo"><b>ResolutionDecision:</b> ${esc(human?.status||r.resolution_decision?.status||'no ejecutado')}<br><b>Consensus:</b> ${esc(r.consensus?.status||'no ejecutado')} · <b>RAG:</b> ${esc(r.rag_result?.status||'no ejecutado')} · <b>LLM adjudicador:</b> ${esc((r.rag_adjudication||r.adjudication)?.status||'no ejecutado')}${Object.keys(errors).length?`<div class="mini" style="color:var(--warn);margin-top:5px">${Object.entries(errors).map(([k,v])=>esc(k+': '+v)).join('<br>')}</div>`:''}</div>`;
  const cards=candidates.map((c,i)=>{const a=resolutionAssessment(r,i),sem=semanticScore(r,i),selected=human?.status==='human_confirmed'&&((human.identity_key&&c.identity_key&&human.identity_key===c.identity_key)||(!human.identity_key&&human.candidate_index===i));return `<div class="candidatecard ${selected?'human':''}"><div class="candidate-title">${i}. ${esc(c.title||'Sin título')} <span class="tag">${esc(c.source||'fuente')}</span></div><div class="candidate-meta">${esc((c.authors||[]).join('; ')||'autor —')} · ${esc(c.year||'año —')}<br>${esc(c.container_title||c.publisher||'')} ${c.doi?`· DOI ${esc(c.doi)}`:''}<br>evidencia determinística: ${a?esc(a.evidence_score):'—'} · similitud semántica: ${sem==null?'—':esc(sem)}</div><div class="actions" style="margin-top:6px"><button class="btn xs ${selected?'ok':'primary'}" onclick="confirmResolutionCandidate('${id}',${i})">${selected?'✓ confirmada':'Confirmar esta'}</button></div></div>`}).join('')||'<div class="mini">No se recuperaron candidatos externos.</div>';
  modal('Resolución · REF '+String(r.order).padStart(3,'0'),status+`<div class="candidategrid">${cards}</div>`,`<button class="btn" onclick="confirmResolutionNone('${id}')">Ninguna coincide</button><button class="btn primary" onclick="closeModal()">Cerrar</button>`);
};
window.confirmResolutionCandidate=async(id,index)=>{if(!S.doc)return;try{const updated=await api(`/api/documents/${S.doc.id}/references/${id}/human-resolution`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision:'candidate',candidate_index:index})});const i=S.doc.references.findIndex(x=>x.id===id);if(i>=0)S.doc.references[i]=updated;renderRefs();showResolutionResult(id)}catch(e){modalWarn('No se pudo confirmar: '+e.message)}};
window.confirmResolutionNone=async id=>{if(!S.doc)return;try{const updated=await api(`/api/documents/${S.doc.id}/references/${id}/human-resolution`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision:'none'})});const i=S.doc.references.findIndex(x=>x.id===id);if(i>=0)S.doc.references[i]=updated;renderRefs();closeModal()}catch(e){modalWarn('No se pudo guardar: '+e.message)}};
window.showParsed=id=>{
  const r=refBy(id);if(!r)return;const raw=r.parsed||{},p=r.effective_parsed||raw,over=r.parsed_review?.overrides||{};
  const fields=[['Autor principal','author'],['Autores','authors'],['Año','year'],['Tipo documental','publication_type'],['Título','title'],['Revista','journal'],['Editorial normalizada','publisher'],['Editorial observada','publisher_observed'],['DOI','doi']];
  const rows=fields.map(([label,key])=>{const changed=Object.prototype.hasOwnProperty.call(over,key),base=parserScalar(raw[key]),effective=parserScalar(p[key]);return `<div style="margin-bottom:8px"><b>${esc(label)}:</b> ${esc(effective||'—')}${changed?` <span class="tag warn">humano</span><div class="mini">parser: ${esc(base||'—')}</div>`:''}</div>`}).join('');
  const body=`<div class="notice"><b>Dos capas separadas.</b> <code>parsed</code> conserva exactamente la salida del parser; <code>effective_parsed</code> aplica encima las correcciones humanas de la planilla. Editar una celda no modifica el texto crudo.</div><div class="candidateinfo">${rows}<div><b>Parser:</b> ${esc(raw.parser_version||'—')} · ${esc(raw.parser_status||'—')}</div></div>`;
  modal('Campos parseados · REF '+String(r.order).padStart(3,'0'),body,`<button class="btn primary" onclick="closeModal()">Cerrar</button>`)
};
$('#searchRefs').oninput=renderRefs;
$('#toggleVisualText').onclick=()=>{S.cleanVisualText=!S.cleanVisualText;$('#toggleVisualText').textContent=S.cleanVisualText?'Aa · vista limpia':'Aa · texto original';renderRefs()};
window.clearRefSelection=()=>{S.selectedRef=null;S.origin=null;closeBelow();paintOrigin();paintHoverOverlays(null);renderRefs()};
// Desde la lista: lleva a la referencia y la abre debajo de su párrafo.
window.pickRef=async id=>{
  if(S.selectedRef===id)return clearRefSelection();
  S.selectedRef=id;const r=refBy(id);if(r?.start_page)await ensureSectionForPage(r.start_page);
  renderRefs();await selectOnPdf(id,'center');
};
function refBy(id){return S.doc.references.find(r=>r.id===id&&!r.deleted)}
window.copyRef=async(id,btn)=>{await navigator.clipboard.writeText(refBy(id).text);if(btn){btn.classList.add('copied');setTimeout(()=>btn.classList.remove('copied'),900)}};
window.pasteRef=async id=>{try{const text=await navigator.clipboard.readText();if(!text)return;if(!await confirmModal('¿Reemplazar esta referencia por el texto del portapapeles?'))return;await api(`/api/documents/${S.doc.id}/references/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,status:'reviewed'})});await selectDoc(S.doc.id)}catch(e){notify('No se pudo leer el portapapeles. Podés usar Editar y pegar con Ctrl+V.')}};
$('#copyAll').onclick=async()=>{if(!S.doc)return;await navigator.clipboard.writeText(S.doc.references.filter(r=>!r.deleted).map(r=>r.text).join('\n\n'))};

let modalLastFocus=null;
function modal(title,body,actions){
  modalLastFocus=document.activeElement;
  $('#modalHost').innerHTML=`<div class="modalback" onclick="if(event.target===this)closeModal()"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle" tabindex="-1"><h2 id="modalTitle">${esc(title)}</h2>${body}<div class="actions" style="margin-top:14px">${actions}</div></div></div>`;
  $('.modal')?.focus();
}
window.closeModal=()=>{
  $('#modalHost').innerHTML='';
  if(modalLastFocus&&document.contains(modalLastFocus))modalLastFocus.focus();
  modalLastFocus=null;
};
function modalFocusables(){
  const box=document.querySelector('#modalHost .modal');if(!box)return[];
  return[...box.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')].filter(el=>!el.disabled&&el.offsetParent!==null);
}
function notify(message){modal('Aviso',`<p>${esc(message)}</p>`,`<button class="btn primary" onclick="closeModal()">Cerrar</button>`)}
function modalWarn(message){
  const box=document.querySelector('#modalHost .modal');if(!box)return notify(message);
  let w=box.querySelector('.modal-inline-warn');if(!w){w=document.createElement('p');w.className='modal-inline-warn';w.style.color='var(--warn)';box.insertBefore(w,box.children[1])}
  w.textContent=message;
}
function confirmModal(message){
  return new Promise(resolve=>{
    modal('Confirmar',`<p>${esc(message)}</p>`,`<button class="btn" onclick="window.__confirmResolve(false)">Cancelar</button><button class="btn primary" onclick="window.__confirmResolve(true)">Confirmar</button>`);
    window.__confirmResolve=v=>{closeModal();delete window.__confirmResolve;resolve(v)};
  });
}
window.editRef=id=>{const r=refBy(id);modal('Editar referencia',`<textarea id="modalText">${esc(r.text)}</textarea>`,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="saveEdit('${id}')">Guardar</button>`)};
window.saveEdit=async id=>{const text=$('#modalText').value;if(!text.trim())return modalWarn('La referencia no puede quedar vacía.');try{await api(`/api/documents/${S.doc.id}/references/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,status:'reviewed'})});closeModal();await selectDoc(S.doc.id)}catch(e){modalWarn('No se pudo guardar: '+e.message)}};
window.splitRef=id=>{const r=refBy(id);modal('Dividir referencia',`<p class="mini">Poné una línea con <b>---</b> exactamente donde comienza la referencia siguiente.</p><textarea id="modalText">${esc(r.text)}</textarea>`,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="saveSplit('${id}')">Dividir</button>`)};
window.saveSplit=async id=>{const parts=$('#modalText').value.split(/\n?---\n?/).map(x=>x.trim()).filter(Boolean);if(parts.length<2)return modalWarn('Agregá --- entre las referencias.');try{S.doc=await api(`/api/documents/${S.doc.id}/references/${id}/split`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({parts})});closeModal();const nuevas=parts.map(refByText).filter(Boolean);S.selectedRef=null;await refreshAfterRefChange(nuevas[0]?.start_page);await loadDocs(S.doc.id);if(nuevas.length>1)showViewerToast(`Dividida en ${nuevas.map(refLabel).join(' y ')}`,3600)}catch(e){modalWarn('No se pudo dividir: '+e.message)}};
window.mergeNext=async id=>{const vis=S.doc.references.filter(r=>!r.deleted);const i=vis.findIndex(r=>r.id===id);if(i<0||i===vis.length-1)return notify('No hay referencia siguiente.');if(!await confirmModal('¿Unir esta referencia con la siguiente?'))return;try{S.doc=await api(`/api/documents/${S.doc.id}/references/${id}/merge`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({with_ref_id:vis[i+1].id})});S.selectedRef=null;await refreshAfterRefChange();await loadDocs(S.doc.id)}catch(e){notify('No se pudo unir: '+e.message)}};
window.deleteRef=async id=>{if(!await confirmModal('¿Eliminar esta referencia de la salida revisada?'))return;try{S.doc=await api(`/api/documents/${S.doc.id}/references/${id}`,{method:'DELETE'});S.selectedRef=null;await refreshAfterRefChange();await loadDocs(S.doc.id)}catch(e){notify('No se pudo eliminar: '+e.message)}};
window.markRef=async(id,status='reviewed')=>{try{await api(`/api/documents/${S.doc.id}/references/${id}/mark?status=${encodeURIComponent(status)}`,{method:'POST'});await selectDoc(S.doc.id)}catch(e){notify('No se pudo actualizar la referencia: '+e.message)}};
$('#insertRef').onclick=()=>{if(!S.doc)return;modal('Agregar referencia manualmente',`<textarea id="modalText" placeholder="Pegá o escribí la referencia"></textarea><div class="fields"><div class="field"><label>página inicial</label><input id="modalPage" type="number" value="${S.page}"></div><div class="field"><label>ubicación</label><input value="${S.selectedRef?'después de la seleccionada':'al final'}" disabled></div></div>`,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="saveInsert()">Agregar</button>`)};
window.saveInsert=async()=>{const text=$('#modalText').value,insertPage=+$('#modalPage').value||null;if(!text.trim())return modalWarn('La referencia no puede quedar vacía.');try{S.doc=await api(`/api/documents/${S.doc.id}/references`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,start_page:+$('#modalPage').value,after_ref_id:S.selectedRef,source:'human_insert'})});closeModal();await refreshAfterRefChange(insertPage);await loadDocs(S.doc.id)}catch(e){modalWarn('No se pudo agregar: '+e.message)}};

function hideViewerToast(){clearTimeout(S.viewerToastTimer);const t=$('#viewerToast');if(t){t.classList.add('hidden');t.textContent=''}}
function showViewerToast(message,duration=2200){const t=$('#viewerToast');if(!t)return;clearTimeout(S.viewerToastTimer);t.textContent=message;t.classList.remove('hidden');if(duration>0)S.viewerToastTimer=setTimeout(hideViewerToast,duration)}
function cancelPdfModes({rerender=false}={}){const had=S.markMode||S.addFromPdfMode;S.markMode=null;S.addFromPdfMode=false;updateViewerMode();hideViewerToast();if(had&&rerender&&S.doc)renderSectionViewer({scrollPage:S.page})}

$('#addFromPdf').onclick=()=>{
  if(!S.doc)return;if(!activeSection())return notify('Primero agregá o seleccioná una sección de referencias.');
  if(S.addFromPdfMode){cancelPdfModes();return}
  S.markMode=null;S.addFromPdfMode=true;updateViewerMode();
  showViewerToast('Clic en la primera línea de la referencia que falta · Esc cancela',2200);
};
async function candidateFromPoint(page,y,x=null){
  const sec=activeSection();if(!sec)return;
  S.addFromPdfMode=false;updateViewerMode();hideViewerToast();showViewerToast('Buscando la referencia…',1400);
  try{
    const c=await api(`/api/documents/${S.doc.id}/references/candidate-from-point`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({page,y,x,end_page:sec.end_page,end_y:sec.end_y,section_label:sec.label||'Referencias',margin_pt:42})});
    S.pdfCandidate=c;
    let warn='';
    if(c.already_present_ref_id)warn=`<div class="candidatewarn">BiblioRef encontró una referencia muy parecida ya cargada. Revisá antes de duplicarla.</div>`;
    const placement=c.before_ref_order?`Se insertará antes de REF ${String(c.before_ref_order).padStart(3,'0')}.`:'Se agregará en la posición disponible; luego podés moverla uniendo/dividiendo si hace falta.';
    modal('Agregar referencia desde el PDF',`${warn}<div class="candidateinfo"><b>Ubicación:</b> pág. ${c.start_page}${c.end_page!==c.start_page?'–'+c.end_page:''} · clic sobre “${esc(c.clicked_line)}”<br><span class="mini">margen automático ${c.selection_margin_pt||42} pt${c.snap_distance_pt?` · ajuste ${c.snap_distance_pt} pt`:``}${c.trusted_click_override?' · inicio forzado por tu clic':''} · ${esc(placement)}</span></div><div class="candidateinfo visualpreview"><b>Vista limpia:</b><br>${esc(visualText(c.text))}</div><textarea id="modalText">${esc(c.text)}</textarea>`,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="savePdfCandidate()">Agregar referencia</button>`);
  }catch(e){hideViewerToast();notify('No se pudo formar una referencia desde ese punto: '+e.message)}
}
window.savePdfCandidate=async()=>{
  const c=S.pdfCandidate;if(!c)return;const text=$('#modalText').value.trim();if(!text)return modalWarn('La referencia no puede quedar vacía.');
  S.doc=await api(`/api/documents/${S.doc.id}/references`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,start_page:c.start_page,end_page:c.end_page,start_y:c.start_y,before_ref_id:c.before_ref_id,source:'human_pdf_click'})});
  if(S.pendingMissingId){try{await api(`/api/documents/${S.doc.id}/audit-checks/${S.pendingMissingId}/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision:'resolved',note:'reference_added_from_pdf'})})}catch(e){}S.pendingMissingId=null}
  const page=c.start_page;closeModal();S.pdfCandidate=null;invalidateRefGeometry();await loadDocs(S.doc.id);S.page=page;await renderSectionViewer({scrollPage:page});
};

window.originRef=async id=>{S.selectedRef=id;S.origin=await fetchOrigin(id);S.page=S.origin?.start_page||1;await ensureSectionForPage(S.page);await renderSectionViewer({scrollPage:S.page});renderRefs()};
function overlayRectFor(origin,p){
  const span=(origin?.span||[]).filter(x=>x.page===p.page);
  // The span is the reference's own line range; candidates are fuzzy matches and can bleed into neighbours.
  const cands=span.length?span:(origin?.candidates||[]).filter(x=>x.page===p.page).slice(0,1);
  if(!cands.length)return null;
  const y0=Math.max(p.crop_top,Math.min(...cands.map(c=>c.y0))),y1=Math.min(p.crop_bottom,Math.max(...cands.map(c=>c.y1)));
  if(y1<=y0)return null;
  const x0=Math.min(...cands.map(c=>c.x0)),x1=Math.max(...cands.map(c=>c.x1));
  return {left:(x0/p.width*100)+'%',width:Math.max(2,(x1-x0)/p.width*100)+'%',top:((y0-p.crop_top)/(p.crop_bottom-p.crop_top)*100)+'%',height:Math.max(1,(y1-y0)/(p.crop_bottom-p.crop_top)*100)+'%'};
}
function cropParams(crop){return {page:+crop.dataset.page,width:+crop.dataset.width,height:+crop.dataset.height,crop_top:+crop.dataset.cropTop,crop_bottom:+crop.dataset.cropBottom}}
function paintHoverOverlays(origin){
  $$('#pageWrap .pdfcrop').forEach(crop=>{
    crop.querySelectorAll('.hoverbox').forEach(x=>x.remove());
    if(!origin)return;
    const rect=overlayRectFor(origin,cropParams(crop));if(!rect)return;
    const o=document.createElement('div');o.className='overlay hoverbox';Object.assign(o.style,rect);crop.appendChild(o);
  });
}
/* Marca todo lo extraído sobre el PDF. Dos colores: azul extraída, ámbar falta. El párrafo sin marco es el que falta. */
window.refreshPdfMarks=async()=>{
  const wrap=$('#pageWrap');if(!wrap||!S.doc)return;
  const seq=S.marksSeq=(S.marksSeq||0)+1;
  const spans=await ensureSpans();
  if(seq!==S.marksSeq||!S.doc)return;
  wrap.querySelectorAll('.refmark').forEach(x=>x.remove());
  const byId=new Map((S.doc.references||[]).filter(r=>!r.deleted).map(r=>[r.id,r]));
  const missing=activeMissing();
  $$('#pageWrap .pdfcrop').forEach(crop=>{
    const p=cropParams(crop);
    Object.entries(spans).forEach(([id,span])=>{
      const r=byId.get(id);if(!r)return;
      const rect=overlayRectFor({span},p);if(!rect)return;
      const mark=document.createElement('div');mark.className='refmark';
      mark.dataset.ref=id;mark.title=`REF ${String(r.order).padStart(3,'0')}`;
      Object.assign(mark.style,rect);
      mark.onclick=e=>{e.stopPropagation();togglePdfRef(id)};
      crop.appendChild(mark);
    });
    // La faltante solo trae la altura de su primera línea; el ancho se toma de las referencias de esa página.
    const boxes=Object.values(spans).flat().filter(b=>b.page===p.page);
    const x0=boxes.length?Math.min(...boxes.map(b=>b.x0)):p.width*.1,x1=boxes.length?Math.max(...boxes.map(b=>b.x1)):p.width*.9;
    const h=Math.max(1,p.crop_bottom-p.crop_top);
    missing.filter(x=>x.page===p.page&&x.y>=p.crop_top&&x.y<p.crop_bottom).forEach(x=>{
      const mark=document.createElement('div');mark.className='refmark miss';
      mark.dataset.missing=x.id;mark.title='Falta: este párrafo no tiene referencia extraída';
      Object.assign(mark.style,{left:(x0/p.width*100)+'%',width:((x1-x0)/p.width*100)+'%',top:((x.y-p.crop_top)/h*100)+'%',height:(Math.min(16,p.crop_bottom-x.y)/h*100)+'%'});
      mark.onclick=e=>{e.stopPropagation();toggleOpenMissing(x.id)};
      crop.appendChild(mark);
    });
  });
  markCurrent();
};
function markCurrent(){$$('#pageWrap .refmark').forEach(m=>m.classList.toggle('current',m.dataset.ref===S.selectedRef))}
function paintOrigin(){
  $$('#pageWrap .pdfcrop').forEach(crop=>{
    crop.querySelectorAll('.overlay:not(.hoverbox)').forEach(x=>x.remove());
    const rect=overlayRectFor(S.origin,cropParams(crop));if(!rect)return;
    const o=document.createElement('div');o.className='overlay';Object.assign(o.style,rect);crop.appendChild(o);
  });
  markCurrent();
}
async function fetchOrigin(id){
  let origin=S.originCache[id];
  if(!origin){try{origin=await api(`/api/documents/${S.doc.id}/references/${id}/origin`)}catch{return null}S.originCache[id]=origin}
  return origin;
}
async function ensurePageOrigins(page){
  if(!S.pageOriginsCache)S.pageOriginsCache={};
  if(S.pageOriginsCache[page])return S.pageOriginsCache[page];
  const candidates=(S.doc.references||[]).filter(r=>!r.deleted&&(r.start_page||1)<=page&&(r.end_page||r.start_page||1)>=page);
  const promise=Promise.all(candidates.map(async r=>({id:r.id,origin:await fetchOrigin(r.id)}))).then(list=>list.filter(x=>x.origin));
  S.pageOriginsCache[page]=promise;
  return promise;
}
window.hoverRefStart=id=>{
  S.hoverRefId=id;clearTimeout(S.hoverTimer);
  S.hoverTimer=setTimeout(async()=>{
    if(!S.doc||S.hoverRefId!==id)return;
    let origin=S.originCache[id];
    if(!origin){try{origin=await api(`/api/documents/${S.doc.id}/references/${id}/origin`)}catch{return}S.originCache[id]=origin}
    if(S.hoverRefId!==id)return;
    paintHoverOverlays(origin);
  },180);
};
window.hoverRefEnd=id=>{
  clearTimeout(S.hoverTimer);
  if(S.hoverRefId===id)S.hoverRefId=null;
  paintHoverOverlays(null);
};
async function ensureSectionForPage(page){
  const secs=S.doc?.sections||[];const idx=secs.findIndex(s=>page>=(s.start_page||1)&&page<=(s.end_page||S.doc.page_count));
  if(idx>=0&&idx!==S.activeSection){S.activeSection=idx;renderSections();await renderSectionViewer({scrollPage:page})}
}
function scrollToPage(page){S.page=Math.max(1,Math.min(page,S.doc?.page_count||1));$('#pageInput').value=S.page;const el=$(`#pageWrap [data-page="${S.page}"]`);if(el)el.scrollIntoView({behavior:'smooth',block:'start'})}

async function renderSectionViewer({scrollPage=null}={}){
  if(!S.doc)return;const seq=++S.renderSeq,wrap=$('#pageWrap');syncSectionDrafts();const sec=activeSection();
  if(!sec){wrap.innerHTML='<div class="viewerempty">No hay una sección de referencias delimitada. Usá “＋ sección” en la barra del visor.</div>';$('#viewerTitle').textContent=displayTitle(S.doc);return}
  const sp=Math.max(1,+sec.start_page||1),ep=Math.min(S.doc.page_count,+sec.end_page||sp),sy=+sec.start_y||0,ey=sec.end_y==null||sec.end_y===''?null:+sec.end_y;
  if(ep<sp){wrap.innerHTML='<div class="viewerempty">El final de la sección debe estar después del inicio.</div>';return}
  $('#viewerTitle').textContent=displayTitle(S.doc);updateViewerMode();
  wrap.innerHTML='<div class="viewerempty"><span class="loader"></span> preparando recorte continuo…</div>';
  try{
    const qs=new URLSearchParams({start_page:sp,end_page:ep,start_y:sy});if(ey!=null)qs.set('end_y',ey);
    const preview=await api(`/api/documents/${S.doc.id}/section-preview?${qs}`);if(seq!==S.renderSeq)return;S.sectionPreview=preview;
    wrap.innerHTML='';
    if(S.markMode)showViewerToast(S.markMode==='start'?'Clic donde comienza la sección · Esc cancela':'Clic donde termina la sección · Esc cancela',2200);
    S.openState=null;S.imgToken=Date.now();
    preview.pages.forEach(p=>wrap.appendChild(buildCrop(p)));
    paintOrigin();renderMargin();refreshPdfMarks();
    const target=scrollPage||S.page||sp;requestAnimationFrame(()=>scrollToPage(Math.max(sp,Math.min(ep,target))));
  }catch(e){if(seq!==S.renderSeq)return;wrap.innerHTML=`<div class="viewerempty">No se pudo preparar la vista de sección: ${esc(e.message)}</div>`}
}
function viewerClick(ev,crop,p){
  if(!S.doc)return;const rect=crop.getBoundingClientRect(),rel=Math.max(0,Math.min(1,(ev.clientY-rect.top)/rect.height)),relx=Math.max(0,Math.min(1,(ev.clientX-rect.left)/rect.width));const y=p.crop_top+rel*(p.crop_bottom-p.crop_top),x=relx*p.width;S.page=p.page;$('#pageInput').value=S.page;
  if(S.markMode){const sec=S.doc.sections[S.activeSection]||S.doc.sections[0];if(S.markMode==='start'){sec.start_page=p.page;sec.start_y=Math.round(y*10)/10}else{sec.end_page=p.page;sec.end_y=Math.round(y*10)/10}S.markMode=null;renderSections();renderSectionViewer({scrollPage:p.page});return}
  if(S.addFromPdfMode){S.addFromPdfMode=false;updateViewerMode();hideViewerToast();candidateFromPoint(p.page,Math.round(y*10)/10,Math.round(x*10)/10);return}
  pickRefNearPoint(p.page,y);
}
async function pickRefNearPoint(page,y){
  const list=await ensurePageOrigins(page);
  let best=null,bestDist=Infinity;
  for(const{id,origin}of list){
    const boxes=(origin.span||origin.candidates||[]).filter(x=>x.page===page);if(!boxes.length)continue;
    const top=Math.min(...boxes.map(x=>x.y0)),bottom=Math.max(...boxes.map(x=>x.y1));
    const dist=y>=top&&y<=bottom?0:Math.min(Math.abs(top-y),Math.abs(bottom-y));
    if(dist<bestDist){bestDist=dist;best=id}
  }
  // A click on blank space or a heading is a request to clear, not to grab the nearest reference.
  if(best&&bestDist<=40)togglePdfRef(best);
  else clearRefSelection();
}

document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){
    if($('#modalHost').innerHTML.trim()){e.preventDefault();closeModal();return}
    if(S.addFromPdfMode||S.markMode){e.preventDefault();cancelPdfModes();showViewerToast('Selección cancelada',900);return}
    if(S.selectedRef){e.preventDefault();clearRefSelection()}
    return;
  }
  if(e.key==='Tab'&&$('#modalHost').innerHTML.trim()){
    const focusables=modalFocusables();if(!focusables.length)return;
    const first=focusables[0],last=focusables[focusables.length-1];
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
  }
});

$('#prevPage').onclick=()=>{if(!S.doc)return;const sec=activeSection();scrollToPage(Math.max(sec?.start_page||1,S.page-1))};
$('#nextPage').onclick=()=>{if(!S.doc)return;const sec=activeSection();scrollToPage(Math.min(sec?.end_page||S.doc.page_count,S.page+1))};
$('#goPage').onclick=async()=>{if(!S.doc)return;const p=+$('#pageInput').value;await ensureSectionForPage(p);scrollToPage(p)};

$('#dashSelectAll').onclick=()=>{S.dashboardTouched=true;S.dashboardIds=new Set(S.docs.map(d=>d.id));renderDashboard()};
$('#dashSelectNone').onclick=()=>{S.dashboardTouched=true;S.dashboardIds.clear();renderDashboard()};
$('#bulkMetadata').onclick=()=>bulkMetadataModal(selectedDashboardIds());
$('#bulkMetadataReview').onclick=()=>bulkMetadataModal(S.doc?[S.doc.id]:[]);
$('#dashboardExport').onclick=()=>openExportModal(selectedDashboardIds(),'Exportar selección');
$('#exportCurrent').onclick=()=>{if(S.doc)openExportModal([S.doc.id],`Exportar · ${titleOf(S.doc)}`)};
async function upload(files){return importProjectFiles(files)}
$('#chooseFiles').onclick=()=>$('#fileInput').click();$('#chooseFolder').onclick=()=>$('#folderInput').click();$('#chooseDrive').onclick=()=>openGoogleDrive();
$('#fileInput').onchange=async e=>{await upload(e.target.files);e.target.value=''};$('#folderInput').onchange=async e=>{await upload(e.target.files);e.target.value=''};
const drop=$('#drop');drop.ondragover=e=>{e.preventDefault();drop.classList.add('drag')};drop.ondragleave=()=>drop.classList.remove('drag');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('drag');importDroppedFiles(e.dataTransfer)};

const DRIVE_ICON_FOLDER='<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1.5 3.5a1 1 0 0 1 1-1h3l1.2 1.5H13.5a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-8.5Z"/></svg>';
const DRIVE_ICON_ZIP='<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 1.5h5l3 3v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1Z"/><path d="M9 1.5V4.5h3"/><path d="M7.5 6v1M7.5 8.2v1M7.5 10.4v1"/></svg>';
const DRIVE_ICON_FILE='<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 1.5h5l3 3v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1Z"/><path d="M9 1.5V4.5h3"/></svg>';
function driveAccountLine(){const u=S.driveStatus?.user||{},name=u.displayName||'',email=u.emailAddress||'';if(!name&&!email)return '<div class="mini">Acceso OAuth · drive.readonly · solo lectura</div>';return `<div class="mini"><b>Cuenta conectada</b> · ${esc(name||email)}${name&&email?' · '+esc(email):''} · drive.readonly</div>`}
function driveItemRow(x){const icon=x.is_folder?DRIVE_ICON_FOLDER:(/\.zip$/i.test(x.name)?DRIVE_ICON_ZIP:DRIVE_ICON_FILE);const open=x.is_folder?`<button class="btn xs" onclick="driveEnterEncoded('${encodeURIComponent(x.effective_id)}','${encodeURIComponent(x.name)}')">Abrir</button>`:'';return `<div style="display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;border-bottom:1px solid var(--line);padding:7px 2px"><input class="drive-pick" type="checkbox" value="${esc(x.id)}"><div><b style="display:inline-flex;align-items:center;gap:6px;color:var(--ink)">${icon}${esc(x.name)}</b><div class="mini">${x.is_folder?'carpeta':(x.size?Math.round(x.size/1024/1024*10)/10+' MB':'archivo')}${x.is_shortcut?' · acceso directo':''}</div></div>${open}</div>`}
function driveSearchBox(value=''){return `<div style="display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px;margin:10px 0"><input id="driveSearchInput" class="search" value="${esc(value)}" placeholder="Buscar PDF, ZIP o carpetas…" aria-label="Buscar en todo Google Drive"><button class="btn primary xs" onclick="driveSearch()">Buscar en todo Drive</button></div>`}
function bindDriveSearchEnter(){setTimeout(()=>{const input=$('#driveSearchInput');if(input)input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();driveSearch()}}},0)}
function driveItemsBox(items,empty){return `<div style="max-height:420px;overflow:auto;border:1px solid var(--line);padding:0 8px">${(items||[]).map(driveItemRow).join('')||`<div class="mini" style="padding:14px">${esc(empty)}</div>`}</div>`}
async function renderDriveFolder(folderId='root',folderName='Mi unidad',push=false){try{const data=await api(`/api/integrations/google-drive/list?folder_id=${encodeURIComponent(folderId)}`);if(push)S.driveStack.push({id:folderId,name:data.folder_name||folderName});const back=S.driveStack.length>1?'<button class="btn xs" onclick="driveBack()">← Atrás</button>':'';const body=`<div class="candidateinfo"><b>Google Drive · solo lectura</b>${driveAccountLine()}</div>${driveSearchBox()}<div class="mini" style="margin:0 0 6px">${esc((S.driveStack.map(x=>x.name).join(' / '))||data.folder_name||'Mi unidad')}</div>${driveItemsBox(data.items,'No hay PDF, ZIP o carpetas visibles aquí.')}<p class="mini">Podés marcar PDF, ZIP o una carpeta completa. Las carpetas marcadas se importan recursivamente.</p>`;modal('Importar desde Google Drive',body,`${back}<button class="btn" onclick="driveDisconnect()">Desconectar</button><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="driveImportSelected()">Importar selección</button>`);bindDriveSearchEnter()}catch(e){notify('No se pudo listar Google Drive: '+e.message)}}
window.driveSearch=async()=>{const input=$('#driveSearchInput'),q=(input?.value||'').trim();if(q.length<2)return modalWarn('Escribí al menos 2 caracteres para buscar en Drive.');try{const data=await api(`/api/integrations/google-drive/search?q=${encodeURIComponent(q)}&limit=100`);const tail=data.truncated?' · primeros resultados':'',body=`<div class="candidateinfo"><b>Google Drive · resultados de búsqueda</b>${driveAccountLine()}</div>${driveSearchBox(data.query||q)}<div class="mini" style="margin:0 0 6px">${(data.items||[]).length} resultado(s) compatible(s)${tail}</div>${driveItemsBox(data.items,'No se encontraron PDF, ZIP o carpetas con ese nombre.')}<p class="mini">La búsqueda consulta nombres, no el contenido de tus documentos.</p>`;modal('Buscar en Google Drive',body,`<button class="btn" onclick="driveRoot()">← Mi unidad</button><button class="btn" onclick="driveDisconnect()">Desconectar</button><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="driveImportSelected()">Importar selección</button>`);bindDriveSearchEnter()}catch(e){notify('No se pudo buscar en Google Drive: '+e.message)}};
window.openGoogleDrive=async()=>{try{const st=await api('/api/integrations/google-drive/status');S.driveStatus=st;if(!st.available){return modal('Google Drive',`<p>Esta instalación no incluye las dependencias de Google Drive.</p><p class="mini">Reinstalá usando requirements-app.txt de APP v2.7.0.</p>`,`<button class="btn" onclick="closeModal()">Cerrar</button>`)}if(!st.configured){return modal('Configurar Google Drive',`<p><b>Configuración inicial · una sola vez por equipo</b></p><ol style="padding-left:20px;line-height:1.7"><li>Creá o elegí un proyecto en Google Cloud.</li><li>Habilitá <b>Google Drive API</b>.</li><li>Configurá la pantalla de consentimiento OAuth.</li><li>Creá un OAuth client ID tipo <b>Aplicación de escritorio</b> y descargá el JSON.</li></ol><p class="mini">La credencial y el token se guardan sólo en este equipo. BiblioRef usa <b>drive.readonly</b>: puede buscar/listar/descargar, nunca modificar Drive.</p><div class="actions"><button class="btn xs" onclick="window.open('https://console.cloud.google.com/apis/library/drive.googleapis.com','_blank','noopener')">Abrir Google Drive API</button><button class="btn xs" onclick="window.open('https://console.cloud.google.com/apis/credentials','_blank','noopener')">Abrir credenciales OAuth</button></div>`,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="document.querySelector('#driveSecretInput').click()">Elegir client_secret.json</button>`)}if(!st.connected){modal('Conectar Google Drive',`<p>La credencial OAuth está configurada.</p><p class="mini">Al conectar se abrirá el navegador para autorizar <b>drive.readonly</b>. BiblioRef no puede modificar tus archivos.</p>`,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" onclick="driveConnect()">Conectar</button>`);return}S.driveStack=[{id:'root',name:'Mi unidad'}];await renderDriveFolder('root','Mi unidad',false)}catch(e){notify(e.message)}};
$('#driveSecretInput').onchange=async e=>{const f=e.target.files?.[0];if(!f)return;const fd=new FormData();fd.append('file',f);try{await api('/api/integrations/google-drive/client-secret',{method:'POST',body:fd});e.target.value='';closeModal();openGoogleDrive()}catch(err){notify('No se pudo guardar la credencial: '+err.message)}};
window.driveConnect=async()=>{try{$('#globalStatus').innerHTML='<span class="loader"></span> conectando Drive';await api('/api/integrations/google-drive/connect',{method:'POST'});S.driveStatus=await api('/api/integrations/google-drive/status');closeModal();S.driveStack=[{id:'root',name:'Mi unidad'}];await renderDriveFolder('root','Mi unidad',false);updateGlobal()}catch(e){notify(e.message);updateGlobal()}};
window.driveDisconnect=async()=>{if(!await confirmModal('¿Desconectar Google Drive de BiblioRef en este equipo?'))return;await api('/api/integrations/google-drive/disconnect',{method:'POST'});S.driveStatus=null;closeModal()};
window.driveEnterEncoded=async(id,name)=>{await renderDriveFolder(decodeURIComponent(id),decodeURIComponent(name),true)};
window.driveEnter=async(id,name)=>{await renderDriveFolder(id,name,true)};
window.driveBack=async()=>{if(S.driveStack.length<=1)return;S.driveStack.pop();const x=S.driveStack[S.driveStack.length-1];await renderDriveFolder(x.id,x.name,false)};
window.driveRoot=async()=>{S.driveStack=[{id:'root',name:'Mi unidad'}];await renderDriveFolder('root','Mi unidad',false)};
window.driveImportSelected=async()=>{if(S.importBusy||!S.project)return;const projectId=S.project.id;const ids=$$('.drive-pick:checked').map(x=>x.value);if(!ids.length)return modalWarn('Seleccioná al menos un PDF, ZIP o carpeta.');const work=startWork('Importando desde Google Drive','Descargando y leyendo los archivos seleccionados.');try{importBusy(true);$('#globalStatus').innerHTML='<span class="loader"></span> importando desde Drive';const r=await api('/api/integrations/google-drive/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file_ids:ids,recursive_folders:true,project_id:projectId})});closeModal();S.exportTouched=false;await loadDocs(r.documents[0]?.id);finishWork(work,'Importación de Drive terminada',`${r.documents.length} tesis incorporadas.`);if(r.warnings?.length)notify(`Importación completada con ${r.warnings.length} aviso(s).`)}catch(e){finishWork(work,'No se pudo importar desde Drive',e.message,true);notify('No se pudo importar desde Drive: '+e.message)}finally{importBusy(false);updateGlobal()}};
window.analyzeOne=async(id,profile='stable',navigate=true)=>{const projectId=S.project?.id;const work=startWork('Procesando las referencias','La tesis se está analizando.');$('#globalStatus').innerHTML='<span class="loader"></span> procesando';try{await api(`/api/documents/${id}/analyze`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rescue_profile:profile,worker:true})});if(S.project?.id!==projectId)return;await loadDocs(id);if(S.project?.id!==projectId)return;if(navigate){show('review');await selectDoc(id)}finishWork(work,'Referencias procesadas','La tesis está disponible para revisar.')}catch(e){if(S.project?.id!==projectId)return;finishWork(work,'No se pudo procesar la tesis',e.message,true);notify('No se pudo procesar la tesis: '+e.message);await loadDocs(id)}};
$('#analyzeAll').onclick=async()=>{
  const projectId=S.project?.id;
  const pending=processableDocs().map(x=>x.id);
  if(!pending.length){show('project');renderDashboard();return}
  const work=startWork('Procesando las referencias',`0 de ${pending.length} tesis terminadas.`);
  if(S.analysisBusy||S.importBusy)return;
  const button=$('#analyzeAll');S.analysisBusy=true;button.disabled=true;
  let failed=0,completed=0,next=0;
  const capacity=Math.max(1,Math.min(pending.length,S.capabilities?.processing?.max_workers||1));
  const active=new Map(),started=Date.now();
  const progress=()=>updateWork(work,{title:'Procesando las referencias',detail:`${completed} de ${pending.length} terminadas · hasta ${capacity} tesis en paralelo · ${Math.floor((Date.now()-started)/1000)} s.`,percent:Math.min(99,100*completed/pending.length),active:[...active].map(([id,since])=>({filename:S.docs.find(d=>d.id===id)?.filename||id,seconds:Math.floor((Date.now()-since)/1000)}))});
  const clock=setInterval(progress,1000);
  const consume=async()=>{
    while(next<pending.length&&S.project?.id===projectId){
      const id=pending[next++];active.set(id,Date.now());progress();
      try{
        const doc=await api(`/api/documents/${id}/analyze`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rescue_profile:'stable',worker:true})});
        if(S.project?.id===projectId){const index=S.docs.findIndex(d=>d.id===id);if(index>=0)S.docs[index]=doc;renderCards();updateGlobal()}
      }catch(e){failed++;console.error(e)}
      finally{completed++;active.delete(id);progress()}
    }
  };
  try{
    await Promise.all(Array.from({length:capacity},consume));
    if(S.project?.id!==projectId)return;
    await loadDocs();if(S.project?.id!==projectId)return;
    S.dashboardTouched=false;S.dashboardIds=new Set(processedDocs().map(d=>d.id));show('project');renderDashboard();
    finishWork(work,failed?'Procesamiento terminado con avisos':'Referencias procesadas',`${pending.length-failed} de ${pending.length} tesis procesadas.${failed?' Revisá las tesis que fallaron.':''}`,failed===pending.length);
  }catch(e){finishWork(work,'No se pudo completar el procesamiento',e.message,true)}
  finally{clearInterval(clock);S.analysisBusy=false;button.disabled=S.importBusy||!S.docs.length;renderCards();updateGlobal()}
};

function renderExport(){if(!S.exportTouched&&S.exportIds.size===0)S.exportIds=new Set(S.docs.filter(d=>d.status!=='uploaded'&&d.status!=='processing').map(d=>d.id));const el=$('#exportDocs');el.innerHTML=S.docs.map(d=>`<label class="exportdoc"><input type="checkbox" ${S.exportIds.has(d.id)?'checked':''} onchange="toggleExport('${d.id}',this.checked)"><div><div class="etitle"><b>${esc(thesisNumber(d)||'')}</b>${thesisNumber(d)?' — ':''}${esc(displayTitle(d))}</div><div class="efile">${esc(d.filename)} · ${d.n_references||0} refs · ${statusText(d)}</div></div><span class="pill ${pillClass(d)}">${statusText(d)}</span></label>`).join('')||'<div class="mini">No hay tesis cargadas.</div>';const selected=S.docs.filter(d=>S.exportIds.has(d.id));const refs=selected.reduce((n,d)=>n+(d.n_references||0),0);$('#exportSummary').textContent=`${selected.length} tesis seleccionadas · ${refs} referencias`;$$('[data-export]').forEach(b=>b.disabled=selected.length===0)}
window.toggleExport=(id,on)=>{S.exportTouched=true;if(on)S.exportIds.add(id);else S.exportIds.delete(id);renderExport()};
$('#selectAllExport').onclick=()=>{S.exportTouched=true;S.exportIds=new Set(S.docs.filter(d=>d.status!=='processing').map(d=>d.id));renderExport()};$('#selectNoneExport').onclick=()=>{S.exportTouched=true;S.exportIds.clear();renderExport()};
function exportQuery(){return encodeURIComponent([...S.exportIds].join(','))}
// Exporting a whole project takes a while, and a server error used to leave the button silent.
async function downloadExport(url,what){
  const work=typeof startWork==='function'?startWork(`Armando ${what}`,'Puede tardar en un proyecto grande.'):null;
  try{
    const response=await fetch(url,{cache:'no-store'});
    if(!response.ok){let m=await response.text();try{m=JSON.parse(m).detail||m}catch{m=`Error del servidor (código ${response.status}).`}throw new Error(m)}
    const blob=await response.blob();
    const name=(response.headers.get('content-disposition')||'').match(/filename="?([^";]+)"?/)?.[1]||'biblioref';
    const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=name;link.click();
    setTimeout(()=>URL.revokeObjectURL(link.href),10000);
    if(work)finishWork(work,'Descarga lista',name);
  }catch(err){
    if(work)finishWork(work,`No se pudo armar ${what}`,err.message,true);
    notify(`No se pudo armar ${what}: `+err.message);
  }
}
$$('[data-export]').forEach(b=>b.onclick=()=>{if(S.exportIds.size)downloadExport(`/api/project/export/selection/${b.dataset.export}?documents=${exportQuery()}`,`la exportación en ${b.dataset.export.toUpperCase()}`)});
$('#exportCorrections').onclick=()=>{if(S.exportIds.size)downloadExport(`/api/project/export/corrections.json?documents=${exportQuery()}`,'las correcciones')};
