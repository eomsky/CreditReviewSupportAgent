/* A shared indicator stays visible in both workspace modes. */
(()=>{
 const offline=document.createElement('span');offline.id='aiOfflineLabel';offline.textContent='(오프라인)';offline.style.cssText='font-size:12px;color:#858d85;white-space:nowrap';offline.setAttribute('aria-live','polite');document.querySelector('#titlebar .app-name').append(offline);
 const dot=document.createElement('button');dot.type='button';dot.id='aiConnectionStatus';
 const tip=document.createElement('span');tip.id='aiConnectionTooltip';tip.setAttribute('role','tooltip');
 dot.setAttribute('aria-describedby',tip.id);dot.append(tip);document.getElementById('appWindow').append(dot);
 const css=document.createElement('style');css.textContent='#aiConnectionStatus{position:absolute;left:14px;bottom:14px;z-index:120;width:12px;height:12px;padding:0;border:0;border-radius:50%;background:#a6aaa5;cursor:default;box-shadow:0 0 0 3px #ffffffb3}#aiConnectionStatus.connected{background:#4caa68}#aiConnectionTooltip{display:none;position:absolute;left:0;bottom:23px;background:#344033;color:white;padding:7px 10px;border-radius:6px;font-size:12px;font-weight:400;white-space:nowrap;pointer-events:none}#aiConnectionStatus:hover #aiConnectionTooltip,#aiConnectionStatus:focus-visible #aiConnectionTooltip{display:block}';document.head.append(css);
 function paint(data){const on=data?.connected===true;dot.classList.toggle('connected',on);offline.hidden=on;let message=on?'AI 서버 연결됨':'AI 서버 연결 끊김';if(data&&data.review!==data.chat)message+=' · '+(data.review?'대화 서버 연결 끊김':'의견 생성 서버 연결 끊김');tip.textContent=message;dot.setAttribute('aria-label',message);}
 let busy=false;async function check(){if(busy)return;busy=true;try{if(!/^https?:$/.test(location.protocol))throw Error();const response=await fetch('/api/credit-review/v1/connection',{cache:'no-store',signal:AbortSignal.timeout(9000)});if(!response.ok)throw Error();paint(await response.json());}catch{paint(null);}finally{busy=false;}}
 paint(null);check();setInterval(check,20000);window.addEventListener('online',check);window.addEventListener('offline',()=>paint(null));document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});
})();
