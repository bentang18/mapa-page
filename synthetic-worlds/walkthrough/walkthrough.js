'use strict';
(async()=>{
const $=id=>document.getElementById(id);let frame=0,playing=false,speed=.25,start=0,anchor=0;const data={},cache={};
const color=(v,scale=4)=>{const p=v<0?[87,122,153]:[196,155,67],q=Math.min(1,Math.abs(v)/Math.max(scale,1e-9));return [245,244,238].map((x,i)=>Math.round(x+(p[i]-x)*q));};
const rgb=v=>'rgb('+v.join(',')+')';
const get=async path=>{const r=await fetch(path);if(!r.ok)throw Error('Example could not load: '+path);return r;};
try{
const meta=await(await get('example.json')).json();
await Promise.all(['core','hga','drive','state','voltage','bins'].map(async k=>{const a=meta[k],bytes=await(await get(a.file)).arrayBuffer();if(crypto.subtle){const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');if(hash!==a.sha256)throw Error('Example hash mismatch');}data[k]=new Float32Array(bytes);if(data[k].length!==a.shape.reduce((x,y)=>x*y,1)||!data[k].every(Number.isFinite))throw Error('Example array differs');}));
$('example-label').textContent=`Recurrent switching · ${meta.profile.replace('-',' / ')} · ${meta.shape[0]} × ${meta.shape[1]} contacts`;
$('tensor-shape').textContent=`${meta.contacts} contacts × (7 + 6 + 7) bins × 1,024 frames`;
$('bin-labels').replaceChildren(...meta.frequencies_hz.map(f=>{const s=document.createElement('span');s.textContent=f+' Hz';return s;}));
for(const id of ['core','hga']){$(id).width=meta.shape[1];$(id).height=meta.shape[0];$(id).style.aspectRatio=meta.shape[1]+'/'+meta.shape[0];}
function surface(id){const e=$(id),dpr=devicePixelRatio||1,r=e.getBoundingClientRect();e.width=Math.round(r.width*dpr);e.height=Math.round(r.height*dpr);return {e,ctx:e.getContext('2d'),w:e.width,h:e.height};}
function heatmap(values,rows,cols,scale){const c=document.createElement('canvas');c.width=cols;c.height=rows;const x=c.getContext('2d'),im=x.createImageData(cols,rows);for(let i=0;i<rows*cols;i++){const co=color(values[i],scale);im.data.set([...co,255],i*4);}x.putImageData(im,0,0);return c;}
const inRows=new Float32Array(16*512);for(let t=0;t<512;t++)for(let d=0;d<16;d++)inRows[d*512+t]=data.drive[t*16+d];
const driveImage=heatmap(inRows,16,512,meta.drive_display_scale),binImage=heatmap(data.bins,20,512,4);
function staticPlot(id){const {ctx,w,h}=surface(id);ctx.fillStyle='#fafafa';ctx.fillRect(0,0,w,h);
if(id==='drive'||id==='bins'){ctx.imageSmoothingEnabled=false;ctx.drawImage(id==='drive'?driveImage:binImage,0,0,w,h);if(id==='bins'){ctx.strokeStyle='#fff';ctx.lineWidth=2*devicePixelRatio;[7,13].forEach(b=>{ctx.beginPath();ctx.moveTo(0,h*b/20);ctx.lineTo(w,h*b/20);ctx.stroke();});}}
if(id==='events'){ctx.font=`${10*devicePixelRatio}px Manrope,Arial`;meta.phones.forEach(p=>{const x=p.start/16*w,ww=(p.stop-p.start)/16*w;ctx.fillStyle='#e4e8eb';ctx.fillRect(x+1,5*devicePixelRatio,Math.max(1,ww-2),h-10*devicePixelRatio);if(ww>18*devicePixelRatio){ctx.fillStyle='#444';ctx.fillText(p.phone,x+3*devicePixelRatio,h*.58);}});}
if(id==='state'){const cols=6,n=512;for(let k=0;k<cols;k++){let max=0;for(let t=0;t<n;t++)max=Math.max(max,Math.abs(data.state[t*cols+k]));ctx.strokeStyle=k%2?'#aa8e55':'#6e8da2';ctx.lineWidth=devicePixelRatio;ctx.beginPath();for(let t=0;t<n;t++){const x=t/(n-1)*w,y=(k+.5)*h/cols-data.state[t*cols+k]/Math.max(max,1e-8)*h/cols*.4;t?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.stroke();}}
if(id==='voltage'){let max=0;data.voltage.forEach(v=>{max=Math.max(max,Math.abs(v));});ctx.strokeStyle='#718897';ctx.lineWidth=.8*devicePixelRatio;ctx.beginPath();data.voltage.forEach((v,i)=>{const x=i/(data.voltage.length-1)*w,y=h/2-v/max*h*.43;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}
cache[id]=ctx.getImageData(0,0,w,h);}
function cursor(id,seconds,duration=16){const e=$(id),ctx=e.getContext('2d');ctx.putImageData(cache[id],0,0);if(seconds<=duration){ctx.strokeStyle='#282828';ctx.lineWidth=devicePixelRatio;ctx.beginPath();ctx.moveTo(seconds/duration*e.width,0);ctx.lineTo(seconds/duration*e.width,e.height);ctx.stroke();}}
function map(id,scale){const e=$(id),ctx=e.getContext('2d'),im=ctx.createImageData(e.width,e.height);for(let j=0;j<meta.contacts;j++)im.data.set([...color(data[id][frame*meta.contacts+j],scale),255],j*4);ctx.putImageData(im,0,0);}
function render(){const seconds=frame/32;$('time').value=frame;$('clock').textContent=seconds.toFixed(2)+' s';const phone=meta.phones.find(p=>p.start<=seconds&&seconds<p.stop);$('phone').textContent=phone?phone.phone:'pause';['events','drive','state','bins'].forEach(id=>cursor(id,seconds));cursor('voltage',seconds,4);map('core',meta.core_display_scale);map('hga',4);document.body.dataset.frame=String(frame);}
function redraw(){['events','drive','state','bins','voltage'].forEach(staticPlot);render();}
function stop(){playing=false;$('play').textContent='▶ Play';}
function tick(now){if(!playing)return;frame=Math.min(511,start+Math.floor((now-anchor)*32*speed/1000));render();if(frame===511)stop();else requestAnimationFrame(tick);}
$('play').disabled=false;$('play').onclick=()=>{if(playing){stop();return;}if(frame===511)frame=0;start=frame;anchor=performance.now();playing=true;$('play').textContent='Ⅱ Pause';requestAnimationFrame(tick);};
$('time').oninput=()=>{stop();frame=Number($('time').value);render();};$('speed').onchange=()=>{speed=Number($('speed').value);if(playing){start=frame;anchor=performance.now();}};
new ResizeObserver(redraw).observe($('input'));document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
window.__syntheticWalkthrough={meta,data,get frame(){return frame;},render};redraw();document.body.dataset.ready='true';
}catch(error){$('example-label').textContent=error.message;console.error(error);}
})();
