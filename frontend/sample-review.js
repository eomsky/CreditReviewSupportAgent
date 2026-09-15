/* Import the delivered draft once. Regeneration requires a real configured service. */
(() => {
  'use strict';
  const bundle=JSON.parse(document.getElementById('sample-review-data').textContent);
  const download=(name,data)=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  window.sampleReviewReady=(async()=>{
    await CreditReview.ready;
    const existing=CreditReview.snapshot().companies.some(c=>c.id===bundle.case.id);
    if(!existing){await CreditReview.loadCase(bundle.case);await CreditReview.installPromptPack(bundle.prompts);}
    else await CreditReview.loadCase({id:bundle.case.id});
    const menu=document.getElementById('menu');
    const add=(label,action)=>{const b=document.createElement('button');b.textContent=label;b.onclick=()=>{closePanels();action();};menu.append(b);};
    add('첨부 샘플 원문 보기',()=>{
      const dialog=document.createElement('dialog');dialog.style.cssText='width:min(900px,90vw);max-height:85vh;overflow:auto;border:1px solid #cad3c8;border-radius:12px;padding:20px';
      const title=document.createElement('h3');title.textContent='첨부 원문 1~6/7쪽';dialog.append(title);
      const close=document.createElement('button');close.textContent='닫기';close.onclick=()=>dialog.close();dialog.append(close);
      for(const source of bundle.sources){const p=document.createElement('p');p.textContent=source.name+' · '+source.page+'/7쪽';const img=document.createElement('img');img.src=source.data;img.alt=p.textContent;img.style.cssText='display:block;max-width:100%;height:auto';dialog.append(p,img);}
      dialog.onclose=()=>dialog.remove();(document.fullscreenElement||document.body).append(dialog);dialog.showModal();
    });
    add('생성 초안 JSON 다운로드',()=>download('sample-review.json',bundle.case));
    add('현재 작업 JSON 다운로드',()=>download('credit-review-workspace.json',CreditReview.snapshot()));
    add('현재 항목별 프롬프트 다운로드',()=>download('generation-prompts.json',CreditReview.generationPrompts()));
    add('생성 근거 및 연결 상태',()=>notify('첨부 1~6쪽을 읽고 작성한 검토용 초안입니다. 실시간 AI 서버는 미연결이며 재생성에는 서버 연결이 필요합니다.'));
    CreditReview.frame.navigate(0);
    window.sampleReviewInfo={caseId:bundle.case.id,viewCount:Object.keys(bundle.case.views).length,sourceCount:bundle.sources.length};
    return window.sampleReviewInfo;
  })().catch(error=>{notify('샘플 초안 불러오기 실패: '+error.message);throw error;});
})();
