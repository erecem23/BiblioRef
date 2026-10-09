const {JSDOM}=require('jsdom');
const fs=require('fs'),assert=require('node:assert/strict');
const root=require('node:path').resolve(__dirname,'..')+'/';
const html=fs.readFileSync(root+'static/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
const dom=new JSDOM(html,{url:'http://localhost',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;let seq=0;
let streamReply=null;let xhrFailure=false;const uploadStages=[];let tokenHeader;
w.XMLHttpRequest=class{
  constructor(){this.upload={}}
  open(method,url){this.method=method;this.url=url}
  setRequestHeader(key,value){if(key==='X-BiblioRef-Token')tokenHeader=value}
  send(body){
    this.upload.onprogress({lengthComputable:true,loaded:512,total:1024});
    uploadStages.push(w.document.querySelector('#workProgressBar').getAttribute('aria-valuenow'));
    this.upload.onload();
    uploadStages.push(w.document.querySelector('#workProgressBar').getAttribute('aria-valuenow'));
    if(streamReply){this.status=200;this.responseText='';streamReply(this);return}
    if(xhrFailure){this.status=500;this.responseText=JSON.stringify({detail:'Fallo simulado'});this.onload();return}
    w.fetch(this.url,{method:this.method,body}).then(r=>r.json()).then(data=>{this.status=200;this.responseText=JSON.stringify(data);this.onload()}).catch(()=>this.onerror());
  }
};
let projects=[{id:'p1',name:'Proyecto prueba',n_documents:1,n_references:0,updated_at:1},{id:'p2',name:'Otro proyecto',n_documents:0,n_references:0,updated_at:1}];
const doc={id:'d1',project_id:'p1',title:'Archivo de prueba',filename:'archivo.pdf',page_count:1,size_mb:0.01,status:'uploaded',ingestion:{relative_path:'UNLP/archivo.pdf'},references:[],metadata:{},analysis:{},sections:[],n_references:0};
w.fetch=async (url,opt={})=>{const u=new URL(url,'http://localhost');const method=opt.method||'GET';let value;
if(u.pathname==='/api/health')value={session_token:'test',software_version:'test',algorithm_version:'test'};
else if(u.pathname==='/api/capabilities')value={layers:[]};
else if(u.pathname==='/api/projects'&&method==='POST'){value={...JSON.parse(opt.body),id:'created'+(++seq),n_documents:0,n_references:0,updated_at:2};projects.unshift(value)}
else if(u.pathname==='/api/projects')value={projects};
else if(u.pathname==='/api/documents')value={documents:u.searchParams.get('project_id')==='p1'?[doc]:[]};
else if(u.pathname==='/api/documents/d1')value=doc;
else if(/\/open$/.test(u.pathname))value=projects.find(p=>p.id===u.pathname.split('/')[3]);
else if(/\/tree$/.test(u.pathname))value={nodes:u.pathname.includes('/p1/')?[{kind:'folder',name:'UNLP',count:1,children:[{kind:'document',id:'d1',name:'archivo.pdf',title:doc.title}]}]:[]};
else if(method==='PATCH'){value=projects.find(p=>p.id===u.pathname.split('/')[3]);Object.assign(value,JSON.parse(opt.body))}
else throw Error('Unexpected '+method+' '+u.pathname);
return {ok:true,headers:{get:()=> 'application/json'},json:async()=>structuredClone(value)};
};
w.eval(fs.readFileSync(root+'static/app.js','utf8')+'\n'+fs.readFileSync(root+'static/projects.js','utf8')+'\n'+fs.readFileSync(root+'static/workspace-layout.js','utf8'));
const tick=()=>new Promise(r=>setTimeout(r,25));
(async()=>{
await tick();assert.equal(w.document.querySelectorAll('.recent-project').length,2);assert.equal(w.S.docs.length,0);
assert(!w.document.querySelector('#screen-new').textContent.includes('archivo.pdf'));
w.document.querySelector('[data-project-id="p1"]').click();await tick();
assert.equal(w.S.project.id,'p1');assert(w.document.querySelector('#screen-collection').classList.contains('active'));
assert(w.document.querySelector('#projectTree').textContent.includes('UNLP'));
// Docked explorer, persistent preferences and selecting a thesis in the center.
const grid=w.document.querySelector('#collectionWorkspace');
const splitter=w.document.querySelector('#explorerSplitter');
const position=w.document.querySelector('#explorerPosition');
assert.equal(grid.dataset.explorerSide,'left');
assert.equal(grid.firstElementChild.id,'projectExplorer');
w.document.querySelector('.tree-file').click();
assert.equal(w.S.collectionFocusedId,'d1');
assert(w.document.querySelector('#uploadCards .card').classList.contains('selected'));
assert(w.document.querySelector('#screen-collection').classList.contains('active'));
position.value='right';position.dispatchEvent(new w.Event('change'));
assert.equal(grid.dataset.explorerSide,'right');
assert(grid.firstElementChild.classList.contains('collection-main'));
assert.equal(JSON.parse(w.localStorage.getItem('biblioref.workspace-layout.v1')).side,'right');
const oldWidth=Number(splitter.getAttribute('aria-valuenow'));
splitter.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}));
assert.equal(Number(splitter.getAttribute('aria-valuenow')),oldWidth+20);
w.document.querySelector('#hideExplorer').click();
assert(w.document.querySelector('#projectExplorer').hidden);
assert.equal(w.document.activeElement.id,'showExplorer');
assert.equal(w.document.querySelector('#showExplorer').getAttribute('aria-expanded'),'false');
w.document.querySelector('#showExplorer').click();
position.value='top';position.dispatchEvent(new w.Event('change'));
assert.equal(splitter.getAttribute('aria-orientation'),'horizontal');
splitter.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));
assert.equal(splitter.getAttribute('aria-valuenow'),'270');
w.document.querySelector('#resetLayout').click();
assert.equal(grid.dataset.explorerSide,'left');
assert.equal(splitter.getAttribute('aria-valuenow'),'340');
// A mouse/touch drag must keep the same captured separator node in the DOM.
let captures=0,releases=0;splitter.setPointerCapture=()=>captures++;splitter.hasPointerCapture=()=>true;splitter.releasePointerCapture=()=>releases++;
const pointer=(type,x)=>{const e=new w.MouseEvent(type,{clientX:x,clientY:0,button:0,bubbles:true});Object.defineProperty(e,'pointerId',{value:7});splitter.dispatchEvent(e)};
pointer('pointerdown',100);pointer('pointermove',180);pointer('pointermove',200);pointer('pointerup',200);
assert.equal(splitter.getAttribute('aria-valuenow'),'440');assert.equal(captures,1);assert.equal(releases,1);
pointer('pointerdown',100);pointer('pointermove',200);splitter.dispatchEvent(new w.Event('pointercancel'));
assert.equal(splitter.getAttribute('aria-valuenow'),'440');
// Dock by dragging the handle; external file drops must not move the panel.
const transfer={effectAllowed:'',dropEffect:'',setData(){}};
const drag=(element,type)=>{const e=new w.Event(type,{bubbles:true,cancelable:true});Object.defineProperty(e,'dataTransfer',{value:transfer});element.dispatchEvent(e)};
drag(w.document.querySelector('#explorerHandle'),'dragstart');
drag(w.document.querySelector('[data-dock-side="right"]'),'drop');
assert.equal(grid.dataset.explorerSide,'right');assert(!grid.classList.contains('is-docking'));
drag(w.document.querySelector('[data-dock-side="left"]'),'drop');assert.equal(grid.dataset.explorerSide,'right');
w.document.querySelector('#resetLayout').click();
const search=w.document.querySelector('#collectionSearch');
search.value='no coincide';search.dispatchEvent(new w.Event('input'));
assert.equal(w.document.querySelectorAll('.tree-file').length,0);
assert(w.document.querySelector('#uploadCards').textContent.includes('No se encontraron'));
search.value='UNLP';search.dispatchEvent(new w.Event('input'));
assert.equal(w.document.querySelectorAll('.tree-file').length,1);
assert.equal(w.document.querySelectorAll('#uploadCards .card').length,1);
search.value='';search.dispatchEvent(new w.Event('input'));
w.document.querySelector('[data-screen="new"]').click();await tick();
w.document.querySelector('#newProject').click();await tick();
w.document.querySelector('#newProjectName').value='Corpus nuevo';w.document.querySelector('#confirmProject').click();await tick();
assert.equal(w.S.project.name,'Corpus nuevo');assert.equal(w.S.docs.length,0);assert.equal(w.S.exportIds.size,0);assert.equal(w.document.querySelectorAll('.tree-file').length,0);
assert(w.document.querySelector('.nav [data-screen="review"]').disabled);
w.document.querySelector('#saveProject').click();await tick();assert.equal(w.document.querySelector('#projectSaved').textContent,'Proyecto guardado');
w.document.querySelector('[data-screen="new"]').click();await tick();
assert.equal(w.document.querySelectorAll('.recent-project').length,3);
assert(!w.document.querySelector('#screen-new').textContent.includes('archivo.pdf'));

