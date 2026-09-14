
// Pause hero playback outside the viewport; resume from the same point.
const heroFrame=document.querySelector('.hero-live');
let heroVisible=true;
const notifyHero=()=>heroFrame.contentWindow?.postMessage({type:'hero-visibility',visible:heroVisible&&!document.hidden},location.origin);
new IntersectionObserver(entries=>{heroVisible=entries[0].isIntersecting;notifyHero();},{threshold:.01}).observe(heroFrame);
heroFrame.addEventListener('load',notifyHero);
document.addEventListener('visibilitychange',notifyHero);
