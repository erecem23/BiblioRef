const {JSDOM}=require('jsdom');
const fs=require('fs'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'static/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
const code=fs.readFileSync(path.join(root,'static/workspace-layout.js'),'utf8');
const key='biblioref.workspace-layout.v1';
function open(saved,blocked=false){
  const dom=new JSDOM(html,{url:'http://localhost',runScripts:'outside-only'}),w=dom.window;
  if(saved)w.localStorage.setItem(key,saved);
  if(blocked)Object.defineProperty(w,'localStorage',{get(){throw Error('Storage unavailable')}});
  const media={matches:false,addEventListener(type,listener){this.listener=listener}};
  w.matchMedia=()=>media;
  w.eval("const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];\n"+code);
  return {dom,w,media};
}
let {dom,w,media}=open(JSON.stringify({side:'right',width:500,height:250,hidden:false}));
assert.equal(w.document.querySelector('#collectionWorkspace').dataset.explorerSide,'right');
assert.equal(w.document.querySelector('#explorerSplitter').getAttribute('aria-valuenow'),'500');
media.matches=true;media.listener();
assert.equal(w.document.querySelector('#explorerSplitter').tabIndex,-1);
assert(w.document.querySelector('#explorerPosition').disabled);
assert.equal(w.document.querySelector('#collectionWorkspace').firstElementChild.id,'projectExplorer');
assert.equal(JSON.parse(w.localStorage.getItem(key)).side,'right');
media.matches=false;media.listener();
assert(w.document.querySelector('#collectionWorkspace').firstElementChild.classList.contains('collection-main'));
w.document.querySelector('#hideExplorer').click();
const saved=w.localStorage.getItem(key);dom.window.close();
({dom,w}=open(saved));
assert(w.document.querySelector('#projectExplorer').hidden);
w.document.querySelector('#showExplorer').click();
assert.equal(w.document.querySelector('#explorerSplitter').getAttribute('aria-valuenow'),'500');
dom.window.close();
for(const saved of ['{broken',JSON.stringify({side:'floating',width:-100,height:'bad',hidden:'true'})]){
  ({dom,w}=open(saved));assert.equal(w.document.querySelector('#collectionWorkspace').dataset.explorerSide,'left');
  assert(!w.document.querySelector('#projectExplorer').hidden);dom.window.close();
}
({dom,w}=open(null,true));
w.document.querySelector('#hideExplorer').click();w.document.querySelector('#showExplorer').click();
assert(!w.document.querySelector('#projectExplorer').hidden);dom.window.close();
console.log('Workspace layout passed: restore, responsive order, hidden panels and unavailable/corrupt preferences.');
