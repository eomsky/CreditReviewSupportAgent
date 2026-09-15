/* Source-image viewer, global system instructions, and evidence coverage. */
(() => {
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
 const activityStyle=el('style');activityStyle.textContent='.analysis-activity-dots{display:inline-block;width:3ch;font-family:monospace;vertical-align:bottom}.analysis-activity-dots::after{content:".";animation:analysis-activity 1.5s steps(1,end) infinite}@keyframes analysis-activity{0%,100%{content:"."}33%{content:".."}66%{content:"..."}}@media(prefers-reduced-motion:reduce){.analysis-activity-dots::after{animation:none;content:"..."}}';document.head.append(activityStyle);
 const makeDialog=(title)=>{const d=el('dialog');d.className='review-dialog';const header=el('header');header.append(el('h2',title));const close=el('button','×');close.setAttribute('aria-label','닫기');close.onclick=()=>d.close();header.append(close);d.append(header);d.onclose=()=>d.remove();(document.fullscreenElement||document.body).append(d);return d;};
 function openEvidence(id,sentence){
  const entries=[];
  for(let view=1;view<reviewLabels.length;view++){
   const box=el('div');box.innerHTML=reviewStates[view]?.html||'';
   box.querySelectorAll('p[data-paragraph-id]').forEach(p=>{
    const spans=[...p.querySelectorAll('.evidence-sentence')];
    for(const span of spans.length?spans:[p]){const clone=span.cloneNode(true);clone.querySelectorAll('.evidence-open').forEach(b=>b.remove());const text=clone.textContent.trim();if(text)entries.push({id:p.dataset.paragraphId,text,view,title:reviewLabels[view]});}
   });
  }
  const normalize=text=>String(text||'').replace(/^[○◯·☞※-]\s*/,'').replace(/\s+/g,' ').trim();
  let index=entries.findIndex(e=>e.id===id&&normalize(e.text)===normalize(sentence));
  if(index<0)index=entries.findIndex(e=>e.id===id);
  if(index<0){entries.push({id,text:sentence||CreditReview.evidenceFor(id)?.text||'',view:activeReview,title:reviewLabels[activeReview]});index=entries.length-1;}
  const d=makeDialog('원문 근거'),itemTitle=el('p'),quote=el('p'),nav=el('div'),body=el('section');
  itemTitle.className='evidence-review-title';itemTitle.style.cssText='font-size:12px;font-weight:600;margin:14px 0 6px';
  quote.style.cssText='font-size:13px;line-height:1.75;margin:0 0 12px';nav.className='evidence-nav';d.append(itemTitle,quote,nav,body);
  const paint=()=>{
   const entry=entries[index],refs=CreditReview.evidenceFor(entry.id)?.sources||[];
   itemTitle.textContent=entry.title;quote.textContent=entry.text;body.replaceChildren();nav.replaceChildren();
   const prev=el('button','‹ 이전'),next=el('button','다음 ›');prev.disabled=index===0;next.disabled=index===entries.length-1;
   prev.title='이전 문장';next.title='다음 문장';prev.onclick=()=>{index--;paint();d.scrollTop=0;};next.onclick=()=>{index++;paint();d.scrollTop=0;};nav.append(prev,next);
   if(!refs.length)body.append(el('p','이 문장에 연결된 원문 근거가 없습니다.'));
   for(const ref of refs){
   const filename=el('p'),download=el('a',ref.document_name||ref.label||'원문');download.href='#';download.title='원본 파일 다운로드';download.style.cssText='color:inherit;text-decoration:underline;text-underline-offset:3px;cursor:pointer';download.onclick=e=>{e.preventDefault();try{CreditReview.downloadDocument(ref);}catch(error){notify(error.message);}};filename.append(download);body.append(filename);
   const excel=['xlsx','xls'].includes(ref.format);
   if(ref.sheet)body.append(el('p','시트: '+ref.sheet));
   const imageUrl=ref.image_url||(excel&&ref.document_id&&ref.id?'/evidence/'+ref.document_id+'/'+ref.id.replace(ref.document_id+'-','')+'.png':null);
   if(imageUrl){const img=el('img');img.src=imageUrl;img.alt='원문 문서의 해당 근거 영역';img.className='evidence-image';img.style.cursor='zoom-in';img.tabIndex=0;img.title='클릭하여 크게 보기';const enlarge=()=>{const large=document.createElement('dialog');large.className='evidence-large-view';const close=el('button','닫기 ×');close.onclick=()=>large.close();const full=el('img');full.src=imageUrl;full.alt=img.alt;full.style.cursor='zoom-out';full.title='클릭하여 원래 크기로 돌아가기';full.tabIndex=0;full.onclick=()=>large.close();full.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();large.close();}};large.append(close,full);large.onclose=()=>large.remove();(document.fullscreenElement||document.body).append(large);large.showModal();};img.onclick=enlarge;img.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();enlarge();}};img.onerror=()=>{img.replaceWith(el('p','원문 이미지를 불러오지 못했습니다. 문서 연결을 확인하세요.'));};body.append(img);}
   else if(ref.text){const pre=el('pre',ref.text);pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px';body.append(pre);}
   else body.append(el('p','이 결과에 원문 위치가 저장되어 있지 않습니다. 첨부 자료로 다시 생성해 주세요.'));
   }
  };paint();
  const revise=el('button','이 문단 보완');revise.onclick=()=>{const entry=entries[index];d.close();if(entry.view!==activeReview)switchReview(entry.view);CreditReview.frame.select([entry.id]);setChatOpen(true,'revise');operatingFrames.get(currentCompany)?.contentDocument?.querySelector('.repair-layout')?.classList.remove('chat-hidden');$('prompt').focus();};d.append(revise);d.showModal();
 }
 const sentenceAnalysisCache=new Map();
 async function openSentenceAnalysis(id,sentence,saved=null){
  const paragraph=CreditReview.evidenceFor(id),text=String(sentence||paragraph?.text||'').trim();
  let title=reviewLabels[activeReview],itemView=activeReview;
  for(let view=1;view<reviewLabels.length;view++){const box=el('div');box.innerHTML=reviewStates[view]?.html||'';if([...box.querySelectorAll('p[data-paragraph-id]')].some(p=>p.dataset.paragraphId===id)){title=reviewLabels[view];itemView=view;break;}}
  if(saved){title=saved.title||title;itemView=saved.view??itemView;}
  const d=makeDialog('문장 분석'),item=el('p',title),quote=el('blockquote','"'+text+'"'),body=el('section'),quoteLabel=el('h3','선택 문장');quote.className='sentence-analysis-quote';
  item.style.cssText='font-size:12px;font-weight:600';quote.style.cssText='font-size:13px;line-height:1.75';const divider=el('hr');divider.className='sentence-analysis-divider';d.append(item,quoteLabel,quote,divider,body);
  const key=saved?.key||JSON.stringify([CreditReview.snapshot().active_case_id,id,text,CreditReview.reviewData()]);
  if(saved?.result)sentenceAnalysisCache.set(key,Promise.resolve(saved.result));
  const run=async()=>{
   const progress=el('div'),badge=el('span','분석 중'),description=el('span','판단 구조와 수치·원문 근거를 확인하고 있습니다'),dots=el('span');dots.className='analysis-activity-dots';dots.setAttribute('aria-hidden','true');description.append(dots);progress.className='sentence-analysis-progress';progress.setAttribute('role','status');badge.className='sentence-analysis-status';progress.append(badge,description);body.replaceChildren(progress);
   try{
    if(!sentenceAnalysisCache.has(key))sentenceAnalysisCache.set(key,CreditReview.analyzeSentence(id,text,title));
    const raw=await sentenceAnalysisCache.get(key);const normalize=value=>typeof value==='string'?window.CreditReviewDisplayText(value):Array.isArray(value)?value.map(normalize):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).map(([k,v])=>[k,normalize(v)])):value;const result=normalize(raw);if(!d.isConnected)return;body.replaceChildren();
    body.append(el('h3','분석 설명'),el('p',result.summary));
    if(result.concept_steps?.length){body.append(el('h3',result.concept_title||'판단 구조'));const flow=el('div');flow.className='sentence-concept-flow';result.concept_steps.forEach((step,i)=>{if(i){const arrow=el('span','→');arrow.setAttribute('aria-hidden','true');flow.append(arrow);}flow.append(el('span',step));});body.append(flow);}
    if(result.comparisons?.length){body.append(el('h3','핵심 수치'));const wrap=el('div'),table=el('table'),head=el('tr');wrap.style.overflowX='auto';table.className='sentence-analysis-table';['지표','값','기준·산출 근거'].forEach(t=>head.append(el('th',t)));table.append(head);result.comparisons.forEach(row=>{const tr=el('tr');[row.metric,row.value,row.basis].forEach(t=>tr.append(el('td',t)));table.append(tr);});wrap.append(table);body.append(wrap);}
    body.append(el('p',[result.evidence_assessment,result.reasoning].filter(Boolean).join(' ')));
    if(result.improvements?.length){const note=el('p','※ 확인할 부분: '+result.improvements.join(' '));note.className='sentence-analysis-note';body.append(note);}
    const continueChat=el('button','대화창에서 이어가기');continueChat.style.marginTop='12px';continueChat.onclick=()=>{if(CreditReview.continueSentenceAnalysis({id,sentence:text,title,view:itemView,result,key}))d.close();};body.append(continueChat);
   }catch(error){sentenceAnalysisCache.delete(key);if(!d.isConnected)return;const retry=el('button','다시 분석');retry.onclick=run;body.replaceChildren(el('p',error.message||'분석 결과를 불러오지 못했습니다.'),retry);}
  };
  d.classList.add('sentence-analysis-dialog');d.showModal();run();
 }
 function renderAnalysisChatEntry(row,message){
  const saved=message.sentenceAnalysis,selected=message.selected_paragraphs?.[0];
  const sentence=saved?.sentence||selected?.text||'선택 문장';
  const doc=row.ownerDocument,p=doc.createElement('p'),button=doc.createElement('button');
  p.textContent=window.CreditReviewDisplayText(sentence);button.type='button';button.className='analysis-chat-link';button.textContent='분석결과 보기';
  button.onclick=e=>{e.preventDefault();e.stopPropagation();
   const data=saved||{id:selected?.id,sentence,title:'문장 분석',key:message.sentenceAnalysisKey,result:{summary:message.text,concept_steps:[],comparisons:[],improvements:[]}};
   openSentenceAnalysis(data.id,data.sentence,data);
  };row.replaceChildren(p,button);
 }
 const sentenceAnalysisCSS='.analysis-chat-link{display:inline-block!important;width:auto!important;min-width:0!important;font-size:11px!important;line-height:1.5!important;padding:2px 7px!important;margin:3px 0 0!important;border:1px solid #d6dfd2!important;border-radius:4px;background:#f5f8f2;color:#61745a;cursor:pointer}.analysis-chat-link:hover{background:#e9f0e2}'+'.sentence-analysis-open{display:inline-flex!important;align-items:center;justify-content:center;vertical-align:middle;width:18px!important;min-width:18px!important;height:18px!important;padding:1px!important;margin-left:3px!important;border:0!important;background:transparent!important;color:#8c7955;cursor:pointer}.sentence-analysis-open svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.25;stroke-linecap:round;stroke-linejoin:round}.sentence-analysis-open:hover,.sentence-analysis-open:focus-visible{background:#f3efdf!important;border-radius:3px}.sentence-analysis-dialog{width:min(540px,94vw)!important}.sentence-analysis-divider{border:0;border-top:1px solid #d8e1d2;margin:16px 0}.sentence-analysis-quote{font-weight:700!important;margin:0 0 16px;padding:10px 12px;border-left:3px solid #b4c3ac;background:#f2f5ef;border-radius:3px;color:#354431}.sentence-analysis-progress{display:flex;align-items:flex-start;gap:8px;margin:16px 0;font-size:12px;line-height:1.7;color:#75816f}.sentence-analysis-status{display:inline-block;flex-shrink:0;padding:1px 7px;border-radius:10px;background:#e8eee3;color:#50664a;font-size:11px;font-weight:600}.sentence-analysis-dialog p,.sentence-analysis-dialog li{font-size:13px;line-height:1.75}.sentence-analysis-dialog h3{font-size:12px;margin:14px 0 6px}.sentence-analysis-note{font-size:12px!important;color:#727768}.sentence-concept-flow{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:12px;background:#f1f5ed;font-size:12px;line-height:1.6}.sentence-analysis-table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.6}.sentence-analysis-table th,.sentence-analysis-table td{border:1px solid #dce4d8;padding:6px;text-align:left;vertical-align:top}.sentence-analysis-table th{background:#f1f5ed}';
 const sentenceAnalysisStyle=el('style');sentenceAnalysisStyle.textContent=sentenceAnalysisCSS;document.head.append(sentenceAnalysisStyle);window.CreditReviewSentenceAnalysisCSS=sentenceAnalysisCSS;
 function systemSettings(){
  const d=makeDialog('시스템 프롬프트 설정'),area=el('textarea');area.setAttribute('aria-label','시스템 프롬프트 내용');area.className='system-prompt-editor';area.value=CreditReview.getSystemPrompt();
  d.append(area);
  const save=el('button','저장');save.onclick=async()=>{await CreditReview.setSystemPrompt(area.value);d.close();notify('시스템 프롬프트를 저장했습니다.');};d.append(save);d.showModal();
 }
 const hierarchyStyle=el('style');hierarchyStyle.textContent='.review-section-heading{margin:22px 0 9px!important;font-size:12px!important;font-weight:650!important;color:#466250!important}.review-subheading{margin:15px 0 6px 6px!important;font-size:12px!important;font-weight:600!important;color:#58685d!important}.review-subparagraph{margin-left:12px!important}.opinion p,#repairBody p{line-height:1.75;overflow-wrap:anywhere}.opinion p .evidence-sentence,#repairBody p .evidence-sentence{margin-bottom:0!important}.fixed-review-table-scroll{container-type:inline-size;width:100%;max-width:100%;min-width:0;margin:8px 0 20px}.fixed-review-table{display:table!important;box-sizing:border-box;border-collapse:collapse;width:100%!important;max-width:100%!important;margin-left:0!important;margin-right:0!important;min-width:0!important;table-layout:fixed;font-size:11px;line-height:1.3}.fixed-review-table th,.fixed-review-table td{border:1px solid #dce4d8;padding:3px 3px!important;white-space:normal!important;overflow-wrap:anywhere;min-width:0!important;text-align:right;font-variant-numeric:tabular-nums}.fixed-review-table th{background:#eef3eb;text-align:center}.fixed-review-table th:first-child,.fixed-review-table td:first-child{width:26%;text-align:left}.fixed-customer-table th:first-child,.fixed-customer-table td:first-child,.fixed-customer-table th:nth-child(4),.fixed-customer-table td:nth-child(4){width:23%;text-align:left}.fixed-customer-table th:first-child,.fixed-customer-table td:first-child,.fixed-customer-table th:nth-child(4),.fixed-customer-table td:nth-child(4){width:24%}.fixed-customer-table th:nth-child(2),.fixed-customer-table td:nth-child(2),.fixed-customer-table th:nth-child(5),.fixed-customer-table td:nth-child(5){width:16%}.fixed-customer-table th:nth-child(3),.fixed-customer-table td:nth-child(3),.fixed-customer-table th:nth-child(6),.fixed-customer-table td:nth-child(6){width:10%}.fixed-industry-line{display:block;white-space:nowrap}.fixed-header-line{display:block;white-space:nowrap;overflow-wrap:normal}.fixed-label-line{display:block;white-space:nowrap;overflow-wrap:normal}.fixed-review-table td:first-child{word-break:keep-all;overflow-wrap:normal}.fixed-customer-table td:not(:first-child):not(:nth-child(4)){white-space:nowrap!important;overflow-wrap:normal}.fixed-review-table caption{text-align:left;font-size:11px;color:#6b7d62;margin-bottom:6px}.fixed-table-title{font-weight:600}.fixed-table-unit{float:right;margin-left:8px;font-size:10px;font-weight:400}@media(max-width:520px){.fixed-review-table{font-size:10px}.fixed-review-table th,.fixed-review-table td{padding:2px 2px!important}}.fixed-review-table.fixed-cols-4:not(.fixed-customer-table) th:not(:first-child),.fixed-review-table.fixed-cols-4:not(.fixed-customer-table) td:not(:first-child){width:24.666666666666668%!important}.fixed-review-table.fixed-cols-5:not(.fixed-customer-table) th:not(:first-child),.fixed-review-table.fixed-cols-5:not(.fixed-customer-table) td:not(:first-child){width:18.5%!important}.fixed-review-table.fixed-cols-6:not(.fixed-customer-table) th:not(:first-child),.fixed-review-table.fixed-cols-6:not(.fixed-customer-table) td:not(:first-child){width:14.8%!important}.fixed-review-table.fixed-cols-7:not(.fixed-customer-table) th:not(:first-child),.fixed-review-table.fixed-cols-7:not(.fixed-customer-table) td:not(:first-child){width:12.333333333333334%!important}@container(min-width:650px){.fixed-industry-line{display:inline}.fixed-header-line,.fixed-label-line{display:inline;white-space:normal}.fixed-header-line+.fixed-header-line:before{content:" "}.fixed-label-line+.fixed-label-line:before{content:" "}}.fixed-review-table th{ text-align:center!important;vertical-align:middle}.fixed-review-table td{vertical-align:middle}.fixed-review-table td:first-child,.fixed-customer-table td:nth-child(4){text-align:center!important}.fixed-customer-table td:first-child,.fixed-customer-table td:nth-child(4){white-space:normal!important;word-break:normal!important;overflow-wrap:anywhere!important}.fixed-customer-table td:first-child span,.fixed-customer-table td:nth-child(4) span{white-space:normal!important;overflow-wrap:anywhere!important}.review-lead-paragraph{font-weight:600;margin-bottom:7px!important}.review-detail-paragraph{margin:5px 0 9px 16px!important;padding-left:9px;border-left:0;font-weight:400;line-height:1.7}.review-detail-paragraph+.review-lead-paragraph{margin-top:20px!important}.review-hanging-paragraph{padding-left:1.35em!important;text-indent:-1.35em!important}.review-hanging-paragraph .evidence-sentence{ text-indent:0}.review-hanging-paragraph .evidence-open{text-indent:0}.review-hanging-paragraph.review-detail-paragraph{padding-left:1.7em!important;text-indent:-1.15em!important}.review-third-paragraph{margin:5px 0 9px 32px!important;padding-left:1.35em!important;text-indent:-1.35em!important;font-weight:400;line-height:1.7}.review-note-paragraph{margin:8px 0 12px 12px!important;padding-left:1.35em!important;text-indent:-1.35em!important;font-weight:400;color:#687663;font-size:12px;line-height:1.7}.review-marked-paragraph{position:relative;padding-left:1.3em!important;text-indent:0!important}.review-paragraph-marker{position:absolute;left:0;top:3px;width:1.3em;text-align:left;font-weight:400}.review-paragraph-content{display:block;text-indent:0!important}.review-detail-paragraph{border-left:0!important;margin:5px 0 8px 16px!important}.review-hanging-paragraph.review-detail-paragraph{padding-left:1.3em!important;text-indent:0!important}.review-third-paragraph{padding-left:1.3em!important;text-indent:0!important}.review-lead-paragraph{font-weight:600;margin-top:16px!important;margin-bottom:7px!important}.review-detail-paragraph,.review-third-paragraph,.review-note-paragraph{border:0!important;box-shadow:none!important}.review-subparagraph{margin-left:0!important}.review-subheading{margin-left:0!important}.review-lead-paragraph{font-weight:400!important}.opinion p:not(.selected),#repairBody p:not(.selected){border-left:0!important;border-inline-start:0!important;box-shadow:none!important}.review-detail-paragraph{border-left:0!important;border-radius:0!important}#opinion p,#repairBody p,.opinion-stream-preview p,.opinion-stream-body{font-family:inherit!important;font-size:13px!important;font-weight:400!important;line-height:1.75!important;letter-spacing:0!important}#opinion p span,#repairBody p span,.opinion-stream-preview p span{font-size:inherit!important;font-weight:inherit!important;line-height:inherit!important;letter-spacing:inherit!important}#opinion p strong,#opinion p b,#repairBody p strong,#repairBody p b{font-size:inherit!important;line-height:inherit!important}#opinion .review-paragraph-marker,#repairBody .review-paragraph-marker{font-size:13px!important;font-weight:400!important}#opinion p:not(.selected),#repairBody p:not(.selected){border:0!important;box-shadow:none!important}.review-detail-paragraph,.review-third-paragraph,.review-note-paragraph{font-size:13px!important;font-weight:400!important;line-height:1.75!important;border-radius:0!important}.review-section-heading,.review-subheading{font-size:12px!important;line-height:1.6!important}.opinion-stream-body{font-size:13px!important;line-height:1.75!important;letter-spacing:0!important}.aggregate-title{font-weight:650!important}.aggregate-title[data-view-id]~.aggregate-title[data-view-id]{border-top:1px solid #dce4d8;padding-top:22px!important;margin-top:26px!important}';document.head.append(hierarchyStyle);window.CreditReviewHierarchyCSS=hierarchyStyle.textContent;

 const gapMaterials={financial_accounts:'비교 재무제표, 계정별 명세서, 매출채권 연령분석표, 재고자산 명세서, 추정 재무제표와 산출 근거',profitability:'비교 손익계산서, 제조원가명세서, 금융비용 명세서, 동업계 비교자료, 추정 손익 산출 근거',financial_stability:'재무상태표, 재무비율 산출표, 차입금 명세서, 매출채권·재고자산 명세서, 동업계 비교자료',cashflow_repayment:'현금흐름표, 차입금 만기·상환 일정, 이자 지급내역, 자금수지 계획과 추정 근거',customer_concentration:'기간별 매출처 원장, 거래처별 매출액·비중, 주요 계약서와 수주잔고',summary_2:'최신 신용조사서, 재무자료, 사업계획 및 주요 위험 관련 자료',report:'최신 신용조사서, 재무자료, 차입금·담보 명세서, 사업계획'};
 function localGapsFor(index){
  const prepared=preparedGapGuidance(index);
  if(prepared.length)return prepared.flatMap(g=>g.needed_contents.map((need,i)=>({id:g.view+':'+i,view:g.view,title:g.title,need,explanation:g.explanation})));
  const data=CreditReview.reviewData(),ids=CreditReview.viewIds;
  const sections=index===0?ids.slice(1,6).map(id=>data.views?.[id]):index===7?data.report?.sections||[]:[data.views?.[ids[index]]];
  const gaps=[];
  if(index===7)for(const need of data.report?.refinement?.remaining_gaps||[])gaps.push({need,materials:''});
  for(const section of sections.filter(Boolean)){
   for(const need of section.refinement?.remaining_gaps||[])gaps.push({need,materials:''});
   for(const table of section.tables||[])for(const row of table.rows||[]){const missing=row.map((v,i)=>v==null||String(v).trim()===''||['—','확인 불가','미제공'].includes(String(v))?i:-1).filter(i=>i>0);if(missing.length)gaps.push({need:row[0]+' — '+missing.map(i=>table.columns[i]?.name||table.columns[i]).join(', ')+' 값 미확인',materials:gapMaterials[ids[index]]||'해당 기간의 원문 재무자료와 계정·비율 산출 명세'});}
   for(const p of section.paragraphs||[]){if(/미제공|미확인|확인.{0,8}필요|자료.{0,8}부족|판단.{0,8}(어려|제한)|확인.{0,8}불가/.test(p.text||''))gaps.push({need:p.text,materials:gapMaterials[ids[index]]||'해당 사항을 확인할 원문 자료와 산출 근거'});}
  }
  return gaps.filter((g,i,a)=>a.findIndex(x=>x.need===g.need)===i).map(g=>({...g,view:index,title:reviewLabels[index]}));
 }
 const coverageViews=[[6,7],[5,6,7],[1,2],[1,3],[4],[7]];
 const coverageMaterials=['신용조사서, 법인등기부, 주주명부, 경영진 현황','사업계획서, 시장·경쟁 현황, 주요 계약서 및 수주잔고','비교 손익계산서, 제조원가명세서, 금융비용 명세서','비교 재무상태표, 재무비율 산출표, 차입금·계정별 명세서','현금흐름표, 차입금 만기·상환계획, 자금수지 계획','담보 명세서, 감정평가서, 등기부, 보증 및 선순위 내역'];
 function gapsFor(index){
  if(preparedGapGuidance(index).length)return localGapsFor(index);
  const indices=index===0?[1,2,3,4,5]:[index];
  const rows=companies[currentCompany].coverageAssessment||[];
  const gaps=rows.flatMap(group=>group.flatMap(item=>(item.gaps||[]).filter(g=>indices.includes(g.view))));
  return gaps.filter((g,i,a)=>a.findIndex(x=>x.view===g.view&&x.need===g.need)===i);
 }
 function explainMissingInformation(needs){
  if(!needs.length)return '최종 검토본에 남은 추가 확인사항이 없습니다.';
  return [...new Set(needs.map(need=>{
   if(/신청|금액|상환방식|담보조건/.test(need)&&/여신|기간|상환|담보/.test(need))return '본 건의 신청금액·기간·상환방식·담보조건이 충분히 확인되지 않아, 신청 조건에 맞춰 상환계획과 채권보전의 적정성을 판단하는 데 한계가 있습니다.';
   if(/재무|지표/.test(need)&&/산출|근거/.test(need))return '재무지표의 세부 산출 근거가 충분히 확인되지 않아, 기간별 지표가 같은 기준으로 계산됐는지 대조하기 어렵습니다.';
   return need.replace(/[.。]$/,'')+'에 대한 확인이 부족합니다.';
  }))].join(' ');
 }
 function preparedGapGuidance(index){
  const data=CreditReview.reviewData(),ids=CreditReview.viewIds,views=index===0?[1,2,3,4,5]:[index];
  return views.flatMap(view=>{
   const section=view===7?data.report:data.views?.[ids[view]],review=section?.refinement;
   const guidance=review?.information_guidance||(review?.remaining_gaps?.length?{explanation:review.remaining_gaps.join(' '),needed_contents:review.remaining_gaps}:null);
   const history=/수정하였|수정했|정정하였|정정했|보완하였|발견되어\s*수정|발견하여\s*정정/;const explanation=history.test(guidance?.explanation||'')||/^(?:최종 검토본에서 )?추가 확인이 필요한 내용은 아래와 같습니다[.]?$/.test((guidance?.explanation||'').trim())?explainMissingInformation(guidance?.needed_contents||[]):guidance?.explanation;return guidance?[{...guidance,explanation,view,title:reviewLabels[view]}]:[];
  });
 }
 function openGaps(index,selectedGaps=null,selectedTitle=null){
  const d=makeDialog((selectedTitle||reviewLabels[index])+' · 추가 정보 안내');d.classList.add('information-guidance-dialog');
  const prepared=preparedGapGuidance(index);
  if(!prepared.length){d.append(el('p','이전 생성본에는 사전 검토 안내가 저장되어 있지 않습니다. 다시 생성하면 본문 작성 후 검토 단계에서 안내까지 준비됩니다.'));}
  else{
   const descriptions=[...new Set(prepared.map(result=>result.explanation).filter(Boolean))];
   d.append(el('h3','부족한 정보'),el('p',descriptions.join(' ')));
   const needed=[...new Set(prepared.flatMap(result=>result.needed_contents||[]))];
   if(needed.length){const list=el('ol');needed.forEach(text=>list.append(el('li',text)));d.append(el('h3','보완이 필요한 내용'),list);}
  }
  d.showModal();
 }
 const guidanceStyle=el('style');guidanceStyle.textContent='.information-guidance-dialog p,.information-guidance-dialog li{font-family:inherit!important;font-size:13px!important;font-weight:400!important;line-height:1.75!important;letter-spacing:0!important}.information-guidance-dialog h3{font-size:13px!important;line-height:1.6!important;margin:16px 0 8px}.information-guidance-dialog ol{padding-left:22px;margin:8px 0}.information-guidance-dialog p{margin:8px 0}';document.head.append(guidanceStyle);
 let gapGenerationStarting=false;
 function gapAssessmentReady(){const run=CreditReview.generationState();return !gapGenerationStarting&&(!run||run.status==='completed');}
 window.addEventListener('credit-review:generation-state',event=>{gapGenerationStarting=event.detail.running;refreshCoverage();paintGapButtons();});
 function paintGapButtons(){
  if(!gapAssessmentReady()){
   document.querySelectorAll('.review-gap-button').forEach(b=>b.remove());
   operatingFrames.get(currentCompany)?.contentDocument?.querySelectorAll('.review-gap-button').forEach(b=>b.remove());return;
  }
  assessCoverage();
  const attach=(doc,selector)=>doc?.querySelectorAll(selector).forEach(heading=>{
   const index=heading.dataset.viewId?CreditReview.viewIds.indexOf(heading.dataset.viewId):activeReview;
   const count=gapsFor(index).length;let button=heading.querySelector('.review-gap-button');
   if(!count){button?.remove();return;}if(!button){button=doc.createElement('button');button.type='button';button.className='review-gap-button';button.innerHTML='<svg width="15" height="15" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 3h14v10H8l-5 4V3Z" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6 6h8M6 9h5" stroke="currentColor"/></svg>';button.style.cssText='display:inline-flex;box-sizing:border-box;width:19px;height:16px;line-height:1;vertical-align:baseline;align-items:center;justify-content:center;margin-left:8px;padding:0;border:0;background:transparent;color:#a37c39;cursor:pointer';heading.append(button);}button.title='부족한 정보 및 추가 자료 '+count+'건';button.setAttribute('aria-label',button.title);button.onclick=e=>{e.preventDefault();e.stopPropagation();openGaps(index);};
  });
  document.querySelectorAll('#opinion .aggregate-title .review-gap-button').forEach(b=>b.remove());const frameDoc=operatingFrames.get(currentCompany)?.contentDocument;frameDoc?.querySelectorAll('#repairBody .aggregate-title .review-gap-button').forEach(b=>b.remove());attach(document,'.heading h1');attach(frameDoc,'.repair-title-row h1');
 }

 const queries=[
  [/설립|업체명|법인명/,/주주|지분/,/대표|경영진/,/연혁|설립/,/계속기업|지속성|경영/],
  [/사업|제품/,/시장|수요/,/경쟁|점유율|기술/,/매출처|고객|거래처/,/수주|계약|매출/],
  [/매출액|매출 추이/,/영업이익/,/원가|매출원가/,/비경상|손상|일회성/,/수익성|이익 지속|영업이익/],
  [/자본|부채비율/,/차입|의존도/,/매출채권|재고|자산의 질/,/유동|현금성/,/우발|지급보증/],
  [/만기|상환계획/,/투자.*조달|투자.*재원/,/현금흐름|CF|현금창출/,/차입금/,/이자|금융비용/],
  [/담보/,/감정|담보.*평가/,/선순위|근저당/,/보증/,/회수가능|회수 가능/]
 ];
 const categoryPrimaryViews=[6,5,2,3,4,7];
 function categoryReviews(category){
  const matches=text=>queries[category].some(query=>query.test(text||''));
  const reviews=[];
  for(let view=1;view<=7;view++){
   const prepared=preparedGapGuidance(view);
   if(prepared.length){
    for(const guidance of prepared){
     const needed=guidance.needed_contents.filter(matches);
     const relevant=needed.length||matches(guidance.explanation)||view===categoryPrimaryViews[category];
     if(!relevant)continue;
     reviews.push({view,title:reviewLabels[view],explanation:guidance.explanation,needed:needed.length?needed:guidance.needed_contents});
    }
   }else{
    const needs=localGapsFor(view).filter(g=>matches(g.need)).map(g=>g.need);
    if(needs.length)reviews.push({view,title:reviewLabels[view],explanation:'',needed:[...new Set(needs)]});
   }
  }
  return reviews;
 }
 let assessmentSignature='';
 function assessCoverage(){
  if(!gapAssessmentReady())return;
  const data=CreditReview.reviewData();if(!data.report&&!Object.keys(data.views||{}).length)return;
  const signature=JSON.stringify([companies[currentCompany].id,data]);if(signature===assessmentSignature)return;assessmentSignature=signature;
  const rows=categories.map((category,i)=>{
   const reviews=categoryReviews(i),gaps=reviews.flatMap(review=>review.needed.map(need=>({view:review.view,title:review.title,need,explanation:review.explanation})));
   return [{name:category[0],status:gaps.length?'missing':preparedGapGuidance(categoryPrimaryViews[i]).length?'confirmed':'partial',gaps,reviews,paragraph_ids:[]}];
  });
  companies[currentCompany].coverageAssessment=rows;
  companies[currentCompany].coverage=rows.map(r=>[r[0].status==='confirmed']);
  refreshCoverage();CreditReview.saveLocal().catch(()=>{});
 }
 const refreshBase=refreshCoverage;refreshCoverage=()=>{refreshBase();const rows=companies[currentCompany].coverageAssessment||[];
  let missingTotal=0;
  $('grid').querySelectorAll('button').forEach((b,i)=>{
   const items=rows[i]||[],gaps=items.flatMap(item=>item.gaps||[]),hasGaps=gaps.length>0;
   const needsReview=!gapAssessmentReady()||!items.length||items.some(item=>item.status!=='confirmed');
   const label=!gapAssessmentReady()?'검토 중':hasGaps?'보완 필요':needsReview?'검토 필요':'보완사항 없음';
   if(needsReview)missingTotal++;
   b.classList.toggle('bad',needsReview);b.classList.remove('partial','unanalysed');b.querySelector('small').textContent=label;
   b.querySelector('.badge').hidden=!needsReview;b.querySelector('.badge').textContent=needsReview?'!':'';b.querySelector('.badge').title=label;
   b.setAttribute('aria-label',categories[i][0]+' · '+label);
  });
  const finalized=gapAssessmentReady();$('coverageCount').hidden=!finalized;$('coverageCount').textContent=finalized?String(missingTotal):'';$('honeyBtn').title=finalized?(missingTotal?'6개 검토항목 중 검토·보완 필요 '+missingTotal+'개':'6개 검토항목 모두 검토 완료 · 보완사항 없음'):'검토 결과 집계 전';$('honeyBtn').setAttribute('aria-label',$('honeyBtn').title);$('coverageCount').classList.toggle('complete',finalized&&missingTotal===0);
 };
 const detailBase=showDetail;showDetail=i=>{
  detailBase(i);assessCoverage();$('items').replaceChildren();$('items').classList.add('category-review-list');
  const reviews=companies[currentCompany].coverageAssessment?.[i]?.[0]?.reviews||categoryReviews(i);
  if(!reviews.length){const empty=el('li','저장된 관련 검토 내용이 없습니다.');empty.className='category-review-empty';$('items').append(empty);return;}
  for(const review of reviews){
   const item=el('li');item.className='category-review-part';item.append(el('h4',review.title));
   if(review.explanation)item.append(el('p',review.explanation));
   if(review.needed.length){const list=el('ul');review.needed.forEach(need=>list.append(el('li',need)));item.append(list);}
   $('items').append(item);
  }
 };
 const categoryStyle=el('style');categoryStyle.textContent='#coverageCount[hidden]{display:none!important}#items.category-review-list{list-style:none;padding:0;margin:0}#items.category-review-list>.category-review-part{display:block;margin:0;padding:14px 0;border:0;border-bottom:1px solid #dce4d8}#items.category-review-list>.category-review-part:last-child{border-bottom:0}#items.category-review-list h4{font-size:12px;line-height:1.6;margin:0 0 8px;color:#466250}#items.category-review-list p,#items.category-review-list ul>li{font-size:13px;line-height:1.75;margin:6px 0;padding:0;border:0}#items.category-review-list ul{padding-left:16px;margin:8px 0 0;list-style:disc}#items.category-review-list .category-review-empty{font-size:13px;padding:12px 0;border:0}';document.head.append(categoryStyle);

 const handler=e=>{const button=e.target.closest('.evidence-open,.sentence-analysis-open');if(!button||editing)return;if(e.type==='keydown'&&!['Enter',' '].includes(e.key))return;e.preventDefault();e.stopImmediatePropagation();const span=button.closest('.evidence-sentence');(button.classList.contains('sentence-analysis-open')?openSentenceAnalysis:openEvidence)(button.closest('p').dataset.paragraphId,span?.textContent||'');};
 document.addEventListener('click',handler,true);document.addEventListener('keydown',handler,true);
 const evidenceCSS=el('style');evidenceCSS.textContent='.evidence-open{display:inline-block;vertical-align:baseline;width:auto;min-width:25px;height:17px;padding:0 4px!important;margin-left:4px;border:1px solid #d6dfd2!important;border-radius:4px!important;background:#f5f8f2!important;color:#75856e;cursor:pointer;line-height:15px;font-size:9px;font-weight:400;white-space:nowrap}.evidence-open:before{content:"근거";font-size:9px}.evidence-open:hover,.evidence-open:focus-visible{color:#345942;outline:1px solid #a9bda5;border-radius:3px}.required-document-reviews{margin:18px 0;font-size:12px;line-height:1.7;color:#697765}.required-document-reviews>div{padding:6px 0}';document.head.append(evidenceCSS);
 window.CreditReviewPresentation={openEvidence,openSentenceAnalysis,renderAnalysisChatEntry,assessCoverage,paintGapButtons,systemSettings};
 const css=el('style');css.textContent='.evidence-sentence{display:inline;white-space:normal;margin:0;cursor:pointer}.evidence-sentence:hover{background:#f0f5ef}.opinion p{white-space:pre-wrap}.review-dialog{width:min(960px,94vw);max-height:90dvh;overflow:auto;border:1px solid #d7dfd5;border-radius:12px;padding:20px;background:white;color:#303734}.review-dialog::backdrop{background:#17261e66}.review-dialog header{display:flex;align-items:center;justify-content:space-between}.review-dialog h2{font-size:17px;margin:0}.review-dialog header button{font-size:24px}.review-dialog>p{font-size:13px;line-height:1.7;white-space:pre-wrap}.review-dialog button{padding:8px 12px;border-radius:6px;background:#eef3ed}.evidence-large-view{box-sizing:border-box;width:96vw;max-width:1600px;height:94vh;max-height:94vh;border:1px solid #d7dfd5;border-radius:10px;padding:14px;overflow:auto;background:white}.evidence-large-view>button{position:sticky;top:0;display:block;margin:0 0 10px auto;padding:7px 12px;background:#eef3ed;border:0;border-radius:5px}.evidence-large-view>img{display:block;max-width:none;width:auto;min-width:100%;height:auto}.evidence-image{width:100%;height:auto;display:block;border:1px solid #eee}.evidence-nav{display:flex;align-items:center;justify-content:space-between;margin:12px 0}.system-prompt-editor{display:block;width:100%;height:50vh;min-height:240px;max-height:none;resize:vertical;border:1px solid #d7dfd5;margin:14px 0;padding:12px;background:#fff;font-size:13px}.review-dialog select{width:100%;padding:8px}.hex.partial:before{background:#f3e8cd}.hex.partial small{color:#8b7029}.coverage-count{min-width:25px!important;width:auto!important}';document.head.append(css);
 const b=el('button','시스템 프롬프트 설정');b.onclick=()=>{closePanels();systemSettings();};$('menu').prepend(b);
 CreditReview.ready.then(()=>{const data=CreditReview.reviewData();if(data.report)CreditReview.loadReport(data.report,data.views);});
})();

(()=>{const s=document.createElement("style");s.textContent=".fixed-review-table.report-template-table th,.fixed-review-table.report-template-table td{width:auto!important;padding:6px 7px!important;line-height:1.5;word-break:normal;overflow-wrap:anywhere}.fixed-review-table.report-template-table caption{line-height:1.5;margin-bottom:7px}.report-template-table .fixed-table-unit{white-space:nowrap}.summary-topic-heading{margin:24px 0 10px!important;font-weight:700!important;color:#344f40!important}.summary-subheading{margin:14px 0 7px 8px!important;font-weight:600!important;color:#58685d!important}.fixed-review-table.summary2-fixed-wide{min-width:760px!important}.summary2-fixed-scroll{overflow-x:auto}.fixed-review-table.report-template-table td.report-cell-text{text-align:left!important}.fixed-review-table.report-template-table td.report-cell-number{text-align:right!important}.fixed-review-table.report-template-table td.report-cell-label{text-align:center!important}@media(max-width:520px){.fixed-review-table.report-template-table th,.fixed-review-table.report-template-table td{padding:4px!important}}";document.head.append(s);window.CreditReviewHierarchyCSS=(window.CreditReviewHierarchyCSS||'')+s.textContent})();
