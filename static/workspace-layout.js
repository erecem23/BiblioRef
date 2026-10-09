/* Docking preferences belong to this browser, never to thesis data. */
(()=>{
  const key='biblioref.workspace-layout.v1';
  const defaults={side:'left',width:340,height:250,hidden:false};
  const grid=$('#collectionWorkspace'),explorer=$('#projectExplorer');
  const splitter=$('#explorerSplitter'),handle=$('#explorerHandle');
  const small=window.matchMedia?.('(max-width:980px)')||{matches:false};
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
  let layout={...defaults},resizing=null,dragging=false;
  try{
    const saved=JSON.parse(localStorage.getItem(key));
    if(saved&&typeof saved==='object')layout={
      side:['left','right','top'].includes(saved.side)?saved.side:defaults.side,
      width:Number.isFinite(saved.width)?clamp(saved.width,240,620):defaults.width,
      height:Number.isFinite(saved.height)?clamp(saved.height,150,420):defaults.height,
      hidden:saved.hidden===true,
    };
  }catch{/* A blocked or damaged preference must not prevent opening projects. */}
  function limits(){
    const rect=grid.getBoundingClientRect();
    return layout.side==='top'?{min:150,max:Math.max(150,Math.min(420,(rect.height||700)-300))}
      :{min:240,max:Math.max(240,Math.min(620,(rect.width||1100)-420))};
  }
  function persist(){try{localStorage.setItem(key,JSON.stringify(layout));return true}catch{return false}}
  function apply(){
    const bounds=limits(),top=layout.side==='top';
    const size=clamp(top?layout.height:layout.width,bounds.min,bounds.max);
    grid.dataset.explorerSide=layout.side;grid.dataset.explorerHidden=String(layout.hidden);
    grid.style.setProperty('--explorer-width',`${top?layout.width:size}px`);
    grid.style.setProperty('--explorer-height',`${top?size:layout.height}px`);
    explorer.hidden=layout.hidden;splitter.hidden=layout.hidden;
    splitter.setAttribute('aria-orientation',top?'horizontal':'vertical');
    splitter.setAttribute('aria-valuemin',bounds.min);splitter.setAttribute('aria-valuemax',bounds.max);
    splitter.setAttribute('aria-valuenow',size);splitter.setAttribute('aria-valuetext',`${size} píxeles de ${top?'alto':'ancho'}`);
    splitter.tabIndex=small.matches?-1:0;
    $('#explorerPosition').value=layout.side;$('#explorerPosition').disabled=small.matches;
    $('#showExplorer').textContent=layout.hidden?'Mostrar explorador':'Ocultar explorador';
    $('#showExplorer').setAttribute('aria-expanded',String(!layout.hidden));
    handle.draggable=!small.matches;
    // Keep keyboard reading order consistent with the docked visual order.
    const main=grid.querySelector('.collection-main');
    const atRight=layout.side==='right'&&!small.matches;
    const first=atRight?main:explorer,second=atRight?explorer:main;
    if(grid.firstElementChild!==first||first.nextElementSibling!==splitter){
      grid.insertBefore(first,grid.firstElementChild);grid.insertBefore(splitter,first.nextElementSibling);grid.insertBefore(second,splitter.nextElementSibling);
    }
  }
  function change(updates,message){
    Object.assign(layout,updates);apply();const saved=persist();
    if(message)$('#layoutStatus').textContent=message+(saved?'':' El navegador conserva esta disposición solo durante esta sesión.');
  }
  function dock(side){
    if(!['left','right','top'].includes(side))return;
    change({side,hidden:false},`Explorador ${side==='left'?'a la izquierda':side==='right'?'a la derecha':'arriba'}.`);
  }
  $('#explorerPosition').onchange=e=>dock(e.target.value);
  $('#showExplorer').onclick=()=>change({hidden:!layout.hidden},layout.hidden?'Explorador visible.':'Explorador oculto.');
  $('#hideExplorer').onclick=()=>{change({hidden:true},'Explorador oculto.');$('#showExplorer').focus()};
  $('#resetLayout').onclick=()=>{change({...defaults},'Disposición inicial restablecida.');$('#layoutMenu').open=false;$('#showExplorer').focus()};
  document.addEventListener('click',e=>{if(!$('#layoutMenu').contains(e.target))$('#layoutMenu').open=false});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('#layoutMenu').open=false;stopDrag();if(resizing)finishResize(true)}});

  function resizeTo(value){
    const bounds=limits();layout[layout.side==='top'?'height':'width']=clamp(value,bounds.min,bounds.max);apply();
  }
  splitter.onkeydown=e=>{
    if(small.matches)return;
    const top=layout.side==='top',size=Number(splitter.getAttribute('aria-valuenow')),bounds=limits();
    const step=e.shiftKey?50:20;
    if(e.key==='Home')resizeTo(bounds.min);
    else if(e.key==='End')resizeTo(bounds.max);
    else if(top&&['ArrowUp','ArrowDown'].includes(e.key))resizeTo(size+(e.key==='ArrowDown'?step:-step));
    else if(!top&&['ArrowLeft','ArrowRight'].includes(e.key))resizeTo(size+(e.key==='ArrowRight'?step:-step)*(layout.side==='right'?-1:1));
    else return;
    e.preventDefault();persist();
  };
  splitter.onpointerdown=e=>{
    if(small.matches||e.button!==0)return;
    e.preventDefault();splitter.focus();
    resizing={id:e.pointerId,x:e.clientX,y:e.clientY,width:layout.width,height:layout.height,side:layout.side,startSize:Number(splitter.getAttribute('aria-valuenow'))};
    splitter.setPointerCapture?.(e.pointerId);grid.classList.add('is-resizing');
  };
  splitter.onpointermove=e=>{
    if(!resizing||e.pointerId!==resizing.id)return;
    const r=resizing,top=r.side==='top';
    resizeTo(top?r.startSize+e.clientY-r.y:r.startSize+(e.clientX-r.x)*(r.side==='right'?-1:1));
  };
  function finishResize(cancel=false){
    if(!resizing)return;
    const r=resizing;resizing=null;
    if(cancel){layout.width=r.width;layout.height=r.height;apply()}
    if(splitter.hasPointerCapture?.(r.id))splitter.releasePointerCapture(r.id);
    grid.classList.remove('is-resizing');persist();
  }
  splitter.onpointerup=()=>finishResize();splitter.onpointercancel=()=>finishResize(true);
  splitter.onlostpointercapture=()=>finishResize();
  splitter.ondblclick=()=>{resizeTo(layout.side==='top'?defaults.height:defaults.width);persist()};

  function stopDrag(){dragging=false;grid.classList.remove('is-docking');$$('[data-dock-side]').forEach(x=>x.classList.remove('dock-active'))}
  handle.ondragstart=e=>{
    if(small.matches||resizing){e.preventDefault();return}
    dragging=true;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('application/x-biblioref-panel','explorer');
    grid.classList.add('is-docking');
  };
  handle.ondragend=stopDrag;
  $$('[data-dock-side]').forEach(target=>{
    target.ondragover=e=>{if(!dragging)return;e.preventDefault();e.dataTransfer.dropEffect='move';target.classList.add('dock-active')};
    target.ondragleave=()=>target.classList.remove('dock-active');
    target.ondrop=e=>{if(!dragging)return;e.preventDefault();e.stopPropagation();dock(target.dataset.dockSide);stopDrag();handle.focus()};
  });
  window.addEventListener('resize',()=>{if(resizing)finishResize(true);apply()});
  small.addEventListener?.('change',apply);
  apply();
})();