// A delayed automatic refresh must not restore the thesis after switching projects.
await w.openProject('p1');
const normalFetch=w.fetch;let finishAnalysis;
doc.analysis_stale=true;doc.has_manual_work=false;
w.fetch=async(url,opt={})=>String(url).endsWith('/d1/analyze')
  ?new Promise(resolve=>{finishAnalysis=()=>resolve({ok:true,headers:{get:()=> 'application/json'},json:async()=>({})})})
  :normalFetch(url,opt);
const opening=w.openDoc('d1');await tick();assert(finishAnalysis);
await w.openProject('p2');finishAnalysis();await opening;
assert.equal(w.S.project.id,'p2');assert.equal(w.S.doc,null);
assert(!w.document.querySelector('#screen-review').classList.contains('active'));
doc.analysis_stale=false;w.fetch=normalFetch;

// Keep project ownership while a browser directory reader is still yielding files.
await w.openProject('p1');let finishFile;let received;let batches=0,extraDocumentReads=0;
const file=new w.File(['pdf fixture'],'archivo.pdf',{type:'application/pdf'});
const entry={name:'Corpus',isDirectory:true,createReader:()=>({readEntries:callback=>callback(batches++===0
  ?[{name:'archivo.pdf',isFile:true,file:resolve=>{finishFile=()=>resolve(file)}}]:[])})};
