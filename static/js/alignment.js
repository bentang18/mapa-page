(async()=>{
'use strict';
const root=document.getElementById('alignment');if(!root)return;
const grid=document.getElementById('alignment-grid'),button=document.getElementById('alignment-play'),slider=document.getElementById('alignment-scrub'),time=document.getElementById('alignment-time');
let D;try{const r=await fetch('static/data/alignment.json');if(!r.ok)throw Error(r.status);D=await r.json();}catch(e){grid.textContent='The trajectories could not load. Please reload the page.';button.disabled=true;slider.disabled=true;return;}
const visible=D.sessions.map((_,i)=>i).filter(i=>!(D.sessions[i].subject===3&&D.sessions[i].session===1));
let frame=0,playing=true,inView=false,last=0,raf=0;
const panels=D.layers.map((layer,li)=>{
 const panel=document.createElement('div');panel.className='alignment-panel';
 const canvas=document.createElement('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',`Layer ${layer}: speech-onset trajectories from six subjects in a shared PCA projection.`);
 const title=document.createElement('h3');title.textContent=`Layer ${layer}`;
 const score=document.createElement('p');score.className='alignment-score';score.textContent=`CKA = ${D.cka[li].toFixed(3)}`;
 const head=document.createElement('div');head.className='alignment-panel-head';head.append(title,score);panel.append(head,canvas);grid.append(panel);
 const curves=visible.map(si=>{const pts=D.coords[si][li],b=[0,1].map(k=>pts.slice(0,16).reduce((s,p)=>s+p[k],0)/16);return pts.map(p=>[p[0]-b[0],p[1]-b[1]]);});
 return {canvas,ctx:canvas.getContext('2d'),curves,limit:Math.max(1e-8,...curves.flat(2).map(Math.abs))*1.1};
});
const seen=new Set();for(const s of D.sessions){if(seen.has(s.subject))continue;seen.add(s.subject);const item=document.createElement('span'),dot=document.createElement('i');dot.style.background=s.color;item.append(dot,document.createTextNode(`S${s.subject}`));document.getElementById('alignment-legend').append(item);}
function drawPanel({canvas,ctx,curves,limit}){
 const w=canvas.getBoundingClientRect().width;if(!w)return;const dpr=window.devicePixelRatio||1;canvas.width=Math.round(w*dpr);canvas.height=canvas.width;ctx.setTransform(dpr,0,0,dpr,0,0);
 const m=26,size=w-2*m,xy=p=>[m+(p[0]+limit)*size/(2*limit),w-m-(p[1]+limit)*size/(2*limit)];
 ctx.strokeStyle='#ededed';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(m,w/2);ctx.lineTo(w-m,w/2);ctx.moveTo(w/2,m);ctx.lineTo(w/2,w-m);ctx.stroke();
 ctx.font='10px Arial, sans-serif';ctx.fillStyle='#888';ctx.textAlign='center';ctx.fillText('PC1',w-m+9,w/2-8);ctx.fillText('PC2',w/2,m-10);ctx.fillText('−'+limit.toPrecision(2),m,w/2+14);ctx.fillText(limit.toPrecision(2),w-m,w/2+14);
 curves.forEach((points,i)=>{ctx.strokeStyle=D.sessions[visible[i]].color;ctx.lineWidth=1.2;ctx.globalAlpha=.52;ctx.setLineDash(visible[i]%2?[4,3]:[]);ctx.beginPath();points.forEach((p,j)=>j?ctx.lineTo(...xy(p)):ctx.moveTo(...xy(p)));ctx.stroke();ctx.globalAlpha=1;ctx.setLineDash([]);
 const start=xy(points[0]);ctx.beginPath();ctx.arc(...start,2,0,Math.PI*2);ctx.fillStyle='white';ctx.fill();ctx.stroke();const end=xy(points[63]);ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(end[0]-2,end[1]-2);ctx.lineTo(end[0]+2,end[1]+2);ctx.moveTo(end[0]-2,end[1]+2);ctx.lineTo(end[0]+2,end[1]-2);ctx.stroke();});
 curves.forEach((points,i)=>{ctx.fillStyle=D.sessions[visible[i]].color;ctx.strokeStyle='white';ctx.lineWidth=1;ctx.beginPath();ctx.arc(...xy(points[frame]),3.5,0,Math.PI*2);ctx.fill();ctx.stroke();});
}
function draw(){panels.forEach(drawPanel);const t=D.times[frame];time.textContent=(t<0?'−':'+')+Math.abs(t).toFixed(2)+' s';slider.value=frame;slider.setAttribute('aria-valuetext',time.textContent+' relative to speech onset');}
function state(){button.textContent=playing?'Pause':'Play';button.setAttribute('aria-pressed',String(playing));}
function tick(now){raf=0;if(!playing||!inView||document.hidden)return;if(now-last>=80){frame=(frame+Math.floor((now-last)/80))%D.times.length;last=now;draw();}raf=requestAnimationFrame(tick);}
function schedule(){if(raf)cancelAnimationFrame(raf);raf=0;last=performance.now();if(playing&&inView&&!document.hidden)raf=requestAnimationFrame(tick);}
button.addEventListener('click',()=>{playing=!playing;state();schedule();});
slider.addEventListener('input',()=>{playing=false;frame=+slider.value;state();schedule();draw();});
new IntersectionObserver(entries=>{inView=entries[0].isIntersecting;schedule();},{threshold:0}).observe(root.querySelector('.alignment-layout'));
new ResizeObserver(draw).observe(root.querySelector('.alignment-layout'));document.addEventListener('visibilitychange',schedule);state();draw();
})();
