/* The full-size view uses the same parent state, requests and revision actions. */
(() => {
  'use strict';
  const host=()=>parent.CreditReview;
  const byId=id=>document.getElementById(id);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=String(text);if(cls)n.className=cls;return n;};
  let payload=null,anchor=null;
  const selectedIds=new Set();
  const nativeKeys=['가. 영업현황','나. 재무상태','다. 상환능력','라. 거래관계','마. 기타'];
  function block(e){e.preventDefault();e.stopImmediatePropagation();}
  function choose(p,e){
    if(payload.busy)return;
    document.querySelector('.repair-layout').classList.remove('chat-hidden');
    const id=p.dataset.paragraphId,rows=[...byId('repairBody').querySelectorAll('p[data-paragraph-id]')];
    if(e.shiftKey&&anchor){const a=rows.findIndex(p=>p.dataset.paragraphId===anchor),b=rows.indexOf(p);if(a>=0){if(!e.ctrlKey&&!e.metaKey)selectedIds.clear();rows.slice(Math.min(a,b),Math.max(a,b)+1).forEach(p=>selectedIds.add(p.dataset.paragraphId));}}
    else if(e.ctrlKey||e.metaKey){if(selectedIds.has(id))selectedIds.delete(id);else selectedIds.add(id);anchor=id;}
    else {const same=selectedIds.size===1&&selectedIds.has(id);selectedIds.clear();if(!same)selectedIds.add(id);anchor=id;}
    rows.forEach(p=>p.classList.toggle('selected',selectedIds.has(p.dataset.paragraphId)));host().frame.select([...selectedIds]);
    const label=document.querySelector('.messenger-context-default');if(label)label.textContent=selectedIds.size?'선택 문구 '+selectedIds.size+'개':'의견 전체';
  }
  function paint(){
    if(!payload)return;
    selectedIds.clear();(payload.selectedIds||[]).forEach(id=>selectedIds.add(id));
    document.querySelector('.chat-mode-switch')?.setAttribute('aria-checked',String(payload.mode==='revise'));byId('repairInput').placeholder=payload.mode==='revise'?'보완할 문장을 선택하고 수정 내용을 입력하세요.':'자유롭게 질문하세요. 문장을 선택하면 함께 참고합니다.';
    activeCaseSelected=true;activeCaseIsNew=false;app.classList.remove('case-empty','case-picker-open');
    const body=byId('repairBody'),scroll=body.parentElement.scrollTop;
    body.innerHTML=payload.html;body.querySelectorAll('p[data-paragraph-id]').forEach(p=>p.classList.toggle('selected',selectedIds.has(p.dataset.paragraphId)));
    body.querySelectorAll('p[data-paragraph-id]').forEach(p=>{
      const variants=[];for(const entry of payload.history||[]){const box=el('div');box.innerHTML=entry.html;const old=[...box.querySelectorAll('p')].find(q=>q.dataset.paragraphId===p.dataset.paragraphId);if(old&&variants.at(-1)!==old.textContent)variants.push(old.textContent);}
      const current=variants.lastIndexOf(p.textContent);if(current<0||variants.length<2)return;
      const bar=el('div',null,'bridge-revisions');for(const [label,delta] of [['<',-1],['>',1]]){const b=el('button',label);b.setAttribute('aria-label',delta<0?'이 문구의 이전 버전':'이 문구의 다음 버전');b.disabled=payload.busy||current+delta<0||current+delta>=variants.length;b.onclick=()=>host().frame.restoreParagraph(p.dataset.paragraphId,variants[current+delta]);bar.append(b);}p.before(bar);
    });
    if(!body.textContent.trim())body.append(el('div','아직 작성된 의견이 없습니다.','empty-review'));
    body.parentElement.scrollTop=scroll;
    document.querySelector('.repair-title-row h1').textContent=payload.labels[payload.view];parent.CreditReviewPresentation?.paintGapButtons();parent.CreditReviewMenu?.syncStream();
    byId('currentItemCrumb').textContent=payload.labels[payload.view];byId('caseTrigger').textContent=payload.company;
    const crumb=byId('caseTrigger');crumb.title=payload.case_id;
    document.querySelectorAll('.nav-row[data-item]').forEach(row=>{const i=nativeKeys.indexOf(row.dataset.item)+1;row.classList.remove('confirmed-item');row.removeAttribute('aria-disabled');row.disabled=false;row.classList.toggle('active',i===payload.view);});
    const side=byId('sidebar');
    side.querySelectorAll('.nav-row[data-item]').forEach(row=>{const i=nativeKeys.indexOf(row.dataset.item)+1;const status=row.querySelector('.nav-status');if(status)status.textContent=payload.statuses[i]??'미작성';});
    side.querySelectorAll('.nav-group').forEach(group=>{const label=group.querySelector('.title')?.textContent.trim();const i={'종합의견1':0,'종합의견2':6,'심사보고서':7}[label];if(i!==undefined){group.classList.toggle('active',payload.view===i);const status=group.querySelector('.nav-status');if(status)status.textContent=payload.statuses[i]??'미작성';}});
    byId('opinionFacts').replaceChildren();byId('repairFacts').replaceChildren();
    for(const id of ['opinionFactSub','repairFactSub'])byId(id).textContent='';
    const chat=byId('repairChatLog');chat.replaceChildren();
    if(!payload.chats.length){const welcome=el('div',null,'message assistant');welcome.append(el('p',payload.mode==='revise'?'안녕하세요. 보완할 의견의 문장이나 항목을 선택하고, 수정할 내용을 말씀해 주세요.':'안녕하세요. 현재 심사항목에 대해 궁금한 내용을 말씀해 주세요. 문장을 선택하면 해당 내용을 함께 참고해 답변드리겠습니다.'));chat.append(welcome);}
    payload.chats.forEach(m=>{const row=el('div',null,'message '+(m.role==='user'?'user':'assistant'));if(m.scope){const context=el('div',m.scope,'chat-context');context.title=m.scope;row.append(context);}row.append(el(m.role==='user'?'div':'p',m.role==='user'?m.text:parent.CreditReviewDisplayText(m.text),m.role==='user'?'bubble':''));if(m.sentenceAnalysisKey)parent.CreditReviewPresentation?.renderAnalysisChatEntry(row,m);chat.append(row);});
    chat.setAttribute('aria-busy',String(!!payload.chatThinking));if(payload.chatThinking){const row=el('div',parent.CreditReviewDisplayText(payload.chatStreamText)||'생각 중…',payload.chatStreamText?'chat-streaming':'chat-thinking');row.setAttribute('role','status');row.setAttribute('aria-live','polite');row.style.whiteSpace='pre-wrap';chat.append(row);}
    if(payload.pending){const row=chat.lastElementChild;const preview=el('section',null,'revision-target-preview');preview.append(el('strong','보완 대상 · '+payload.pending.originals.length+'개'));const list=el('ol');payload.pending.originals.forEach(p=>list.append(el('li',p.text)));preview.append(list,el('p','요청: '+payload.pending.text));row.append(preview);const group=el('div',null,'revision-choice');for(const [label,yes] of [['예',true],['아니오',false]]){const b=el('button',label);b.onclick=()=>host().frame.decide(yes);group.append(b);}row.append(group);}
    const hint=document.querySelector('.messenger-context-default');if(hint)hint.textContent=selectedIds.size?'선택 문구 '+selectedIds.size+'개':'의견 전체';
    const chips=byId('fullChatAttachments');if(chips){chips.replaceChildren();(payload.chatFiles||[]).forEach((name,i)=>{const chip=el('span',name+' '),remove=el('button','×');remove.setAttribute('aria-label',name+' 첨부 제거');remove.onclick=()=>parent.CreditReviewChatAttachments.remove(i);chip.append(remove);chips.append(chip);});}
    const footer=byId('applyRepair').parentElement;[...footer.querySelectorAll('span')].filter(n=>/AI 미연결|AI 연결 설정됨|예시 화면/.test(n.textContent)).forEach(n=>n.hidden=true);
    byId('applyRepair').disabled=payload.busy||!byId('repairInput').value.trim();
    const logScroll=byId('repairChatScroll');logScroll.scrollTop=logScroll.scrollHeight;
    // Keep the native sidebar layout, but all entries come from the parent case.
    for(const [kind,root] of [['notes',document.querySelector('[data-review-drop="memo"]')],['prompts',document.querySelector('[data-review-drop="prompt"]')]]){
      if(!root)continue;
      root.querySelectorAll('[data-note-type],.bridge-note').forEach(n=>n.remove());
      payload[kind].forEach((entry,index)=>{const b=el('button',entry.title||entry.text,'bridge-note nav-row');b.dataset.bridgeKind=kind;b.dataset.bridgeIndex=index;root.append(b);});
      root.querySelectorAll('.count,.sidebar-count').forEach(n=>n.textContent=payload[kind].length);
    }
    renderSources();
  }
  function renderSources(){
    const popup=byId('sourcePopover');let list=byId('bridgeSourceList');
    if(!list){[...popup.children].filter(n=>!n.classList.contains('source-popover-head')).forEach(n=>n.remove());list=el('div',null,'pop-scroll');list.id='bridgeSourceList';popup.append(list);}
    list.replaceChildren();list.append(el('div','업로드 자료','pop-section-title'));
    if(!payload.files.length)list.append(el('div','등록된 자료가 없습니다.','source-search-empty'));
    payload.files.forEach(f=>{const b=el('button',f.name,'pop-row');b.onclick=()=>host().frame.openFiles();list.append(b);});
    if(payload.audit.length){list.append(el('div','금액 검수 결과 — 보고서 미반영','pop-section-title'));payload.audit.forEach(f=>list.append(el('div',[f.path,f.old,'→',f.new,f.reason].filter(Boolean).join(' '),'pop-row')));}
  }
  window.operatingAdapter={load(data){const changed=payload?.case_id!==data.case_id||payload?.view!==data.view;if(changed){selectedIds.clear();anchor=null;}byId('repairInput').value=data.draft||'';payload=data;paint();},export(){return null;},updateEntries(){payload=host().frame.payload();paint();}};
  // Legacy view actions must not regenerate sample text or write to a second API.
  workbenchClient.connected=false;
  syncRepairFromOpinion=()=>{if(payload)paint();};
  renderItemFacts=()=>{byId('opinionFacts').replaceChildren();byId('repairFacts').replaceChildren();};
  renderOpinionGenerationHistory=()=>{};
  setView('repair');
  window.addEventListener('click',e=>{
    if(parent.CreditReviewToolbar?.isResultsOnly()&&e.target.closest('#repairBody')){e.stopImmediatePropagation();return;}
    parent.CreditReviewToolbar?.dismiss();
    if(!payload)return;
    if(e.target.closest('.review-gap-button'))return;const heading=e.target.closest('#repairBody .aggregate-title');if(heading){block(e);const i=['summary_1','financial_accounts','profitability','financial_stability','cashflow_repayment','customer_concentration'].indexOf(heading.dataset.viewId);if(i>0){host().frame.discuss(i);document.querySelector('.repair-layout').classList.remove('chat-hidden');}return;}
    const target=e.target.closest('button,[data-item],p[data-paragraph-id],.pop-row');if(!target)return;
    const p=target.closest('#repairBody p[data-paragraph-id]');if(p){block(e);if(e.target.closest('.evidence-open,.sentence-analysis-open')&&parent.CreditReviewPresentation){(e.target.closest('.sentence-analysis-open')?parent.CreditReviewPresentation.openSentenceAnalysis:parent.CreditReviewPresentation.openEvidence)(p.dataset.paragraphId,e.target.closest('.evidence-sentence')?.textContent||p.textContent);}else choose(p,e);return;}
    const nav=target.closest('.nav-row[data-item]');if(nav){block(e);const i=nativeKeys.indexOf(nav.dataset.item);if(i>=0)host().frame.navigate(i+1);return;}
    const group=target.closest('#caseSidebarNav .nav-group');if(group){const label=group.querySelector('.title')?.textContent.trim();const index={'종합의견1':0,'종합의견2':6,'심사보고서':7}[label];if(index!==undefined){block(e);host().frame.navigate(index);return;}}
    if(target.id==='applyRepair'){block(e);const input=byId('repairInput'),text=input.value;input.value='';host().frame.submit(text,[...selectedIds]);return;}
    const entryAnchor=()=>{const r=target.getBoundingClientRect(),f=window.frameElement.getBoundingClientRect();return {right:f.left+r.right,top:f.top+r.top};};
    if(target.dataset.bridgeKind){block(e);host().frame.openEntry(target.dataset.bridgeKind,Number(target.dataset.bridgeIndex),entryAnchor());return;}
    if(target.matches('[data-note-type], [data-add-note], #saveReviewNote')||/메모 추가|프롬포트 반영 추가|프롬프트 추가/.test(target.getAttribute('aria-label')||target.textContent)){block(e);host().frame.openEntry(/프롬/.test(target.getAttribute('aria-label')||target.textContent)?'prompts':'notes',null,entryAnchor());return;}
    if(['companySelectionTrigger','caseTrigger'].includes(target.id)){block(e);const r=target.getBoundingClientRect(),f=window.frameElement.getBoundingClientRect();host().frame.openCompanies({left:f.left+r.left,bottom:f.top+r.bottom});return;}
    if(['creditSurveyRow','additionalSourceRow','surveyEvidenceRow'].includes(target.id)){block(e);host().frame.openFiles();return;}
    if(['startUnwrittenGeneration','regenerateOpinion','confirmRegenerate','generateOtherOpinion'].includes(target.id)){block(e);host().analyze().catch(err=>toast(err.message));return;}
    if(target.id==='reviewRepair'){block(e);host().save().then(()=>toast('작업을 저장했습니다.')).catch(err=>toast(err.message));return;}
    if(target.id==='confirmOpinion'){block(e);toast('최종 확정은 서버의 검토·승인 절차에 연결해야 합니다.');return;}
    if(['sourceTrigger','closeSourcePopover'].includes(target.id)){block(e);byId('sourcePopover').classList.remove('show');parent.CreditReviewToolbar?.openHistory();return;}
  },true);
  window.addEventListener('keydown',e=>{const span=e.target.closest('.evidence-sentence');if(span&&['Enter',' '].includes(e.key)&&parent.CreditReviewPresentation){block(e);(e.target.closest('.sentence-analysis-open')?parent.CreditReviewPresentation.openSentenceAnalysis:parent.CreditReviewPresentation.openEvidence)(span.closest('p').dataset.paragraphId,span.textContent);return;}if(e.target===byId('repairInput')&&e.key==='Enter'&&!e.shiftKey&&!e.isComposing){block(e);const text=e.target.value;e.target.value='';host().frame.submit(text,[...selectedIds]);}},true);
  byId('repairInput').addEventListener('paste',e=>parent.CreditReviewChatAttachments.paste(e));
  byId('repairInput').addEventListener('input',()=>{byId('applyRepair').disabled=payload?.busy||!byId('repairInput').value.trim();host().frame.draft(byId('repairInput').value);});
  const analysisStyle=el('style');analysisStyle.textContent=parent.CreditReviewSentenceAnalysisCSS||'';document.head.append(analysisStyle);
  const inlineCSS=el('style');inlineCSS.textContent='.evidence-open{display:inline-block;vertical-align:baseline;width:auto;min-width:25px;height:17px;padding:0 4px!important;margin-left:4px;border:1px solid #d6dfd2!important;border-radius:4px!important;background:#f5f8f2!important;color:#75856e;cursor:pointer;line-height:15px;font-size:9px;font-weight:400;white-space:nowrap}.evidence-open:before{content:"근거";font-size:9px}.required-document-reviews{display:none!important;margin:18px 0;font-size:12px;line-height:1.7}';document.head.append(inlineCSS);
  const evidenceStyle=el('style');evidenceStyle.textContent='#repairBody .evidence-sentence{display:inline;white-space:normal;margin-bottom:0;cursor:pointer}#repairBody .evidence-sentence:hover{background:#f0f5ef}';document.head.append(evidenceStyle);
  byId('repairBody').replaceChildren();byId('repairChatLog').replaceChildren();
  const attach=el('button','+');attach.id='fullChatAttach';attach.type='button';attach.setAttribute('aria-label','대화 파일 첨부');attach.title='대화 파일 첨부';
  const chatPicker=el('input');chatPicker.type='file';chatPicker.accept='.docx,.pptx,.hwp,.hwpx,.gif,.bmp,.tif,.tiff,.xlsx,.xls,.pdf,.json,.txt,.csv,.md,.png,.jpg,.jpeg,.webp';chatPicker.multiple=true;chatPicker.hidden=true;document.body.append(chatPicker);
  chatPicker.onchange=()=>{const files=[...chatPicker.files];chatPicker.value='';parent.CreditReviewChatAttachments.upload(files);};
  window.addEventListener('click',e=>{if(e.target.closest('#fullChatAttach')){block(e);chatPicker.click();}},true);
  const composer=byId('applyRepair').parentElement;composer.append(attach);
  const attachCSS=el('style');attachCSS.textContent='#fullChatAttach{position:absolute;left:8px;bottom:8px;width:28px;height:28px;display:grid;place-items:center;border:0;background:transparent;color:#72836a;font-size:23px;padding:0;line-height:1;cursor:pointer}#fullChatAttach:hover{background:#eef3eb;border-radius:5px}';document.head.append(attachCSS);composer.style.position='relative';
  byId('repairPlusButton').hidden=true;byId('messengerRepairToggle').hidden=true;
  byId('repairInput').placeholder='자유롭게 질문하세요. 문장을 선택하면 함께 참고합니다.';
  const head=document.querySelector('.repair-chat-section-label');head.replaceChildren(el('span'));const modeSwitch=el('button');modeSwitch.className='chat-mode-switch';modeSwitch.type='button';modeSwitch.setAttribute('role','switch');modeSwitch.setAttribute('aria-label','의견보완 모드');modeSwitch.append(el('span','대화'),el('span','의견보완'));head.firstChild.append(modeSwitch);modeSwitch.onclick=()=>host().setMode(host().getMode()==='chat'?'revise':'chat');const modeStyle=el('style');modeStyle.textContent=parent.CreditReviewModeCSS||'';document.head.append(modeStyle);
  const alpha=el('button','투명도'),hide=el('button','숨기기'),alphaBox=el('div');alphaBox.hidden=true;alphaBox.className='full-chat-transparency';
  const range=el('input');range.type='range';range.min=0;range.max=65;range.step=5;range.value=parent.document.getElementById('chatTransparency').value;range.setAttribute('aria-label','대화창 배경 투명도');const value=el('output',range.value+'%');
  range.oninput=()=>{value.textContent=range.value+'%';const p=parent.document.getElementById('chatTransparency');p.value=range.value;p.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('.repair-chat').style.background='rgba(255,255,255,'+(1-Number(range.value)/100)+')';};
  alphaBox.append(range,value);alpha.setAttribute('aria-expanded','false');alpha.onclick=()=>{alphaBox.hidden=!alphaBox.hidden;alpha.setAttribute('aria-expanded',String(!alphaBox.hidden));};
  hide.style.marginLeft='8px';hide.onclick=()=>{document.querySelector('.repair-layout').classList.add('chat-hidden');alphaBox.hidden=true;alpha.setAttribute('aria-expanded','false');};head.append(alpha,hide,alphaBox);
  const reopen=el('button','대화 열기');reopen.className='full-chat-reopen';reopen.onclick=()=>{host().setMode('chat');document.querySelector('.repair-layout').classList.remove('chat-hidden');};document.querySelector('.repair-layout').append(reopen);
  const chips=el('div');chips.id='fullChatAttachments';document.querySelector('.repair-input-box').prepend(chips);
  const controlsCSS=el('style');controlsCSS.textContent='.repair-chat-section-label{display:flex!important;position:relative;align-items:center;gap:8px;padding:9px 14px;font-size:12px}.repair-chat-section-label>span:first-child{flex:1}.repair-chat-section-label button{border:0;background:transparent;color:#72836a;font-size:12px}.repair-chat-toolbar{display:none!important}.repair-chat{grid-template-rows:auto minmax(0,1fr) auto!important}.full-chat-transparency:not([hidden]){position:absolute;right:90px;top:100%;z-index:20;background:white;padding:10px;border:1px solid #dce4d8;border-radius:8px;display:flex;gap:8px}.repair-layout.chat-hidden{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:1fr!important}.chat-hidden>.repair-chat,.chat-hidden>#repairDivider{display:none!important}.full-chat-reopen{display:none}.chat-hidden>.full-chat-reopen{display:block;position:absolute;right:20px;bottom:20px;border:0;background:#edf3e9;padding:10px;border-radius:8px}#fullChatAttachments{display:flex;flex-wrap:wrap;gap:6px;font-size:12px}#bridgeSourceList .pop-row{width:100%;text-align:left;white-space:normal;word-break:keep-all}.chat-context{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:11px;line-height:1.5;color:#89967e;margin:0 0 5px;overflow-wrap:anywhere}.chat-streaming{white-space:pre-wrap;line-height:1.7}';document.head.append(controlsCSS);
  const hierarchyStyle=el('style');hierarchyStyle.textContent=(parent.CreditReviewHierarchyCSS||'')+'.duplicate-header-row{display:none!important}';document.head.append(hierarchyStyle);
  const thinkingCSS=el('style');thinkingCSS.textContent='.chat-thinking{padding:10px 4px;color:#82917c;font-size:12px;animation:chat-thinking-pulse 1.4s ease-in-out infinite}@keyframes chat-thinking-pulse{50%{opacity:.45}}@media(prefers-reduced-motion:reduce){.chat-thinking{animation:none}}';document.head.append(thinkingCSS);
  byId('opinionFacts').replaceChildren();byId('repairFacts').replaceChildren();
  const runStyle=el('style');runStyle.textContent=parent.CreditReviewRunCSS||'';document.head.append(runStyle);
  const generatePlay=el('button');generatePlay.type='button';generatePlay.className='icon-button ide-run';generatePlay.setAttribute('aria-label','의견 생성하기');generatePlay.title='의견 생성하기';generatePlay.innerHTML='<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M6.5 4.5 15 10 6.5 15.5Z" fill="currentColor"/></svg>';generatePlay.onclick=e=>{block(e);parent.CreditReviewMenu.startAll();};byId('sourceTrigger').before(generatePlay);
  const runGroup=el('span');runGroup.className='ide-run-group';generatePlay.before(runGroup);runGroup.append(generatePlay);
  parent.CreditReviewToolbar?.attachResultsButton(document,runGroup);
  const parentPlay=parent.document.getElementById('generatePlay');
  const syncPlay=()=>{generatePlay.disabled=parentPlay.disabled;generatePlay.title=parentPlay.title;generatePlay.setAttribute('aria-label',parentPlay.title);const path=generatePlay.querySelector('path'),shape=parentPlay.querySelector('path').getAttribute('d');if(path.getAttribute('d')!==shape)path.setAttribute('d',shape);};
  new MutationObserver(syncPlay).observe(parentPlay,{attributes:true,subtree:true});syncPlay();
  const progressStyle=el('style');progressStyle.textContent=parent.CreditReviewProgressCSS||'';document.head.append(progressStyle);
  const progressSource=parent.document.getElementById('generationStatus'),progressLabel=el('span');progressLabel.className='toolbar-run-status';progressLabel.setAttribute('role','status');runGroup.before(progressLabel);
  let lastProgress='';
  const syncProgress=()=>{const key=JSON.stringify([progressSource?.hidden,progressSource?.title,progressSource?.textContent]);if(key===lastProgress)return;lastProgress=key;progressLabel.hidden=!progressSource||progressSource.hidden;progressLabel.title=progressSource?.title||'';progressLabel.replaceChildren(...[...(progressSource?.childNodes||[])].map(n=>n.cloneNode(true)));};
  if(progressSource)new MutationObserver(syncProgress).observe(progressSource,{childList:true,subtree:true,attributes:true});syncProgress();
  byId('sourcePopover').classList.remove('show');byId('sourceTrigger').setAttribute('aria-expanded','false');
  const style=el('style');style.textContent='html body #repairBody,html body #repairBody p,html body #repairBody .evidence-sentence{font-size:var(--report-full-font,14px)!important;line-height:1.8!important}html body #repairBody .section-title,html body #repairBody .aggregate-title{font-size:calc(var(--report-full-font,14px) + 1px)!important;line-height:1.6!important}html body #repairBody table,html body #repairBody td,html body #repairBody th{font-size:calc(var(--report-full-font,14px) - 2px)!important}html body #repairBody .fixed-table-title{font-size:calc(var(--report-full-font,14px) + 1px)!important}html .ide-run-group,html .toolbar-run-status,html #resultOnlyToggle{display:none!important}#sourcePopover{display:none!important}#repairBody table{border-collapse:collapse;display:table;width:100%;table-layout:fixed;max-width:100%;font-size:12px;margin:12px 0}#repairBody th,#repairBody td{border:1px solid #dde4d9;padding:7px}#repairBody p{white-space:pre-wrap}#repairBody p.selected{background:#eef4ef;box-shadow:inset 2px 0 #6d927b}.source-reference{font-size:11px;color:#72836a}.empty-review{font-size:13px;color:#939a94}.bridge-note{width:100%;text-align:left}.pop-section-title{font-size:12px;font-weight:600;padding:12px}';document.head.append(style);
})();
