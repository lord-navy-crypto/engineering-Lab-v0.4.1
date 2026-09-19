const NATIVE_EXPERIMENTS = Object.freeze([
  {id:'numerical-methods',name:'Numerical Error Analysis',category:'Numerical Physics',icon:'∑',focus:'floating-point error, cancellation, convergence and reliability',stage:'adapter'},
  {id:'ising-monte-carlo',name:'Ising Monte Carlo Lab',category:'Statistical Physics',icon:'▦',focus:'Ising states, Monte Carlo sampling, critical behavior and convergence',stage:'adapter'},
  {id:'random-walk-monte-carlo',name:'Random Walk & Monte Carlo',category:'Stochastic Physics',icon:'⌁',focus:'random walks, QMC comparison, ensemble statistics and uncertainty',stage:'adapter'},
  {id:'nonlinear-chaos',name:'Nonlinear Dynamics & Chaos',category:'Dynamics',icon:'∿',focus:'nonlinear trajectories, Lyapunov structure, maps and bifurcation diagnostics',stage:'adapter'},
  {id:'oscillation-integration',name:'Oscillation & Integration',category:'Dynamics',icon:'≈',focus:'oscillators, ODE integration, frequency response and energy/work balance',stage:'adapter'},
  {id:'radia-magnet-studio',name:'RADIA Magnet Studio',category:'Accelerator Physics',icon:'⊞',focus:'magnet geometry, field solving, manufacturing errors and harmonics',stage:'adapter'},
  {id:'radiation-platform',name:'Radiation Platform',category:'Accelerator Physics',icon:'↯',focus:'magnet → trajectory → radiation, spectra and polarization',stage:'adapter'},
  {id:'kerr-geodesics',name:'Kerr Black Hole Geodesics',category:'Relativity & Astrophysics',icon:'◎',focus:'massive/photon geodesics, invariants, frequencies and verification',stage:'adapter'},
  {id:'solar-system-dynamics',name:'Sun–Jupiter–Saturn Dynamics',category:'Computational Astrophysics',icon:'☉',focus:'barycentric orbital dynamics, long-horizon diagnostics and commensurability',stage:'adapter'},
  {id:'honeycomb-lattice',name:'Multilayer Honeycomb Lattice',category:'Materials & Condensed Matter',icon:'⬡',focus:'lattice dynamics, phonons, defects, strain and transport studies',stage:'adapter'},
  {id:'utube-studio',name:'Rotating U-Tube',category:'Engineering Club · Fluid Experiment',icon:'∪',focus:'thresholds, capacity, uncertainty, robust design, twin and hysteresis',stage:'native'},
  {id:'kerr-shadow',name:'Kerr Shadow Morphology',category:'Relativity & Astrophysics',icon:'◉',focus:'shadow morphology sweeps and analysis',stage:'adapter'},
  {id:'undulator-spectrum',name:'Undulator Spectrum & Beam Broadening',category:'Accelerator Physics',icon:'≋',focus:'undulator spectrum, harmonics and beam-broadening analysis',stage:'adapter'},
  {id:'frequency-response',name:'Frequency Response Studio',category:'Dynamics',icon:'⌇',focus:'frequency-response analysis for supported dynamic models',stage:'adapter'}
]);
const NATIVE_EXPERIMENT_MAP = new Map(NATIVE_EXPERIMENTS.map(x=>[x.id,x]));
let activeNativeExperimentId = null;