w.fetch=async(url,opt={})=>{
  if(String(url).startsWith('/api/documents?'))extraDocumentReads++;
  if(url==='/api/documents'&&opt.method==='POST'){
    received={project:opt.body.get('project_id'),path:opt.body.get('files').name};
    return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({documents:[doc],warnings:[]})};
  }
  return normalFetch(url,opt);
};
const dropping=w.importDroppedFiles({items:[{kind:'file',webkitGetAsEntry:()=>entry}],files:[]});
assert.equal(w.S.importBusy,true);await w.openProject('p2');assert.equal(w.S.project.id,'p1');
w.closeModal();finishFile();await dropping;
assert.deepEqual(received,{project:'p1',path:'Corpus/archivo.pdf'});
assert.equal(w.S.importBusy,false);assert.equal(batches,2);w.fetch=normalFetch;
assert.equal(extraDocumentReads,0);
assert.equal(tokenHeader,'test');assert.deepEqual(uploadStages,['50',null]);
assert.equal(w.document.querySelector('#workProgress').dataset.state,'done');
assert.equal(w.document.querySelector('#workProgressBar').getAttribute('aria-valuenow'),'100');
xhrFailure=true;await w.importProjectFiles([file]);
assert.equal(w.S.importBusy,false);assert.equal(w.document.querySelector('#workProgress').dataset.state,'error');
assert(w.document.querySelector('#importFeedback').textContent.includes('Fallo simulado'));
// Real streaming protocol: split JSON frames, persistent partial rows and a
// later failure must not lose successful documents or leave controls disabled.
xhrFailure=false;
const arriving={...doc,id:'d2',filename:'segunda.pdf',title:'Segunda tesis'};
const push=(xhr,event)=>{xhr.responseText+=JSON.stringify(event)+'\n';xhr.onprogress()};
streamReply=xhr=>{
  push(xhr,{type:'progress',phase:'read',total:2,completed:0,imported:0,workers:2,elapsed_seconds:1,active:[{filename:'segunda.pdf',seconds:1}]});
  assert(w.document.querySelector('#workProgressFiles').textContent.includes('segunda.pdf'));
  const frame=JSON.stringify({type:'document',document:arriving,tree_branch:[{kind:'document',id:'d2',name:'segunda.pdf',title:arriving.title}]})+'\n';
  xhr.responseText+=frame.slice(0,17);xhr.onprogress();
  assert(!w.S.docs.some(d=>d.id==='d2'));
  xhr.responseText+=frame.slice(17);xhr.onprogress();
  assert(w.S.docs.some(d=>d.id==='d2'));
  assert(w.document.querySelector('#projectTree').textContent.includes('segunda.pdf'));
  assert.equal(w.S.importBusy,true);
  push(xhr,{type:'heartbeat'});
  push(xhr,{type:'progress',phase:'read',total:2,completed:1,imported:1,workers:2,elapsed_seconds:36,active:[{filename:'lenta.pdf',seconds:35}]});
  assert.equal(w.document.querySelector('#workProgressBar').getAttribute('aria-valuenow'),'50');
  assert(w.document.querySelector('#workProgressFiles').textContent.includes('35 s'));
  push(xhr,{type:'error',detail:'Fallo posterior; la primera tesis sigue guardada.'});xhr.onload();
};
await w.importProjectFiles([file]);
assert.equal(w.S.importBusy,false);assert(w.S.docs.some(d=>d.id==='d2'));
assert.equal(w.document.querySelector('#workProgress').dataset.state,'error');
assert(!w.document.querySelector('#uploadCards .actions button').disabled);
streamReply=xhr=>{
  push(xhr,{type:'document',document:arriving,tree_branch:[]});
  push(xhr,{type:'done',imported:1,warnings:[]});xhr.onload();
};
await w.importProjectFiles([file]);
assert.equal(w.S.docs.filter(d=>d.id==='d2').length,1);
assert.equal(w.document.querySelector('#workProgress').dataset.state,'done');
streamReply=null;

