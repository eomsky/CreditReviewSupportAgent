/* Retain the original titlebar fullscreen/restore behavior. */
(() => {
  'use strict';
  const app=document.getElementById('appWindow');
  document.getElementById('titlebar').addEventListener('pointerdown',e=>e.stopImmediatePropagation(),true);
  window.CreditReview.ready.then(()=>{
    app.classList.remove('minimized','expanded');
    reflectFullscreen();
  });
})();
