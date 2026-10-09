/* Height handle for «Tesis incorporadas»; the page rail lives in review-navigation.js. */
(() => {
  const style = document.createElement('style');
  style.id = 'viewer-navigation-style';
  style.textContent = `
    #chooseDrive{display:none!important}
    /* The old «← pág. [n] Ir pág. →» group stays in the DOM for the code that updates it, hidden. */
    .viewerbar .toolbar-group[aria-label="Navegación de página"]{display:none}
    .cards-resizer{height:12px;margin:4px 0 0;cursor:ns-resize;display:flex;align-items:center;justify-content:center;border-radius:6px;touch-action:none}
    .cards-resizer::before{content:'';width:48px;height:4px;border-radius:999px;background:#c9ced8}
    .cards-resizer:hover::before,.cards-resizer:focus-visible::before{background:var(--accent)}
    .cards-resizer:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
  `;
  document.head.appendChild(style);

  // The page scrubber moved to review-navigation.js as a vertical rail beside the PDF.

  // ---- «Tesis incorporadas»: drag the handle to make the list taller or shorter -----------
  const cards = document.getElementById('uploadCards');
  if(cards){
    const KEY = 'biblioref.cards-height.v1';
    const apply = h => { cards.style.maxHeight = 'none'; cards.style.height = `${Math.round(h)}px`; };
    try{ const saved = +localStorage.getItem(KEY); if(saved >= 200) apply(saved); }catch{ /* only this session */ }
    const handle = document.createElement('div');
    handle.className = 'cards-resizer';
    handle.setAttribute('role', 'separator');
    handle.setAttribute('aria-orientation', 'horizontal');
    handle.setAttribute('aria-label', 'Alto de la lista de tesis');
    handle.tabIndex = 0;
    handle.title = 'Arrastrá para agrandar o achicar la lista';
    cards.insertAdjacentElement('afterend', handle);
    const save = () => { try{ localStorage.setItem(KEY, String(cards.getBoundingClientRect().height)); }catch{ /* ignore */ } };
    let startY = 0, startH = 0;
    handle.addEventListener('pointerdown', e => {
      startY = e.clientY; startH = cards.getBoundingClientRect().height;
      handle.setPointerCapture(e.pointerId);
      const move = ev => apply(Math.max(200, Math.min(window.innerHeight * 2, startH + ev.clientY - startY)));
      const up = () => { handle.removeEventListener('pointermove', move); handle.removeEventListener('pointerup', up); save(); };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
    });
    handle.addEventListener('keydown', e => {
      const step = {ArrowUp: -40, ArrowDown: 40}[e.key];
      if(!step) return;
      e.preventDefault();
      apply(Math.max(200, cards.getBoundingClientRect().height + step));
      save();
    });
  }
})();
