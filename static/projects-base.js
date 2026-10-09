/* Project navigation and import UI. No bibliography extraction rules live here. */
const folderIcon='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M3 6h6l2 3h10v11H3Z"/><path d="M3 6V4h7l2 2h8v3"/></svg>';
const fileIcon='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M5 3h9l5 5v13H5Z"/><path d="M14 3v6h5M8 13h8M8 17h6"/></svg>';

function startWork(title,detail='',{announceDone=false}={}){
  clearTimeout(S.workHideTimer);
  const token=(S.workSequence||0)+1;S.workSequence=token;S.workAnnounce=announceDone;
  updateWork(token,{title,detail,percent:null,state:'busy'});return token;
}
function updateWork(token,{title,detail='',percent=null,state='busy',active=[]}){
  if(token!==S.workSequence)return;
  const panel=$('#workProgress'),bar=$('#workProgressBar');
  const announce=$('#workProgressTitle').textContent!==title||panel.dataset.state!==state;
  panel.classList.remove('hidden');panel.dataset.state=state;panel.setAttribute('aria-busy',String(state==='busy'));
  $('#workProgressTitle').textContent=title;$('#workProgressDetail').textContent=detail;
  $('#workProgressFiles').innerHTML=active.map(x=>`<li><span>${esc(x.filename)}</span><b>${x.seconds} s${x.seconds>=30?' · sigue en este archivo':''}</b></li>`).join('');
  $('#workProgressIcon').textContent=state==='busy'?'':state==='error'?'!':'✓';
  const amount=Number.isFinite(percent)?Math.max(0,Math.min(100,percent)):null;
  bar.classList.toggle('indeterminate',amount===null&&state==='busy');
  if(amount===null){bar.removeAttribute('aria-valuenow');$('#workProgressFill').style.width=state==='busy'?'35%':'0%'}
  else{bar.setAttribute('aria-valuenow',String(Math.round(amount)));$('#workProgressFill').style.width=amount+'%'}
  $('#workProgressValue').textContent=amount===null?(state==='busy'?'En curso':state==='error'?'Revisar':'Listo'):Math.round(amount)+'%';
  if(announce)$('#workProgressStatus').textContent=title+'. '+detail;
}
function finishWork(token,title,detail='',error=false){
  updateWork(token,{title,detail,state:error?'error':'done',percent:error?null:100});
  // A finished task is announced once and then leaves; errors stay until the next task replaces them.
  clearTimeout(S.workHideTimer);
  // Only opening a project or loading PDFs is announced in green; other tasks just leave when done.
  if(!error&&token===S.workSequence&&!S.workAnnounce){$('#workProgress').classList.add('hidden');return}
  if(!error&&token===S.workSequence)S.workHideTimer=setTimeout(()=>{if(token===S.workSequence&&$('#workProgress').dataset.state==='done')$('#workProgress').classList.add('hidden')},3500);
}
function mergeTreeBranches(target,branches){
  for(const node of branches){
    const current=target.find(x=>x.kind===node.kind&&(node.kind==='folder'?x.name===node.name:x.id===node.id));
    if(!current)target.push(node);
    else if(node.kind==='folder')mergeTreeBranches(current.children,node.children);
    else Object.assign(current,node);
  }
  for(const node of target)if(node.kind==='folder')node.count=node.children.reduce((n,x)=>n+(x.kind==='folder'?(x.count||0):1),0);
  target.sort((a,b)=>(a.kind!=='folder')-(b.kind!=='folder')||a.name.localeCompare(b.name,'es'));
}
function receiveImportedDocument(event,projectId){
  if(S.project?.id!==projectId||event.document.project_id!==projectId)return;
  const index=S.docs.findIndex(d=>d.id===event.document.id);
  if(index<0)S.docs.push(event.document);else S.docs[index]=event.document;
  mergeTreeBranches(S.projectTree,event.tree_branch||[]);
  renderCards();renderDocs();renderProjectHeader();renderProjectTree();updateGlobal();
  $('#projectSaved').textContent=`${S.docs.length} tesis guardadas · carga en curso`;
}
function uploadWithProgress(form,token){
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();xhr.open('POST','/api/documents');
    const documents=[],projectId=form.get('project_id');let offset=0,buffer='',lastEvent=Date.now(),terminal=null,uploadComplete=false;
    form.append('stream_progress','true');
    const silence=setInterval(()=>{
      if(uploadComplete&&Date.now()-lastEvent>30000)updateWork(token,{title:'Esperando respuesta de la lectura',detail:'El servidor no informa avances hace más de 30 segundos. Las tesis que ya aparecen están guardadas.'});
    },1000);
    const fail=error=>{clearInterval(silence);reject(error)};
    const event=e=>{
      lastEvent=Date.now();
      if(e.type==='progress'){
        if(e.phase==='discover')updateWork(token,{title:'Preparando los archivos del lote',detail:`${e.filename} · archivo ${e.file_index} de ${e.file_total}. Buscando los PDF y sus carpetas.`});
        else updateWork(token,{title:`Leyendo las tesis · ${e.completed} de ${e.total}`,detail:`${e.imported} guardadas · hasta ${e.workers} PDF en paralelo · ${e.elapsed_seconds} s transcurridos.`,percent:Math.min(99,100*e.completed/e.total),active:e.active||[]});
      }else if(e.type==='document'){
        documents.push(e.document);receiveImportedDocument(e,projectId);
      }else if(e.type==='done'||e.type==='error')terminal=e;
    };
    const readEvents=()=>{
      // XHR can split JSON and multibyte text at any network chunk boundary.
      buffer+=xhr.responseText.slice(offset);offset=xhr.responseText.length;
      let end;while((end=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,end);buffer=buffer.slice(end+1);if(line.trim())event(JSON.parse(line))}
    };
    if(S.token)xhr.setRequestHeader('X-BiblioRef-Token',S.token);
    xhr.upload.onprogress=e=>{
      if(!e.lengthComputable)return;
      updateWork(token,{title:'Enviando los archivos',detail:`${(e.loaded/1048576).toFixed(1)} de ${(e.total/1048576).toFixed(1)} MB enviados`,percent:100*e.loaded/e.total});
    };
    xhr.upload.onload=()=>{uploadComplete=true;lastEvent=Date.now();updateWork(token,{title:'Envío completo · preparando la lectura',detail:'El servidor está preparando el lote. Los PDF aparecerán a medida que se guarden.'})};
    xhr.onprogress=()=>{if(xhr.status>=200&&xhr.status<300)try{readEvents()}catch{fail(new Error('No se pudo leer el avance del servidor. Revisá las tesis guardadas antes de repetir la carga.'))}};
    xhr.onerror=()=>fail(new Error('Se perdió la conexión. Revisá las tesis incorporadas antes de volver a cargar.'));
    xhr.onabort=()=>fail(new Error('La carga fue interrumpida.'));
    xhr.onload=()=>{
      clearInterval(silence);
      try{
        readEvents();
        if(terminal?.type==='error')return fail(new Error(terminal.detail));
        if(terminal?.type==='done')return resolve({documents,warnings:terminal.warnings||[],skipped:terminal.skipped_duplicates||0});
        // Compatibility with a previous server and ordinary HTTP error bodies.
        const data=JSON.parse(xhr.responseText);
        if(xhr.status<200||xhr.status>=300)return fail(new Error(typeof data.detail==='string'?data.detail:`No se pudo completar la carga (${xhr.status}).`));
        if(!Array.isArray(data.documents))throw Error('incomplete');
        resolve(data);
      }catch{return fail(new Error('La respuesta terminó sin confirmar el lote. Las tesis que ya aparecen están guardadas; revisalas antes de volver a cargar.'))}
    };
    xhr.send(form);
  });
}

