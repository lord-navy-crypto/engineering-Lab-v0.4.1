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
const UTUBE_ORIGINAL_SETUP_GROUPS = Object.freeze([
  {
    title:'Experiment scan & DOE',
    fields:[
      {name:'dataRole',label:'U-tube data role',type:'select',value:'theory',options:['theory','experiment','comparison']},
      {name:'volumeMinMl',label:'Volume min / mL',type:'number',value:.5,min:.05,max:30,step:.05},
      {name:'volumeMaxMl',label:'Volume max / mL',type:'number',value:6,min:.05,max:30,step:.05},
      {name:'volumeSamples',label:'Volume samples',type:'number',value:21,min:3,max:301,step:2},
      {name:'speedMinRpm',label:'Speed min / rpm',type:'number',value:50,min:0,max:2000,step:1},
      {name:'speedMaxRpm',label:'Speed max / rpm',type:'number',value:500,min:1,max:2000,step:1},
      {name:'speedSamples',label:'Speed samples',type:'number',value:31,min:3,max:301,step:2},
      {name:'convergenceVolumesMl',label:'Volumes for convergence study / mL',type:'text',value:'1,2,3,4,5'},
      {name:'scanNRpm',label:'n / rpm',type:'number',value:260,min:0,max:2000,step:1},
      {name:'scanGammaMnM',label:'γ / mN m⁻¹',type:'number',value:72,min:1,max:500,step:.1},
      {name:'scanThetaDeg',label:'θ / deg',type:'number',value:0,min:-180,max:180,step:.5},
      {name:'doeFactors',label:'Factors · name,low,high',type:'textarea',value:'volume_ml,1,5\nrpm,150,350'},
      {name:'doeMethod',label:'DOE',type:'select',value:'latin-hypercube',options:['latin-hypercube','full-factorial','random']},
      {name:'doeSamples',label:'Samples',type:'number',value:24,min:2,max:500,step:1},
      {name:'doeSeed',label:'Seed',type:'number',value:0,min:0,max:2147483647,step:1},
      {name:'projectSource',label:'Project source',type:'select',value:'Current native result',options:['Current native result','Project dataset','Imported dataset']},
      {name:'utubeTask',label:'U-Tube task',type:'select',value:'Threshold map',options:['Threshold map','Capacity map','Convergence study','DOE sweep']}
    ]
  },
  {
    title:'Research physics & inverse design',
    fields:[
      {name:'researchDataset',label:'Research dataset',type:'select',value:'Current native result',options:['Current native result','Imported dataset','Project dataset']},
      {name:'xColumn',label:'X column',type:'text',value:'volume_ml'},
      {name:'yColumn',label:'Y column',type:'text',value:'n_g_rpm'},
      {name:'secondYColumn',label:'Second Y',type:'text',value:''},
      {name:'plotKind',label:'Plot',type:'select',value:'Line',options:['Line','Scatter','Step']},
      {name:'groupSeries',label:'Group / series',type:'text',value:''},
      {name:'sortByX',label:'Sort by X',type:'checkbox',value:true},
      {name:'maxPlottedRows',label:'Max plotted rows',type:'number',value:500,min:10,max:100000,step:10},
      {name:'visibleXRange',label:'Visible X range',type:'text',value:''},
      {name:'overlayTheory',label:'Overlay deterministic U-tube n_g(V) model',type:'checkbox',value:true},
      {name:'modelRinM',label:'Model R_in / m',type:'number',value:.01512,min:.001,max:.1,step:.0001},
      {name:'modelAM',label:'Model a / m',type:'number',value:.00748,min:.0001,max:.05,step:.0001},
      {name:'modelNq',label:'Model quadrature order',type:'number',value:48,min:12,max:128,step:4},
      {name:'advancedNRpm',label:'n / rpm',type:'number',value:260,min:0,max:2000,step:1},
      {name:'rinTextM',label:'R_in / m',type:'text',value:'0.01512'},
      {name:'aTextM',label:'a / m',type:'text',value:'0.00748'},
      {name:'rhoKgM3Original',label:'ρ / kg m⁻³',type:'number',value:997.8,min:100,max:5000,step:.1},
      {name:'gammaMnMOriginal',label:'γ / mN m⁻¹',type:'number',value:72,min:1,max:500,step:.1},
      {name:'volumeOriginalMl',label:'V / mL',type:'number',value:3,min:.05,max:30,step:.05},
      {name:'nearThresholdBandRpm',label:'Near-threshold band / rpm',type:'number',value:3,min:.1,max:50,step:.1},
      {name:'targetThresholdRpm',label:'Target n_g / rpm',type:'number',value:250,min:1,max:1000,step:1},
      {name:'inverseVolumeMl',label:'Volume / mL',type:'number',value:3,min:.05,max:30,step:.05},
      {name:'solveFor',label:'Solve geometry',type:'select',value:'rin_m',options:['rin_m','a_m']},
      {name:'geometryLowerM',label:'Lower bound / m',type:'number',value:.001,min:.0001,max:.1,step:.0001},
      {name:'geometryUpperM',label:'Upper bound / m',type:'number',value:.05,min:.0002,max:.2,step:.0001},
      {name:'elasticityVolumeMl',label:'Elasticity volume / mL',type:'number',value:3,min:.05,max:30,step:.05},
      {name:'designVolumesMl',label:'Volumes / mL',type:'text',value:'1,2,3,4,5'},
      {name:'optionalTargetRpm',label:'Optional target n_g / rpm',type:'number',value:250,min:1,max:1000,step:1},
      {name:'planningVolumeMl',label:'Planning volume / mL',type:'number',value:3,min:.05,max:30,step:.05},
      {name:'planningNq',label:'Planning quadrature order',type:'number',value:48,min:12,max:128,step:4}
    ]
  },
  {
    title:'Uncertainty & theory ↔ experiment',
    fields:[
      {name:'uGeneric',label:'u({label})',type:'number',value:.1,min:0,max:100,step:.01},
      {name:'mcSamplesOriginal',label:'Monte Carlo samples',type:'number',value:300,min:50,max:100000,step:50},
      {name:'mcSeedOriginal',label:'Seed',type:'number',value:0,min:0,max:2147483647,step:1},
      {name:'predictiveOutput',label:'Predictive output',type:'select',value:'n_g_rpm',options:['n_g_rpm','n_c_rpm','capacity_ml']},
      {name:'budgetOutput',label:'Output for local budget',type:'select',value:'n_g_rpm',options:['n_g_rpm','n_c_rpm','capacity_ml']},
      {name:'experimentalDataset',label:'Experimental dataset',type:'select',value:'Current native result',options:['Current native result','Project dataset','Imported dataset']},
      {name:'compareVolumeMl',label:'Compare volume / mL',type:'select',value:'3',options:['1','2','3','4','5']}
    ]
  },
  {
    title:'Robust design & adaptive experiment',
    fields:[
      {name:'nominalVText',label:'Nominal V / mL',type:'text',value:'3'},
      {name:'nominalRinText',label:'Nominal R_in / m',type:'text',value:'0.01512'},
      {name:'nominalAText',label:'Nominal a / m',type:'text',value:'0.00748'},
      {name:'tolVMl',label:'±V tolerance / mL',type:'number',value:.05,min:0,max:10,step:.01},
      {name:'tolRinM',label:'±R_in tolerance / m',type:'number',value:.0002,min:0,max:.01,step:.00001},
      {name:'tolAM',label:'±a tolerance / m',type:'number',value:.0001,min:0,max:.01,step:.00001},
      {name:'robustTargetRpm',label:'Target n_g / rpm',type:'number',value:250,min:1,max:1000,step:1},
      {name:'robustPlanningVMl',label:'Planning V / mL',type:'number',value:3,min:.05,max:30,step:.05},
      {name:'robustNq',label:'Quadrature order',type:'number',value:48,min:12,max:128,step:4},
      {name:'empiricalBracketRpm',label:'Target empirical bracket / rpm',type:'number',value:10,min:.1,max:200,step:.5},
      {name:'observedClassifications',label:'Observed classifications · rpm,below / rpm,above',type:'textarea',value:'245,below\n255,above'},
      {name:'thresholdToleranceRpm',label:'Threshold tolerance / rpm',type:'number',value:2,min:.01,max:100,step:.1},
      {name:'minGapRpm',label:'Minimum n_g−n_c / rpm',type:'number',value:5,min:-100,max:500,step:.1},
      {name:'maxNumericalDeltaRpm',label:'Max numerical Δn_g / rpm',type:'number',value:1,min:0,max:100,step:.1}
    ]
  },
  {
    title:'Digital twin',
    fields:[
      {name:'twinDataset',label:'Twin dataset',type:'select',value:'Current native result',options:['Current native result','Project dataset','Imported dataset']},
      {name:'twinVolumeColumn',label:'V / mL',type:'text',value:'volume_ml'},
      {name:'twinObservedNgColumn',label:'Observed n_g / rpm',type:'text',value:'observed_n_g_rpm'},
      {name:'twinRinM',label:'R_in / m',type:'number',value:.01512,min:.001,max:.1,step:.0001},
      {name:'twinAM',label:'a / m',type:'number',value:.00748,min:.0001,max:.05,step:.0001},
      {name:'twinNq',label:'nq',type:'number',value:48,min:12,max:128,step:4},
      {name:'timeColumn',label:'Time / s',type:'text',value:'time_s'},
      {name:'commandRpmColumn',label:'Command RPM',type:'text',value:'command_rpm'},
      {name:'measuredRpmColumn',label:'Measured RPM',type:'text',value:'measured_rpm'},
      {name:'tauMinS',label:'τ min / s',type:'number',value:.01,min:0,max:100,step:.01},
      {name:'tauMaxS',label:'τ max / s',type:'number',value:5,min:.01,max:100,step:.01}
    ]
  },
  {
    title:'Hysteresis & rate envelope',
    fields:[
      {name:'rampDataset',label:'Ramp dataset',type:'select',value:'Current native result',options:['Current native result','Project dataset','Imported dataset']},
      {name:'hystVolumeColumn',label:'Volume / mL',type:'text',value:'volume_ml'},
      {name:'hystRateColumn',label:'|dn/dt| / rpm s⁻¹',type:'text',value:'ramp_rate_rpm_s'},
      {name:'spinUpColumn',label:'Spin-up threshold / rpm',type:'text',value:'spin_up_rpm'},
      {name:'spinDownColumn',label:'Spin-down threshold / rpm',type:'text',value:'spin_down_rpm'},
      {name:'hystRinM',label:'R_in / m',type:'number',value:.01512,min:.001,max:.1,step:.0001},
      {name:'hystAM',label:'a / m',type:'number',value:.00748,min:.0001,max:.05,step:.0001},
      {name:'hystNq',label:'Quadrature order',type:'number',value:48,min:12,max:128,step:4},
      {name:'predictionVMl',label:'Prediction V / mL',type:'number',value:3,min:.05,max:30,step:.05},
      {name:'empiricalHRpm',label:'Empirical H / rpm',type:'number',value:2,min:0,max:100,step:.1},
      {name:'rateLagTauS',label:'Rate-lag τ / s',type:'number',value:.35,min:0,max:100,step:.01},
      {name:'rampRatesText',label:'Ramp rates / rpm s⁻¹',type:'text',value:'0.5,1,2,4,8'},
      {name:'predictionRinM',label:'Prediction R_in / m',type:'number',value:.01512,min:.001,max:.1,step:.0001},
      {name:'predictionAM',label:'Prediction a / m',type:'number',value:.00748,min:.0001,max:.05,step:.0001},
      {name:'predictionNq',label:'Prediction nq',type:'number',value:48,min:12,max:128,step:4}
    ]
  }
]);

