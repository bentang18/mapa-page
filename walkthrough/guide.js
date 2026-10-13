// Presentation-only transitions; no data/model computation.
document.querySelectorAll('.snippets').forEach(group=>{
 const panels=[...group.querySelectorAll('.snippet')];
 const bar=document.createElement('div');bar.className='code-tabs';bar.setAttribute('role','tablist');bar.setAttribute('aria-label','Source excerpts');
 panels.forEach((panel,i)=>{
  const button=document.createElement('button');button.type='button';button.setAttribute('role','tab');button.textContent=panel.querySelector('h3').textContent.replace('Zoom in: ','');button.id=panel.id+'-tab';button.setAttribute('aria-controls',panel.id);button.setAttribute('aria-selected',String(i===0));
  panel.hidden=i!==0;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);
  button.addEventListener('click',()=>{panels.forEach(p=>p.hidden=p!==panel);[...bar.children].forEach(b=>b.setAttribute('aria-selected',String(b===button)));});
  button.addEventListener('keydown',e=>{if(['ArrowRight','ArrowLeft'].includes(e.key)){e.preventDefault();const j=(i+(e.key==='ArrowRight'?1:-1)+panels.length)%panels.length;bar.children[j].click();bar.children[j].focus();}});
  bar.append(button);
 });group.prepend(bar);
});
function selected(buttons,current){buttons.forEach(b=>b.setAttribute('aria-pressed',String(b===current)));}
const tokenButtons=[...document.querySelectorAll('[data-token-step]')];
const tokenFigure=document.querySelector('#tokens .token-steps-figure .math-figure');
const captions=[
 'Columns = timepoints · rows = frequency bins',
 '7 / 6 / 7 bins → 384 features. Token counts unchanged.',
 '4 slow + 16 mid + 32 fast = 52 tokens/contact.'
];
tokenButtons.forEach(button=>button.addEventListener('click',()=>{
 const stage=Number(button.dataset.tokenStep);selected(tokenButtons,button);
 tokenFigure.querySelectorAll('.moving-token').forEach(g=>{
  const band=Number(g.dataset.band),j=Number(g.dataset.j),off=Number(g.dataset.offset),stride=[8,2,1][band];
  const x=stage===2?110+off*12.4:162+j*stride*18,y=stage===2?130:72+band*71;
  g.setAttribute('transform',`translate(${x},${y})`);g.querySelector('rect').setAttribute('height',stage===0?'42':'32');
 });
 tokenFigure.querySelectorAll('.bin-dividers').forEach(g=>g.style.opacity=stage===0?'1':'0');
 tokenFigure.querySelectorAll('.band-label,.band-count').forEach(g=>g.style.opacity=stage===2?'0':'1');
 tokenFigure.querySelectorAll('.frame-guides').forEach(g=>g.style.opacity=stage===0?'1':'0');
 tokenFigure.querySelector('#packed-labels').style.opacity=stage===2?'1':'0';
 document.getElementById('tokens-code-'+([3,0,1][stage])+'-tab').click();
 const eq=tokenFigure.querySelector('text.shape:last-child');
 eq.textContent=['32 frontend frames → 4 + 16 + 32 retained frames','7 / 6 / 7 bins → clip → Linear + band embedding → 384 features','4 slow + 16 mid + 32 fast = 52 tokens / contact'][stage];
 document.querySelector('#token-caption').textContent=captions[stage];
}));
tokenButtons[0].click(); // Initial figure shows retained frames; open that implementation.
const maeButtons=[...document.querySelectorAll('[data-mae-step]')];
const mae=document.querySelector('#training .mae-detail .math-figure');
const visible=[1,5,10,14];
const maeCaptions=[
 'Gray positions are withheld from the encoder. The selected locations are illustrative; training samples an exact 75% mask per array/clip.',
 'Only visible tokens enter the encoder. Tokens retain their original contact, band, and time coordinates after gathering.',
 'Project visible features to width 192 and restore their positions. Fill the gaps with a learned mask token; add band/region identity and RoPE.',
 'The decoder predicts bins at every position. Only the gold, originally masked positions contribute to loss; decoder attention carries gradients back into the encoder.'
];
maeButtons.forEach(button=>button.addEventListener('click',()=>{
 const stage=Number(button.dataset.maeStep);selected(maeButtons,button);
 document.getElementById('training-code-'+([0,1,4,8][stage])+'-tab').click();
 mae.querySelectorAll('.mae-token').forEach(g=>{
  const i=Number(g.dataset.i),isVisible=g.dataset.visible==='true';
  const x=stage===1&&isVisible?326+visible.indexOf(i)*64:46+i*49;
  g.setAttribute('transform',`translate(${x},106)`);g.style.opacity=stage===1&&!isVisible?'0':'1';
  g.querySelector('rect').setAttribute('class',isVisible?'blue':stage===3?'gold':stage===2?'mask-learned':'ghost');
  g.querySelector('text').textContent=!isVisible&&stage===2?'m':String(i+1);
 });
 mae.querySelector('#encoder-symbol').style.opacity=stage===1?'1':'0';
 mae.querySelector('.equation').textContent=['13,312 total → 3,328 visible','3,328 × 384 → encoder → four normalized taps','3,328 × 1,536 → fusion → restore 13,312 × 192','9,984 masked tokens → reconstruction loss'][stage];
 document.querySelector('#mae-caption').textContent=maeCaptions[stage];
}));

