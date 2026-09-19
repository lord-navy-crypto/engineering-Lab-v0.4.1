const UTUBE_DEFAULTS={g:9.80665,rin:15.12e-3,a:7.48e-3,rho:997.8};
const uEl=id=>document.getElementById(id);
const uEsc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function utubeOmega(rpm){return 2*Math.PI*Number(rpm)/60}
function utubeGeometry(rin=UTUBE_DEFAULTS.rin,a=UTUBE_DEFAULTS.a){
  rin=Number(rin);a=Number(a);
  if(!(rin>0)||!(a>0))throw new Error('R_in and tube radius must be positive.');
  return {rin,a,R:rin+a,ell:rin+2*a};
}
function utubeCriticalSpeed(rin=UTUBE_DEFAULTS.rin,a=UTUBE_DEFAULTS.a){
  const {ell}=utubeGeometry(rin,a);
  return 60*Math.sqrt(UTUBE_DEFAULTS.g/ell)/(2*Math.PI);
}
const utubeQuadratureCache=new Map();
function gaussLegendre(n){
  n=Math.max(12,Math.min(128,Math.round(Number(n)||48)));
  if(utubeQuadratureCache.has(n))return utubeQuadratureCache.get(n);
  const x=new Array(n),w=new Array(n),m=Math.floor((n+1)/2);
  for(let i=0;i<m;i++){
    let z=Math.cos(Math.PI*(i+.75)/(n+.5)),p1=0,p2=0,pp=0;
    for(let k=0;k<40;k++){
      p1=1;p2=0;
      for(let j=1;j<=n;j++){const p3=p2;p2=p1;p1=((2*j-1)*z*p2-(j-1)*p3)/j}
      pp=n*(z*p1-p2)/(z*z-1);
      const next=z-p1/pp;
      if(Math.abs(next-z)<1e-14){z=next;break}
      z=next;
    }
    x[i]=-z;x[n-1-i]=z;
    const weight=2/((1-z*z)*pp*pp);
    w[i]=weight;w[n-1-i]=weight;
  }
  const out={x,w};utubeQuadratureCache.set(n,out);return out;
}
function utubeCapacity(rpm,rin=UTUBE_DEFAULTS.rin,a=UTUBE_DEFAULTS.a,nq=48){
  rpm=Number(rpm);if(!(rpm>0))throw new Error('RPM must be positive.');
  const {x,w}=gaussLegendre(nq),{R,ell}=utubeGeometry(rin,a),omega=utubeOmega(rpm),g=UTUBE_DEFAULTS.g;
  let arc=0;
  for(let i=0;i<x.length;i++){
    const theta=.5*Math.PI*x[i],wt=.5*Math.PI*w[i],ct=Math.cos(theta),st=Math.sin(theta);
    for(let j=0;j<x.length;j++){
      const s=a*x[j],ws=a*w[j],radius=R+s,tmax=Math.sqrt(Math.max(0,a*a-s*s));
      const q=2*g*(ell-radius*ct)/(omega*omega)-radius*radius*st*st;
      let len=0;
      if(q<=0)len=2*tmax;
      else if(q<tmax*tmax)len=2*(tmax-Math.sqrt(q));
      arc+=radius*len*wt*ws;
    }
  }
  let leg=0;
  for(let i=0;i<x.length;i++){
    const radial=.5*a*(x[i]+1),wr=.5*a*w[i];
    for(let j=0;j<x.length;j++){
      const polar=Math.PI*(x[j]+1),wp=Math.PI*w[j],u=radial*Math.cos(polar),t=radial*Math.sin(polar);
      const r2=(R+u)*(R+u)+t*t,zmax=Math.max(omega*omega*r2/(2*g)-ell,0);
      leg+=2*zmax*radial*wr*wp;
    }
  }
  return {total:(arc+leg)*1e6,arc:arc*1e6,legs:leg*1e6};
}
function utubeThreshold(volume,rin=UTUBE_DEFAULTS.rin,a=UTUBE_DEFAULTS.a,nq=48){
  volume=Number(volume);if(!(volume>0))throw new Error('Volume must be positive.');
  let lo=utubeCriticalSpeed(rin,a)+1e-5,hi=520;
  let flo=utubeCapacity(lo,rin,a,nq).total-volume,fhi=utubeCapacity(hi,rin,a,nq).total-volume;
  if(flo>0)return lo;
  if(fhi<0)throw new Error('Threshold is above 520 rpm for this configuration.');
  for(let k=0;k<70;k++){
    const mid=(lo+hi)/2,f=utubeCapacity(mid,rin,a,nq).total-volume;
    if(f>0)hi=mid;else lo=mid;
  }
  return (lo+hi)/2;
}
function utubePotential(rpm,rin=UTUBE_DEFAULTS.rin,a=UTUBE_DEFAULTS.a,count=181){
  const {R,ell}=utubeGeometry(rin,a),omega=utubeOmega(rpm),rows=[];
  let min=Infinity;
  for(let i=0;i<count;i++){
    const theta=-Math.PI/2+Math.PI*i/(count-1),x=R*Math.sin(theta),z=ell-R*Math.cos(theta),u=UTUBE_DEFAULTS.g*z-.5*omega*omega*x*x;
    min=Math.min(min,u);rows.push({theta:theta*180/Math.PI,u});
  }
  return rows.map(r=>({...r,u:r.u-min}));
}
function utubeLineSvg(series,{xLabel='',yLabel='',height=250}={}){
  const all=series.flatMap(s=>s.points).filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));
  if(all.length<2)return '<div class="empty-state">No finite data.</div>';
  let xmin=Math.min(...all.map(p=>p.x)),xmax=Math.max(...all.map(p=>p.x)),ymin=Math.min(...all.map(p=>p.y)),ymax=Math.max(...all.map(p=>p.y));
  if(xmax===xmin)xmax=xmin+1;if(ymax===ymin)ymax=ymin+1;
  const W=760,H=height,L=58,R=18,T=18,B=42;
  const sx=x=>L+(x-xmin)/(xmax-xmin)*(W-L-R),sy=y=>T+(H-T-B)-(y-ymin)/(ymax-ymin)*(H-T-B);
  const grid=Array.from({length:5},(_,i)=>{
    const f=i/4,x=L+f*(W-L-R),y=T+f*(H-T-B);
    return '<line x1="'+x+'" y1="'+T+'" x2="'+x+'" y2="'+(H-B)+'"/><line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'"/>';
  }).join('');
  const paths=series.map((s,idx)=>'<path class="ut-series s'+idx+'" d="'+s.points.map((p,i)=>(i?'L':'M')+sx(p.x).toFixed(2)+' '+sy(p.y).toFixed(2)).join(' ')+'"/>').join('');
  const legend=series.map((s,idx)=>'<span><i class="s'+idx+'"></i>'+uEsc(s.label)+'</span>').join('');
  return '<div class="ut-chart"><div class="ut-chart-legend">'+legend+'</div><svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+uEsc(yLabel+' versus '+xLabel)+'"><g class="ut-grid">'+grid+'</g>'+paths+'<text class="ut-axis" x="'+((L+W-R)/2)+'" y="'+(H-8)+'" text-anchor="middle">'+uEsc(xLabel)+'</text><text class="ut-axis" transform="translate(14 '+((T+H-B)/2)+') rotate(-90)" text-anchor="middle">'+uEsc(yLabel)+'</text></svg></div>';
}
function nativeUtubeCard(){
  return '<article class="module-card native-lab-card" data-search="rotating u-tube engineering club fluid threshold hysteresis"><div class="card-top"><div class="module-icon">∪</div><span class="status-pill ready">Ready</span></div><div class="category">Engineering Club · Fluid experiment</div><h4>Rotating U-Tube</h4><p class="desc">Threshold model, capacity decomposition, effective potential, and dynamic hysteresis.</p><div class="card-actions"><button class="primary" data-open-native-utube>Open experiment</button></div></article>';
}
function openNativeUtube(){showView('utube');document.querySelector('[data-utube-tab="setup"]')?.click()}
function readUtubeInputs(){
  const volume=Number(uEl('utVolume').value),rpm=Number(uEl('utRpm').value),rin=Number(uEl('utRin').value)/1000,a=Number(uEl('utRadius').value)/1000,nq=Number(uEl('utNq').value);
  if(!(volume>0&&rpm>0&&rin>0&&a>0&&nq>=12))throw new Error('Use positive geometry/operating values and quadrature ≥ 12.');
  return {volume,rpm,rin,a,nq:Math.round(nq)};
}
function renderNativeUtube(){
  try{
    const {volume,rpm,rin,a,nq}=readUtubeInputs(),nc=utubeCriticalSpeed(rin,a),ng=utubeThreshold(volume,rin,a,nq),cap=utubeCapacity(rpm,rin,a,nq);
    uEl('utMetricCritical').textContent=nc.toFixed(3)+' rpm';
    uEl('utMetricThreshold').textContent=ng.toFixed(3)+' rpm';
    uEl('utMetricMargin').textContent=(rpm-ng).toFixed(3)+' rpm';
    uEl('utMetricCapacity').textContent=cap.total.toFixed(4)+' mL';
    const v0=Math.max(.25,volume*.35),v1=Math.max(6,volume*1.75);
    const vols=Array.from({length:21},(_,i)=>v0+i*(v1-v0)/20);
    uEl('utThresholdChart').innerHTML=utubeLineSvg([{label:'n_g(V)',points:vols.map(v=>({x:v,y:utubeThreshold(v,rin,a,nq)}))}],{xLabel:'Volume (mL)',yLabel:'Threshold (rpm)'});
    const pot=utubePotential(rpm,rin,a);
    uEl('utPotentialChart').innerHTML=utubeLineSvg([{label:'Relative effective potential',points:pot.map(r=>({x:r.theta,y:r.u}))}],{xLabel:'Bend angle (deg)',yLabel:'Relative potential (J/kg)'});
    const total=Math.max(cap.total,1e-12),parts=[{label:'Curved section',value:cap.arc},{label:'Legs',value:cap.legs}];
    uEl('utCapacityBars').innerHTML=parts.map(p=>'<div class="ut-cap-row"><span>'+p.label+'</span><div><i style="width:'+Math.max(0,Math.min(100,p.value/total*100))+'%"></i></div><strong>'+p.value.toFixed(4)+' mL</strong></div>').join('');
    renderNativeUtubeHysteresis(ng);
    uEl('utNativeStatus').textContent='Completed.';
  }catch(e){
    uEl('utNativeStatus').textContent=String(e);
    if(typeof toast==='function')toast(String(e),true);
  }
}
function renderNativeUtubeHysteresis(staticThreshold){
  const rate=Math.max(0,Number(uEl('utRampRate').value)||0),tau=Math.max(0,Number(uEl('utTau').value)||0),half=Math.max(0,Number(uEl('utHalfwidth').value)||0);
  const maxRate=Math.max(1,rate*2),rates=Array.from({length:31},(_,i)=>i*maxRate/30);
  const up=rates.map(r=>({x:r,y:staticThreshold+half+r*tau})),down=rates.map(r=>({x:r,y:staticThreshold-half-r*tau}));
  uEl('utHysteresisChart').innerHTML=utubeLineSvg([{label:'Ramp up',points:up},{label:'Ramp down',points:down}],{xLabel:'Ramp rate (rpm/s)',yLabel:'Command threshold (rpm)'});
  uEl('utLoopWidth').textContent=(2*(half+rate*tau)).toFixed(3)+' rpm';
}

