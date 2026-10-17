(function () {
'use strict';
function start() {
 const root = document.querySelector('.esi-site');
 if (!root) return;
 const button = root.querySelector('.menu-toggle');
 const nav = root.querySelector('.main-nav');
 function close() { if (!button || !nav) return; button.setAttribute('aria-expanded','false'); button.setAttribute('aria-label','Abrir menú'); nav.classList.remove('is-open'); }
 button?.addEventListener('click', function () { const open = button.getAttribute('aria-expanded') !== 'true'; button.setAttribute('aria-expanded',String(open)); button.setAttribute('aria-label',open?'Cerrar menú':'Abrir menú'); nav?.classList.toggle('is-open',open); });
 nav?.querySelectorAll('a').forEach(a => a.addEventListener('click',close));
 document.addEventListener('keydown',e => {if(e.key==='Escape') close();});
 document.querySelector('#esi-advice-form')?.addEventListener('submit', function () { const submit=this.querySelector('[type=submit]'); if(submit){submit.disabled=true;submit.textContent='Enviando…';} });
 window.addEventListener('pageshow',()=>{const submit=document.querySelector('#esi-advice-form [type=submit]');if(submit){submit.disabled=false;submit.textContent='Solicitar asesoría';}});
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start);else start();
})();