// Common 32 Hz clock. Hold each band at its most recent retained frame.
const clockSlider=document.getElementById('clock-frame'), play=document.getElementById('clock-play');
const reduceMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
let frame=0,playing=!reduceMotion,visibleClock=true,lastTick=0,holdUntil=0;
function drawClock(k){
 frame=k;clockSlider.value=String(k);
 const ms=k*31.25;
 document.getElementById('clock-time').textContent=`${ms} ms`;
 clockSlider.setAttribute('aria-valuetext',`Frame ${k}, ${ms} milliseconds`);
 document.getElementById('shared-clock').setAttribute('d',`M${240+k*15},49 V410`);
 document.querySelectorAll('.stft-window').forEach(el=>{
  const b=Number(el.dataset.band),stride=[8,2,1][b],center=Math.floor(k/stride)*stride;
  const width=[500,125,62.5][b]*.48;
  el.setAttribute('x',240+center*15-width/2);
  el.classList.toggle('emitting',k%stride===0);
  document.getElementById(`frame-count-${b}`).textContent=`${Math.floor(k/stride)+1} / ${32/stride}`;
 });
 document.querySelectorAll('.retained-frame').forEach(el=>{
  const j=Number(el.dataset.frame),b=Number(el.dataset.band),stride=[8,2,1][b];
  el.setAttribute('opacity',j<=k?'1':'0');
  el.classList.toggle('latest',j===Math.floor(k/stride)*stride);
 });
}
function setPlaying(value){playing=value;play.textContent=value?'Pause':'Play';lastTick=0;holdUntil=0;}
play.addEventListener('click',()=>setPlaying(!playing));
document.getElementById('clock-step').addEventListener('click',()=>{setPlaying(false);drawClock((frame+1)%32);});
clockSlider.addEventListener('input',()=>{setPlaying(false);drawClock(Number(clockSlider.value));});
new IntersectionObserver(entries=>{visibleClock=entries[0].isIntersecting;lastTick=0;},{threshold:.15}).observe(document.querySelector('.frontend-animation'));
function animateClock(now){
 if(playing&&visibleClock&&!document.hidden){
  if(!lastTick)lastTick=now;
  if(now>=holdUntil&&now-lastTick>=125){
   drawClock(frame===31?0:frame+1);
   lastTick=now;if(frame===31)holdUntil=now+1250;
  }
 }else{lastTick=0;}
 requestAnimationFrame(animateClock);
}
drawClock(0);setPlaying(!reduceMotion);requestAnimationFrame(animateClock);

