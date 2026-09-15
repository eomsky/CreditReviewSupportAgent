/* Shared toolbar panels for both layouts. */
(() => {
  const resultButtons=new Set();
  function syncFontSize(){
    const size=window.CreditReview?.getReportFontSize?.()||13;
    document.documentElement.style.setProperty('--report-font',size+'px');
    for(const frame of operatingFrames.values())frame.contentDocument?.documentElement.style.setProperty('--report-full-font',(size+1)+'px');
  }
  const fontStyle=document.createElement('style');fontStyle.textContent='html body #opinion,html body #opinion p,html body #opinion .evidence-sentence{font-size:var(--report-font,13px)!important}html body #opinion .section-title,html body #opinion .aggregate-title{font-size:calc(var(--report-font,13px) + 1px)!important}html body #opinion td,html body #opinion th{font-size:calc(var(--report-font,13px) - 2px)!important}html body #opinion .fixed-table-title{font-size:calc(var(--report-font,13px) + 1px)!important}.opinion-stream-preview{font-size:var(--report-font,13px)!important}';document.head.append(fontStyle);
  window.addEventListener('credit-review:font-size',syncFontSize);syncFontSize();
  const resultCSS='.result-only-toggle{display:inline-flex!important;align-items:center;justify-content:center;box-sizing:border-box;width:26px!important;height:26px!important;min-width:26px!important;padding:2px!important;margin-right:5px;border:1px solid #dce4d8!important;border-radius:5px;background:#fff!important;color:#6d826a;cursor:pointer;transition:background .12s,box-shadow .12s,transform .12s}.result-only-toggle svg{width:21px;height:21px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}.result-only-toggle:hover{background:#f1f5ed!important}.result-only-toggle[aria-pressed=true]{background:#dce8d5!important;border-color:#8fa585!important;color:#405d38;box-shadow:inset 0 2px 4px #38502a35!important;transform:translateY(1px)}.result-only-toggle:focus-visible{outline:2px solid #8fa585;outline-offset:2px}.results-only .evidence-open,.results-only .sentence-analysis-open,.results-only .review-gap-button,.results-only #chatPanel,.results-only #chatLaunchRow,.results-only #chatToggle,.results-only #drawer,.results-only #coverage,.results-only #filePopover,.results-only .repair-chat,.results-only .repair-divider,.results-only .repair-tip,.results-only .repair-version-control,.results-only .regenerate-control,.results-only .inline-revision,.results-only .revision-nav{display:none!important}.results-only .repair-layout{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:minmax(0,1fr)!important}.results-only #opinion p,.results-only #repairBody p{cursor:text!important}.results-only #opinion p.selected,.results-only #repairBody p.selected{background:transparent!important;box-shadow:none!important;outline:0!important}.results-only #opinion p:hover,.results-only #repairBody p:hover,.results-only #opinion .evidence-sentence:hover,.results-only #repairBody .evidence-sentence:hover,.results-only #opinion p:focus,.results-only #repairBody p:focus{background:transparent!important;box-shadow:none!important;outline:0!important;cursor:text!important}.results-only .evidence-sentence{cursor:text!important;background:transparent!important;text-decoration:none!important;box-shadow:none!important}.results-only #opinion p,.results-only #repairBody p{ text-decoration:none!important}.results-only .evidence-sentence:hover,.results-only .evidence-sentence:hover span{background:transparent!important;text-decoration:none!important;box-shadow:none!important}.results-only .sentence-tools,.results-only .repair-sentence-tools{display:none!important}';
  const isResultsOnly=()=>appWindow.classList.contains('results-only');
  function syncResultMode(){
    const active=isResultsOnly(),label=active?'분석모드로 돌아가기':'결과만 보기';
    for(const b of resultButtons){if(!b.isConnected){resultButtons.delete(b);continue;}b.title=label;b.setAttribute('aria-label',label);b.setAttribute('aria-pressed',String(active));if(b.ownerDocument!==document)b.ownerDocument.documentElement.classList.toggle('results-only',active);}
  }
  function toggleResultsOnly(){appWindow.classList.toggle('results-only');syncResultMode();}
  function attachResultsButton(doc,before){
    syncFontSize();
    if(!before||doc.getElementById('resultOnlyToggle'))return;
    const style=doc.createElement('style');style.textContent=resultCSS;doc.head.append(style);
    const button=doc.createElement('button');button.id='resultOnlyToggle';button.type='button';button.className='result-only-toggle';button.innerHTML='<svg viewBox="0 0 20 20" aria-hidden="true"><rect x=".75" y="1.5" width="18.5" height="17" rx="1.8" fill="#a8b7a2" stroke="none"/><rect x="2" y="2.75" width="16" height="14.5" rx=".6" fill="none" stroke="white" stroke-width="1.2"/><path d="M6 5h5.5L14 7.5V15H6Z" fill="white" stroke="none"/><path d="M11.5 5v2.5H14M8 10h4M8 12h4" stroke="currentColor" stroke-width="1"/></svg>';
    button.onclick=e=>{e.preventDefault();e.stopPropagation();toggleResultsOnly();};before.before(button);resultButtons.add(button);syncResultMode();
  }
  attachResultsButton(document,document.querySelector('.ide-run-group'));
  window.addEventListener('click',e=>{if(isResultsOnly()&&e.target.closest('#opinion p,#opinion .aggregate-title'))e.stopImmediatePropagation();},true);
  const historyButton=$('fullSourceButton');
  const style=document.createElement('style');
  style.textContent='.app.expanded .top .tools{gap:8px}.app.expanded .top .tools>.icon{width:32px;height:32px;flex-shrink:0}.app.expanded .ide-run-group{gap:3px;margin-right:10px}.app.expanded .ide-run{width:29px!important;height:29px!important}.recent-chat-row{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid #e3e9df;background:transparent;padding:11px 2px;color:inherit;cursor:pointer}.recent-chat-row small{display:block;font-size:10px;color:#819077;margin-bottom:5px}.recent-chat-row span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:12px;line-height:1.5}.recent-chat-row:hover{background:#f0f5ed}';
  document.head.append(style);
  const dialogStyle=document.createElement('style');
  dialogStyle.textContent='.review-dialog.compact-dialog{box-sizing:border-box;position:fixed;inset:auto;margin:0;width:var(--dialog-width)!important;max-width:var(--dialog-width)!important;max-height:var(--dialog-height)!important;left:var(--dialog-left);top:var(--dialog-top);padding:14px;font-size:12px}.compact-dialog h2{font-size:14px}.compact-dialog header button{font-size:18px;padding:3px 7px}.compact-dialog button{font-size:12px;padding:5px 9px}.compact-dialog .generation-list{margin-top:10px}.compact-dialog .generation-row{padding:7px 0;font-size:12px;gap:8px}.compact-dialog .generation-row button{min-width:48px}.compact-dialog .generation-child{padding-left:18px}.compact-dialog .system-prompt-editor{box-sizing:border-box;min-height:130px;height:32vh;font-size:12px;padding:8px}.compact-dialog>p{font-size:11px}';
  document.head.append(dialogStyle);
  function fitDialogs(){
    const r=appWindow.getBoundingClientRect(),compact=!appWindow.classList.contains('expanded');
    document.querySelectorAll('.review-dialog').forEach(d=>{
      d.classList.toggle('compact-dialog',compact);
      if(compact){d.style.setProperty('--dialog-width',Math.max(0,r.width-24)+'px');d.style.setProperty('--dialog-height',Math.max(0,r.height-64)+'px');d.style.setProperty('--dialog-left',r.left+12+'px');d.style.setProperty('--dialog-top',r.top+42+'px');}
    });
  }
  new MutationObserver(fitDialogs).observe(document.body,{childList:true,subtree:true});
  new MutationObserver(fitDialogs).observe(appWindow,{attributes:true,attributeFilter:['class']});
  window.addEventListener('resize',fitDialogs);
  historyButton.title='최근 대화 이력';historyButton.setAttribute('aria-label','최근 대화 이력');
  syncFullSourceButton=()=>historyButton.setAttribute('aria-expanded',String(!$('drawer').hidden&&$('drawerTitle').textContent==='최근 대화 이력'));
  function dismiss(){closePanels();syncFullSourceButton();}
  function openHistory(){
    const wasOpen=!$('drawer').hidden&&$('drawerTitle').textContent==='최근 대화 이력';
    dismiss();if(wasOpen)return;
    $('drawerTitle').textContent='최근 대화 이력';$('drawerBody').replaceChildren();$('drawer').hidden=false;
    const rows=[];
    for(const [key,messages] of chatThreads){
      const [company,view,mode]=key.split(':');if(Number(company)!==currentCompany)continue;
      messages.forEach((m,index)=>{if(m.role==='user')rows.push({m,index,view:Number(view),mode:mode==='revise'?'revise':'chat'});});
    }
    rows.sort((a,b)=>(Date.parse(b.m.createdAt)||0)-(Date.parse(a.m.createdAt)||0)||b.index-a.index);
    if(!rows.length){const empty=document.createElement('p');empty.textContent='아직 대화 이력이 없습니다.';$('drawerBody').append(empty);}
    for(const row of rows.slice(0,50)){
      const b=document.createElement('button');b.className='recent-chat-row';
      const label=document.createElement('small');label.textContent=reviewLabels[row.view]+' · '+(row.mode==='revise'?'의견보완':'대화');
      const text=document.createElement('span');text.textContent=row.m.text;b.append(label,text);
      b.onclick=()=>{if($('prompt').disabled)return;dismiss();switchReview(row.view);CreditReview.setMode(row.mode);setChatOpen(true);const frame=operatingFrames.get(currentCompany);frame?.contentDocument?.querySelector('.repair-layout')?.classList.remove('chat-hidden');};
      $('drawerBody').append(b);
    }
    syncFullSourceButton();
  }
  historyButton.onclick=e=>{e.stopPropagation();openHistory();};
  document.addEventListener('pointerdown',e=>{
    if(e.target.closest('.top .tools,#drawer,#filePopover,#coverage,#menu,dialog'))return;
    dismiss();
  },true);
  new MutationObserver(syncFullSourceButton).observe($('drawer'),{attributes:true,attributeFilter:['hidden']});
  window.CreditReviewToolbar={dismiss,openHistory,isResultsOnly,attachResultsButton};
  for(const frame of operatingFrames.values()){const doc=frame.contentDocument;if(doc)attachResultsButton(doc,doc.querySelector('.ide-run-group'));}
})();
