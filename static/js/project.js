const regimes={within:'Fit the readout on one half of a session. Test on the other half.',session:'Fit the readout on one session. Test on another session of the same subject.',subject:'Fit the readout on one subject. Test on other subjects.'};
const benchmarkTabs=[...document.querySelectorAll('[data-regime]')];
function selectRegime(key,focus=false){
  benchmarkTabs.forEach(tab=>{
    const selected=tab.dataset.regime===key;
    tab.setAttribute('aria-selected',String(selected));
    tab.tabIndex=selected?0:-1;
    document.getElementById(tab.getAttribute('aria-controls')).hidden=!selected;
    if(selected&&focus)tab.focus();
  });
  document.getElementById('regime-description').textContent=regimes[key];
}
benchmarkTabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>selectRegime(tab.dataset.regime));
  tab.addEventListener('keydown',event=>{
    let next;
    if(event.key==='ArrowRight')next=(index+1)%benchmarkTabs.length;
    if(event.key==='ArrowLeft')next=(index+benchmarkTabs.length-1)%benchmarkTabs.length;
    if(event.key==='Home')next=0;
    if(event.key==='End')next=benchmarkTabs.length-1;
    if(next===undefined)return;
    event.preventDefault();selectRegime(benchmarkTabs[next].dataset.regime,true);
  });
});
selectRegime('subject');
document.getElementById('copy-citation').addEventListener('click',async()=>{const status=document.getElementById('copy-status'),text=document.querySelector('#citation code').textContent;try{await navigator.clipboard.writeText(text);status.textContent='Citation copied.'}catch{const range=document.createRange();range.selectNodeContents(document.querySelector('#citation code'));const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);status.textContent='Citation selected. Copy it with your keyboard.'}});
