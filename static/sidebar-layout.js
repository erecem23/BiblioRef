/* Sidebar collapse state is a browser preference, never app data. */
(()=>{
  const key='biblioref.sidebar-collapsed.v1';
  const sidebar=$('#appSidebar'),btn=$('#toggleSidebar');
  if(!sidebar||!btn)return;
  let collapsed=false;
  try{collapsed=localStorage.getItem(key)==='1'}catch{/* A blocked preference must not prevent opening the app. */}
  function apply(){
    sidebar.classList.toggle('collapsed',collapsed);
    btn.setAttribute('aria-expanded',String(!collapsed));
    btn.title=collapsed?'Mostrar menú':'Minimizar menú';
    const label=btn.querySelector('.collapse-label');
    if(label)label.textContent=collapsed?'Mostrar':'Minimizar';
  }
  btn.onclick=()=>{
    collapsed=!collapsed;
    apply();
    try{localStorage.setItem(key,collapsed?'1':'0')}catch{/* Session-only fallback. */}
  };
  apply();
})();
