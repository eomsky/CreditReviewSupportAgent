(() => {
 const data=JSON.parse(document.getElementById('live-test-data').textContent);
 window.liveTestReady=(async()=>{
  await CreditReview.ready;
  await CreditReview.installSystemPromptPack(data.prompts);
  CreditReview.configure({baseUrl:'/api/credit-review/v1/',timeoutMs:45000});
  // Open the selected registration; no document or company is seeded automatically.
  const selected=CreditReview.snapshot().companies.find(c=>c.id===CreditReview.snapshot().active_case_id);
  if(selected&&!selected.example)CreditReviewMenu.observe(await CreditReview.refresh());
  CreditReview.frame.navigate(0);
 })();
})();