function projectDate(p){const stamp=Math.max(p.updated_at||0,p.last_opened_at||0);return new Date(stamp*1000).toLocaleDateString('es-AR',{day:'numeric',month:'short',year:'numeric'})}
function collectionQuery(){return $('#collectionSearch').value.trim().toLocaleLowerCase('es')}
function matchesCollectionSearch(doc){
  const query=collectionQuery();if(!query)return true;const ing=doc.ingestion||{};
  return [doc.title,doc.filename,doc.thesis_id,doc.metadata?.university,ing.relative_path,ing.archive_member,...(ing.archive_chain||[])].join(' ').toLocaleLowerCase('es').includes(query);
}
$('#collectionSearch').oninput=()=>{renderCards();renderProjectTree()};
async function loadProjects(){const r=await api('/api/projects');S.projects=r.projects;renderRecentProjects();updateProjectNav()}
function renderRecentProjects(){
  const query=($('#projectSearch').value||'').trim().toLocaleLowerCase('es');
  const projects=S.projects.filter(p=>(p.name+' '+(p.description||'')).toLocaleLowerCase('es').includes(query));
  $('#projectCount').textContent=S.projects.length;
  $('#recentProjects').innerHTML=projects.map(p=>`<div class="recent-project-wrap"><button class="recent-project" data-project-id="${esc(p.id)}" aria-label="Abrir proyecto ${esc(p.name)}">${folderIcon}<h3>${esc(p.name)}</h3><p>${p.n_documents} ${p.n_documents===1?'tesis incorporada':'tesis incorporadas'} · ${p.n_references} referencias</p><footer><span>${esc(projectDate(p))}</span><span>Abrir proyecto →</span></footer></button><button type="button" class="recent-delete" data-delete-project="${esc(p.id)}" aria-label="Eliminar el proyecto ${esc(p.name)}" title="Eliminar proyecto">Eliminar</button></div>`).join('')||`<div class="projects-empty"><b>${query?'No se encontraron proyectos':'Todavía no hay proyectos guardados'}</b><p>${query?'Probá con otro nombre.':'Creá tu primer proyecto y agregá las tesis con las que vas a trabajar.'}</p></div>`;
}
function updateProjectNav(){
  $$('.nav button').forEach(b=>{b.disabled=b.dataset.screen!=='new'&&(!S.project||(b.dataset.screen==='review'&&!S.docs.length))});
  const b=$('.nav [data-screen="collection"]');if(b)b.title=S.project?.name||'Abrí o creá un proyecto';
}
function renderProjectHeader(){
  if(!S.project)return;
  $('#projectName').textContent=S.project.name;$('#treeRootName').textContent=S.project.name;$('#treeRootName').title=S.project.name;
  $('#projectDescription').textContent=S.project.description||'Tesis, referencias y correcciones de este proyecto.';
  $('#groupUniversity').checked=!!S.project.group_loose_by_university;
  $('#collectionCount').textContent=S.docs.length;updateProjectNav();
}
async function openProject(id){
  if(S.importBusy)return notify('Esperá a que termine la carga del proyecto actual.');
  const sequence=(S.projectOpenSequence||0)+1;S.projectOpenSequence=sequence;
  const work=startWork('Abriendo el proyecto','Recuperando las tesis y sus carpetas.',{announceDone:true});
  try{
    const p=await api(`/api/projects/${encodeURIComponent(id)}/open`,{method:'POST'});
    if(sequence!==S.projectOpenSequence)return;
    S.project=p;S.collectionFocusedId=null;S.docSelectSequence=(S.docSelectSequence||0)+1;S.doc=null;S.docs=[];S.projectTree=[];S.treeClosed=new Set();S.treeCollapsed=false;
    S.exportIds=new Set();S.exportTouched=false;S.dashboardIds=new Set();S.dashboardTouched=false;
    S.activeSection=0;S.selectedRef=null;S.origin=null;S.sectionPreview=null;S.pdfCandidate=null;S.pendingMissingId=null;S.renderSeq++;
    clearTimeout(S.previewTimer);$('#importFeedback').classList.add('hidden');$('#projectSaved').textContent='Guardado';$('#collectionSearch').value='';
    $('#uploadCards').innerHTML='';$('#projectTree').innerHTML='<div class="tree-empty">Cargando el proyecto…</div>';
    $('#toggleTree').textContent='Contraer';$('#toggleTree').setAttribute('aria-label','Contraer todas las carpetas');
    renderProjectHeader();show('collection');await loadDocs();
    if(sequence===S.projectOpenSequence)finishWork(work,'Proyecto abierto',`${S.docs.length} tesis disponibles.`);
  }catch(e){finishWork(work,'No se pudo abrir el proyecto',e.message,true);notify('No se pudo abrir el proyecto: '+e.message)}
}
window.openProject=openProject;

