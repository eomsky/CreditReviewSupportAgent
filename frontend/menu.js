/* The same four menu actions in the standalone and connected interfaces. */
(() => {
 const menu=$('menu'),outline=$('reportOutlineOpen');
 const button=(id,label,action)=>{const b=document.createElement('button');b.id=id;b.textContent=label;b.onclick=()=>{closePanels();Promise.resolve().then(action).catch(e=>notify(e.message));};return b;};
 const system=button('systemPromptOpen','시스템 프롬프트 설정',()=>CreditReviewPresentation.systemSettings());
 const fontSettings=button('reportFontSizeOpen','글자 크기 설정',()=>{
  const d=document.createElement('dialog');d.className='review-dialog review-level-dialog';
  d.innerHTML='<header><h2>글자 크기 설정</h2><button type="button" aria-label="닫기">×</button></header><p>본문 글자 크기 <output></output></p><input type="range" min="12" max="18" step="1" aria-label="본문 글자 크기"><div class="review-level-labels"><span>작게</span><span>크게</span></div><p class="font-size-preview">가. 재무제표 주요계정<br>선택한 글자 크기가 보고서에 바로 반영됩니다.</p><small>전체 모드 본문은 1px, 소제목은 본문보다 1px 크게 표시됩니다.</small><p><button type="button" class="font-default">기본 크기로</button></p>';
  const range=d.querySelector('input');range.value=CreditReview.getReportFontSize();
  const paint=()=>{d.querySelector('output').textContent=range.value+'px';d.querySelector('.font-size-preview').style.fontSize=range.value+'px';range.setAttribute('aria-valuetext',range.value+'px');};
  range.oninput=()=>{CreditReview.setReportFontSize(Number(range.value));paint();};d.querySelector('.font-default').onclick=()=>{range.value=13;range.oninput();};d.querySelector('header button').onclick=()=>d.close();d.onclose=()=>d.remove();paint();(document.fullscreenElement||document.body).append(d);d.showModal();
 });
 const reviewSettings=button('reviewLevelOpen','검토 수준 설정',()=>{
  const d=document.createElement('dialog');d.className='review-dialog review-level-dialog';
  d.innerHTML='<header><h2>검토 수준 설정</h2><button type="button" aria-label="닫기">×</button></header><p>기존 의견 수정은 최소화하고, 추가 의견의 깊이와 범위를 조절합니다.</p><input id="reviewLevelRange" type="range" min="0" max="2" step="1" aria-label="검토 수준"><div class="review-level-labels"><button type="button" data-level="0">최소 보완</button><button type="button" data-level="1">적극 보완</button><button type="button" data-level="2">심층 보완</button></div><p class="review-level-description" role="status"></p><small>선택 즉시 저장되며 다음 의견 생성의 검토 단계부터 적용됩니다.</small>';
  const labels=['최소 보완','적극 보완','심층 보완'],descriptions=['현재 수준 · 기존 의견 수정과 추가를 최소화합니다.','기존 문장은 유지하면서 부족한 근거와 분석 의견을 더 적극적으로 추가합니다.','기존 문장은 유지하면서 원인·영향·상환재원·위험과 완충요인까지 추가 검토합니다.'];
  const range=d.querySelector('input');range.value=CreditReview.getReviewLevel();
  function paint(){const value=Number(range.value);range.setAttribute('aria-valuetext',labels[value]);d.querySelector('.review-level-description').textContent=descriptions[value];d.querySelectorAll('[data-level]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.level)===value)));}
  range.oninput=()=>{CreditReview.setReviewLevel(Number(range.value));paint();};d.querySelectorAll('[data-level]').forEach(b=>b.onclick=()=>{range.value=b.dataset.level;range.oninput();});
  d.querySelector('header button').onclick=()=>d.close();d.onclose=()=>d.remove();paint();(document.fullscreenElement||document.body).append(d);d.showModal();
 });
 const levelStyle=document.createElement('style');levelStyle.textContent='.review-level-dialog{width:min(460px,92vw);font-size:13px}.review-level-dialog p{line-height:1.7}.review-level-dialog input[type=range]{width:100%;accent-color:#66815c;margin:20px 0 6px;cursor:pointer}.review-level-labels{display:flex;justify-content:space-between;gap:8px}.review-level-labels button{padding:6px 8px;border-radius:5px;font-size:12px}.review-level-labels button[aria-pressed=true]{background:#e4eddf;color:#3f6036;font-weight:600}.review-level-description{min-height:48px;background:#f3f6f0;border-radius:7px;padding:10px}.review-level-dialog small{color:#7d8877;font-size:11px}';document.head.append(levelStyle);
 let pendingStart=null,stopDialog=null;
 let polling=false,pollTimer=null,caseId=null,generationDialog=null,activeTarget=null,stream=null,lastCompleted=-1,streamPreview='';
 const livePreview=document.createElement('aside');livePreview.hidden=true;livePreview.className='opinion-stream-preview';
 const streamHeading=document.createElement('div'),streamBody=document.createElement('div');streamHeading.className='opinion-stream-heading';streamBody.className='opinion-stream-body';livePreview.append(streamHeading,streamBody);$('opinion').before(livePreview);
 const streamCSS='.opinion-stream-preview{box-sizing:border-box;width:100%;margin:0;padding:0;background:transparent;color:inherit;font:inherit;font-size:13px}.opinion-stream-preview[hidden],.stream-original-hidden{display:none!important}.opinion-stream-heading{display:none}.opinion-stream-body{white-space:pre-wrap;line-height:1.75;overflow-wrap:anywhere;padding:0 4px}';
 let streamStageKey=null,lastStreamRun=null,lastStreamCase=null;
 let followRun=null,followLocked=false,followSwitch=false;
 const watchedDocuments=new WeakSet();
 function watchInteraction(doc){if(!doc||watchedDocuments.has(doc))return;watchedDocuments.add(doc);const stop=e=>{if(e.isTrusted&&lastStreamRun?.status==='running')followLocked=true;};doc.addEventListener('pointerdown',stop,true);doc.addEventListener('click',stop,true);doc.addEventListener('wheel',stop,{capture:true,passive:true});doc.addEventListener('keydown',e=>{if(['ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '].includes(e.key))stop(e);},true);}
 watchInteraction(document);
 function refinementPreview(panel,run){
  const owner=panel.ownerDocument,copy=owner.createElement('div');copy.innerHTML=$('opinion').innerHTML;
  const find=id=>[...copy.querySelectorAll('p[data-paragraph-id]')].filter(p=>p.dataset.paragraphId===id||p.dataset.paragraphId.startsWith(id+'::part'));
  let latest=null;const anchors=new Map();
  const tableChanges=run.table_review_preview||[];
  for(const change of tableChanges){
   const table=[...copy.querySelectorAll('table[data-table-key]')].find(t=>t.dataset.tableKey===change.table_key);
   const row=table?.rows[change.row+1],cell=row?.cells[change.column];if(!cell)continue;
   const next=change.value==null||change.value===''?'—':typeof change.value==='number'?change.value.toLocaleString('en-US',{maximumFractionDigits:10}):String(change.value);
   const old=cell.textContent.trim();
   if(old!==next){cell.replaceChildren();const del=owner.createElement('del'),ins=owner.createElement('ins');del.textContent=old;ins.textContent=next;cell.append(del,owner.createTextNode(' '),ins);cell.classList.add('refinement-table-revised');}
   latest=cell;
  }
  if(run.table_review_active){const active=latest||copy.querySelector('table td');if(active){active.classList.add('refinement-table-active');latest=active;}}
  for(const layout of run.table_review_layout||[]){
   const table=[...copy.querySelectorAll('table[data-table-key]')].find(t=>t.dataset.tableKey===layout.table_key);if(!table)continue;
   for(const ri of [...layout.omitted_rows].sort((a,b)=>b-a))table.rows[ri+1]?.remove();
   for(const ci of [...layout.omitted_columns].sort((a,b)=>b-a)){for(const row of table.rows)row.cells[ci]?.remove();table.querySelectorAll('col')[ci]?.remove();}
   if(layout.omitted_columns.length){const cols=[...table.querySelectorAll('col')],sum=cols.reduce((n,c)=>n+parseFloat(c.getAttribute('width')||0),0);if(sum)cols.forEach(c=>c.setAttribute('width',parseFloat(c.getAttribute('width'))*100/sum+'%'));for(const name of [...table.classList])if(/^fixed-cols-/.test(name))table.classList.remove(name);table.classList.add('fixed-cols-'+table.rows[0].cells.length);}
   if(layout.caption&&table.caption)table.caption.textContent=layout.caption;
  }
  for(const change of run.review_preview||[]){
   const matches=find(change.id),p=matches[0];if(!p)continue;
   if(change.kind==='add'){
    const added=owner.createElement('p'),ins=owner.createElement('ins');ins.textContent=change.text;added.append(ins);added.className='refinement-added';(anchors.get(change.id)||matches[matches.length-1]).after(added);anchors.set(change.id,added);latest=added;continue;
   }
   const before=matches.map(row=>{const clone=row.cloneNode(true);clone.querySelectorAll('.evidence-open').forEach(b=>b.remove());return clone.textContent.trim();}).join(' ');
   const normalize=s=>s.replace(/^[○◯]\s*/,'· ').replace(/\s+/g,' ').trim();
   const old=normalize(before),next=normalize(change.text);let start=0,end=0;
   while(start<old.length&&start<next.length&&old[start]===next[start])start++;
   if(change.complete)while(end<old.length-start&&end<next.length-start&&old[old.length-1-end]===next[next.length-1-end])end++;
   p.replaceChildren(owner.createTextNode(old.slice(0,start)));p.className='refinement-revised';
   const deleted=old.slice(start,end?old.length-end:undefined),added=next.slice(start,end?next.length-end:undefined);
   if(change.complete&&deleted){const del=owner.createElement('del');del.textContent=deleted;p.append(del);}
   if(added){const ins=owner.createElement('ins');ins.textContent=added;p.append(ins);}
   if(!change.complete&&deleted){const pending=owner.createElement('span');pending.className='refinement-pending';pending.textContent=deleted;p.append(pending);}
   if(end)p.append(owner.createTextNode(old.slice(-end)));
   matches.slice(1).forEach(row=>row.remove());latest=p;
  }
  const positions=[];for(let parent=panel.parentElement;parent;parent=parent.parentElement)positions.push([parent,parent.scrollTop,parent.scrollLeft]);
  panel.replaceChildren(...copy.childNodes);if(followLocked)positions.forEach(([node,top,left])=>{node.scrollTop=top;node.scrollLeft=left;});
  if(latest&&!followLocked){const frame=operatingFrames.get(currentCompany);const visible=owner===document?!appWindow.classList.contains('operating-full'):appWindow.classList.contains('operating-full')&&!!frame; if(visible)requestAnimationFrame(()=>{if(!followLocked&&latest.isConnected)latest.scrollIntoView({block:'nearest',behavior:'auto'});});}
 }
 const refinementCSS='.opinion-stream-preview ins{background:#eaf3df;color:inherit;text-decoration:none}.opinion-stream-preview del{background:#fae8e5;color:#99635c;text-decoration:line-through}.opinion-stream-preview .refinement-pending{opacity:.5}.opinion-stream-preview p{font-size:13px!important;line-height:1.75!important;letter-spacing:0;font-weight:400}.refinement-table-active{position:relative;overflow:hidden}.refinement-table-active::after{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(100deg,transparent 15%,#ffffffdd 50%,transparent 85%);transform:translateX(-100%);animation:table-review-sweep 1.3s ease-in-out infinite}.refinement-table-revised ins,.refinement-table-revised del{display:inline-block}@keyframes table-review-sweep{to{transform:translateX(100%)}}@media(prefers-reduced-motion:reduce){.refinement-table-active::after{animation:none;transform:none;background:#ffffff55}}';
 const refinementStyle=document.createElement('style');refinementStyle.textContent=refinementCSS;document.head.append(refinementStyle);
 const streamStyle=document.createElement('style');streamStyle.textContent=streamCSS;document.head.append(streamStyle);
 function paintStream(run){
  lastStreamRun=run;lastStreamCase=CreditReview.snapshot().active_case_id;
  if(run?.id&&run.id!==followRun){followRun=run.id;followLocked=false;}
  watchInteraction(operatingFrames.get(currentCompany)?.contentDocument);
  const running=run?.status==='running';
  const viewId=run?.target_views?.[Number(run.completed_calls)||0],index=CreditReview.viewIds.indexOf(viewId),stageKey=run?.id+':'+viewId;
  if(running&&index>=0)streamStageKey=stageKey;
  if(!running)streamStageKey=null;
  const refining=run?.phase==='refinement';
  if(running&&refining&&!followLocked&&!followSwitch&&index>=0&&index!==activeReview&&!(activeReview===0&&index>=1&&index<=5)){followSwitch=true;try{switchReview(index);}finally{followSwitch=false;}}
  const aggregate=activeReview===0&&index>=1&&index<=5;const showing=running&&(refining?!!(run.review_preview?.length||run.table_review_preview?.length||run.table_review_active):!!run?.preview?.trim())&&(index===activeReview||aggregate);
  $('opinion').classList.toggle('stream-original-hidden',showing);
  const heading=(run?.stage||'의견')+' · 생성 중';const content=(run?.preview||'자료를 검토하고 있습니다…').replace(/\[\s*S\d+(?:\s*[,;]\s*S\d+)*\s*\]/g,'').replace(/▷/g,'☞').replace(/(^|\n)(\s*)-\s/g,'$1$2☞ ').replace(/(^|\n)(\s*)[○◯]/g,'$1$2·');
  const paint=panel=>{
   panel.hidden=!showing;if(!showing)return;
   if(refining){panel._streamKey=null;refinementPreview(panel,run);return;}
   const original=$('opinion').innerHTML,key=stageKey+':'+activeReview+':'+original;
   if(panel._streamKey!==key){
    panel._streamKey=key;panel.replaceChildren();const owner=panel.ownerDocument,body=owner.createElement('div');body.className='opinion-stream-body';
    if(aggregate){
     const copy=owner.createElement('div');copy.innerHTML=original;
     let title=[...copy.querySelectorAll('.aggregate-title')].find(h=>h.dataset.viewId===viewId);
     if(title){let next=title.nextSibling;while(next&&!(next.nodeType===1&&next.matches('.aggregate-title'))){const remove=next;next=next.nextSibling;remove.remove();}title.after(body);}
     else{title=owner.createElement('h2');title.className='aggregate-title';title.dataset.viewId=viewId;title.textContent=reviewLabels[index];const next=[...copy.querySelectorAll('.aggregate-title')].find(h=>CreditReview.viewIds.indexOf(h.dataset.viewId)>index);if(next){next.before(title,body);}else copy.append(title,body);}
     panel.append(...copy.childNodes);
    }else if(index===7&&run.report_parts_done>0){const copy=owner.createElement('div');copy.innerHTML=original;panel.append(copy,body);}else panel.append(body);
   }
   const body=panel.querySelector('.opinion-stream-body');
   const source=panel.ownerDocument.getElementById(panel.ownerDocument===document?'opinion':'repairBody');
   if(source){const sample=source.querySelector('p:not(.review-lead-paragraph)')||source;const style=panel.ownerDocument.defaultView.getComputedStyle(sample);for(const name of ['fontFamily','fontSize','fontWeight','lineHeight','letterSpacing','color'])body.style[name]=style[name];body.style.setProperty('font-size','13px','important');body.style.lineHeight='1.75';body.style.letterSpacing='0';body.style.fontWeight='400';}
   if(body.textContent!==content)body.textContent=content;
  };
  paint(livePreview);
  const doc=operatingFrames.get(currentCompany)?.contentDocument,target=doc?.getElementById('repairBody');if(target){target.classList.toggle('stream-original-hidden',showing);let panel=doc.getElementById('fullOpinionStream');if(!panel){const style=doc.createElement('style');style.textContent=streamCSS+refinementCSS;doc.head.append(style);panel=livePreview.cloneNode(true);panel.id='fullOpinionStream';target.before(panel);}paint(panel);}
 }
 function syncStream(){paintStream(lastStreamCase===CreditReview.snapshot().active_case_id?lastStreamRun:CreditReview.generationState());}
 function progress(run){if(!run)return;if(run.id&&window.CreditReview.snapshot().active_case_id!==caseId)return;paintRunStatus(run);streamPreview=run.preview||'';paintStream(run);paintGeneration(run.stage);if(run.status!=='running'){stream?.close();stream=null;poll();}else if(run.completed_calls!==lastCompleted){lastCompleted=run.completed_calls;CreditReview.refresh().then(syncStream).catch(()=>{});}}
 const generation=button('generateOpinions','의견 (재)생성',openGeneration);
 const play=document.createElement('button');play.id='generatePlay';play.type='button';play.className='icon ide-run';play.title='의견 생성하기';play.setAttribute('aria-label','의견 생성하기');play.innerHTML='<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M6.5 4.5 15 10 6.5 15.5Z" fill="currentColor" stroke="none"/></svg>';play.onclick=()=>{closePanels();primaryAction();};$('rail_files').before(play);
 const runStyle=document.createElement('style');runStyle.textContent='.ide-run-group{display:inline-flex;align-items:center;gap:2px;margin-right:6px;flex-shrink:0;--run-badge-bg:transparent}.ide-run{position:relative!important;display:inline-grid!important;place-items:center!important;width:24px!important;height:26px!important;padding:3px!important;background:transparent!important;border:1px solid #c8d3c180!important;border-radius:5px!important;color:#54845b!important;box-shadow:none!important}.ide-run:hover:not(:disabled){background:#e7eee4!important;color:#396d43!important}.ide-run:focus-visible{outline:1px solid #8ca486;outline-offset:1px}.ide-run:disabled{color:#a4aea1!important;cursor:default;opacity:.5!important}.ide-run svg{width:17px!important;height:17px!important;display:block}.ide-run small{right:0!important;bottom:0!important;font-size:8px!important;line-height:10px!important;font-weight:600;color:inherit;background:var(--run-badge-bg,#f8faf6);padding:0 1px;border-radius:2px}';document.head.append(runStyle);window.CreditReviewRunCSS=runStyle.textContent;
 const runGroup=document.createElement('span');runGroup.className='ide-run-group';play.before(runGroup);runGroup.append(play);
 const runStatus=document.createElement('span');runStatus.id='generationStatus';runStatus.hidden=true;runStatus.className='toolbar-run-status';runStatus.setAttribute('role','status');runStatus.setAttribute('aria-live','polite');runStatus.setAttribute('aria-atomic','true');runGroup.before(runStatus);
 const progressPhase=document.createElement('small'),progressTask=document.createElement('small'),progressValue=document.createElement('strong');runStatus.append(progressPhase,progressTask,progressValue);
 const statusStyle=document.createElement('style');statusStyle.textContent='.required-document-reviews{display:none!important}.toolbar-run-status{display:flex;flex-direction:column;justify-content:center;flex:0 1 86px;min-width:0;max-width:86px;margin-right:3px;font-size:10px;line-height:1.3;color:#65806a;white-space:nowrap}.toolbar-run-status[hidden]{display:none}.toolbar-run-status strong{font-size:11px;font-weight:600;font-variant-numeric:tabular-nums}.toolbar-run-status small{display:block;width:100%;min-width:0;font:inherit;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.app.expanded .toolbar-run-status{max-width:150px;flex-basis:150px;flex-direction:column;align-items:flex-start;gap:1px}';document.head.append(statusStyle);window.CreditReviewProgressCSS=statusStyle.textContent;
 function paintRunStatus(run){
  if(!run||['completed','cancelled'].includes(run.status)){runStatus.hidden=true;return;}
  const total=Number(run.total_calls)||0,done=Number(run.completed_calls)||0;
  const progressKey=[run.id,run.phase,run.completed_calls].join(':');
  const supplied=Math.max(0,Math.min(100,Number(run.item_percent)||0));
  const percent=run.status==='running'&&runStatus.dataset.progressKey===progressKey?Math.max(Number(runStatus.dataset.percent)||0,supplied):supplied;
  runStatus.dataset.progressKey=progressKey;runStatus.dataset.percent=String(percent);
  const phase=run.phase==='refinement'?'(검토)':'(최초생성)';
  const target=(run.target_views||[])[Number(run.completed_calls)||0];
  const shortNames={financial_accounts:'가',profitability:'나',financial_stability:'다',cashflow_repayment:'라',customer_concentration:'마',summary_2:'종합의견2',report:'심사보고서'};
  const targetName=shortNames[target]||'';
  const detail=run.stage==='자료 충분성 및 표 구성 검토'?(Number(run.item_percent)>=30?'생성 중':'자료 검토'):(run.stage||'자료 업로드');
  const readableStage=targetName&&/자료 검토|생성 중|자료 충분성/.test(detail)?targetName+' · '+(detail.includes('생성 중')?'생성 중':'자료 검토'):detail;
  const stage=run.status==='failed'?'작업 실패':run.recovery_status?'토큰 조정 중':run.stage==='시작'?'자료 분석 준비':readableStage.replace(/ · 보완 검토$/,'');
  const label=phase+' '+stage+' '+percent+'%';
  progressPhase.textContent=phase;
  if(runStatus.dataset.label===label&&!runStatus.hidden)return;runStatus.dataset.label=label;
  runStatus.hidden=false;runStatus.title=label+' (현재 항목의 자료 준비·생성·검증 단계 기준)'+(run.recovery_status?' · '+run.recovery_status:'');
  if(progressValue.textContent!==percent+'%')progressValue.textContent=percent+'%';if(progressTask.textContent!==stage){progressTask.textContent=stage;progressTask.title=stage;}
 }
 async function startGeneration(index,useSupplement=false){
  if(polling)return;
  if(!localFiles.length){notify('의견을 생성하려면 기초자료를 먼저 첨부해 주세요.');return;}
  caseId=CreditReview.snapshot().active_case_id;activeTarget=index;paintRunStatus({status:'running',stage:'자료 업로드'});setRunning(true,index===-1?'전체':reviewLabels[index]);
  try{const indices=index===-1?[0,1,2,3,4,5,6,7]:index===0?[0,1,2,3,4,5]:[index];const supplements=Object.fromEntries(indices.map(i=>[CreditReview.viewIds[i],CreditReview.supplementRequest(i)]).filter(([,text])=>text));pendingStart=CreditReview.analyze({...(index===-1?{}:{viewIds:[CreditReview.viewIds[index]]}),supplements});await pendingStart;pendingStart=null;await poll();}catch(e){setRunning(false);paintRunStatus({status:'failed'});notify('의견 생성 시작 실패: '+e.message);}
 }
 function primaryAction(){if(polling)confirmStop();else openGeneration();}
 function confirmStop(){
  if(stopDialog?.open)return;
  const d=document.createElement('dialog');d.className='review-dialog';stopDialog=d;
  const message=document.createElement('p');message.textContent='중단하시겠습니까?';d.append(message);
  const no=document.createElement('button'),yes=document.createElement('button');no.textContent='아니요';yes.textContent='네';no.onclick=()=>d.close();
  yes.onclick=async()=>{yes.disabled=true;try{if(pendingStart)await pendingStart;await CreditReview.cancelGeneration();d.close();await poll();}catch(e){d.close();notify('중단 요청 실패: '+e.message);}};
  d.append(no,yes);d.onclose=()=>{stopDialog=null;d.remove();};(document.fullscreenElement||document.body).append(d);d.showModal();no.focus();
 }
 function openGeneration(){
  if(generationDialog?.open)return;
  const d=document.createElement('dialog');d.className='review-dialog generation-dialog';generationDialog=d;
  const header=document.createElement('header'),title=document.createElement('h2');title.textContent='의견 생성 범위';const close=document.createElement('button');close.textContent='×';close.setAttribute('aria-label','닫기');close.onclick=()=>d.close();header.append(title,close);d.append(header);
  const list=document.createElement('div');list.className='generation-list';
  ['전체',...reviewLabels].forEach((label,n)=>{const i=n-1;const row=document.createElement('div');row.className='generation-row'+(i>=1&&i<=5?' generation-child':' generation-parent')+(i===-1?' generation-all':'');const name=document.createElement('span');name.textContent=label;const action=document.createElement('button');action.dataset.viewIndex=i;action.onclick=()=>{if(i>=0&&CreditReview.supplementRequest(i))openSupplement(i);else{d.close();startGeneration(i);}};const badge=document.createElement('small');badge.className='supplement-badge';row.append(name,badge,action);list.append(row);});
  const state=document.createElement('p');state.className='generation-progress';state.setAttribute('role','status');const preview=document.createElement('pre');preview.className='generation-preview';preview.style.cssText='white-space:pre-wrap;max-height:240px;overflow:auto;font:inherit;line-height:1.7';d.append(list,state,preview);d.onclose=()=>{generationDialog=null;d.remove();};(document.fullscreenElement||document.body).append(d);paintGeneration();d.showModal();
 }
 function openSupplement(index){
  const d=document.createElement('dialog');d.className='review-dialog supplement-dialog';
  const title=document.createElement('h2');title.textContent=reviewLabels[index]+' · 보완 요청사항';
  const input=document.createElement('textarea');input.value=CreditReview.supplementRequest(index);input.setAttribute('aria-label','보완 요청사항');input.style.cssText='box-sizing:border-box;width:100%;min-height:180px;margin:14px 0;padding:10px;resize:vertical;font:inherit;line-height:1.6';
  const actions=document.createElement('div');actions.style.cssText='display:flex;gap:8px;flex-wrap:wrap';
  const add=(label,action)=>{const b=document.createElement('button');b.textContent=label;b.onclick=async()=>{b.disabled=true;try{await action();}catch(e){notify(e.message);}finally{b.disabled=false;}};actions.append(b);};
  add('닫기',()=>d.close());
  add('요청 삭제',async()=>{await CreditReview.saveSupplementRequest(index,'');d.close();paintGeneration();});
  add('수정 저장',async()=>{await CreditReview.saveSupplementRequest(index,input.value);d.close();paintGeneration();});
  add('재생성',async()=>{if(input.value.trim()!==CreditReview.supplementRequest(index))await CreditReview.saveSupplementRequest(index,input.value);d.close();generationDialog?.close();await startGeneration(index);});
  d.append(title,input,actions);d.onclose=()=>d.remove();(document.fullscreenElement||document.body).append(d);d.showModal();
 }
 function paintGeneration(stage=''){
  if(!generationDialog)return;
  const snapshot=CreditReview.snapshot(),reviews=snapshot.companies.find(c=>c.id===snapshot.active_case_id).state.reviews;
  const run=CreditReview.generationState(),failed=run?.status==='failed',failedView=failed?run.target_views?.[Number(run.completed_calls)||0]:null;
  generationDialog.querySelectorAll('[data-view-index]').forEach(b=>{const i=Number(b.dataset.viewIndex);const requested=i>=0&&!!CreditReview.supplementRequest(i);b.classList.toggle('has-supplement',requested);const badge=b.parentElement.querySelector('.supplement-badge');badge.textContent=requested?'보완 요청건':'';badge.hidden=!requested;b.disabled=polling;b.textContent=polling&&i===activeTarget?'생성 중':(i===-1?Object.values(reviews).some(r=>r.html?.trim()):reviews[i]?.html?.trim())?'재생성':'생성';b.setAttribute('aria-label',(i===-1?'전체':reviewLabels[i])+' '+b.textContent);});
  generationDialog.querySelector('.generation-progress').textContent=polling?'생성 중'+(stage?' · '+stage:''):'생성할 항목을 선택하세요. 종합의견1은 가~마를 함께 생성합니다.';
  generationDialog.querySelector('.generation-preview').textContent=polling?streamPreview:'';
  generationDialog.querySelectorAll('[data-view-index]').forEach(b=>{const i=Number(b.dataset.viewIndex),view=CreditReview.viewIds[i],matches=failed&&!!failedView&&(view===failedView||i===0&&['financial_accounts','profitability','financial_stability','cashflow_repayment','customer_concentration'].includes(failedView));let badge=b.parentElement.querySelector('.generation-failure-badge');if(!badge){badge=document.createElement('small');badge.className='generation-failure-badge';badge.style.cssText='color:#b45c54;font-size:11px;white-space:nowrap';b.before(badge);}badge.hidden=!matches;badge.textContent=matches?'작업 실패':'';badge.title=matches?(run.stage||'')+' · '+(run.error||'오류 발생'):'';if(matches&&!polling){b.textContent='다시 시도';b.setAttribute('aria-label',reviewLabels[i]+' 다시 시도');}});
  if(failed&&!polling){const error=run.error||'원인 확인 필요';generationDialog.querySelector('.generation-progress').textContent=(run.stage||'의견 생성')+'에서 작업이 실패했습니다. '+error+' · 완료된 의견은 유지됩니다.';}
 }
 function setRunning(value,stage=''){
  polling=value;play.disabled=false;play.setAttribute('aria-busy',String(value));const path=play.querySelector('path'),shape=value?'M5 5H15V15H5Z':'M6.5 4.5 15 10 6.5 15.5Z';if(path.getAttribute('d')!==shape)path.setAttribute('d',shape);play.title=value?'의견 생성 중단':'의견 생성하기';play.setAttribute('aria-label',play.title);window.dispatchEvent(new CustomEvent('credit-review:generation-state',{detail:{running:value}}));generation.setAttribute('aria-busy',String(value));paintGeneration(stage);
  generation.title=value?'의견 생성 중'+(stage?' · '+stage:''):'종합의견1·종합의견2·심사보고서 생성';
  if(!value){clearTimeout(pollTimer);pollTimer=null;stream?.close();stream=null;paintStream(null);}
 }
 function observe(result){
  paintRunStatus(result.run);paintStream(result.run);
  if(result.run?.status==='running'){
   caseId=result.id||CreditReview.snapshot().active_case_id;setRunning(true,result.run.stage);
   if(!stream)stream=CreditReview.watchGeneration(progress);clearTimeout(pollTimer);pollTimer=setTimeout(poll,5000);
  }else{
   const wasRunning=polling;setRunning(false);
   if(wasRunning&&result.run?.status==='completed'){if(activeTarget!==null)CreditReview.frame.navigate(activeTarget===-1?7:activeTarget);notify('선택한 항목의 의견 생성이 완료되었습니다.');}
   else if(wasRunning&&result.run?.status==='cancelled')notify('의견 생성을 중단했습니다.');
   else if(wasRunning&&result.run?.status==='failed')notify('의견 생성 중단: '+(result.run.error||'상태 확인 필요'));
  }
 }
 async function poll(){
  if(CreditReview.snapshot().active_case_id!==caseId){setRunning(false);paintRunStatus(null);return;}
  try{observe(await CreditReview.refresh());}catch(e){setRunning(false);notify('결과 조회 실패: '+e.message);}
 }
 function buildExport(){
  const snapshot=CreditReview.snapshot(),company=snapshot.companies.find(c=>c.id===snapshot.active_case_id);
  const escape=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const reviews=company.state.reviews;
  if(![0,6,7].some(i=>reviews[i]?.html?.trim()))throw Error('내보낼 의견이 없습니다. 의견을 먼저 생성해 주세요.');
  const sections=[0,6,7].map(i=>{
   const box=document.createElement('div');box.innerHTML=reviews[i]?.html||'';
   box.querySelectorAll('.evidence-open,.duplicate-header-row').forEach(n=>n.remove());
   box.querySelectorAll('*').forEach(n=>{for(const a of [...n.attributes])if(a.name.startsWith('data-')||['tabindex','role','title'].includes(a.name))n.removeAttribute(a.name);});
   return '<section><h1>'+escape(reviewLabels[i])+'</h1>'+(box.innerHTML||'<p class="empty">미작성</p>')+'</section>';
  }).join('\n');
  return {filename:company.name.replace(/[\\/:*?"<>|]/g,'_')+'_심사의견.html',html:'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(company.name)+' · 심사의견</title><style>body{max-width:960px;margin:40px auto;padding:0 24px;color:#303734;font-family:"Malgun Gothic",sans-serif;line-height:1.8}header{border-bottom:1px solid #ddd;margin-bottom:32px}section{margin-bottom:48px}h1{font-size:22px}h2{font-size:18px}.section-title{margin:20px 0 8px;font-weight:600}p,.evidence-sentence{white-space:pre-wrap}.evidence-sentence{display:inline;margin:0}table{border-collapse:collapse;width:100%;margin:16px 0}td,th{border:1px solid #ddd;padding:8px}.empty{color:#8a938c}@media print{section{break-before:page}section:first-of-type{break-before:auto}}</style><body><header><h1>'+escape(company.name)+'</h1></header>'+sections+'</bo'+'dy></html>'};
 }
 const exportGroup=document.createElement('div');exportGroup.className='report-export-group';
 const exportButton=document.createElement('button');exportButton.id='exportOpinions';exportButton.type='button';exportButton.textContent='내보내기';exportButton.setAttribute('aria-haspopup','true');exportButton.setAttribute('aria-expanded','false');
 const exportChoices=document.createElement('div');exportChoices.className='report-export-choices';exportChoices.setAttribute('aria-label','다운로드 형식');
 let exportBusy=false;
 function exportPayload(format){
  const result=buildExport(),doc=new DOMParser().parseFromString(result.html,'text/html');
  doc.querySelectorAll('button,script,style,.sentence-tools,.repair-sentence-tools,.review-gap-button,.sentence-analysis-open,del').forEach(n=>n.remove());
  const sections=[...doc.querySelectorAll('section')].map(section=>({title:section.querySelector('h1').textContent,blocks:[...section.querySelectorAll('h2,h3,h4,.aggregate-title,.section-title,.table-unit,caption,table,p')].filter(n=>!n.closest('td,th,caption')&&!n.parentElement.closest('p')).map(n=>n.tagName==='TABLE'?{type:'table',caption:n.caption?.textContent.trim()||'',column_widths:[...n.querySelectorAll('colgroup col')].map(c=>parseFloat(c.getAttribute('width'))),rows:[...n.rows].map(r=>[...r.cells].map(c=>c.textContent.trim()))}:{type:n.matches('h2,h3,h4,.aggregate-title,.section-title')?'heading':'paragraph',text:n.textContent.trim()}).filter(b=>b.type==='table'||b.text)}));
  return {format,title:doc.querySelector('header h1').textContent+' 심사의견',sections,filename:result.filename.replace(/\.html$/,'.'+format)};
 }
 async function downloadReport(format){
  if(exportBusy)return;
  const payload=exportPayload(format);exportBusy=true;exportChoices.querySelectorAll('button').forEach(b=>b.disabled=true);exportButton.textContent='파일 생성 중…';
  try{
   const response=await fetch('/api/credit-review/v1/export',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
   if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.error||'다운로드에 실패했습니다.');}
   const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download=payload.filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);closePanels();
  }finally{exportBusy=false;exportButton.textContent='내보내기';exportChoices.querySelectorAll('button').forEach(b=>b.disabled=false);}
 }
 for(const [format,label] of [['pdf','PDF'],['docx','Word']]){const b=document.createElement('button');b.type='button';b.dataset.format=format;b.textContent=label;b.title=label+' 다운로드';b.onclick=e=>{e.stopPropagation();downloadReport(format).catch(e=>notify(e.message));};exportChoices.append(b);}
 function showFormats(open){exportGroup.classList.toggle('open',open);exportButton.setAttribute('aria-expanded',String(open));}
 exportGroup.addEventListener('mouseenter',()=>showFormats(true));exportGroup.addEventListener('mouseleave',()=>{if(!exportGroup.contains(document.activeElement))showFormats(false);});
 exportGroup.addEventListener('focusin',()=>showFormats(true));exportGroup.addEventListener('focusout',e=>{if(!exportGroup.contains(e.relatedTarget))showFormats(false);});
 exportButton.onclick=e=>{e.stopPropagation();showFormats(true);exportChoices.firstElementChild.focus();};
 exportGroup.addEventListener('keydown',e=>{if(e.key==='Escape'){e.stopPropagation();exportButton.focus();showFormats(false);}});
 const reset=button('resetOpinions','의견 초기화',()=>CreditReview.resetOpinions());
 exportGroup.append(exportButton,exportChoices);menu.replaceChildren(system,outline,reviewSettings,fontSettings,generation,reset,exportGroup);
 const exportStyle=document.createElement('style');exportStyle.textContent='#menu{overflow:visible!important}.report-export-group{position:relative}.report-export-group>#exportOpinions{width:100%}.report-export-choices{display:none;position:absolute;right:100%;top:0;padding:4px 8px 4px 4px;align-items:center;gap:4px;white-space:nowrap;background:#fff;border:1px solid #dce4d8;border-radius:7px;box-shadow:0 3px 12px #26382c18;z-index:10}.report-export-group.open .report-export-choices{display:flex}.menu .report-export-choices button{width:auto!important;min-width:48px;padding:7px 9px;border:1px solid #dce4d8;border-radius:4px;font-size:12px}.report-export-choices button:hover{background:#edf3e8}.report-export-choices button:active{background:#dce8d5;box-shadow:inset 0 1px 3px #38502a35}.report-export-choices button:disabled{opacity:.5;cursor:wait}';document.head.append(exportStyle);
 const css=document.createElement('style');css.textContent='.app .top .tools,.app.expanded .top .tools{display:flex;align-items:center;justify-content:flex-end;gap:3px;flex-shrink:0;margin-left:auto}.app .top .tools>.icon{width:24px;height:28px}.app .top .tools #honeyBtn{margin-right:3px}.app .top>div:first-child{flex:1;min-width:0;overflow:hidden}.app .top #companyName{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.generation-dialog{width:min(560px,94vw)}.generation-list{margin-top:16px}.generation-row{display:flex;align-items:center;gap:16px;padding:12px 0;border-bottom:1px solid #e6ebe3;font-size:13px}.generation-row span{flex:1;min-width:0}.generation-row button{flex-shrink:0;min-width:66px}.generation-row button:disabled{opacity:.5;cursor:default}.generation-row.generation-child{padding-left:28px;position:relative}.generation-child:before{content:"";position:absolute;left:10px;top:0;bottom:0;border-left:1px solid #d9e2d5}.generation-child:after{content:"";position:absolute;left:10px;top:50%;width:10px;border-top:1px solid #d9e2d5}.generation-parent>span{font-weight:600}.generation-all{border-bottom:2px solid #d9e2d5;margin-bottom:6px}.generation-progress{font-size:12px;color:#7a8873}.generation-row .supplement-badge{font-size:10px;color:#bd6a20;white-space:nowrap}.generation-row button.has-supplement{background:#fff0dc!important;color:#b55c13!important;border:1px solid #edbb80}.generation-row{gap:8px}';document.head.append(css);
 window.CreditReviewMenu={syncStream,observe,buildExport,openGeneration,startAll:primaryAction,startSupplement:()=>{if(!polling&&CreditReview.supplementation().length)return startGeneration(activeReview,true);}};
})();