// A batch starts only the configured number of requests, then refills a slot.
w.S.capabilities.processing={max_workers:2};
w.S.docs=[1,2,3].map(i=>({...doc,id:'batch'+i,status:'uploaded'}));
const waiting=new Map();let calls=0;
w.fetch=async(url,opt={})=>{
  if(String(url).endsWith('/analyze')){
    calls++;assert.equal(JSON.parse(opt.body).worker,true);
    const id=url.split('/')[3];
    return new Promise(resolve=>waiting.set(id,()=>resolve({ok:true,headers:{get:()=> 'application/json'},json:async()=>({...doc,id,status:'ready'})})));
  }
  return normalFetch(url,opt);
};
const batch=w.document.querySelector('#analyzeAll').onclick();await tick();
assert.equal(calls,2);
waiting.get('batch1')();await tick();assert.equal(calls,3);
waiting.get('batch2')();waiting.get('batch3')();await batch;
assert.equal(w.S.analysisBusy,false);
assert.equal(w.document.querySelector('#workProgress').dataset.state,'done');
w.fetch=normalFetch;
console.log('DOM flow passed: home, open, tree, create, clear, save, reopen, delayed refresh and directory ownership.');dom.window.close();
})().catch(e=>{console.error(e);dom.window.close();process.exitCode=1});