function utubeExtendedFieldHtml(field){
  const id='utx_'+field.name;
  const label=uEsc(field.label);
  if(field.type==='checkbox') return '<label class="native-check professional-check"><input id="'+id+'" data-utube-extra="'+uEsc(field.name)+'" type="checkbox" '+(field.value?'checked':'')+'><span>'+label+'</span></label>';
  if(field.type==='select') return '<label>'+label+'<select id="'+id+'" data-utube-extra="'+uEsc(field.name)+'">'+field.options.map(v=>'<option '+(String(v)===String(field.value)?'selected':'')+'>'+uEsc(v)+'</option>').join('')+'</select></label>';
  if(field.type==='textarea') return '<label>'+label+'<textarea id="'+id+'" data-utube-extra="'+uEsc(field.name)+'" rows="3">'+uEsc(field.value||'')+'</textarea></label>';
  if(field.type==='text') return '<label>'+label+'<input id="'+id+'" data-utube-extra="'+uEsc(field.name)+'" type="text" value="'+uEsc(field.value||'')+'"></label>';
  return '<label>'+label+'<input id="'+id+'" data-utube-extra="'+uEsc(field.name)+'" type="number" value="'+uEsc(field.value)+'" min="'+uEsc(field.min??'')+'" max="'+uEsc(field.max??'')+'" step="'+uEsc(field.step??'any')+'"></label>';
}

