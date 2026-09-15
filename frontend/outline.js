/* Editable report headings and descriptions, reordered with a drag handle. */
(() => {
 const defaults=['업체개요','사업성','수익성','재무안정','상환능력','채권보전','종합 심사의견'];
 const normalize=rows=>rows.map(x=>typeof x==='string'?{title:x,description:''}:{title:String(x.title||''),description:String(x.description||'')});
 window.getCreditReviewReportOutline=()=>normalize(reportOutlines.get(currentCompany)||defaults);
 let drag=null;
 const clearDrag=()=>{drag=null;$('reportOutlineRows').querySelectorAll('.outline-row').forEach(r=>r.classList.remove('dragging','drop-before','drop-after'));};
 const move=(from,to)=>{const [row]=reportOutlineDraft.splice(from,1);reportOutlineDraft.splice(to,0,row);renderReportOutlineRows();$('reportOutlineRows').children[to]?.querySelector('.outline-drag').focus();};
 renderReportOutlineRows=()=>{
  const box=$('reportOutlineRows');box.replaceChildren();
  reportOutlineDraft.forEach((item,index)=>{
   const row=document.createElement('div');row.className='outline-row';row.dataset.index=index;
   const handle=document.createElement('button');handle.textContent='⠿';handle.className='outline-drag';handle.type='button';handle.setAttribute('aria-label',`${index+1}. ${item.title||'새 항목'} 순서 이동`);handle.title='드래그하여 순서 변경 · 키보드 Alt+↑/↓';
   handle.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();handle.focus();handle.setPointerCapture(e.pointerId);drag={from:index,to:index,pointer:e.pointerId};row.classList.add('dragging');};
   handle.onpointermove=e=>{if(!drag)return;const rect=box.getBoundingClientRect();if(e.clientY<rect.top+28)box.scrollTop-=12;else if(e.clientY>rect.bottom-28)box.scrollTop+=12;const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('.outline-row');if(!target||!box.contains(target))return;const r=target.getBoundingClientRect(),after=e.clientY>r.top+r.height/2;let insertion=Number(target.dataset.index)+(after?1:0);if(insertion>drag.from)insertion--;drag.to=insertion;box.querySelectorAll('.outline-row').forEach(n=>n.classList.remove('drop-before','drop-after'));target.classList.add(after?'drop-after':'drop-before');};
   handle.onpointerup=()=>{if(!drag)return;const {from,to}=drag;clearDrag();if(from!==to)move(from,to);};handle.onpointercancel=clearDrag;handle.onlostpointercapture=clearDrag;
   handle.onkeydown=e=>{if(e.key==='Escape'){clearDrag();return;}if(e.altKey&&['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();const to=index+(e.key==='ArrowUp'?-1:1);if(to>=0&&to<reportOutlineDraft.length)move(index,to);}};
   const fields=document.createElement('div');fields.className='outline-fields';
   const nameLabel=document.createElement('label');nameLabel.textContent='목차명';const name=document.createElement('input');name.value=item.title;name.placeholder='목차명';name.oninput=()=>item.title=name.value;nameLabel.append(name);
   const descriptionLabel=document.createElement('label');descriptionLabel.textContent='설명';const description=document.createElement('textarea');description.value=item.description;description.placeholder='이 목차에서 다룰 내용과 작성 기준';description.oninput=()=>item.description=description.value;descriptionLabel.append(description);fields.append(nameLabel,descriptionLabel);
   const remove=document.createElement('button');remove.textContent='×';remove.className='outline-remove';remove.setAttribute('aria-label',`${item.title||'새 항목'} 삭제`);remove.onclick=()=>{reportOutlineDraft.splice(index,1);renderReportOutlineRows();};
   row.append(handle,fields,remove);box.append(row);
  });
 };
 $('reportOutlineOpen').onclick=()=>{closePanels();reportOutlineDraft=window.getCreditReviewReportOutline();renderReportOutlineRows();const dialog=$('reportOutlineDialog');(document.fullscreenElement||document.body).append(dialog);dialog.showModal();};
 $('reportOutlineAdd').onclick=()=>{reportOutlineDraft.push({title:'',description:''});renderReportOutlineRows();$('reportOutlineRows').lastElementChild.querySelector('input').focus();};
 $('reportOutlineSave').onclick=async()=>{const rows=reportOutlineDraft.map(x=>({title:x.title.trim(),description:x.description.trim()}));if(!rows.length||rows.some(x=>!x.title)){notify('목차명을 입력하세요.');[...$('reportOutlineRows').querySelectorAll('input')].find(x=>!x.value.trim())?.focus();return;}reportOutlines.set(currentCompany,rows);await CreditReview.saveLocal();$('reportOutlineDialog').close();notify('목차명·설명·순서를 저장했습니다.');};
 $('reportOutlineDialog').querySelector('.outline-help').textContent='손잡이를 드래그하여 순서를 바꿀 수 있습니다. 목차명과 설명은 보고서 생성에 반영됩니다.';
 const css=document.createElement('style');css.textContent='#reportOutlineDialog{width:min(620px,calc(100vw - 32px))}.outline-row{align-items:flex-start;padding:10px 0;border-bottom:1px solid #e4e9e1}.outline-fields{flex:1;min-width:0;display:grid;gap:8px}.outline-fields label{display:grid;gap:4px;font-size:11px;color:#76816f}.outline-fields input,.outline-fields textarea{width:100%;border:1px solid #dce4d8;border-radius:5px;padding:8px;font:inherit;font-size:13px;color:#354432;background:white}.outline-fields textarea{height:70px;min-height:60px;max-height:none;resize:vertical}#reportOutlineDialog .outline-drag{touch-action:none;cursor:grab;border:0;background:transparent;padding:8px 5px;margin-top:18px;font-size:21px}#reportOutlineDialog .outline-drag:active{cursor:grabbing}#reportOutlineDialog .outline-remove,#reportOutlineDialog #reportOutlineClose,.review-dialog header button{border:0!important;background:transparent!important;box-shadow:none!important;border-radius:0!important;padding:4px 7px;font-size:22px}.outline-row.dragging{opacity:.55}.outline-row.drop-before{box-shadow:0 -2px #6c8a70}.outline-row.drop-after{box-shadow:0 2px #6c8a70}';document.head.append(css);
})();
