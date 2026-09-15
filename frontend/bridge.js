/* Connection layer: the original DOM/CSS remains the visual template. */
(() => {
  'use strict';
  const VIEW_IDS = ['summary_1','financial_accounts','profitability','financial_stability','cashflow_repayment','customer_concentration','summary_2','report'];
  const legacyChatKey=currentChatKey;
  currentChatKey=()=>legacyChatKey()+(reviseMode?':revise':'');
  const clone = value => structuredClone(value);
  const uid = () => crypto.randomUUID();
  const records = new Map();
  let systemPrompts={},systemPrompt=null,reviewLevel=0,reportFontSize=13;
  function mergeSystemPrompts(pack){
    // Preserve legacy instructions, removing only identical repeated paragraphs.
    const seen=new Set(),parts=[];
    for(const id of VIEW_IDS){
      for(const part of String(pack[id]||'').split(/\n\s*\n/)){
        const text=part.trim();if(text&&!seen.has(text)){seen.add(text);parts.push(text);}
      }
    }
    return parts.join('\n\n');
  }
  const systemForView=i=>systemPrompt?systemPrompt+'\n\n이번 작성 대상: '+reviewLabels[i]+'. 본문 중 해당 대상에 적용되는 지침을 사용하고 요청된 항목만 작성한다.':'';
  let transport = null, busy = false, restoring = false, timer, db, persistChain = Promise.resolve();
  let chatThinking=false,chatStreamText='',eventUrl=null;
  const connection = {state:'disconnected', error:null};
  const node = (tag, text, cls) => {const el=document.createElement(tag); if(text!=null)el.textContent=String(text);if(cls)el.className=cls;return el;};
  const currentId = () => companies[currentCompany].id ||= uid();
  const record = () => {const id=currentId();if(!records.has(id))records.set(id,{id,revision:null,report:null,audit:[],documents:[],run:null});return records.get(id);};
  companies.forEach(c=>c.id ||= uid());

  // Never deserialize executable markup from a server, backup, or rich paste.
  function safeHTML(html) {
    const doc=new DOMParser().parseFromString(String(html||''),'text/html');
    const allowed=new Set(['P','DIV','SPAN','BUTTON','DETAILS','SUMMARY','H1','H2','H3','H4','STRONG','EM','B','I','BR','UL','OL','LI','TABLE','COLGROUP','COL','CAPTION','THEAD','TBODY','TR','TH','TD','SUP','A']);
    const walk=root=>Array.from(root.children).forEach(el=>{
      if(!allowed.has(el.tagName)){el.remove();return;}
      for(const attr of [...el.attributes]){
        const keep=(el.tagName==='COL'&&attr.name==='width'&&/^\d+(?:\.\d+)?%$/.test(attr.value)&&parseFloat(attr.value)>0&&parseFloat(attr.value)<=100)||['class','type','aria-label','contenteditable','data-paragraph-id','data-table-key','data-view-id','data-source-id','data-sentence-index','data-original-caption','colspan','rowspan','scope','title','tabindex','role'].includes(attr.name);
        if(!keep)el.removeAttribute(attr.name);
      }
      walk(el);
    });walk(doc.body);return doc.body.innerHTML;
  }
  function evidenceSentences(text){
    const clean=String(text).replace(/[▹▸▻]/g,'▷').replace(/↗/g,'').replace(/([.!?。])\s*\/+(?=\s|$)/g,'$1').replace(/^\s*\/+\s*$/gm,'').replace(/[ \t]+/g,' ').trim();
    const parts=typeof Intl.Segmenter==='function'?[...new Intl.Segmenter('ko',{granularity:'sentence'}).segment(clean)].map(s=>s.segment):[clean];
    const result=[];
    let prefix='';
    for(const part of parts){if(!part.trim())continue;if(/^\s*(?:[가-하]|\d{1,2})[.)]\s*$/.test(part)){prefix+=part;continue;}if(!/[\p{L}\p{N}]/u.test(part)){if(result.length)result[result.length-1]+=part;continue;}result.push(prefix+part);prefix='';}
    if(prefix&&result.length)result[result.length-1]+=prefix;
    return result;
  }
  function withoutRepeatedHeading(text,heading){
    const label=String(heading||'').trim().replace(/^(?:[가-하]|\d+)[.)]\s*/,'');
    if(!label)return text;
    const escaped=label.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    return String(text).replace(new RegExp('^\\s*(?:[·○☞]\\s*)?(?:(?:[가-하]|\\d+)[.)]\\s*)?'+escaped+'\\s*[:：]\\s*'),'');
  }
  function formatTableNumber(value){
    const text=String(value).trim();
    if(!/^[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(text))return value;
    const [integer,decimal]=text.replace(/,/g,'').split('.');
    return integer.replace(/\B(?=(\d{3})+(?!\d))/g,',')+(decimal===undefined?'':'.'+decimal);
  }
  function formatFixedTable(table){
    const header=[...table.querySelectorAll('thead tr:first-child th')].map(x=>x.textContent.trim());
    const firstDataRow=table.querySelector('tbody tr');
    if(firstDataRow){const cells=[...firstDataRow.cells].map(x=>x.textContent.trim());if(cells.length===header.length&&cells.length>1&&['','.',header[0]].includes(cells[0])&&cells.slice(1).every((v,i)=>v===header[i+1]))firstDataRow.classList.add('duplicate-header-row');}
    for(const name of [...table.classList])if(/^fixed-cols-/.test(name))table.classList.remove(name);table.classList.add('fixed-cols-'+table.querySelectorAll('thead tr:first-child th').length);
    table.querySelectorAll('tbody td').forEach(cell=>{cell.textContent=formatTableNumber(cell.textContent);});
    table.querySelectorAll('thead th').forEach(th=>{if(th.textContent.replace(/\s/g,'')==='동업계평균')th.replaceChildren(node('span','동업계','fixed-industry-line'),node('span','평균','fixed-industry-line'));});
    const labelLines={
      '영업활동으로인한현금흐름':['영업활동으로','인한 현금흐름'],
      '투자활동으로인한현금흐름':['투자활동으로','인한 현금흐름'],
      '재무활동으로인한현금흐름':['재무활동으로','인한 현금흐름'],
      '기말현금및현금성자산':['기말 현금 및','현금성자산'],
      '감가상각비(제조원가명세서+손익계산서)':['감가상각비','(제조원가명세서','+손익계산서)'],
      '유동성장기부채상환후CF':['유동성장기부채','상환후 CF'],
      '비유동장기적합률':['비유동장기','적합률'],
      '(평균)매출채권/매출액':['(평균)매출채권','/매출액'],
      '(평균)재고자산/매출액':['(평균)재고자산','/매출액'],
      '영업활동후의CF':['영업활동후의','CF'],
      '이자지급후의CF':['이자지급후의','CF'],
      'EBITDA/금융비용':['EBITDA','/금융비용']
    };
    table.querySelectorAll('tbody tr td:first-child').forEach(cell=>{
      const lines=labelLines[cell.textContent.replace(/\s/g,'')];
      if(lines)cell.replaceChildren(...lines.map(text=>node('span',text,'fixed-label-line')));
    });

    let caption=table.querySelector('caption');if(!caption){caption=node('caption');table.prepend(caption);}
    let unit=caption.querySelector('.fixed-table-unit')?.textContent||((caption.textContent.match(/단위\s*:\s*([^)]*)/)||[])[1]||'').trim();
    if(/^(해당 없음|없음|—|-)$/.test(unit))unit='';
    const original=table.dataset.originalCaption||caption.querySelector('.fixed-table-title')?.textContent||caption.textContent;
    table.dataset.originalCaption=original;
    const first=table.querySelector('th')?.textContent||'';
    const cashflow=[...table.querySelectorAll('tbody tr td:first-child')].some(c=>c.textContent.replace(/\s/g,'')==='영업활동으로인한현금흐름');
    let title=cashflow?'현금흐름표':first.includes('매출처')?(original==='현황 및 향후 전망'?'주요 매출처 및 매출비중 변동 추이':original.replace(/\s*\(단위:[^)]*\)/g,'').replace(/^마\.\s*/,'')):original==='현황 및 향후 전망'||/[가나다라]\./.test(original)?'현황 및 향후 전망':original.replace(/\s*\(단위:[^)]*\)/g,'');
    if(/기업 기본|기업개요|기업 개요|사업 및 영업구조/.test(title))title=title.replace(/\s*·\s*(별도|연결)\s*,?\s*/,' · ');else title=title.replace(/(별도|연결)(?=\s*[,·]|\s*20)/g,'$1재무제표');title=title.replace(/(20\d{2})[-./](\d{2})(?!\d)/g,(_,y,m)=>y+'년 '+Number(m)+'월 기준').replace(/기준\s*기준/g,'기준');
    caption.replaceChildren(node('span',cashflow?'현금흐름표':first.includes('매출처')||title==='현황 및 향후 전망'?'현황 및 전망':title,'fixed-table-title'),node('span',unit?'(단위 : '+unit.replace(/^\(?\s*단위\s*:\s*/,'').replace(/\)\s*$/,'').trim()+')':'','fixed-table-unit'));
    table.classList.toggle('fixed-customer-table',!!table.querySelector('th')?.textContent.includes('매출처'));
    if(first.includes('매출처')){
      table.querySelectorAll('thead th').forEach((th,index)=>{
        const text=th.textContent.replace(/\s+/g,' ').trim();
        const parts=index===0||index===3?text.match(/^(.*?)\s*(\([^)]*\))$/):index===1||index===4?text.match(/^(.*?)\s*(금액)$/):null;
        if(parts)th.replaceChildren(node('span',parts[1].trim(),'fixed-header-line'),node('span',parts[2],'fixed-header-line'));
      });
      table.querySelectorAll('tbody tr').forEach(row=>[2,5].forEach(index=>{
        const cell=row.children[index];if(!cell)return;const text=cell.textContent.replace(/,/g,'').trim();
        if(/^[+-]?\d+(?:\.\d+)?$/.test(text))cell.textContent=Number(text).toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1});
      }));
    }

  }
  function normalizeSummaryHierarchy(box){
    const headings=[...box.querySelectorAll('.section-title')];
    if(!headings.some(n=>/^1\.\s*업체개요/.test(n.textContent.trim()))||!headings.some(n=>/^2\.\s*경영현황/.test(n.textContent.trim())))return;
    headings.forEach(h=>{
      const parts=h.textContent.trim().split(/\s*·\s*/);const topic=/^(평가 개요|[1-6]\.\s*(업체개요|경영현황|지배구조|영업현황|우발적 재무위험|종합의견))/.test(parts[0]);
      h.classList.remove('review-subheading','review-section-heading');h.classList.add(topic?'summary-topic-heading':'summary-subheading');
      if(topic){h.textContent=parts.shift();if(parts.length){const sub=node('h4',parts.join(' · ').replace(/^[가-하][.)]\s*/,''),'section-title summary-subheading');h.after(sub);}}
      else h.textContent=h.textContent.replace(/^[가-하][.)]\s*/,'');
    });
    box.querySelectorAll('p .evidence-sentence:first-child').forEach(span=>{
      const first=span.firstChild;if(first?.nodeType!==3)return;
      const match=first.textContent.match(/^[가-하][.)]\s*([^:：]{1,30})[:：]\s*/);
      if(match){const p=span.closest('p'),label=match[1].trim();if(p.previousElementSibling?.textContent.trim()!==label)p.before(node('h4',label,'section-title summary-subheading'));first.textContent=first.textContent.slice(match[0].length);}
    });
  }
  function identify(html) {
    const box=node('div');box.innerHTML=safeHTML(html);normalizeSummaryHierarchy(box);box.querySelectorAll('.review-gap-button').forEach(b=>b.remove());box.querySelectorAll('table').forEach(t=>{if((t.caption?.textContent||'').includes('표 근거 확인')&&t.textContent.includes('표 작성 근거'))t.closest('.fixed-review-table-scroll')?.remove()||t.remove();});box.querySelectorAll('.fixed-review-table').forEach(formatFixedTable);
    // Refresh citation layout in saved HTML without replacing edited paragraph text.
    box.querySelectorAll('p').forEach(p=>{
      if(!p.querySelector('.evidence-sentence')||p.querySelector('table,.inline-revision'))return;
      const content=p.cloneNode(true);content.querySelectorAll('.evidence-open,.sentence-analysis-open').forEach(b=>b.remove());const heading=p.previousElementSibling?.matches('.section-title')?p.previousElementSibling.textContent:'';const text=withoutRepeatedHeading(content.textContent.trim(),heading);
      if(!text)return;
      const sentences=evidenceSentences(text);
      p.replaceChildren();sentences.forEach((sentence,k)=>{const span=node('span',sentence.trimEnd(),'evidence-sentence');span.dataset.sentenceIndex=String(k);const button=node('button',null,'evidence-open');button.type='button';button.contentEditable='false';button.setAttribute('aria-label','원문 근거 보기');button.title='원문 근거 보기';span.append(button);p.append(span,document.createTextNode(' '));});
    });
    box.querySelectorAll('p').forEach(p=>{
      if(!p.querySelector('.evidence-sentence'))return;
      const text=p.textContent,parts=text.split(/(?=[○◯▷☞※])|\n(?=\s*-\s)/).map(t=>t.trim()).filter(Boolean);
      if(parts.length<2)return;
      const fragment=document.createDocumentFragment(),base=p.dataset.paragraphId||uid();
      parts.forEach((part,index)=>{
        const row=node('p');row.dataset.paragraphId=index?base+'::part'+index:base;
        row.className=/^☞/.test(part)?'review-third-paragraph':/^(?:▷|-\s)/.test(part)?'review-detail-paragraph':p.className;

        evidenceSentences(part).forEach(sentence=>{const span=node('span',sentence.trim(),'evidence-sentence'),button=node('button',null,'evidence-open');button.type='button';button.contentEditable='false';button.setAttribute('aria-label','원문 근거 보기');button.title='원문 근거 보기';span.append(button);row.append(span,document.createTextNode(' '));});fragment.append(row);
      });p.replaceWith(fragment);
    });
    box.querySelectorAll('p').forEach(p=>{
      const walker=document.createTreeWalker(p,NodeFilter.SHOW_TEXT);let first;while(first=walker.nextNode())if(first.textContent.trim())break;
      if(first)first.textContent=first.textContent.replace(/^(\s*)([▷◯○]|-(?=\s))/,(_,space,marker)=>space+(/[▷-]/.test(marker)?'☞':'·'));
      p.classList.remove('review-subparagraph','review-lead-paragraph','review-marked-paragraph');
      const text=p.textContent.trim();p.classList.toggle('review-hanging-paragraph',/^(?:[○·]|☞|-\s)/.test(text));p.classList.toggle('review-detail-paragraph',/^☞/.test(text));p.classList.remove('review-third-paragraph');p.classList.toggle('review-note-paragraph',/^※/.test(text));
    });
    box.querySelectorAll('p').forEach(p=>{
      const walker=document.createTreeWalker(p,NodeFilter.SHOW_TEXT);let first;while(first=walker.nextNode())if(first.textContent.trim())break;
      const match=first?.textContent.match(/^\s*([○·☞※]|-(?=\s))\s*/);if(!match)return;
      first.textContent=first.textContent.slice(match[0].length);const content=node('span',null,'review-paragraph-content');content.append(...p.childNodes);p.append(node('span',match[1]+' ','review-paragraph-marker'),content);p.classList.add('review-marked-paragraph');
    });
    const seen=new Set();box.querySelectorAll('p').forEach(p=>{if(!p.dataset.paragraphId||seen.has(p.dataset.paragraphId))p.dataset.paragraphId=uid();seen.add(p.dataset.paragraphId);});
    box.querySelectorAll('.sentence-analysis-open').forEach(b=>b.remove());
    box.querySelectorAll('.evidence-open').forEach(b=>{const wand=node('button',null,'sentence-analysis-open');wand.type='button';wand.contentEditable='false';wand.title='이 문장 분석';wand.setAttribute('aria-label','이 문장 분석');wand.innerHTML='<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m4 16 9-9 3 3-9 9ZM11 9l3 3M5 2v4M3 4h4M15 1v4M13 3h4M16 13v4M14 15h4"/></svg>';b.after(wand);});
    return box.innerHTML;
  }
  combinedReview = () => [1,2,3,4,5].filter(i=>reviewStates[i].html.trim()).map(i=>{
    const title=node('h2',reviewLabels[i],'aggregate-title');title.dataset.viewId=VIEW_IDS[i];title.setAttribute('role','button');title.tabIndex=0;title.title='이 항목 전체에 대해 대화';return title.outerHTML+reviewStates[i].html;
  }).join('');
  syncRevisionState = () => {
    const html=identify(cleanOpinion());
    if(activeReview===0){
      const box=node('div');box.innerHTML=html;let index=null,part=node('div');
      const flush=()=>{if(index!=null)reviewStates[index]={html:part.innerHTML,status:'수정본'};part=node('div');};
      [...box.children].forEach(el=>{if(el.matches('.aggregate-title')){flush();index=VIEW_IDS.indexOf(el.dataset.viewId);if(index<1||index>5)index=null;}else part.append(el);});flush();
    }else reviewStates[activeReview]={html,status:$('status').textContent};
    reviewStates[0].html=combinedReview();schedule();
  };
  function capture() {
    if(editing){reviewStates[activeReview]={html:identify(cleanOpinion()),status:'수정본'};}
    else if(activeReview!==0)reviewStates[activeReview]={html:identify(cleanOpinion()),status:$('status').textContent};
    reviewStates[0].html=combinedReview();stashEntries();captureCompany();
    return {schema_version:1,active_case_id:currentId(),companies:clone(companies),records:clone([...records]),
      scoped:clone([...scopedEntries]),chats:clone([...chatThreads]),drafts:clone([...chatDrafts]),
      histories:clone([...revisionHistories]),outlines:clone([...reportOutlines]),review_level:reviewLevel,report_font_size:reportFontSize,common_prompt:commonUserPrompt,system_prompts:clone(systemPrompts),system_prompt:systemPrompt};
  }
  function status() {
    document.querySelectorAll('.demo').forEach(el=>el.textContent=busy?'처리 중':transport?'AI 연결 설정됨':'AI 미연결');
    $('send').disabled=busy||!$('prompt').value.trim();
    window.dispatchEvent(new CustomEvent('credit-review:connection',{detail:{...connection,busy}}));
  }
  function schedule(){if(restoring)return;clearTimeout(timer);timer=setTimeout(()=>saveLocal().catch(()=>{}),350);}
  async function saveLocal(){
    const state=capture();
    persistChain=persistChain.catch(()=>{}).then(async()=>{
      const database=await db;
      await new Promise((resolve,reject)=>{const tx=database.transaction('state','readwrite');tx.objectStore('state').put(state,'workspace');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});
    });
    try{await persistChain;}catch(error){connection.error='브라우저 저장 실패';notify('저장하지 못했습니다. 브라우저 저장 공간을 확인해 주세요.');throw error;}
  }
  function restore(snapshot){
    if(snapshot?.schema_version!==1||!Array.isArray(snapshot.companies)||!snapshot.companies.length)throw Error('지원하지 않는 작업 데이터입니다.');
    restoring=true;
    try{
      companies.splice(0,companies.length,...clone(snapshot.companies));
      companies.forEach(c=>{c.id ||= uid();if(c.state)Object.values(c.state.reviews).forEach(v=>v.html=identify(v.html));});
      for(const [map,values] of [[records,snapshot.records],[scopedEntries,snapshot.scoped],[chatThreads,snapshot.chats],[chatDrafts,snapshot.drafts],[revisionHistories,snapshot.histories],[reportOutlines,snapshot.outlines]]){map.clear();for(const entry of values||[])map.set(...clone(entry));}
      for(const messages of chatThreads.values())for(const message of messages)if(message.supplementControl&&message.text==='기존 대화이력은 삭제되었습니다.')message.text='기존 대화이력은 미반영 처리 되었습니다.';
      for(const history of revisionHistories.values())for(const entry of history.items||[])entry.html=safeHTML(entry.html);
      commonUserPrompt=snapshot.common_prompt||'';
      reviewLevel=[0,1,2].includes(snapshot.review_level)?snapshot.review_level:0;
      reportFontSize=Number.isInteger(snapshot.report_font_size)&&snapshot.report_font_size>=12&&snapshot.report_font_size<=18?snapshot.report_font_size:13;window.dispatchEvent(new Event('credit-review:font-size'));
      systemPrompts=clone(snapshot.system_prompts||{});
      systemPrompt=typeof snapshot.system_prompt==='string'?snapshot.system_prompt:Object.keys(systemPrompts).length?mergeSystemPrompts(systemPrompts):null;
      currentCompany=Math.max(0,companies.findIndex(c=>c.id===snapshot.active_case_id));
      const c=companies[currentCompany],s=c.state||emptyCompanyState();
      localFiles=s.files||[];Object.keys(reviewStates).forEach(k=>reviewStates[k]={...s.reviews[k]});activeReview=s.active||0;
      $('companyName').textContent=c.name;$('companyName').title=c.name;restoreEntries();restoreChatDraft();renderCurrent();
    }finally{restoring=false;}
  }
  function renderCurrent(){
    $('opinion').innerHTML=identify(reviewStates[activeReview].html);$('status').textContent=reviewStates[activeReview].status;
    document.querySelector('.heading h1').textContent=reviewLabels[activeReview];$('emptyReview').hidden=!!$('opinion').textContent.trim();
    reviewLabels.forEach((_,i)=>$('review_'+i).setAttribute('aria-pressed',String(i===activeReview)));
    updateFileCount();updateEntryCounts();refreshCoverage();renderChat();showRevisionNav();renderFrame();status();window.CreditReviewPresentation?.paintGapButtons();window.CreditReviewMenu?.syncStream();
  }
  function context(){return {case_id:currentId(),company_name:companies[currentCompany].name,run_id:record().run?.id||null,view_id:VIEW_IDS[activeReview],base_revision:record().revision};}
  function generationPrompts(){
    stashEntries();
    return Object.fromEntries(VIEW_IDS.map((id,i)=>[id,[
      ...(systemPrompt?[{text:systemForView(i),kind:'system'}]:[]),
      ...clone(scopedEntries.get(currentCompany+':'+i)?.prompts||[]),
      {kind:'system',text:window.CreditReviewWritingRules}
    ]]));
  }
  async function request(operation,payload){
    if(!transport)throw Error('AI 서버가 연결되지 않았습니다. 연결 후 다시 요청해 주세요.');
    const result=await transport(operation,clone(payload));return result;
  }
  function configure(options={}){
    if(options.transport){if(typeof options.transport!=='function')throw Error('transport must be a function');transport=options.transport;}
    else {
      const base=new URL(options.baseUrl||'/api/credit-review/v1/',location.href);
      if(!['http:','https:'].includes(base.protocol)||base.origin!==location.origin)throw Error('동일 출처의 API 주소를 사용해 주세요.');
      transport=async(operation,payload)=>{
        const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),operation==='chat'?115000:options.timeoutMs||120000);
        try{
          const headers={'X-Request-ID':uid()};let body;
          if(operation==='upload'&&payload.file instanceof Blob){body=new FormData();body.append('file',payload.file,payload.name);const metadata={...payload};delete metadata.file;body.append('metadata',JSON.stringify(metadata));}
          else{headers['Content-Type']='application/json';body=JSON.stringify(payload);}
          if(payload.base_revision!=null)headers['If-Match']=String(payload.base_revision);
          const response=await fetch(new URL(operation,base.href.replace(/\/?$/,'/')),{method:'POST',credentials:'same-origin',headers,body,signal:controller.signal});
          eventUrl=new URL('events',base.href.replace(/\/?$/,'/')).href;
          if(response.status===409||response.status===412){const detail=await response.json().catch(()=>({}));throw Error(detail.error&&detail.error!=='Revision conflict'?detail.error:'서버에 더 최신 수정본이 있습니다. 다시 불러온 뒤 작업해 주세요.');}
          if(!response.ok){const detail=await response.json().catch(()=>({}));throw Error(detail.error||'서버 요청 실패 ('+response.status+')');}
          if(operation==='chat'&&response.headers.get('content-type')?.includes('text/event-stream'))return await readReviewStream(response,(kind,data)=>{if(kind==='delta'){chatStreamText+=data.text;renderChat();renderFrame();}});
          return response.status===204?{}:await response.json();
        }finally{clearTimeout(timeout);}
      };
    }
    connection.state='configured';connection.error=null;status();renderFrame();return window.CreditReview;
  }
  function paragraphs(){return [...$('opinion').querySelectorAll('p')];}
  function supplementRequest(index){
    const rows=chatThreads.get(currentCompany+':'+index+':revise')||[];
    const boundary=rows.findLastIndex(m=>m.supplementControl);
    const initial=boundary>=0?rows[boundary].requestText||'':'';
    const requests=rows.slice(boundary+1).filter(m=>m.role==='user').map(m=>{
      const selected=(m.selected_paragraphs||[]).map(p=>typeof p==='string'?p:p.text).filter(Boolean).join(' / ');
      return (selected?'대상: '+selected+'\n':'')+m.text;
    });
    return [initial,...requests].filter(Boolean).join('\n\n').trim();
  }
  function addMessage(message,key=currentChatKey()){const list=chatThreads.get(key)||[];list.push({id:uid(),createdAt:new Date().toISOString(),mode:key.endsWith(':revise')?'revise':'chat',...message});chatThreads.set(key,list);renderChat();schedule();}
  const renderChatBase=renderChat;
  renderChat=()=>{renderChatBase();const messages=chatThreads.get(currentChatKey())||[];$('chatMessages').querySelectorAll('.chat-message').forEach((row,i)=>{if(messages[i]?.sentenceAnalysisKey)window.CreditReviewPresentation?.renderAnalysisChatEntry(row,messages[i]);});$('chatMessages').querySelectorAll('.chat-message.assistant p').forEach(p=>p.textContent=window.CreditReviewDisplayText(p.textContent));$('chatMessages').querySelectorAll('.chat-thinking,.chat-streaming').forEach(n=>n.remove());$('chatMessages').setAttribute('aria-busy',String(chatThinking));if(chatThinking){const row=node('div',window.CreditReviewDisplayText(chatStreamText)||'생각 중…',chatStreamText?'chat-streaming':'chat-thinking');row.setAttribute('role','status');row.setAttribute('aria-live','polite');$('chatMessages').append(row);$('chatMessages').scrollTop=$('chatMessages').scrollHeight;}};
  function askRevision(row,apply){addRevisionChoices(row,apply);}
  async function submit(text,ids=[]){
    if(busy||editing){notify('진행 중인 작업을 먼저 완료해 주세요.');return;}
    text=String(text||'').trim();if(!text)return;
    chatDrafts.set(currentChatKey(),'');$('prompt').value='';
    const ctx=context(),chatKey=currentChatKey(),all=paragraphs();
    const targets=ids.length?all.filter(p=>ids.includes(p.dataset.paragraphId)):[];
    const originals=targets.map(p=>({id:p.dataset.paragraphId,text:p.textContent}));
    // A question about changes is not a request to change the report.
    const intent=reviseMode?'revise':'chat';
    const allHistory=clone(chatThreads.get(chatKey)||[]);const boundary=allHistory.findLastIndex(m=>m.supplementControl);const history=(boundary<0?allHistory:[...(allHistory[boundary].requestText?[{role:'user',text:allHistory[boundary].requestText}]:[]),...allHistory.slice(boundary+1)]).slice(-10);
    const scope=originals.length?'선택 문구'+(originals.length>1?' '+originals.length+'개':'')+' · '+originals.map(p=>p.text).join(' / '):null;
    addMessage({role:'user',text,scope,selected_paragraphs:clone(originals)},chatKey);
    if(!transport){addMessage({role:'assistant',text:'AI 미연결 상태입니다. 연결 후 다시 요청해 주세요. 의견은 변경하지 않았습니다.'});renderFrame();return;}
    const perform=async()=>{
      if(ctx.case_id!==currentId()||ctx.view_id!==VIEW_IDS[activeReview]){notify('해당 항목에서 다시 요청해 주세요.');return;}
      if(originals.some(o=>!paragraphs().some(p=>p.dataset.paragraphId===o.id&&p.textContent===o.text))){notify('의견이 변경되었습니다. 다시 요청해 주세요.');return;}
      busy=true;chatThinking=true;chatStreamText='';renderChat();status();renderFrame();
      const before=identify(cleanOpinion());
      try{
        const result=await request('chat',{...ctx,mode:intent,request:text,paragraphs:originals,history,attachments:window.CreditReviewChatAttachments?.current()||[]});
        if(ctx.case_id!==currentId()||ctx.view_id!==VIEW_IDS[activeReview]||identify(cleanOpinion())!==before)throw Error('요청 이후 의견이 변경되어 응답을 적용하지 않았습니다.');
        if(intent==='revise'){
          if(!Array.isArray(result.replacements))throw Error('보완 응답 형식이 올바르지 않습니다.');
          const seen=new Set();for(const r of result.replacements){if(!originals.some(o=>o.id===r.id)||seen.has(r.id)||typeof r.text!=='string'||!r.text.trim())throw Error('보완 응답 문장 ID가 올바르지 않습니다.');seen.add(r.id);}
          result.replacements.forEach(r=>{paragraphs().find(p=>p.dataset.paragraphId===r.id).textContent=r.text;});
          $('status').textContent='보완본';syncRevisionState();
          const h=revisionHistories.get(revisionKey())||{items:[{html:before}],index:0};h.items.push({html:cleanOpinion()});h.index=h.items.length-1;revisionHistories.set(revisionKey(),h);
        }else if(typeof result.message!=='string')throw Error('대화 응답 형식이 올바르지 않습니다.');
        if(result.revision!=null)record().revision=result.revision;
        addMessage({role:'assistant',completed:true,text:result.message||(intent==='revise'?'의견을 보완했습니다.':'')},chatKey);
        connection.state='connected';
      }catch(error){connection.error=error.message;addMessage({role:'assistant',text:error.message},chatKey);}
      finally{busy=false;chatThinking=false;chatStreamText='';renderChat();status();clearSelection();renderCurrent();renderFrame();await saveLocal().catch(()=>{});}
    };
    if(intent==='revise'){
      if(!targets.length){addMessage({role:'assistant',text:'보완할 의견이 없습니다.'});renderFrame();return;}
      addMessage({role:'assistant',text:'선택한 의견에 보완을 반영할까요?'});
      const attach=()=>{const row=$('chatMessages').lastElementChild;appendRevisionTargetList(row,originals.map(o=>o.text),text);askRevision(row,yes=>{pending=null;if(yes)perform();else{addMessage({role:'assistant',text:'반영하지 않았습니다.'});renderFrame();}});};
      pending={ctx,text,originals,perform};attach();renderFrame();
    }else await perform();
  }
  let pending=null;
  $('form').onsubmit=e=>{e.preventDefault();const text=$('prompt').value;const ids=selectedInOrder().map(p=>p.dataset.paragraphId);$('prompt').value='';submit(text,ids);};
  showRevisionNav=()=>{
    $('revisionNav').hidden=true;$('opinion').querySelectorAll('.inline-revision').forEach(el=>el.remove());
    const h=revisionHistories.get(revisionKey());if(!h)return;
    paragraphs().forEach(p=>{
      const variants=[];for(const entry of h.items){const box=node('div');box.innerHTML=safeHTML(entry.html);const old=[...box.querySelectorAll('p')].find(q=>q.dataset.paragraphId===p.dataset.paragraphId);if(old&&variants.at(-1)!==old.textContent)variants.push(old.textContent);}
      let index=variants.lastIndexOf(p.textContent);if(index<0||variants.length<2)return;
      const bar=node('div',null,'inline-revision');bar.contentEditable='false';
      for(const [label,delta] of [['<',-1],['>',1]]){const b=node('button',label);b.setAttribute('aria-label',delta<0?'이 문구의 이전 버전':'이 문구의 다음 버전');b.disabled=busy||editing||index+delta<0||index+delta>=variants.length;b.onclick=()=>{p.textContent=variants[index+delta];syncRevisionState();showRevisionNav();schedule();};bar.append(b);}p.before(bar);
    });positionRevisionControls();
  };
  const oldSwitch=switchReview;switchReview=i=>{if(busy||editing){notify('진행 중인 작업을 먼저 완료해 주세요.');return;}pending=null;if(i!==activeReview)window.CreditReview.setMode('chat');oldSwitch(i);$('opinion').innerHTML=identify(reviewStates[i].html);renderFrame();window.CreditReviewPresentation?.paintGapButtons();window.CreditReviewMenu?.syncStream();schedule();};
  const oldCompany=selectCompany;selectCompany=i=>{if(busy||editing){notify('진행 중인 작업을 먼저 완료해 주세요.');return;}pending=null;if(i!==currentCompany)window.CreditReview.setMode('chat');oldCompany(i);currentId();renderCurrent();schedule();};
  const oldEdit=$('edit').onclick;$('edit').onclick=()=>{if(busy)return;oldEdit();if(!editing){syncRevisionState();renderCurrent();}schedule();};
  $('opinion').addEventListener('paste',event=>{if(!editing)return;event.preventDefault();document.execCommand('insertText',false,event.clipboardData.getData('text/plain'));});

  function renderBlocks(section,summary2=false){
    const box=node('div'),tables=section.tables||[],used=new Set(),headings=new Set();let inSubsection=false;let lastTopic='';
    const table=t=>{if(t.needs_evidence||t.template_id==='evidence_status')return;const el=node('table');el.dataset.tableKey=String(section.paragraphs?.[0]?.id||section.title||'table')+'::table-'+tables.indexOf(t);if(t.report_template)el.classList.add('report-template-table');if(t.summary2_fixed_table&&t.columns?.length>6)el.classList.add('summary2-fixed-wide');if(t.caption)el.append(node('caption',t.caption));if(t.column_widths?.length===t.columns?.length){const cols=node('colgroup');t.column_widths.forEach(width=>{const col=node('col');col.setAttribute('width',width+'%');cols.append(col);});el.append(cols);}const head=node('thead'),hr=node('tr');(t.columns||[]).forEach(c=>hr.append(node('th',typeof c==='object'?c.name:c)));head.append(hr);el.append(head);const body=node('tbody');(t.rows||[]).forEach(row=>{const tr=node('tr');row.forEach((v,i)=>{const td=node('td',v??'—');if(t.report_template){td.classList.add(typeof v==='number'?'report-cell-number':i===0?'report-cell-label':'report-cell-text');td.style.whiteSpace='normal';}tr.append(td);});body.append(tr);});el.append(body);if(t.fixed_template||t.report_template){el.classList.add('fixed-review-table');formatFixedTable(el);const wrap=node('div',null,'fixed-review-table-scroll');if(t.summary2_fixed_table&&t.columns?.length>6)wrap.classList.add('summary2-fixed-scroll');wrap.append(el);box.append(wrap);}else box.append(el);};
    const positioned=index=>tables.forEach((t,i)=>{if(t.after_paragraph_index===index){table(t);used.add(i);}});
    positioned(-1);
    (section.paragraphs||[]).forEach((p,i)=>{const heading=String(p.heading||'').replace(/\[\s*S\d+(?:\s*[,;]\s*S\d+)*\s*\]/g,'').trim(),key=heading.replace(/[\[\]\s○◯]/g,'');if(heading&&heading!==String(p.text||'').replace(/\[\s*S\d+(?:\s*[,;]\s*S\d+)*\s*\]/g,'').trim()&&!(['분석의견','특이사항'].includes(key)&&headings.has(key))){if(summary2){const parts=heading.split(/\s*·\s*/);const primary=p.topic_title||(/^(평가 개요|[1-6]\.\s*)/.test(parts[0])?parts.shift():'');if(primary&&primary!==lastTopic){box.append(node('h3',primary,'section-title summary-topic-heading'));lastTopic=primary;}const sub=(p.subheading!==undefined?p.subheading:parts.join(' · ')).replace(/^(?:[가-하]|\d+)[.)]\s*/,'');if(sub&&sub!==primary)box.append(node('h4',sub,'section-title summary-subheading'));}else{const primary=['특이사항','분석의견','확인필요','현황분석'].includes(key);inSubsection=!primary;box.append(node('div',heading.replace(/^[○◯]\s*/,''),primary?'section-title review-section-heading':'section-title review-subheading'));}headings.add(key);}const el=node('p');el.dataset.paragraphId=p.id||uid();
        const text=String(p.text||'').replace(/\[\s*S\d+(?:\s*[,;]\s*S\d+)*\s*\]/g,'').replace(/[\[(]\s*(?:[a-f0-9]{64}-)?p\d+-r\d+(?:\s*[,;]\s*(?:[a-f0-9]{64}-)?p\d+-r\d+)*\s*[\])]/gi,'').replace(/\[(?:[^\]\n]*(?:종합의견|Page|page|자료명|\.jpg|[pP]\.\s*\d|쪽)[^\]\n]*)\]/g,'').replace(/\[(?:[pP]\d+)\]/g,'').replace(/"\s*\}\s*[,\]]?\s*(?:\{|\],?)?/g,'').trim();
      const chunks=text.split(/\n\s*\n|(?=○|◯|▷|☞|※)|\n(?=\s*-\s)/).map(t=>t.replace(/\s*\n\s*/g,' ').trim()).filter(Boolean);
      chunks.forEach((text,j)=>{
        if(chunks.length>1&&j===0&&key&&text.replace(/[\[\]\s○◯]/g,'')===key)return;
        const row=node('p');row.dataset.paragraphId=(p.id||el.dataset.paragraphId)+(j?'::part'+j:'');
        const paragraphText=summary2?text.replace(/^[가-하][.)]\s*/, '').replace(/^[^:：]{1,24}[:：]\s*/,m=>{const label=m.replace(/[:：]\s*$/,'');return heading.includes(label)||p.subheading===label?'':m;}):text;const sentences=evidenceSentences(withoutRepeatedHeading(paragraphText,heading));sentences.forEach((sentence,k)=>{const span=node('span',sentence.trimEnd(),'evidence-sentence');span.dataset.sentenceIndex=String(k);const button=node('button',null,'evidence-open');button.type='button';button.contentEditable='false';button.setAttribute('aria-label','원문 근거 보기');button.title='원문 근거 보기';span.append(button);row.append(span,document.createTextNode(' '));});box.append(row);
      });positioned(i);});
    tables.forEach((t,i)=>{if(!used.has(i))table(t);});appendDocumentReviews(box,section.required_document_reviews);return box.innerHTML;
  }
  function appendDocumentReviews(){}
  function loadReport(report,views={}){
    if(busy||editing)throw Error('진행 중인 작업을 먼저 완료해 주세요.');
    if(report.case_id&&report.case_id!==currentId())throw Error('현재 심사건과 보고서 ID가 다릅니다.');
    record().report=clone(report);
    record().views=clone(views);
    const reportStatus='';
    const body=node('div');(report.sections||[]).forEach(s=>{body.append(node('h2',s.title,'aggregate-title'));const section=node('div');section.innerHTML=renderBlocks(s);body.append(section);});
    appendDocumentReviews(body,report.required_document_reviews);reviewStates[7]={html:body.innerHTML,status:body.innerHTML?reportStatus:'미작성'};
    for(const [viewId,section] of Object.entries(views)){const i=VIEW_IDS.indexOf(viewId);if(i<1||i>6)throw Error('알 수 없는 심사항목 ID: '+viewId);reviewStates[i]={html:renderBlocks(section,i===6),status:reportStatus};}
    reviewStates[0].html=combinedReview();reviewStates[0].status=reviewStates[0].html?reportStatus:'미작성';renderCurrent();window.CreditReviewPresentation?.assessCoverage();schedule();
  }
  // The child is only a presentation. No child network requests or independent storage.
  operatingPayload=()=>({view:activeReview,view_id:VIEW_IDS[activeReview],case_id:currentId(),company:companies[currentCompany].name,labels:reviewLabels,
    statuses:VIEW_IDS.map((_,i)=>reviewStates[i].status),
    mode:reviseMode?'revise':'chat',selectedIds:selectedInOrder().map(p=>p.dataset.paragraphId),selectionLabel:$('target').textContent,html:identify(reviewStates[activeReview].html),status:reviewStates[activeReview].status,busy,chatThinking,chatStreamText,connected:!!transport,
    chats:clone(chatThreads.get(currentChatKey())||[]),chatFiles:window.CreditReviewChatAttachments?.names()||[],draft:$('prompt').value,history:clone(revisionHistories.get(revisionKey())?.items||[]),notes:clone(noteLists.notes),prompts:clone(noteLists.prompts),files:localFiles.map(f=>({name:f.name,id:f.id})),
    audit:clone(record().audit),pending:pending&&pending.ctx.case_id===currentId()&&pending.ctx.view_id===VIEW_IDS[activeReview]?{text:pending.text,originals:pending.originals}:null});
  exportOperating=()=>{};
  function renderFrame(){if(!appWindow.classList.contains('operating-full'))return;operatingFrames.get(currentCompany)?.contentWindow?.operatingAdapter?.load(operatingPayload());}
  const entryPositionProperties=['position','left','right','top','bottom','width','height','max-height'];
  function clearEntryPosition(){const drawer=$('drawer');if(!drawer.dataset.entryAnchor)return;entryPositionProperties.forEach(key=>drawer.style.removeProperty(key));delete drawer.dataset.entryAnchor;}
  const closePanelsBeforeEntry=closePanels;closePanels=()=>{clearEntryPosition();return closePanelsBeforeEntry();};
  function openEntry(kind,index,anchor){
    if(busy)return;clearEntryPosition();openSidebarEntry(kind,index);
    if(!anchor||!appWindow.classList.contains('operating-full'))return;
    const drawer=$('drawer'),bounds=appWindow.getBoundingClientRect(),scale=bounds.width/appWindow.offsetWidth||1;
    const width=Math.min(320,appWindow.clientWidth-24),height=Math.min(460,appWindow.clientHeight-24);
    const left=Math.max(12,Math.min((anchor.right-bounds.left)/scale+8,appWindow.clientWidth-width-12));
    const top=Math.max(12,Math.min((anchor.top-bounds.top)/scale,appWindow.clientHeight-height-12));
    drawer.dataset.entryAnchor='true';for(const [key,value] of Object.entries({position:'absolute',left:left+'px',right:'auto',top:top+'px',bottom:'auto',width:width+'px',height:height+'px','max-height':height+'px'}))drawer.style.setProperty(key,value,'important');
  }
  window.CreditReview={
    setMode:mode=>{if(busy||pending){notify('진행 중인 요청을 먼저 완료해 주세요.');return;}const next=mode==='revise';if(next===reviseMode)return;storeChatDraft();reviseMode=next;restoreChatDraft();renderChat();status();window.dispatchEvent(new Event('credit-review:mode'));renderFrame();schedule();},getMode:()=>reviseMode?'revise':'chat',
    version:'0.1.66',viewIds:[...VIEW_IDS],configure,disconnect(){transport=null;connection.state='disconnected';status();renderFrame();},
    getReportFontSize:()=>reportFontSize,setReportFontSize:value=>{if(!Number.isInteger(value)||value<12||value>18)return;reportFontSize=value;schedule();window.dispatchEvent(new Event('credit-review:font-size'));},
    getReviewLevel:()=>reviewLevel,setReviewLevel:value=>{if(![0,1,2].includes(value))throw Error('검토 수준 오류');reviewLevel=value;schedule();},
    snapshot:capture,restore:async s=>{if(busy||editing)throw Error('작업 중에는 복원할 수 없습니다.');restore(s);await saveLocal();},
    supplementRequest,
    async saveSupplementRequest(index,text){
      if(busy||pending)throw Error('진행 중인 작업을 먼저 완료해 주세요.');
      text=String(text).trim();
      addMessage({role:'assistant',text:text?'보완 요청사항이 수정되었습니다.':'기존 대화이력은 미반영 처리 되었습니다.',supplementControl:true,requestText:text},currentCompany+':'+index+':revise');
      renderFrame();await saveLocal();
    },
    supplementation:()=>{const rows=chatThreads.get(currentCompany+':'+activeReview+':revise')||[];const last=rows.findLastIndex(m=>m.role==='assistant'&&m.completed);return last<0?[]:clone(rows.slice(0,last+1));},
    saveLocal,loadReport,generationPrompts,
    getSystemPrompt:()=>systemPrompt||'',
    async setSystemPrompt(text){systemPrompt=String(text);await saveLocal();},
    getSystemPrompts:()=>Object.fromEntries(VIEW_IDS.map(id=>[id,systemPrompt||''])),
    async setSystemPrompts(pack){systemPrompts=clone(pack);systemPrompt=mergeSystemPrompts(pack);await saveLocal();},
    async installSystemPromptPack(pack){
      stashEntries();
      const defaults=new Set(Object.values(pack));
      for(const scope of scopedEntries.values())scope.prompts=scope.prompts.filter(p=>!defaults.has(p.text));
      for(const [id,text] of Object.entries(pack))if(!(id in systemPrompts))systemPrompts[id]=text;
      if(systemPrompt===null)systemPrompt=mergeSystemPrompts(systemPrompts);
      restoreEntries();renderCurrent();await saveLocal();
    },
    evidenceFor(id){const sections=[...(record().report?.sections||[]),...Object.values(record().views||{})];return clone(sections.flatMap(s=>s.paragraphs||[]).find(p=>p.id===id||p.id===id.split('::part')[0])||null);},
    analyzeSentence:(id,sentence,title)=>request('sentence-analysis',{...context(),paragraph_id:id,sentence,review_title:title}),
    continueSentenceAnalysis({id,sentence,title,view,result,key}){
      if(busy||editing||pending){notify('진행 중인 요청을 먼저 완료해 주세요.');return false;}
      if(view!==activeReview)switchReview(view);window.CreditReview.setMode('chat');
      const lines=['심사항목: '+title,'선택 문장: '+sentence,'',result.summary];
      if(result.concept_steps?.length)lines.push('',result.concept_title||'판단 구조',result.concept_steps.join(' → '));
      if(result.comparisons?.length)lines.push('','핵심 수치',...result.comparisons.map(row=>row.metric+': '+row.value+' ('+row.basis+')'));
      lines.push('',result.evidence_assessment,result.reasoning);
      if(result.improvements?.length)lines.push('','※ 확인할 부분: '+result.improvements.join(' '));
      const rows=chatThreads.get(currentChatKey())||[];
      if(!rows.some(m=>m.sentenceAnalysisKey===key))addMessage({role:'assistant',completed:true,text:lines.filter(v=>v!=null).join('\n'),scope:'문장 분석에서 이어가기',sentenceAnalysisKey:key,sentenceAnalysis:{id,sentence,title,view,result:clone(result),key},selected_paragraphs:[{id,text:sentence}]});
      window.CreditReview.frame.select([id]);setChatOpen(true,'chat');renderChat();renderFrame();
      operatingFrames.get(currentCompany)?.contentDocument?.querySelector('.repair-layout')?.classList.remove('chat-hidden');
      const input=appWindow.classList.contains('operating-full')?operatingFrames.get(currentCompany)?.contentDocument?.getElementById('repairInput'):$('prompt');
      setTimeout(()=>input?.focus(),0);schedule();return true;
    },
    explainGaps:(index,candidates)=>request('information-gaps',{...context(),target_view:VIEW_IDS[index],candidates,documents:localFiles.filter(f=>f.server_id).map(f=>({id:f.server_id,name:f.name,priority:f.priority||'보통',required:!!f.required,description:f.description||''}))}),
    downloadDocument(ref){
      const name=ref.document_name||ref.label||'';
      const exact=localFiles.find(f=>ref.document_id&&(f.server_id===ref.document_id||f.id===ref.document_id));
      const matches=localFiles.filter(f=>f.name===name);
      const file=exact||(!ref.document_id&&matches.length===1?matches[0]:null);
      if(!(file?.file instanceof Blob))throw Error('다운로드할 원본 파일이 이 브라우저에 없습니다. 기초자료에 원본을 다시 첨부해 주세요.');
      const url=URL.createObjectURL(file.file),link=node('a');link.href=url;link.download=file.name||name||'첨부파일';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
    },
    generationState:()=>clone(record().run||null),
    reviewData:()=>clone({report:record().report,views:record().views}),
    async installPromptPack(pack){
      if(busy||editing)throw Error('진행 중인 작업을 먼저 완료해 주세요.');
      stashEntries();
      for(const [id,text] of Object.entries(pack)){
        const index=VIEW_IDS.indexOf(id);if(index<0||typeof text!=='string')throw Error('유효하지 않은 프롬프트입니다.');
        const key=currentCompany+':'+index;
        const scope=scopedEntries.get(key)||{notes:[],prompts:[],noteDraft:{text:'',index:null},promptDraft:{text:'',index:null}};
        if(!scope.prompts.some(p=>p.text===text))scope.prompts.push({text,created:Date.now()});
        scopedEntries.set(key,scope);
      }
      restoreEntries();renderCurrent();await saveLocal();
    },
    loadCase:async data=>{
      if(busy||editing)throw Error('진행 중인 작업을 먼저 완료해 주세요.');
      if(typeof data.id!=='string'||!data.id)throw Error('심사건 ID가 필요합니다.');
      let index=companies.findIndex(c=>c.id===data.id);
      if(index<0){companies.push({id:data.id,name:data.name||data.id,caseInfo:data.caseInfo||'',example:false,state:emptyCompanyState()});index=companies.length-1;}
      if(data.name)companies[index].name=companies[index].registrationName||data.name;
      if(index===currentCompany&&(!data.report||(JSON.stringify(record().report)===JSON.stringify(data.report)&&JSON.stringify(record().views||{})===JSON.stringify(data.views||{})))){
        for(const key of ['revision','documents','audit','run'])if(key in data)record()[key]=clone(data[key]);
        await saveLocal();return;
      }
      if(index!==currentCompany)selectCompany(index);$('companyName').textContent=companies[index].name;$('companyName').title=companies[index].name;for(const key of ['revision','documents','audit','run'])if(key in data)record()[key]=clone(data[key]);
      if(data.coverage)window.setReviewCoverage(data.coverage);
      if(data.report)loadReport(data.report,data.views);renderCurrent();await saveLocal();
    },
    submit,watchGeneration:listener=>{if(!eventUrl)return null;const url=new URL(eventUrl);url.searchParams.set('case_id',currentId());const source=new EventSource(url.href);source.addEventListener('progress',e=>listener(JSON.parse(e.data)));return source;},chatSettings:payload=>request('chat-settings',{...context(),...payload}),uploadChatFile:file=>request('upload',{...context(),name:file.name,file}),refreshChatFiles:()=>renderFrame(),
    cancelGeneration:()=>request('cancel',context()),
    async resetOpinions(){
      if(busy||editing||record().run?.status==='running')throw Error('진행 중인 생성·검토가 끝난 뒤 초기화해 주세요.');
      const ctx=context(),result=await request('reset-opinions',ctx);if(ctx.case_id!==currentId())return;
      pending=null;clearSelection();Object.assign(reviewStates,emptyCompanyState().reviews);
      await window.CreditReview.loadCase(result);renderCurrent();window.CreditReviewMenu?.syncStream();notify('의견을 초기화했습니다. 기초자료와 설정은 유지됩니다.');
    },
    async save(){await saveLocal();const ctx=context();const result=await request('save',{...ctx,workspace:capture()});if(ctx.case_id!==currentId())throw Error('심사건이 변경되어 저장 응답을 적용하지 않았습니다.');if(result.revision!=null)record().revision=result.revision;await saveLocal();return result;},
    async analyze(options={}){
      if(busy||editing)throw Error('진행 중인 작업을 먼저 완료해 주세요.');
      busy=true;status();renderFrame();const ctx=context();
      try{
        if(!localFiles.length)throw Error('의견을 생성하려면 기초자료를 먼저 첨부해 주세요.');
        const documents=[];for(const f of localFiles){f.id ||= uid();if(!f.server_id){if(!(f.file instanceof Blob))throw Error('원본 파일을 다시 첨부해 주세요: '+f.name);const uploaded=await request('upload',{...ctx,id:f.id,name:f.name,mime_type:f.file.type,file:f.file});if(!uploaded.document_id)throw Error('업로드 응답에 document_id가 없습니다.');f.server_id=uploaded.document_id;}documents.push({id:f.server_id,name:f.name,description:f.description||'',priority:f.priority||'보통',required:!!f.required});}
        const result=await request('analyze',{...ctx,documents,review_level:reviewLevel,outline:window.getCreditReviewReportOutline(),common_prompt:commonUserPrompt,generation_prompts:(()=>{const prompts=generationPrompts();for(const [id,text] of Object.entries(options.supplements||{})){if(VIEW_IDS.includes(id)&&String(text).trim())(prompts[id] ||= []).push({text:'사용자 보완 요청사항: 원문 근거를 검증하여 아래 요청을 반영한다. 근거 없는 사실은 만들지 않는다.\n'+text});}return prompts;})(),...(options.viewIds?{target_views:clone(options.viewIds)}:{})});
        if(ctx.case_id!==currentId())throw Error('심사건이 변경되었습니다.');record().run=result;notify('분석 요청을 접수했습니다.');schedule();return result;
      }finally{busy=false;status();renderFrame();schedule();}
    },
    async refresh(){const ctx=context(),selected=selectedInOrder().map(p=>({id:p.dataset.paragraphId,text:p.textContent})),result=await request('state',ctx);if(ctx.case_id!==currentId())throw Error('심사건이 변경되었습니다.');if(busy||editing)return result;await window.CreditReview.loadCase(result);if(ctx.view_id===VIEW_IDS[activeReview])window.CreditReview.frame.select(selected.filter(s=>paragraphs().some(p=>p.dataset.paragraphId===s.id&&p.textContent===s.text)).map(s=>s.id));return result;},
    frame:{discuss:i=>{if(busy||editing)return;switchReview(i);window.CreditReview.frame.select(paragraphs().map(p=>p.dataset.paragraphId));setChatOpen(true);renderFrame();$('prompt').focus();},navigate:i=>switchReview(i),submit,openEntry,openFiles:()=>$('rail_files').click(),openCompanies:()=>$('rail_companies').click(),
      draft:text=>{$('prompt').value=text;chatDrafts.set(currentChatKey(),text);schedule();},
      decide:yes=>{const p=pending;pending=null;if(yes&&p)return p.perform();else{addMessage({role:'assistant',text:'반영하지 않았습니다.'});renderFrame();}},
      select:ids=>{clearSelection();paragraphs().filter(p=>ids.includes(p.dataset.paragraphId)).forEach(p=>{selectedParagraphs.add(p);p.classList.add('selected');});updateSelectionLabel();},
      restoreParagraph:(id,text)=>{if(busy)return;const p=paragraphs().find(p=>p.dataset.paragraphId===id);if(p){p.textContent=text;syncRevisionState();renderCurrent();}},
      payload:()=>operatingPayload()}
  };
  const discussHeading=e=>{if(e.target.closest('.review-gap-button'))return;const h=e.target.closest('#opinion .aggregate-title,.heading h1');if(!h||editing)return;if(e.type==='keydown'&&!['Enter',' '].includes(e.key))return;const i=h.dataset.viewId?VIEW_IDS.indexOf(h.dataset.viewId):activeReview;if(i<1||i>5)return;e.preventDefault();e.stopImmediatePropagation();window.CreditReview.frame.discuss(i);};
  document.addEventListener('click',discussHeading,true);document.addEventListener('keydown',discussHeading,true);
  const heading=document.querySelector('.heading h1');heading.tabIndex=0;heading.setAttribute('role','button');heading.title='이 항목 전체에 대해 대화';
  const discussCSS=node('style');discussCSS.textContent='.aggregate-title,.heading h1{cursor:pointer}.aggregate-title:hover,.heading h1:hover{color:#53785b}.aggregate-title:focus-visible,.heading h1:focus-visible{outline:1px solid #8aa58b}';document.head.append(discussCSS);
  const menu=$('menu');
  for(const [label,action] of [['자료 분석 시작',()=>window.CreditReview.analyze()],['작업 저장',async()=>{await saveLocal();if(transport)await window.CreditReview.save();notify(transport?'작업을 저장했습니다.':'이 브라우저에 저장했습니다.');}],['분석 결과 불러오기',()=>window.CreditReview.refresh()],['금액 검수 결과',()=>{
    const dialog=node('dialog');dialog.style.cssText='max-width:600px;border:1px solid #dce4d8;border-radius:12px;padding:20px';dialog.append(node('h3','금액 검수 결과 — 보고서 미반영'));const findings=record().audit;dialog.append(node('p',findings.length?findings.length+'건':'검수 결과가 없습니다.'));findings.forEach(f=>dialog.append(node('p',[f.path,f.old,'→',f.new,f.reason].filter(Boolean).join(' '))));const b=node('button','닫기');b.onclick=()=>{dialog.close();dialog.remove();};dialog.append(b);document.body.append(dialog);dialog.showModal();
  }]]){const b=node('button',label);b.onclick=async()=>{closePanels();try{await action();}catch(e){notify(e.message);}};menu.append(b);}
  const uploadBarStyle=node('style');uploadBarStyle.textContent='.source-card{padding:8px 0}.source-tools{margin-top:3px;gap:5px}.source-tools .meta-btn{width:21px;min-width:21px;height:21px;padding:0 3px;font-size:10px;border-radius:4px}.source-tools .meta-btn svg{width:12px;height:12px}.source-card .source-selection-summary{margin-top:4px!important;font-size:10px!important} .source-upload-bar{padding:0 0 14px;margin:0 0 16px;border-bottom:1px solid #dce4d7}.source-upload-bar .source-add-button{font-size:11px;line-height:16px;padding:5px 9px;border-radius:5px;min-height:0;height:auto}';document.head.append(uploadBarStyle);
  const baseFileList=renderFileList;renderFileList=()=>{localFiles.forEach(f=>f.id ||= uid());baseFileList();$('drawerBody').querySelectorAll('.source-name').forEach((name,index)=>{const item=localFiles[index],link=node('a');link.textContent=item.name;link.href='#';link.className='source-name';link.title='다운로드';link.style.cssText='color:inherit;cursor:pointer;text-decoration:underline;text-underline-offset:3px';link.onclick=e=>{e.preventDefault();try{window.CreditReview.downloadDocument({document_id:item.server_id||item.id,document_name:item.name});}catch(error){notify(error.message);}};name.replaceWith(link);});const p=$('drawerBody').querySelector('.drawer-meta');if(p)p.textContent='신용조사서(필수), 관련 부속서류, 기타 참고자료를 첨부하세요';};
  const templateStyle=node('style');templateStyle.textContent='.source-upload-bar{display:flex;align-items:center;justify-content:space-between;gap:8px}.source-template-download{font-size:11px;line-height:16px;padding:5px 7px;border-radius:5px;white-space:nowrap}';document.head.append(templateStyle);
  const templateFileList=renderFileList;renderFileList=()=>{
    templateFileList();
    const bar=$('drawerBody').querySelector('.source-upload-bar');
    if(bar){
      const button=node('button');button.type='button';button.className='plain-action source-template-download';button.textContent='신용조사서 양식 다운로드';
      button.onclick=()=>{
        const bytes=Uint8Array.from(atob(window.CreditReviewTemplateData),c=>c.charCodeAt(0));
        const url=URL.createObjectURL(new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}));
        const link=node('a');link.href=url;link.download='양식_신용조사서.xlsx';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      };
      bar.append(button);
    }
  };
    const metadataFileList=renderFileList;renderFileList=()=>{localFiles.forEach(f=>{if(f.priority==='높음')f.priority='중요';});metadataFileList();const help=$('drawerBody').querySelector('.source-help');if(help)help.textContent='설명·우선순위·필수 여부는 업체별로 저장되며 분석에 반영됩니다.';};
    const priorDetail=showDetail;showDetail=i=>{priorDetail(i);$('items').querySelectorAll('em').forEach(n=>n.textContent=n.textContent.replace(' (예시)',''));};
  const oldRenderEntries=renderEntryList;renderEntryList=key=>{oldRenderEntries(key);const note=$('drawerBody').querySelector('.entry-footnote');if(note)note.textContent='이 브라우저에 자동 저장됩니다.';};
  // Prevent oversized or unsupported files from being accepted by the template handlers.
  document.addEventListener('change',e=>{if(e.target.type==='file'){const files=[...e.target.files];if(files.some(f=>! /\.(docx|pptx|hwp|hwpx|gif|bmp|tif|tiff|pdf|json|xlsx|xls|txt|csv|md|png|jpg|jpeg|webp)$/i.test(f.name)||f.size>200*1024*1024)){e.stopImmediatePropagation();e.target.value='';notify('PDF·Excel·텍스트·이미지 파일만 첨부할 수 있습니다. 파일당 최대 200MB입니다.');}}},true);
  document.addEventListener('input',schedule);document.addEventListener('change',schedule);document.addEventListener('click',()=>{schedule();setTimeout(status,0);});
  addEventListener('beforeunload',e=>{if(busy||editing){e.preventDefault();e.returnValue='';}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)saveLocal().catch(()=>{});});
  const style=node('style');style.textContent='.duplicate-header-row{display:none!important}.opinion table{border-collapse:collapse;display:block;overflow:auto;font-size:12px;max-width:100%;margin:12px 0}.opinion th,.opinion td{border:1px solid #dde4d9;padding:6px;text-align:left}.source-reference{font-size:11px;color:#72836a;margin:0 6px 10px}';document.head.append(style);
  db=new Promise((resolve,reject)=>{const r=indexedDB.open('credit-review-ui-0166',1);r.onupgradeneeded=()=>r.result.createObjectStore('state');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
  window.CreditReview.ready=(async()=>{
    restoring=true;
    try{const database=await db;const saved=await new Promise((resolve,reject)=>{const r=database.transaction('state').objectStore('state').get('workspace');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});if(saved)restore(saved);}
    catch(e){notify('자동 저장을 사용할 수 없습니다. 브라우저 저장 설정을 확인해 주세요.');}
    finally{restoring=false;status();}
    window.dispatchEvent(new CustomEvent('credit-review:ready'));return window.CreditReview;
  })();
})();