// Spatial encodings: illustrative placements, actual first contact RoPE frequency.
const spatialButtons=[...document.querySelectorAll('[data-spatial-step]')];
spatialButtons.forEach(button=>button.addEventListener('click',()=>{
 const stage=Number(button.dataset.spatialStep);selected(spatialButtons,button);
 document.getElementById('region-panel').hidden=stage!==0;
 document.getElementById('rope-panel').hidden=stage!==1;
 document.getElementById('spatial-code-'+stage+'-tab').click();
 if(stage===0) stopRope();
}));
const sharedRegions=[{id:43,name:'Right medial orbitofrontal cortex'},{id:41,name:'Right lateral orbitofrontal cortex'},{id:49,name:'Right pars triangularis'}];
let regionIndex=0;
document.getElementById('region-move').addEventListener('click',()=>{
 regionIndex=(regionIndex+1)%sharedRegions.length;const region=sharedRegions[regionIndex];
 document.querySelectorAll('.real-region-contact').forEach(g=>{
  const active=Number(g.dataset.region)===region.id;
  g.querySelector('.region-halo').setAttribute('opacity',active?'1':'0');
  g.querySelector('.region-fill').setAttribute('opacity',active?'1':'0');
  g.querySelector('.region-contact').setAttribute('opacity',active?'0':'1');
 });
 document.getElementById('region-row').textContent=`row ${region.id}`;
 document.getElementById('region-name').textContent=region.name;
});
const ropeSlider=document.getElementById('rope-offset'),ropePlay=document.getElementById('rope-play'),ropeGap=document.getElementById('rope-gap');
let ropeDistance=2,ropeRunning=false,ropeStart=0,ropeStartValue=2;
function drawRope(value){
 const maxOffset=9-ropeDistance;
 ropeSlider.max=String(maxOffset);
 value=Math.max(0,Math.min(maxOffset,Math.round(value)));
 const positions=[value,value+ropeDistance];
 ['q','k'].forEach((id,i)=>{
  const c=positions[i],x=62+c*41,theta=c;
  document.getElementById('rope-contact-'+id).setAttribute('transform',`translate(${x},0)`);
  const ex=664+77*Math.cos(theta),ey=136-77*Math.sin(theta);
  const vector=document.getElementById('rope-vector-'+id),tip=document.getElementById('rope-tip-'+id),label=document.getElementById('rope-label-'+id);
  vector.setAttribute('x2',ex);vector.setAttribute('y2',ey);tip.setAttribute('cx',ex);tip.setAttribute('cy',ey);
  label.setAttribute('x',664+94*Math.cos(theta));label.setAttribute('y',141-94*Math.sin(theta));
 });
 const x1=62+positions[0]*41,x2=62+positions[1]*41;
 document.getElementById('rope-bracket').setAttribute('d',`M${x1},165 v9 H${x2} v-9`);
 document.getElementById('rope-delta').textContent=`Δcontact = ${ropeDistance}`;
 document.getElementById('rope-score').textContent=`Q′ · K′ = cos(${ropeDistance}) = ${Math.cos(ropeDistance).toFixed(3).replace('-', '−')}`;
 ropeSlider.value=String(value);ropeSlider.setAttribute('aria-valuetext',`Illustrative contact coordinates ${value} and ${value+ropeDistance}; separation ${ropeDistance}`);
}
function stopRope(){ropeRunning=false;ropePlay.textContent='Animate shift';}
ropeSlider.addEventListener('input',()=>{stopRope();drawRope(Number(ropeSlider.value));});
ropeGap.addEventListener('click',()=>{
 stopRope();
 ropeDistance=ropeDistance===2?3:2;ropeGap.setAttribute('aria-pressed',String(ropeDistance===3));
 ropeGap.textContent=ropeDistance===2?'Change separation: 2 → 3':'Change separation: 3 → 2';drawRope(Number(ropeSlider.value));
});
ropePlay.addEventListener('click',()=>{
 if(ropeRunning){stopRope();return;}
 ropeRunning=true;ropeStart=performance.now();ropeStartValue=Number(ropeSlider.value);ropePlay.textContent='Pause shift';requestAnimationFrame(animateRope);
});
function animateRope(now){
 if(!ropeRunning)return;
 // Hold each integer contact coordinate for 700 ms; no intermediate positions.
 const maxOffset=9-ropeDistance,period=2*maxOffset;
 const steps=Math.floor((now-ropeStart)/700),phase=(ropeStartValue+steps)%period,value=phase<=maxOffset?phase:period-phase;
 drawRope(value);requestAnimationFrame(animateRope);
}
new IntersectionObserver(entries=>{if(!entries[0].isIntersecting)stopRope();}).observe(document.getElementById('spatial'));
drawRope(2);

// Evaluation tabs keep one flow visible and open its corresponding source excerpt.
const readoutModes=[...document.querySelectorAll('[data-readout-mode]')];
readoutModes.forEach((button,index)=>{
 button.addEventListener('click',()=>{
  readoutModes.forEach((other,i)=>{
   other.setAttribute('aria-selected',String(i===index));
   other.setAttribute('aria-pressed',String(i===index));
   document.getElementById('readout-view-'+i).hidden=i!==index;
  });
  document.getElementById('readout-code-'+(index===0?0:2)+'-tab').click();
 });
 button.addEventListener('keydown',event=>{
  if(['ArrowLeft','ArrowRight'].includes(event.key)){
   event.preventDefault(); const next=readoutModes[1-index]; next.click(); next.focus();
  }
 });
});

