const {chromium}=require('C:/Users/lasts/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');
(async()=>{
  const root=process.cwd(),out=path.join(root,'workspace','qa-visual');fs.mkdirSync(out,{recursive:true});
  const caseId=process.argv[2]||'qa-haeon-20260911-1439';
  const state=await(await fetch('http://127.0.0.1:8766/api/credit-review/v1/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case_id:caseId})})).json();
  fs.writeFileSync(path.join(out,'state.json'),JSON.stringify(state,null,2));
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1100,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file:///'+path.join(root,'frontend','CreditReviewSupportAgent_App_v0.1.69.html').replaceAll('\\','/'));
  await page.waitForFunction(()=>!!window.CreditReview);
  await page.evaluate(state=>{const report={...state.report,case_id:CreditReview.snapshot().active_case_id};CreditReview.loadReport(report,state.views);document.getElementById('reviewHome').hidden=true;document.getElementById('companyName').textContent=state.name;},state);
  const results=[];
  for(const [key,view] of Object.entries(state.views||{})){
    const index=await page.evaluate(key=>{const index=CreditReview.viewIds.indexOf(key);CreditReview.frame.navigate(index);return index;},key);
    await page.locator('#appWindow').screenshot({path:path.join(out,key+'.png')});
    results.push(await page.evaluate(({key,index})=>({key,index,tables:[...document.querySelectorAll('#opinion table')].map(t=>({caption:t.caption?.textContent,columns:[...t.querySelectorAll('thead th')].map(x=>x.textContent),rows:t.tBodies[0]?.rows.length,hidden:[...t.querySelectorAll('tbody tr')].filter(r=>getComputedStyle(r).display==='none').length})),opinion:document.getElementById('opinion')?.textContent.slice(0,160)}),{key,index}));
  }
  if(results.length){const key=results[results.length-1].key;fs.copyFileSync(path.join(out,key+'.png'),path.join(root,'outputs','business_report_test','qa-latest.png'));}
  fs.writeFileSync(path.join(out,'visual-check.json'),JSON.stringify({errors,results},null,2));console.log(JSON.stringify({errors,results}));
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