function projectForm(edit=false){
  if(S.importBusy)return notify('Esperá a que termine la carga.');
  const p=edit?S.project:null;
  modal(edit?'Editar proyecto':'Nuevo proyecto',`<p class="mini">${edit?'El nombre te ayuda a reconocer este corpus.':'Dale un nombre al corpus. Después podrás cargar PDF, ZIP o carpetas completas.'}</p><form class="project-form" id="projectForm"><label>Nombre del proyecto<input id="newProjectName" maxlength="160" required placeholder="Por ejemplo: Tesis de Psicología 2008–2025" value="${esc(p?.name||'')}"></label><label>Descripción <span class="mini">Opcional</span><textarea id="newProjectDescription" maxlength="1200" placeholder="Tema, período o criterio de selección">${esc(p?.description||'')}</textarea></label></form>${edit?`<div class="danger-zone" style="margin-top:18px;padding-top:14px;border-top:1px solid var(--line)"><b>Empezar de cero</b><p class="mini">Quita todas las tesis del proyecto con sus PDF guardados en BiblioRef, referencias, correcciones, carpetas y selecciones. El proyecto y su nombre quedan. No se puede deshacer.</p><button type="button" class="btn warn" id="resetProject">Vaciar proyecto…</button></div>`:''}`,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn primary" id="confirmProject">${edit?'Guardar cambios':'Crear proyecto'}</button>`);
  const submit=async()=>{
    if($('#confirmProject').disabled)return;
    const name=$('#newProjectName').value.trim();if(!name){$('#newProjectName').focus();return modalWarn('Escribí un nombre para el proyecto.')}
    const button=$('#confirmProject');button.disabled=true;
    try{
      const body={name,description:$('#newProjectDescription').value.trim()};
      const result=await api(edit?`/api/projects/${p.id}`:'/api/projects',{method:edit?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      closeModal();if(edit){S.project=result;renderProjectHeader();$('#projectSaved').textContent='Cambios guardados'}else await openProject(result.id);
      await loadProjects();
    }catch(e){button.disabled=false;modalWarn('No se pudo guardar: '+e.message)}
  };
  if(edit)$('#resetProject').onclick=()=>resetProjectForm(p);
  $('#confirmProject').onclick=submit;$('#projectForm').onsubmit=e=>{e.preventDefault();submit()};$('#newProjectName').focus();
}
function resetProjectForm(p,remove=false){
  const n=remove&&S.project?.id!==p.id?(p.n_documents||0):S.docs.length,verb=remove?'Eliminar proyecto':'Vaciar proyecto';
  modal(verb,`<p>${remove?`Se elimina el proyecto «${esc(p.name)}» junto con sus <b>${n} tesis</b>`:`Se quitan <b>${n} tesis</b> de «${esc(p.name)}»`}, con sus PDF guardados en BiblioRef, referencias, correcciones, carpetas y selecciones. <b>No se puede deshacer.</b> Los archivos originales de tu computadora no se tocan.</p><form class="project-form" id="resetForm"><label>Para confirmar, escribí el nombre del proyecto<input id="resetName" autocomplete="off" placeholder="${esc(p.name)}"></label></form>`,`<button class="btn" onclick="closeModal()">Cancelar</button><button class="btn warn" id="resetOk" disabled>${verb}</button>`);
  const input=$('#resetName'),ok=$('#resetOk');
  input.oninput=()=>{ok.disabled=input.value.trim()!==p.name.trim()};
  const run=async()=>{
    if(ok.disabled)return;ok.disabled=true;ok.textContent=remove?'Eliminando…':'Vaciando…';
    try{
      const r=await api(`/api/projects/${encodeURIComponent(p.id)}/reset`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm_name:input.value,delete_project:remove})});
      closeModal();S.doc=null;if(S.org){S.org.selected.clear();S.org.view=null;S.org.duplicates=null}
      if(r.project_deleted){if(!S.project||S.project.id===p.id){S.project=null;S.docs=[];S.projectTree=[]}await loadProjects();show('new');return}
      await loadDocs();await refreshProjectTree();await loadProjects();window.BiblioRefLoadDuplicates?.();
      $('#projectSaved').textContent=`Proyecto vacío · ${r.removed} tesis quitadas`;
    }catch(e){ok.disabled=false;ok.textContent=verb;modalWarn((remove?'No se pudo eliminar el proyecto: ':'No se pudo vaciar el proyecto: ')+e.message)}
  };
  ok.onclick=run;$('#resetForm').onsubmit=e=>{e.preventDefault();run()};input.focus();
}
$('#newProject').onclick=()=>projectForm();$('#editProject').onclick=()=>projectForm(true);
$('#projectSearch').oninput=renderRecentProjects;
$('#recentProjects').onclick=e=>{
  const del=e.target.closest('[data-delete-project]');
  if(del){const p=S.projects.find(x=>x.id===del.dataset.deleteProject);if(p)resetProjectForm(p,true);return}
  const b=e.target.closest('[data-project-id]');if(b)openProject(b.dataset.projectId)};