function renderUtubeExtendedSetup(){
  const host=uEl('utubeExtendedSetup'); if(!host)return;
  host.innerHTML=UTUBE_ORIGINAL_SETUP_GROUPS.map((group,index)=>'<section class="parameter-section"><div class="parameter-section-heading"><span>'+String(index+5).padStart(2,'0')+'</span><div><strong>'+uEsc(group.title)+'</strong><small>'+group.fields.length+' Original Workspace controls</small></div></div><div class="native-control-grid professional-control-grid">'+group.fields.map(utubeExtendedFieldHtml).join('')+'</div></section>').join('');
  const extraCount=UTUBE_ORIGINAL_SETUP_GROUPS.reduce((sum,g)=>sum+g.fields.length,0);
  if(uEl('utubeSetupCount'))uEl('utubeSetupCount').textContent=String(22+extraCount);
}

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
  const out={
    volumeMl:base.volume,rpm:base.rpm,rinMm:base.rin*1000,radiusMm:base.a*1000,nq:base.nq,
    rhoKgM3:Number(uEl('utRho').value),gammaMnM:Number(uEl('utGamma').value),thetaDeg:Number(uEl('utThetaDeg').value),
    uVolumeMl:Number(uEl('utUVolume').value),uRpm:Number(uEl('utURpm').value),uRinMm:Number(uEl('utURin').value),uRadiusMm:Number(uEl('utURadius').value),
    uncertaintySamples:Number(uEl('utUncertaintySamples').value),uncertaintySeed:Number(uEl('utUncertaintySeed').value),
    elasticityStep:Number(uEl('utElasticityStep').value),
    coarseSpanRpm:Number(uEl('utCoarseSpan').value),coarseStepRpm:Number(uEl('utCoarseStep').value),
    fineSpanRpm:Number(uEl('utFineSpan').value),fineStepRpm:Number(uEl('utFineStep').value),
    responseTau:Number(uEl('utTau').value),quasiStaticHalfwidth:Number(uEl('utHalfwidth').value)
  };
  document.querySelectorAll('#utubeExtendedSetup [data-utube-extra]').forEach(node=>{
    const key=node.dataset.utubeExtra;
    if(node.type==='checkbox')out[key]=node.checked;
    else if(node.type==='number'){const value=Number(node.value);out[key]=Number.isFinite(value)?value:null}
    else out[key]=node.value;
  });
  return out;
}

