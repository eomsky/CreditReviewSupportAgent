/* Plain-text UI: render common LaTeX arrow commands without a math renderer. */
(() => {
 const arrows={rightarrow:'→',longrightarrow:'→',Rightarrow:'⇒',Longrightarrow:'⇒',to:'→',
  leftarrow:'←',longleftarrow:'←',Leftarrow:'⇐',Longleftarrow:'⇐',gets:'←',
  leftrightarrow:'↔',longleftrightarrow:'↔',Leftrightarrow:'⇔',Longleftrightarrow:'⇔',
  uparrow:'↑',downarrow:'↓',mapsto:'↦',longmapsto:'↦'};
 const names=Object.keys(arrows).sort((a,b)=>b.length-a.length).join('|');
 const command='\\\\+('+names+')(?![A-Za-z])';
 const inline=new RegExp('\\${1,2}\\s*'+command+'\\s*\\${1,2}','g');
 const parenthesized=new RegExp('\\\\[([]\\s*'+command+'\\s*\\\\[)\\]]','g');
 const bare=new RegExp(command,'g');
 const labels={draft_tables:'보고서 표',related_draft_tables:'관련 보고서 표',paragraph_context:'관련 문단',selected_sentence:'선택 문장',source_ids:'근거 위치',source_excerpts:'원문 발췌'};
 const internalNames=new RegExp('`?\\b('+Object.keys(labels).sort((a,b)=>b.length-a.length).map(name=>name.replaceAll('_','\\\\?_')).join('|')+')\\b`?','gi');
 window.CreditReviewDisplayText=value=>String(value??'')
  .replace(inline,(_,name)=>arrows[name])
  .replace(parenthesized,(_,name)=>arrows[name])
  .replace(bare,(_,name)=>arrows[name])
  .replace(internalNames,(_,name)=>labels[name.replaceAll('\\','').toLowerCase()]);
})();