function nativeExperimentSpec(id){return NATIVE_EXPERIMENT_MAP.get(id)||null}
function nativeExperimentModuleIds(){return new Set(NATIVE_EXPERIMENTS.filter(x=>x.id!=='utube-studio'&&x.id!=='kerr-shadow'&&x.id!=='undulator-spectrum'&&x.id!=='frequency-response').map(x=>x.id))}
function nativeExperimentCardFor(spec){
  const status=spec.stage==='native'?'Native':'Native shell';
  return '<article class="module-card native-lab-card" data-search="'+uEsc((spec.name+' '+spec.category+' '+spec.focus).toLowerCase())+'"><div class="card-top"><div class="module-icon">'+uEsc(spec.icon)+'</div><span class="status-pill ready">'+status+'</span></div><div class="category">'+uEsc(spec.category)+'</div><h4>'+uEsc(spec.name)+'</h4><p class="desc">'+uEsc(spec.focus)+'.</p><div class="tags"><span class="tag">in-app workspace</span><span class="tag">no iframe</span><span class="tag">native visualization</span></div><div class="card-actions"><button class="primary" data-open-native-experiment="'+uEsc(spec.id)+'">Open experiment</button></div></article>';
}
function nativeExtraExperimentCards(){
  return ['utube-studio','kerr-shadow','undulator-spectrum','frequency-response'].map(id=>nativeExperimentCardFor(nativeExperimentSpec(id))).join('');
}
function nativeModuleCard(m){
  const spec=nativeExperimentSpec(m.id);
  if(!spec)return null;
  const s=statusFor(m), state=s.ready?'Ready':(s.installed?'Installed':'Native shell');
  return '<article class="module-card native-lab-card" data-search="'+uEsc((spec.name+' '+spec.category+' '+spec.focus).toLowerCase())+'"><div class="card-top"><div class="module-icon">'+uEsc(spec.icon)+'</div><span class="status-pill '+(s.ready?'ready':'')+'">'+uEsc(state)+'</span></div><div class="category">'+uEsc(spec.category)+'</div><h4>'+uEsc(spec.name)+'</h4><p class="desc">'+uEsc(spec.focus)+'.</p><div class="tags"><span class="tag">native shell</span><span class="tag">solver-preserving migration</span></div><div class="card-actions"><button class="primary" data-open-native-experiment="'+uEsc(spec.id)+'">Open experiment</button></div></article>';
}
function openNativeExperiment(id){
  if(id==='utube-studio'){openNativeUtube();return}
  const spec=nativeExperimentSpec(id);if(!spec){toast('Unknown native experiment: '+id,true);return}
  activeNativeExperimentId=id;
  showView('experiment');
  renderNativeExperimentShell(spec);
}
function renderNativeExperimentShell(spec){
  uEl('nativeExperimentEyebrow').textContent=spec.category.toUpperCase();
  uEl('nativeExperimentTitle').textContent=spec.name;
  uEl('nativeExperimentSubtitle').textContent=spec.focus+'.';
  uEl('nativeExperimentBadge').textContent='Application workspace · no iframe';
  const cards=[
    ['Model','Scientific parameters and solver state belong to this experiment only.'],
    ['Visualization','Figures render in the Engineering Lab application surface rather than a nested web page.'],
    ['Analysis','Experiment-specific analysis stays scoped to this experiment; shared evidence is linked explicitly.'],
    ['Verification','Convergence, references, uncertainty and validation evidence stay separate from model truth claims.']
  ];
  uEl('nativeExperimentOverview').innerHTML=cards.map((x,i)=>'<article class="native-exp-cap"><span>0'+(i+1)+'</span><h3>'+uEsc(x[0])+'</h3><p>'+uEsc(x[1])+'</p></article>').join('');
  renderNativeMigrationViz(spec);\n  renderNativeExperimentPreview(spec);
  uEl('nativeExperimentStatus').textContent=spec.stage==='native'
    ? 'Native experiment implementation active.'
    : 'Native application shell active. Legacy Streamlit/localhost presentation is not used by this entry; solver adapters are migrated behind this surface.';
}
function renderNativeMigrationViz(spec){
  const nodes=[
    {x:80,y:82,label:'Parameters',sub:'experiment state'},
    {x:280,y:82,label:'Solver adapter',sub:'scientific code'},
    {x:480,y:82,label:'Results',sub:'typed data'},
    {x:680,y:82,label:'Visualization',sub:'native SVG/DOM'},
    {x:480,y:210,label:'Analysis',sub:'scoped tools'},
    {x:680,y:210,label:'Evidence',sub:'explicit handoff'}
  ];
  const edges=[[0,1],[1,2],[2,3],[2,4],[4,5],[3,5]];
  const by=i=>nodes[i];
  const edgeSvg=edges.map(([a,b])=>'<path d="M '+by(a).x+' '+by(a).y+' L '+by(b).x+' '+by(b).y+'"/>').join('');
  const nodeSvg=nodes.map(n=>'<g transform="translate('+n.x+' '+n.y+')"><rect x="-64" y="-28" width="128" height="56" rx="12"/><text y="-2" text-anchor="middle">'+uEsc(n.label)+'</text><text class="sub" y="15" text-anchor="middle">'+uEsc(n.sub)+'</text></g>').join('');
  uEl('nativeExperimentFlow').innerHTML='<svg viewBox="0 0 780 270" role="img" aria-label="'+uEsc(spec.name)+' native experiment architecture"><g class="native-flow-edges">'+edgeSvg+'</g><g class="native-flow-nodes">'+nodeSvg+'</g></svg>';
}
function bindNativeExperimentShell(){
  document.querySelectorAll('[data-open-native-experiment]').forEach(b=>b.onclick=()=>openNativeExperiment(b.dataset.openNativeExperiment));
  if(uEl('backFromNativeExperiment'))uEl('backFromNativeExperiment').onclick=()=>showView('labs');
  document.querySelectorAll('[data-native-exp-tab]').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('[data-native-exp-tab]').forEach(x=>x.classList.toggle('active',x===b));
    document.querySelectorAll('.native-exp-tab-panel').forEach(p=>p.hidden=p.dataset.nativeExpPanel!==b.dataset.nativeExpTab);
  });
}
\n
function nativePreviewSeries(id){
  const linspace=(a,b,n)=>Array.from({length:n},(_,i)=>a+(b-a)*i/(n-1));
  if(id==='numerical-methods'){
    const xs=linspace(-1.5,1.5,121);
    const approx=x=>x-x*x*x/6+x*x*x*x*x/120;
    return {title:'Taylor approximation error preview',xLabel:'x',yLabel:'|sin(x) − T5(x)|',series:[{label:'absolute error',points:xs.map(x=>({x,y:Math.abs(Math.sin(x)-approx(x))}))}],boundary:'Analytic UI sanity preview; authoritative numerical experiments remain solver-owned.'};
  }
  if(id==='ising-monte-carlo'){
    const temps=linspace(.2,5,120);
    return {title:'1-D nearest-neighbor correlation preview',xLabel:'T / J·k⁻¹',yLabel:'tanh(1/T)',series:[{label:'analytic correlation scale',points:temps.map(x=>({x,y:Math.tanh(1/x)}))}],boundary:'Analytic 1-D reference visualization only; it is not the Monte Carlo result or a 2-D criticality claim.'};
  }
  if(id==='random-walk-monte-carlo'){
    const n=linspace(0,200,101);
    return {title:'Random-walk MSD reference',xLabel:'Steps N',yLabel:'Expected MSD',series:[{label:'1-D unbiased E[x²]=N',points:n.map(x=>({x,y:x}))}],boundary:'Reference expectation only; finite ensemble scatter and uncertainty come from the stochastic solver.'};
  }
  if(id==='nonlinear-chaos'){
    let x=.211,points=[];for(let n=0;n<160;n++){x=3.9*x*(1-x);if(n>19)points.push({x:n-20,y:x})}
    return {title:'Chaotic-map sensitivity preview',xLabel:'Iteration',yLabel:'State',series:[{label:'logistic map r=3.9',points}],boundary:'UI-native bounded chaos preview, not a replacement for the Lab’s pendulum/Lyapunov solvers.'};
  }
  if(id==='oscillation-integration'||id==='frequency-response'){
    if(id==='frequency-response'){
      const r=linspace(.05,2.5,160),z=.08;
      return {title:'Second-order frequency-response preview',xLabel:'Frequency ratio ω/ω₀',yLabel:'Amplitude ratio',series:[{label:'|H|',points:r.map(x=>({x,y:1/Math.sqrt((1-x*x)*(1-x*x)+(2*z*x)*(2*z*x))}))}],boundary:'Analytic second-order reference; experiment-specific solver settings remain authoritative.'};
    }
    const t=linspace(0,20,180),z=.08,w=2*Math.PI*.45,wd=w*Math.sqrt(1-z*z);
    return {title:'Damped oscillator preview',xLabel:'Time',yLabel:'x(t)',series:[{label:'analytic response',points:t.map(x=>({x,y:Math.exp(-z*w*x)*Math.cos(wd*x)}))}],boundary:'Analytic reference visualization; numerical integrator comparisons remain solver-owned.'};
  }
  if(id==='radia-magnet-studio'){
    const z=linspace(-50,50,180),b0=.15,period=50;
    return {title:'Ideal undulator field preview',xLabel:'z (mm)',yLabel:'Bᵧ (T)',series:[{label:'ideal Bᵧ',points:z.map(x=>({x,y:b0*Math.sin(2*Math.PI*x/period)}))}],boundary:'Safe analytic field preview only; finite geometry and manufacturing errors require RADIA.'};
  }
  if(id==='radiation-platform'||id==='undulator-spectrum'){
    if(id==='undulator-spectrum'){
      const e=linspace(.72,1.28,180);
      const sinc=x=>Math.abs(x)<1e-10?1:Math.sin(Math.PI*x)/(Math.PI*x);
      return {title:'Finite-period spectral envelope preview',xLabel:'Normalized photon energy E/E₁',yLabel:'Relative intensity',series:[{label:'sinc² envelope',points:e.map(x=>({x,y:sinc(20*(x-1))*sinc(20*(x-1))}))}],boundary:'Normalized finite-period envelope preview, not a full beam-spectrum or detector prediction.'};
    }
    const th=linspace(0,1.2,160),gamma=6000,k=.7,period=.05,hc=1.2398419843320026e-6;
    return {title:'Undulator resonance versus angle',xLabel:'θ (mrad)',yLabel:'Photon energy (eV)',series:[{label:'ideal resonance',points:th.map(x=>{const a=x/1000,lambda=period*(1+k*k/2+(gamma*a)*(gamma*a))/(2*gamma*gamma);return{x,y:hc/lambda}})}],boundary:'Ideal resonance preview; full trajectory, polarization and field-map effects remain solver-owned.'};
  }
  if(id==='kerr-geodesics'){
    const r=linspace(6,30,140);
    return {title:'Relativistic orbital-frequency reference',xLabel:'Radius r/M',yLabel:'Ω·M',series:[{label:'Schwarzschild circular reference',points:r.map(x=>({x,y:1/Math.pow(x,1.5)}))}],boundary:'Schwarzschild circular-orbit reference only; not a Kerr geodesic solution or invariant check.'};
  }
  if(id==='kerr-shadow'){
    const p=linspace(0,2*Math.PI,181),R=3*Math.sqrt(3);
    return {title:'Non-spinning shadow reference',xLabel:'α / M',yLabel:'β / M',series:[{label:'Schwarzschild shadow',points:p.map(t=>({x:R*Math.cos(t),y:R*Math.sin(t)}))}],boundary:'Non-spinning reference circle only; Kerr spin/inclination morphology remains solver-owned.'};
  }
  if(id==='solar-system-dynamics'){
    const t=linspace(0,2*Math.PI,181);
    return {title:'Barycentric orbit-scale schematic',xLabel:'x (normalized)',yLabel:'y (normalized)',series:[
      {label:'Jupiter-scale orbit',points:t.map(a=>({x:1*Math.cos(a),y:1*Math.sin(a)}))},
      {label:'Saturn-scale orbit',points:t.map(a=>({x:1.84*Math.cos(a),y:1.84*Math.sin(a)}))}
    ],boundary:'Normalized orbital-scale schematic; not the N-body integration or 1PN result.'};
  }
  if(id==='honeycomb-lattice'){
    const pts=[];for(let i=-4;i<=4;i++)for(let j=-3;j<=3;j++){const x=1.5*i,y=Math.sqrt(3)*(j+(i%2)*.5);pts.push({x,y});pts.push({x:x+.5,y:y+Math.sqrt(3)/2})}
    return {title:'Honeycomb lattice geometry preview',xLabel:'x (reduced)',yLabel:'y (reduced)',series:[{label:'sites',points:pts}],scatter:true,boundary:'Reduced-coordinate lattice geometry only; phonons, defects, strain and transport remain solver-owned.'};
  }
  return {title:'Native visualization surface',xLabel:'state',yLabel:'value',series:[{label:'preview',points:[{x:0,y:0},{x:1,y:1}]}],boundary:'Visualization adapter pending.'};
}
function nativeScatterSvg(series,{xLabel='',yLabel=''}={}){
  const pts=series.flatMap(s=>s.points);if(!pts.length)return '';
  const W=760,H=280,L=58,R=18,T=18,B=42,xmin=Math.min(...pts.map(p=>p.x)),xmax=Math.max(...pts.map(p=>p.x)),ymin=Math.min(...pts.map(p=>p.y)),ymax=Math.max(...pts.map(p=>p.y));
  const sx=x=>L+(x-xmin)/(Math.max(1e-12,xmax-xmin))*(W-L-R),sy=y=>T+(H-T-B)-(y-ymin)/(Math.max(1e-12,ymax-ymin))*(H-T-B);
  const dots=pts.map(p=>'<circle cx="'+sx(p.x).toFixed(2)+'" cy="'+sy(p.y).toFixed(2)+'" r="2.4"/>').join('');
  return '<div class="ut-chart"><svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+uEsc(yLabel+' versus '+xLabel)+'"><g class="native-scatter">'+dots+'</g><text class="ut-axis" x="'+((L+W-R)/2)+'" y="'+(H-8)+'" text-anchor="middle">'+uEsc(xLabel)+'</text><text class="ut-axis" transform="translate(14 '+((T+H-B)/2)+') rotate(-90)" text-anchor="middle">'+uEsc(yLabel)+'</text></svg></div>';
}
function renderNativeExperimentPreview(spec){
  const preview=nativePreviewSeries(spec.id);
  uEl('nativeExperimentPreviewTitle').textContent=preview.title;
  uEl('nativeExperimentPreviewBoundary').textContent=preview.boundary;
  uEl('nativeExperimentPreview').innerHTML=preview.scatter
    ? nativeScatterSvg(preview.series,{xLabel:preview.xLabel,yLabel:preview.yLabel})
    : utubeLineSvg(preview.series,{xLabel:preview.xLabel,yLabel:preview.yLabel,height:280});
}
