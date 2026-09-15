/* Remind new assessments to attach their source documents. */
(() => {
 const hint=document.createElement('button');hint.type='button';hint.id='sourceUploadHint';hint.hidden=true;hint.textContent='기초 데이터를 업로드 해주세요';hint.setAttribute('aria-label','기초 데이터를 업로드 해주세요');appWindow.append(hint);
 const style=document.createElement('style');style.textContent='#sourceUploadHint{position:absolute;z-index:100;padding:9px 12px;border:1px solid #cddbc7;border-radius:7px;background:#f5f9f1;color:#53694a;font:inherit;font-size:12px;line-height:18px;white-space:nowrap;box-shadow:0 3px 10px #20351b14;cursor:pointer}#sourceUploadHint[hidden]{display:none}#sourceUploadHint:before{content:"";position:absolute;top:-5px;left:var(--arrow-left,20px);width:8px;height:8px;background:#f5f9f1;border-left:1px solid #cddbc7;border-top:1px solid #cddbc7;transform:rotate(45deg)}';document.head.append(style);
 hint.onclick=()=>CreditReview.frame.openFiles();
 function update(){
  const home=document.getElementById('reviewHome');
  if(!home?.hidden||localFiles.length||companies[currentCompany]?.name==='업체 미선택'||!$('drawer').hidden||appWindow.classList.contains('minimized')){hint.hidden=true;return;}
  const visible=e=>e&&e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
  let anchor=$('rail_files'),rect;
  if(visible(anchor))rect=anchor.getBoundingClientRect();
  else if(appWindow.classList.contains('operating-full')){
   const frame=operatingFrames.get(currentCompany),button=frame?.contentDocument?.getElementById('sourceTrigger');
   if(button&&button.getClientRects().length){const r=button.getBoundingClientRect(),f=frame.getBoundingClientRect();rect={left:r.left+f.left,right:r.right+f.left,bottom:r.bottom+f.top};}
  }
  if(!rect){hint.hidden=true;return;}
  hint.hidden=false;const app=appWindow.getBoundingClientRect(),left=Math.max(8,Math.min(rect.left-app.left,appWindow.clientWidth-hint.offsetWidth-8));hint.style.left=left+'px';hint.style.top=(rect.bottom-app.top+8)+'px';hint.style.setProperty('--arrow-left',Math.max(10,Math.min((rect.left+rect.right)/2-app.left-left-4,hint.offsetWidth-18))+'px');
 }
 setInterval(update,400);window.addEventListener('resize',update);CreditReview.ready.then(update);
})();