function renderUtubePayload(payload,targets){
  const metrics=payload.metrics||{};
  uEl(targets.metrics).innerHTML=Object.entries(metrics).slice(0,24).map(([k,val])=>'<div class="native-result-metric"><span>'+uEsc(k.replace(/([A-Z])/g,' $1'))+'</span><strong>'+uEsc(typeof nativeMetricText==='function'?nativeMetricText(val):String(val))+'</strong></div>').join('');
  uEl(targets.charts).innerHTML=(payload.series||[]).map(series=>{
    const points=(series.x||[]).map((x,i)=>({x:Number(x),y:Number((series.y||[])[i])})).filter(point=>Number.isFinite(point.x)&&Number.isFinite(point.y));
    return '<article class="native-viz-panel"><div class="native-viz-title"><span>'+uEsc(series.label||series.id)+'</span></div>'+utubeLineSvg([{label:series.label||series.id,points}],{xLabel:series.xLabel||'x',yLabel:series.yLabel||'y'})+'</article>';
  }).join('');
  uEl(targets.tables).innerHTML=(payload.tables||[]).map(table=>{
    const rows=Array.isArray(table.rows)?table.rows:[];if(!rows.length)return '';
    const keys=Object.keys(rows[0]).slice(0,14);
    return '<article class="native-table-panel"><div class="native-viz-title"><span>'+uEsc(table.label||table.id||'Result table')+'</span><small>'+rows.length+' rows</small></div><div class="table-wrap"><table class="research-table"><thead><tr>'+keys.map(k=>'<th>'+uEsc(k)+'</th>').join('')+'</tr></thead><tbody>'+rows.slice(0,160).map(row=>'<tr>'+keys.map(k=>'<td>'+uEsc(typeof nativeMetricText==='function'?nativeMetricText(row[k]):String(row[k]??''))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></article>';
  }).join('');
  if(targets.boundary)uEl(targets.boundary).textContent=payload.boundary||'';
  if(targets.backend)uEl(targets.backend).textContent=payload.backend||'scientific adapter';
  if(targets.empty)uEl(targets.empty).hidden=true;
}

function renderUtubeToolPayload(payload){
  renderUtubePayload(payload,{metrics:'utToolMetrics',charts:'utToolCharts',tables:'utToolTables',boundary:'utToolBoundary'});
}

function renderUtubeVerificationPayload(payload){
  renderUtubePayload(payload,{metrics:'utVerificationMetrics',charts:'utVerificationCharts',tables:'utVerificationTables',boundary:'utVerificationBoundary',backend:'utVerificationBackend',empty:'utVerificationEmpty'});
}

async function runUtubeTool(tool){
  if(!invoke){toast('Experiment execution is available in the desktop build.',true);return}
  const status=uEl('utToolStatus');
  try{
    status.textContent='Running '+tool+'…';
    const parameters=collectUtubeToolParameters();parameters.__tool=tool;
    const payload=await invoke('native_experiment_run',{experimentId:'utube-studio',parameters,mode:'safe'});
    renderUtubeToolPayload(payload);
    status.textContent='Completed '+tool+'. Analysis output remains in Tools & Analysis.';
  }catch(e){
    status.textContent=String(e);
    if(typeof toast==='function')toast(String(e),true);
  }
}

async function runUtubeVerificationTool(tool){
  if(!invoke){toast('Experiment execution is available in the desktop build.',true);return}
  const status=uEl('utNativeStatus');
  try{
    status.textContent='Running verification '+tool+'…';
    const parameters=collectUtubeToolParameters();parameters.__tool=tool;
    const payload=await invoke('native_experiment_run',{experimentId:'utube-studio',parameters,mode:'safe'});
    renderUtubeVerificationPayload(payload);
    status.textContent='Completed verification '+tool+'.';
  }catch(e){
    status.textContent=String(e);
    if(typeof toast==='function')toast(String(e),true);
  }
}

function bindUtubeProfessionalSliders(){
  document.querySelectorAll('#utubeView [data-utube-panel="setup"] input[type="number"]').forEach(input=>{
    if(/seed/i.test(input.id))return;
    const min=Number(input.min),max=Number(input.max);
    if(!Number.isFinite(min)||!Number.isFinite(max)||!(max>min))return;
    if(input.dataset.sliderBound)return;
    input.dataset.sliderBound='1';
    const wrap=document.createElement('div');
    wrap.className='utube-range-wrap';
    const range=document.createElement('input');
    range.type='range';
    range.className='param-range';
    range.dataset.rangeFor=input.id;
    const log=min>0&&max/min>=1000;
    range.dataset.rangeMode=log?'log':'linear';
    range.min=String(log?Math.log10(min):min);
    range.max=String(log?Math.log10(max):max);
    range.step=String(log?.001:(Number(input.step)||.01));
    range.value=String(log?Math.log10(Math.max(min,Number(input.value))):Number(input.value));
    const readout=document.createElement('span');
    readout.className='param-value-tag';
    readout.textContent=input.value;
    wrap.append(range,readout);
    input.insertAdjacentElement('afterend',wrap);
    const syncFromNumber=()=>{
      const value=Number(input.value);
      if(!Number.isFinite(value))return;
      range.value=String(log&&value>0?Math.log10(value):value);
      readout.textContent=input.value;
    };
    input.addEventListener('input',syncFromNumber);
    range.addEventListener('input',()=>{
      let value=Number(range.value);
      if(log)value=10**value;
      input.value=(Math.abs(value)>=1e5||Math.abs(value)<1e-5&&value!==0)?value.toExponential(8):String(Number(value.toPrecision(9)));
      readout.textContent=input.value;
    });
  });
}

function bindNativeUtube(){
  document.querySelectorAll('[data-open-native-utube]').forEach(b=>b.onclick=openNativeUtube);
  document.querySelectorAll('[data-utube-tab]').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('[data-utube-tab]').forEach(x=>x.classList.toggle('active',x===b));
    document.querySelectorAll('.utube-panel').forEach(p=>p.hidden=p.dataset.utubePanel!==b.dataset.utubeTab);
  });
  document.querySelectorAll('[data-utube-tool]').forEach(b=>b.onclick=()=>runUtubeTool(b.dataset.utubeTool));
  document.querySelectorAll('[data-utube-verification-tool]').forEach(b=>b.onclick=()=>runUtubeVerificationTool(b.dataset.utubeVerificationTool));
  if(uEl('utOpenFullOriginal'))uEl('utOpenFullOriginal').onclick=()=>openFullOriginalWorkspace('utube-studio');
  if(uEl('utVerificationOpenOriginal'))uEl('utVerificationOpenOriginal').onclick=()=>openFullOriginalWorkspace('utube-studio');
  renderUtubeExtendedSetup();
  bindUtubeProfessionalSliders();
  if(uEl('utRun'))uEl('utRun').onclick=()=>{
    renderNativeUtube();
    document.querySelector('[data-utube-tab="results"]')?.click();
  };
  if(uEl('backFromUtube'))uEl('backFromUtube').onclick=()=>showView('labs');
}
