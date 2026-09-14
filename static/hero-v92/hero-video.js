// Prerendered opening and repeating flow. No particle simulation or canvas redraws.
const opening=document.getElementById('opening'),flow=document.getElementById('flow');
for(const video of [opening,flow]){video.muted=true;video.defaultMuted=true;}
let phase='opening',visible=true,parentVisible=true,revealed=false;
function running(){return visible&&parentVisible&&!document.hidden;}
function sync(){const active=phase==='opening'?opening:flow;for(const video of [opening,flow])if(video!==active||!running())video.pause();if(running())active.play().catch(()=>{});}
function revealFlow(){if(revealed)return;revealed=true;flow.hidden=false;opening.hidden=true;opening.removeAttribute('src');opening.load();}
opening.addEventListener('ended',()=>{
 if(phase==='loop')return;
 phase='loop';
 flow.addEventListener('playing',revealFlow,{once:true});
 sync();
});
for(const video of [opening,flow])video.addEventListener('canplay',sync);
document.addEventListener('visibilitychange',sync);
new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.01}).observe(document.querySelector('.stage'));
window.addEventListener('message',e=>{if(e.source===parent&&e.origin===location.origin&&e.data?.type==='hero-visibility'){parentVisible=e.data.visible;sync();}});
window.addEventListener('pageshow',sync);
window.addEventListener('pointerdown',sync,{once:true,passive:true});
window.addEventListener('keydown',sync,{once:true});
window.heroPlayback={get state(){return {phase,playing:running(),revealed};}};
sync();