(()=>{const st=document.createElement('style');st.textContent=`#importFeedback{max-height:none}.import-summary{display:flex;align-items:flex-start;gap:10px;font-weight:600}.import-summary>div{flex:1}.import-close{border:0;background:none;font-size:18px;line-height:1;cursor:pointer;color:inherit;padding:0 4px}.import-group{margin-top:6px}.import-group summary{cursor:pointer;font-weight:500}.import-group summary:hover{text-decoration:underline}.import-group ul{margin:6px 0 0;padding-left:18px;max-height:180px;overflow:auto;columns:2 320px;column-gap:24px;font-weight:400}.import-group li{break-inside:avoid;margin-bottom:2px}.recent-project-wrap{position:relative;display:flex}.recent-project-wrap>.recent-project{flex:1;min-width:0}.recent-delete{position:absolute;top:12px;right:12px;border:1px solid transparent;background:none;color:var(--muted);border-radius:6px;padding:3px 8px;font:inherit;font-size:12px;font-weight:600;cursor:pointer;opacity:0}.recent-project-wrap:hover .recent-delete,.recent-delete:focus-visible{opacity:1}.recent-delete:hover,.recent-delete:focus-visible{color:var(--danger);border-color:var(--line);background:var(--surface)}@media(hover:none){.recent-delete{opacity:1}}`;document.head.appendChild(st)})();
$('#saveProject').onclick=async()=>{
  if(!S.project||S.importBusy)return;const id=S.project.id;const b=$('#saveProject');b.disabled=true;
  try{const p=await api(`/api/projects/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:'{}'});if(S.project?.id===id){S.project=p;$('#projectSaved').textContent='Proyecto guardado';renderProjectHeader()}await loadProjects()}
  catch(e){$('#projectSaved').textContent='No se pudo guardar';notify(e.message)}finally{b.disabled=false}
};

async function refreshProjectTree(){
  const id=S.project?.id;if(!id)return;
  const data=await api(`/api/projects/${id}/tree`);if(S.project?.id!==id)return;
  S.projectTree=data.nodes;renderProjectTree();
}
function renderProjectTree(){
  const query=collectionQuery(),matchingIds=new Set(S.docs.filter(matchesCollectionSearch).map(d=>d.id));
  function filtered(items,parentMatch=false){return items.flatMap(n=>{
    const match=parentMatch||n.name.toLocaleLowerCase('es').includes(query);
    if(n.kind==='document')return match||matchingIds.has(n.id)?[n]:[];
    const children=filtered(n.children,match);return children.length?[{...n,children}]:[];
  })}
  function nodes(items,parents=[]){return items.map(n=>{
    if(n.kind==='folder'){
      const path=JSON.stringify([...parents,n.name]);
      return `<details class="tree-folder" data-tree-path="${esc(path)}" ${!query&&(S.treeCollapsed||S.treeClosed.has(path))?'':'open'}><summary title="${esc(n.name)}">${folderIcon}<span>${esc(n.name)}</span><small>${n.count}</small></summary><div class="tree-children">${nodes(n.children,[...parents,n.name])}</div></details>`;
    }
    return `<button class="tree-file ${(S.collectionFocusedId||S.doc?.id)===n.id?'selected':''}" data-doc-id="${esc(n.id)}" title="${esc(n.name)} · ${esc(n.title)}${n.university_suggested?' · Universidad sugerida en portada':''}">${fileIcon}<span>${esc(n.name)}</span>${n.university_suggested?'<small>por revisar</small>':''}</button>`;
  }).join('')}
  $('#projectTree').innerHTML=nodes(query?filtered(S.projectTree):S.projectTree)||(query?'<div class="tree-empty">No hay archivos que coincidan.</div>':'<div class="tree-empty">Tu estructura aparecerá aquí<br>cuando incorpores las tesis.</div>');
  if(!query)$$('#projectTree details').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)S.treeClosed.delete(d.dataset.treePath);else S.treeClosed.add(d.dataset.treePath)}));
}
function focusCollectionDocument(id){
  S.collectionFocusedId=id;
  $$('#projectTree [data-doc-id]').forEach(b=>b.classList.toggle('selected',b.dataset.docId===id));
  $$('#uploadCards [data-card-id]').forEach(card=>{
    const selected=card.dataset.cardId===id;card.classList.toggle('selected',selected);
    if(selected){card.scrollIntoView?.({block:'nearest',behavior:'auto'});card.focus({preventScroll:true})}
  });
}
$('#projectTree').onclick=e=>{const b=e.target.closest('[data-doc-id]');if(b)focusCollectionDocument(b.dataset.docId)};
$('#projectTree').ondblclick=e=>{const b=e.target.closest('[data-doc-id]');if(b)openDoc(b.dataset.docId)};
$('#toggleTree').onclick=()=>{
  S.treeCollapsed=!S.treeCollapsed;S.treeClosed.clear();
  $$('#projectTree details').forEach(d=>{d.open=!S.treeCollapsed});
  $('#toggleTree').textContent=S.treeCollapsed?'Expandir':'Contraer';
  $('#toggleTree').setAttribute('aria-label',(S.treeCollapsed?'Expandir':'Contraer')+' todas las carpetas');
};
$('#groupUniversity').onchange=async e=>{
  if(!S.project)return;const id=S.project.id;const enabled=e.target.checked;e.target.disabled=true;
  try{
    const p=await api(`/api/projects/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({group_loose_by_university:enabled})});
    if(S.project?.id!==id)return;S.project=p;await refreshProjectTree();$('#projectSaved').textContent='Organización guardada';
  }catch(err){e.target.checked=!!S.project.group_loose_by_university;notify('No se pudo guardar la organización: '+err.message)}finally{e.target.disabled=false}
};