// Diagram labels open the corresponding panel. Resolve by panel ID, never file order.
document.querySelectorAll('[data-code-target]').forEach(link=>{
 link.addEventListener('click',event=>{
  event.preventDefault();
  const panel=document.getElementById(link.dataset.codeTarget);
  document.getElementById(panel.id+'-tab').click();
  panel.closest('.snippets').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
 });
});

// Code-to-figure links reveal the matching view before returning to the operation.
document.querySelectorAll('[data-figure-target]').forEach(link=>{
 link.addEventListener('click',event=>{
  event.preventDefault();
  const target=document.getElementById(link.dataset.figureTarget);
  const readout=target.closest('[id^="readout-view-"]');
  if(readout) document.getElementById(readout.getAttribute('aria-labelledby')).click();
  const spatial=target.closest('#region-panel, #rope-panel');
  if(spatial) document.querySelector(`[data-spatial-step="${spatial.id==='region-panel'?0:1}"]`).click();
  const details=target.closest('details'); if(details) details.open=true;
  target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'center'});
 });
});

// Shared snippet URLs must reveal the tab before the browser scrolls to it.
function revealLinkedSnippet(){
 const panel=document.getElementById(location.hash.slice(1));
 if(!panel?.classList.contains('snippet')) return;
 document.getElementById(panel.id+'-tab').click();
 requestAnimationFrame(()=>panel.closest('.snippets').scrollIntoView({behavior:'instant',block:'start'}));
}
window.addEventListener('hashchange',revealLinkedSnippet);
window.addEventListener('pageshow',()=>document.fonts.ready.then(revealLinkedSnippet));
revealLinkedSnippet();

// Reuse the hero's anatomical projection; contact names match the overview exactly.
const brainCanvas=document.getElementById('recording-brain');
if(brainCanvas){
 const details=brainCanvas.closest('details'),angleInput=document.getElementById('brain-angle');
 let anatomy,loading=false;
 function drawBrain(){
  if(!anatomy)return;
  const c=brainCanvas.getContext('2d'),angle=Number(angleInput.value)*Math.PI/180;
  const project=p=>{const x=p[0]-30,y=p[1]+20,z=p[2]-20;return [330+(y*Math.cos(angle)+x*Math.sin(angle))*3.25,257+(-z+x*.10)*3.25,x*Math.cos(angle)+y*Math.sin(angle)];};
  c.setTransform(1.5,0,0,1.5,0,0);c.clearRect(0,0,660,530);
  const dots=anatomy.surface.map(p=>({p,q:project(p)})).sort((a,b)=>a.q[2]-b.q[2]);
  for(const {p,q} of dots){
   const facing=p[3]*Math.cos(angle)+p[4]*Math.sin(angle);
   const light=.22+.78*Math.max(0,facing*.7+p[5]*.3);
   c.fillStyle='#4d4952';c.globalAlpha=(.25+.57*light)*(q[2]<-10?.55:1)*.55;
   c.beginPath();c.arc(q[0],q[1],1.05,0,2*Math.PI);c.fill();
  }
  // Draw the highlighted shaft last so its contacts remain easy to locate.
  for(const shaft of [...anatomy.shafts.slice(1),anatomy.shafts[0]]){
   const selected=shaft.alias==='Shaft A',points=shaft.contacts.map(t=>project(t.position));
   c.globalAlpha=selected?1:.55;c.strokeStyle=selected?'#8265a5':'#596370';c.lineWidth=selected?2.5:1.3;
   c.beginPath();points.forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));c.stroke();
   for(const p of points){c.beginPath();c.arc(p[0],p[1],selected?4.1:2.6,0,2*Math.PI);c.fillStyle=c.strokeStyle;c.fill();}
  }
  c.globalAlpha=1;brainCanvas.dataset.ready='true';
 }
 async function loadBrain(){
  if(!details.open||anatomy||loading)return;
  loading=true;
  try{const response=await fetch('subject-1-brain.json');if(!response.ok)throw Error('Geometry unavailable');anatomy=await response.json();drawBrain();}
  catch(error){brainCanvas.insertAdjacentHTML('afterend','<p class="note">Brain preview unavailable. The geometry link below contains the source data.</p>');}
 }
 details.addEventListener('toggle',loadBrain);angleInput.addEventListener('input',drawBrain);loadBrain();
}