function collectUtubeToolParameters(){
  const base=readUtubeInputs();
  return {
    volumeMl:base.volume,rpm:base.rpm,rinMm:base.rin*1000,radiusMm:base.a*1000,nq:base.nq,
    rhoKgM3:Number(uEl('utRho').value),gammaMnM:Number(uEl('utGamma').value),thetaDeg:Number(uEl('utThetaDeg').value),
    uVolumeMl:Number(uEl('utUVolume').value),uRpm:Number(uEl('utURpm').value),uRinMm:Number(uEl('utURin').value),uRadiusMm:Number(uEl('utURadius').value),
    uncertaintySamples:Number(uEl('utUncertaintySamples').value),uncertaintySeed:Number(uEl('utUncertaintySeed').value),
    elasticityStep:Number(uEl('utElasticityStep').value),
    coarseSpanRpm:Number(uEl('utCoarseSpan').value),coarseStepRpm:Number(uEl('utCoarseStep').value),
    fineSpanRpm:Number(uEl('utFineSpan').value),fineStepRpm:Number(uEl('utFineStep').value)
  };
}
function renderUtubeToolPayload(payload){
  const metrics=payload.metrics||{};
  uEl('utToolMetrics').innerHTML=Object.entries(metrics).slice(0,18).map(([k,val])=>'<div class="native-result-metric"><span>'+uEsc(k.replace(/([A-Z])/g,' $1'))+'</span><strong>'+uEsc(typeof nativeMetricText==='function'?nativeMetricText(val):String(val))+'</strong></div>').join('');
  uEl('utToolCharts').innerHTML=(payload.series||[]).map(s=>{
    const points=(s.x||[]).map((x,i)=>({x:Number(x),y:Number((s.y||[])[i])})).filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));
    return '<article class="native-viz-panel"><div class="native-viz-title"><span>'+uEsc(s.label||s.id)+'</span></div>'+utubeLineSvg([{label:s.label||s.id,points}],{xLabel:s.xLabel||'x',yLabel:s.yLabel||'y'})+'</article>';
  }).join('');
  uEl('utToolTables').innerHTML=(payload.tables||[]).map(t=>{
    const rows=Array.isArray(t.rows)?t.rows:[];if(!rows.length)return '';
    const keys=Object.keys(rows[0]).slice(0,12);
    return '<article class="native-table-panel"><div class="native-viz-title"><span>'+uEsc(t.label||t.id||'Result table')+'</span><small>'+rows.length+' rows</small></div><div class="table-wrap"><table class="research-table"><thead><tr>'+keys.map(k=>'<th>'+uEsc(k)+'</th>').join('')+'</tr></thead><tbody>'+rows.slice(0,120).map(row=>'<tr>'+keys.map(k=>'<td>'+uEsc(typeof nativeMetricText==='function'?nativeMetricText(row[k]):String(row[k]??''))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></article>';
  }).join('');
  uEl('utToolBoundary').textContent=payload.boundary||'';
}
async function runUtubeTool(tool){
  if(!invoke){toast('Experiment execution is available in the desktop build.',true);return}
  const status=uEl('utToolStatus');
  try{
    status.textContent='Running '+tool+'…';
    const parameters=collectUtubeToolParameters();parameters.__tool=tool;
    const payload=await invoke('native_experiment_run',{experimentId:'utube-studio',parameters,mode:'safe'});
    renderUtubeToolPayload(payload);
    status.textContent='Completed '+tool+'.';
  }catch(e){
    status.textContent=String(e);
    if(typeof toast==='function')toast(String(e),true);
  }
}

function bindNativeUtube(){
  document.querySelectorAll('[data-open-native-utube]').forEach(b=>b.onclick=openNativeUtube);
  document.querySelectorAll('[data-utube-tab]').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('[data-utube-tab]').forEach(x=>x.classList.toggle('active',x===b));
    document.querySelectorAll('.utube-panel').forEach(p=>p.hidden=p.dataset.utubePanel!==b.dataset.utubeTab);
  });
  document.querySelectorAll('[data-utube-tool]').forEach(b=>b.onclick=()=>runUtubeTool(b.dataset.utubeTool));
  if(uEl('utOpenFullOriginal'))uEl('utOpenFullOriginal').onclick=()=>openFullOriginalWorkspace('utube-studio');
  if(uEl('utRun'))uEl('utRun').onclick=()=>{
    renderNativeUtube();
    document.querySelector('[data-utube-tab="results"]')?.click();
  };
  if(uEl('backFromUtube'))uEl('backFromUtube').onclick=()=>showView('labs');
}