function importBusy(busy){S.importBusy=busy;$('#chooseFiles').disabled=busy;$('#chooseFolder').disabled=busy;$('#chooseDrive').disabled=busy;$('#saveProject').disabled=busy;$('#analyzeAll').disabled=busy||S.analysisBusy||!S.docs.length;$('#drop').setAttribute('aria-busy',String(busy));renderCards()}
function importFeedback(message,warnings=[]){
  const el=$('#importFeedback');el.classList.remove('hidden');
  // Repeated files are one message with the list of names, not one long sentence per file.
  const repeated=[],other=[];
  for(const w of warnings){const m=/^(.*?): ya estaba (en el proyecto como (\S+)|en esta misma carga como «(.*)»)/.exec(w);if(m)repeated.push({file:m[1],code:m[3]||null});else other.push(w)}
  const shortName=n=>n.replace(/_/g,' ').replace(/\.pdf$/i,'');
  const inBatch=repeated.filter(r=>!r.code),inProject=repeated.filter(r=>r.code);
  const block=(title,items)=>items.length?`<details class="import-group"><summary>${title}</summary><ul>${items.join('')}</ul></details>`:'';
  el.innerHTML=`<div class="import-summary"><div>${esc(message)}</div><button type="button" class="import-close" aria-label="Cerrar el aviso" onclick="$('#importFeedback').classList.add('hidden')">×</button></div>
    ${block(`${inBatch.length} ${inBatch.length===1?'archivo venía dos veces en la carga (por ejemplo, en una carpeta y en un ZIP): se agregó':'archivos venían dos veces en la carga (por ejemplo, en una carpeta y en un ZIP): se agregaron'} una sola vez · ver cuáles`,inBatch.map(r=>`<li>${esc(shortName(r.file))}</li>`))}
    ${block(`${inProject.length} ${inProject.length===1?'archivo ya estaba en el proyecto: no se agregó':'archivos ya estaban en el proyecto: no se agregaron'} de nuevo · ver cuáles`,inProject.map(r=>`<li>${esc(shortName(r.file))} <span class="mini">(${esc(r.code)})</span></li>`))}
    ${block(`${other.length} ${other.length===1?'aviso':'avisos'} más · ver`,other.map(w=>`<li>${esc(w)}</li>`))}`;
}
async function importProjectFiles(entries){
  if(!S.project)return projectForm();if(S.importBusy||S.analysisBusy)return;
  const items=[...entries].map(entry=>entry.file?entry:{file:entry,path:entry.webkitRelativePath||entry.name});
  const files=items.filter(x=>/\.(pdf|zip)$/i.test(x.file.name));
  const omitted=items.length-files.length;
  if(!files.length)return importFeedback('No se encontraron PDF o ZIP en la selección.');
  const id=S.project.id;const fd=new FormData();fd.append('project_id',id);files.forEach(x=>fd.append('files',x.file,x.path||x.file.name));
  const work=startWork('Cargando las tesis',`${files.length} ${files.length===1?'archivo seleccionado':'archivos seleccionados'}.`,{announceDone:true});
  importBusy(true);importFeedback(`Cargando ${files.length} ${files.length===1?'archivo':'archivos'}…`);$('#projectSaved').textContent='Cargando…';
  try{
    const r=await uploadWithProgress(fd,work);if(S.project?.id!==id)return;
    updateWork(work,{title:'Mostrando las tesis',detail:'Actualizando el explorador del proyecto.'});
    S.exportTouched=false;await loadDocs(null,[...new Map([...S.docs,...r.documents].map(d=>[d.id,d])).values()]);await loadProjects();
    const warnings=[...(omitted?[`Se omitieron ${omitted} archivos de otros formatos.`]:[]),...(r.warnings||[])];
    const repeated=r.skipped?` · ${r.skipped} ${r.skipped===1?'archivo repetido no se agregó':'archivos repetidos no se agregaron'}`:'';
    importFeedback(`${r.documents.length} ${r.documents.length===1?'tesis incorporada':'tesis incorporadas'}${repeated}.`,warnings);
    window.BiblioRefLoadDuplicates?.();
    $('#projectSaved').textContent='Cambios guardados';
    finishWork(work,`${r.documents.length} ${r.documents.length===1?'tesis incorporada':'tesis incorporadas'}`,warnings.length?'Carga terminada con avisos. Revisalos debajo de los botones de carga.':'El proyecto está guardado. Ya podés procesar las referencias.');
  }catch(e){importFeedback('No se pudo completar la carga.',[e.message]);$('#projectSaved').textContent='Revisá la carga';finishWork(work,'No se pudo completar la carga',e.message,true)}
  finally{importBusy(false);updateGlobal()}
}
async function importDroppedFiles(transfer){
  if(S.importBusy)return;
  if(!S.project)return projectForm();
  // Read browser entries synchronously while the drop event still owns them.
  const entries=[...(transfer.items||[])].filter(x=>x.kind==='file').map(x=>x.webkitGetAsEntry?.()).filter(Boolean);
  const fallback=[...transfer.files];
  async function walk(entry,prefix=''){
    if(entry.isFile){const file=await new Promise((resolve,reject)=>entry.file(resolve,reject));return [{file,path:prefix+entry.name}]}
    if(!entry.isDirectory)return [];
    const reader=entry.createReader();const output=[];
    while(true){const batch=await new Promise((resolve,reject)=>reader.readEntries(resolve,reject));if(!batch.length)break;for(const child of batch)output.push(...await walk(child,prefix+entry.name+'/'))}
    return output;
  }
  const work=startWork('Leyendo las carpetas','Buscando PDF y ZIP en las subcarpetas.',{announceDone:true});
  importBusy(true);importFeedback('Leyendo las carpetas…');
  try{
    const all=[];for(const entry of entries)all.push(...await walk(entry));
    importBusy(false);
    await importProjectFiles(entries.length?all:fallback);
    if(S.workSequence===work)finishWork(work,'No se encontraron PDF o ZIP','Elegí una carpeta que contenga tesis.');
  }catch(e){importFeedback('No se pudo leer la carpeta. Probá con «Carpeta completa».',[e.message]);finishWork(work,'No se pudo leer la carpeta',e.message,true)}
  finally{importBusy(false)}
}
// Long tasks shrink to a small circle with the percentage in a corner; a click shows the details.
(()=>{
  const panel=$('#workProgress');if(!panel)return;
  const st=document.createElement('style');
  st.textContent=`.work-progress.compact{position:fixed;top:auto;left:auto;right:18px;bottom:18px;margin:0;padding:6px 12px 6px 6px;border-left-width:1px;border-radius:999px;display:flex;align-items:center;gap:8px;max-width:min(360px,calc(100vw - 36px));cursor:pointer;z-index:60}
  .work-progress.compact .work-progress-track,.work-progress.compact .work-progress-files,.work-progress.compact p{display:none}
  .work-progress.compact .work-progress-top{gap:8px}
  .work-progress.compact .work-progress-icon{display:none}
  .work-progress.compact strong{font-size:12.5px;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .work-progress.compact .work-progress-top>b{display:none}
  .work-ring{--p:0;width:34px;height:34px;flex:none;border-radius:50%;display:grid;place-items:center;font:700 10px/1 inherit;font-family:inherit;color:var(--accent-dark,#1f56c4);background:conic-gradient(var(--accent) calc(var(--p)*1%),#cddbf3 0)}
  .work-ring::before{content:attr(data-label);width:26px;height:26px;border-radius:50%;background:#edf3ff;display:grid;place-items:center}
  .work-progress:not(.compact) .work-ring{display:none}
  .work-progress[data-state="done"] .work-ring{background:conic-gradient(var(--ok) 100%,#cfe9d8 0);color:#116331}
  .work-progress[data-state="done"] .work-ring::before{background:var(--okbg)}
  .work-ring.spin{background:conic-gradient(var(--accent) 25%,#cddbf3 0);animation:work-spin .9s linear infinite}
  .work-ring.spin::before{animation:work-spin .9s linear infinite reverse}
  .work-progress:not(.compact){cursor:pointer}`;
  document.head.appendChild(st);
  const ring=document.createElement('span');ring.className='work-ring';ring.setAttribute('aria-hidden','true');
  panel.prepend(ring);
  let expanded=false;
  const sync=()=>{
    const state=panel.dataset.state;
    panel.classList.toggle('compact',state!=='error'&&!expanded);
    const value=$('#workProgressValue').textContent.trim(),pct=parseInt(value,10);
    const known=Number.isFinite(pct);
    ring.classList.toggle('spin',!known&&state==='busy');
    ring.style.setProperty('--p',known?pct:(state==='done'?100:0));
    ring.dataset.label=state==='done'?'✓':known?`${pct}%`:'';
    panel.title=expanded?'Clic para minimizar':'Clic para ver el detalle';
  };
  panel.addEventListener('click',()=>{expanded=!expanded;sync()});
  new MutationObserver(sync).observe(panel,{attributes:true,attributeFilter:['data-state','class'],childList:true,subtree:true,characterData:true});
  sync();
})();
// Status notes next to «Guardar proyecto» are confirmations: seen briefly, then gone. Only an import in progress stays.
(()=>{
  const el=$('#projectSaved');if(!el)return;let timer;
  new MutationObserver(()=>{
    clearTimeout(timer);
    const text=el.textContent.trim();
    if(text&&!/cargando|carga en curso/i.test(text))timer=setTimeout(()=>{if(el.textContent.trim()===text)el.textContent=''},2500);
  }).observe(el,{childList:true,characterData:true,subtree:true});
})();
updateProjectNav();
health().then(()=>loadProjects()).catch(e=>{$('#globalStatus').innerHTML='No se pudo conectar con BiblioRef · <a href="#" onclick="location.reload();return false">Reintentar</a>';$('#recentProjects').innerHTML='<div class="projects-empty"><b>No se pudieron cargar los proyectos</b><p>Reintentá la conexión para ver los proyectos guardados.</p></div>';console.error(e)});
