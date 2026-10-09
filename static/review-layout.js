/* La lista vive detrás de una solapa: abierta o cerrada es una preferencia del navegador, nunca dato de la tesis. */
(()=>{
  const key='biblioref.review-drawer.v1';
  const workspace=$('#reviewWorkspace'),tab=$('#refTab');
  if(!workspace||!tab)return;
  let open=false;
  try{open=localStorage.getItem(key)==='1'}catch{/* una preferencia bloqueada no impide abrir la revisión */}
  function apply(){
    workspace.classList.toggle('drawer-open',open);
    tab.setAttribute('aria-expanded',String(open));
    tab.setAttribute('aria-label',open?'Cerrar la lista de referencias':'Abrir la lista de referencias');
    if(open)window.renderDocMap?.();
    // Abrir o cerrar cambia el ancho del PDF: el margen se reubica al terminar la transición.
    setTimeout(()=>window.renderMargin?.(),260);
  }
  tab.addEventListener('click',()=>{
    open=!open;apply();
    try{localStorage.setItem(key,open?'1':'0')}catch{/* solo dura esta sesión */}
  });
  let timer;
  window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(()=>window.renderMargin?.(),150)});
  apply();
})();