// Native anatomy is an opt-in local preview; normal public builds omit the figure.
const intuitionRoot=document.getElementById('spatial-intuition');
if(intuitionRoot){
 const origin=document.getElementById('uecog-origin');
 const originVideo=document.getElementById('uecog-origin-video');
 const originTrials=[...origin.querySelectorAll('[data-origin-trial]')];
 originTrials.forEach(button=>button.addEventListener('click',()=>{
  originVideo.pause();selected(originTrials,button);
  originVideo.poster=`uecog-origin/s62-${button.dataset.originTrial}.jpg`;
  originVideo.querySelector('source').src=`uecog-origin/s62-${button.dataset.originTrial}.mp4`;
  originVideo.querySelector('a').href=`uecog-origin/s62-${button.dataset.originTrial}.mp4`;
  originVideo.load();
 }));
 origin.addEventListener('toggle',()=>{
  if(!origin.open){originVideo.pause();return;}
  if(originVideo.preload==='none'){originVideo.preload='metadata';originVideo.load();}
 });
 const shift=document.getElementById('local-shift');
 const shiftButton=document.getElementById('local-shift-play');
 let localOffset=0,localFrame=0;
 function drawLocalPosition(offset){
  localOffset=offset;
  document.getElementById('local-moving-hotspot').setAttribute('transform',`translate(${offset*52},0)`);
  const point=(theta,r)=>[747+r*Math.cos(theta),103-r*Math.sin(theta)];
  const angles=[4+offset,5+offset];
  ['q','k'].forEach((kind,i)=>{
   const [x,y]=point(angles[i],52),line=document.getElementById('local-rope-'+kind),tip=document.getElementById('local-rope-tip-'+kind);
   line.setAttribute('x2',x);line.setAttribute('y2',y);tip.setAttribute('cx',x);tip.setAttribute('cy',y);
  });
  const [qx,qy]=point(angles[0],27),[kx,ky]=point(angles[1],27);
  document.getElementById('local-rope-wedge').setAttribute('d',`M747,103 L${qx},${qy} A27,27 0 0 0 ${kx},${ky} Z`);
 }
 function shiftHotspot(value,animate=false){
  cancelAnimationFrame(localFrame);
  const target=Math.max(0,Math.min(5,Math.round(value))),start=localOffset;
  shift.value=String(target);
  document.getElementById('local-shift-range').textContent=`Contacts ${4+target}–${5+target}`;
  shift.setAttribute('aria-valuetext',`Contacts ${4+target} through ${5+target}`);
  shiftButton.innerHTML=`Translate <span aria-hidden="true">${target===0?'→':'←'}</span>`;
  if(!animate||matchMedia('(prefers-reduced-motion: reduce)').matches){drawLocalPosition(target);return;}
  const started=performance.now();
  function frame(now){
   const t=Math.min(1,(now-started)/1700),ease=(1-Math.cos(Math.PI*t))/2;
   drawLocalPosition(start+(target-start)*ease);
   if(t<1)localFrame=requestAnimationFrame(frame);
  }
  localFrame=requestAnimationFrame(frame);
 }
 shift.addEventListener('input',()=>shiftHotspot(Number(shift.value)));
 shiftButton.addEventListener('click',()=>shiftHotspot(Number(shift.value)===0?5:0,true));
 shiftHotspot(0);
 const buttons=[...intuitionRoot.querySelectorAll('[data-intuition-step]')];
 const modes={1:'parcels-leveled',2:'stg-leveled'};
 buttons.forEach(button=>button.addEventListener('click',()=>{
  const stage=Number(button.dataset.intuitionStep);selected(buttons,button);
  intuitionRoot.dataset.stage=String(stage);
  intuitionRoot.querySelectorAll('[data-intuition-panel]').forEach(p=>p.hidden=Number(p.dataset.intuitionPanel)!==stage);
  intuitionRoot.querySelectorAll('[data-native-brain]').forEach(img=>img.src=`native-anatomy/${img.dataset.nativeBrain}-${modes[stage]}.png`);
 }));
 Object.values(modes).forEach(mode=>['person-a','person-b'].forEach(person=>{const img=new Image();img.src=`native-anatomy/${person}-${mode}.png`;}));
}
