
const FULL_ORIGINAL_WORKSPACE_PROFILE = Object.freeze({
  'numerical-methods':'numerical-methods',
  'ising-monte-carlo':'ising-monte-carlo',
  'random-walk-monte-carlo':'random-walk-monte-carlo',
  'nonlinear-chaos':'nonlinear-chaos',
  'oscillation-integration':'oscillation-integration',
  'radia-magnet-studio':'radia-magnet-studio',
  'radiation-platform':'radiation-platform',
  'kerr-geodesics':'kerr-geodesics',
  'solar-system-dynamics':'solar-system-dynamics',
  'honeycomb-lattice':'honeycomb-lattice',
  'utube-studio':'oscillation-integration',
  'kerr-shadow':'kerr-geodesics',
  'undulator-spectrum':'radiation-platform',
  'frequency-response':'oscillation-integration'
});
async function openFullOriginalWorkspace(experimentId){
  if(!invoke){toast('Full Original Workspace is available in the desktop build.',true);return}
  const moduleId=FULL_ORIGINAL_WORKSPACE_PROFILE[experimentId];
  if(!moduleId){toast('No compatibility profile is mapped for '+experimentId,true);return}
  const m=modules.find(x=>x.id===moduleId);
  if(!m){toast('Compatibility module is not registered: '+moduleId,true);return}
  try{
    const requested=selectedModes[moduleId]||'safe';
    const info=await invoke('launch_module',{moduleId,mode:requested});
    activeModule=moduleId;
    activeMode=info.mode||requested;
    el('openLabTitle').textContent=m.name+' · Full Original Workspace';
    el('openLabUrl').textContent=info.url;
    el('labFrame').src=info.url;
    showView('lab');
  }catch(e){toast(String(e),true)}
}

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
  return '<article class="module-card native-lab-card" data-search="'+uEsc((spec.name+' '+spec.category+' '+spec.focus).toLowerCase())+'"><div class="card-top"><div class="module-icon">'+uEsc(spec.icon)+'</div><span class="status-pill ready">Ready</span></div><div class="category">'+uEsc(spec.category)+'</div><h4>'+uEsc(spec.name)+'</h4><p class="desc">'+uEsc(spec.focus)+'.</p><div class="card-actions"><button class="primary" data-open-native-experiment="'+uEsc(spec.id)+'">Open experiment</button></div></article>';
}
function nativeExtraExperimentCards(){
  return ['utube-studio','kerr-shadow','undulator-spectrum','frequency-response'].map(id=>nativeExperimentCardFor(nativeExperimentSpec(id))).join('');
}
function nativeModuleCard(m){
  const spec=nativeExperimentSpec(m.id);
  if(!spec)return null;
  const state=statusFor(m);
  const label=state.ready?'Ready':(state.installed?'Installed':'Setup needed');
  return '<article class="module-card native-lab-card" data-search="'+uEsc((spec.name+' '+spec.category+' '+spec.focus).toLowerCase())+'"><div class="card-top"><div class="module-icon">'+uEsc(spec.icon)+'</div><span class="status-pill '+(state.ready?'ready':'')+'">'+uEsc(label)+'</span></div><div class="category">'+uEsc(spec.category)+'</div><h4>'+uEsc(spec.name)+'</h4><p class="desc">'+uEsc(spec.focus)+'.</p><div class="card-actions"><button class="primary" data-open-native-experiment="'+uEsc(spec.id)+'">Open experiment</button></div></article>';
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
  renderNativeExperimentControls(spec);
  document.querySelector('[data-native-exp-tab="setup"]')?.click();
  uEl('nativeExperimentStatus').textContent='Ready.';
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
  if(uEl('capabilitySearch')&&!uEl('capabilitySearch').dataset.bound){uEl('capabilitySearch').dataset.bound='1';uEl('capabilitySearch').addEventListener('input',renderCapabilityCatalog)}

  document.querySelectorAll('[data-open-native-experiment]').forEach(b=>b.onclick=()=>openNativeExperiment(b.dataset.openNativeExperiment));
  if(uEl('backFromNativeExperiment'))uEl('backFromNativeExperiment').onclick=()=>showView('labs');
  if(uEl('nativeExperimentRun'))uEl('nativeExperimentRun').onclick=runNativeExperiment;
  document.querySelectorAll('[data-native-exp-tab]').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('[data-native-exp-tab]').forEach(x=>x.classList.toggle('active',x===b));
    document.querySelectorAll('.native-exp-tab-panel').forEach(p=>p.hidden=p.dataset.nativeExpPanel!==b.dataset.nativeExpTab);
  });
}

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


const NATIVE_PARAMETER_SCHEMAS = Object.freeze({
  'numerical-methods':[
    {name:'xMax',label:'Domain ±x',type:'number',value:2.5,min:.2,max:8,step:.1},
    {name:'order',label:'Taylor order',type:'number',value:9,min:1,max:19,step:2},
    {name:'points',label:'Samples',type:'number',value:401,min:81,max:2001,step:40}
  ],
  'ising-monte-carlo':[
    {name:'size',label:'Lattice L×L',type:'number',value:24,min:6,max:64,step:2},
    {name:'temperature',label:'Temperature T/J',type:'number',value:2.269,min:.05,max:8,step:.05},
    {name:'sweeps',label:'MC sweeps',type:'number',value:160,min:20,max:1200,step:20},
    {name:'seed',label:'Seed',type:'number',value:12345,min:0,max:2147483647,step:1}
  ],
  'random-walk-monte-carlo':[
    {name:'steps',label:'Steps',type:'number',value:400,min:20,max:5000,step:20},
    {name:'walkers',label:'Walkers',type:'number',value:1500,min:50,max:12000,step:50},
    {name:'dimension',label:'Dimension',type:'select',value:'2',options:['1','2','3']},
    {name:'seed',label:'Seed',type:'number',value:20260919,min:0,max:2147483647,step:1}
  ],
  'nonlinear-chaos':[
    {name:'duration',label:'Duration',type:'number',value:80,min:5,max:400,step:5},
    {name:'dt',label:'Time step',type:'number',value:.02,min:.001,max:.1,step:.001},
    {name:'damping',label:'Damping',type:'number',value:.2,min:0,max:4,step:.02},
    {name:'drive',label:'Drive amplitude',type:'number',value:1.2,min:0,max:5,step:.05},
    {name:'driveOmega',label:'Drive ω',type:'number',value:.6666667,min:.05,max:5,step:.01},
    {name:'theta0',label:'Initial θ',type:'number',value:.2,min:-3.14159,max:3.14159,step:.05}
  ],
  'oscillation-integration':[
    {name:'duration',label:'Duration',type:'number',value:30,min:1,max:300,step:1},
    {name:'dt',label:'Time step',type:'number',value:.01,min:.0005,max:.1,step:.001},
    {name:'omega0',label:'Natural ω₀',type:'number',value:2,min:.05,max:20,step:.05},
    {name:'zeta',label:'Damping ζ',type:'number',value:.08,min:0,max:2,step:.01},
    {name:'force',label:'Force amplitude',type:'number',value:.6,min:0,max:20,step:.05},
    {name:'driveOmega',label:'Drive ω',type:'number',value:1.6,min:0,max:20,step:.05}
  ],
  'radia-magnet-studio':[
    {name:'periodMm',label:'Period λu (mm)',type:'number',value:50,min:1,max:1000,step:.5},
    {name:'b0T',label:'Peak B₀ (T)',type:'number',value:.15,min:0,max:20,step:.01},
    {name:'periods',label:'Periods',type:'number',value:20,min:1,max:500,step:1},
    {name:'samples',label:'Field samples',type:'number',value:401,min:81,max:3001,step:40}
  ],
  'radiation-platform':[
    {name:'periodMm',label:'Period λu (mm)',type:'number',value:50,min:1,max:1000,step:.5},
    {name:'K',label:'Undulator K',type:'number',value:.7003,min:0,max:50,step:.01},
    {name:'energyGeV',label:'Electron energy (GeV)',type:'number',value:3,min:.001,max:1000,step:.1},
    {name:'harmonic',label:'Harmonic',type:'number',value:1,min:1,max:99,step:2},
    {name:'periods',label:'Periods',type:'number',value:20,min:2,max:500,step:1}
  ],
  'kerr-geodesics':[
    {name:'spin',label:'Spin a/M',type:'number',value:.7,min:0,max:.995,step:.01},
    {name:'inclinationDeg',label:'Inclination (deg)',type:'number',value:25,min:0,max:89,step:1},
    {name:'particleType',label:'Particle',type:'select',value:'massive',options:['massive','photon']},
    {name:'periapsis',label:'Periapsis r/M',type:'number',value:6.5,min:2.1,max:80,step:.1},
    {name:'apoapsis',label:'Apoapsis r/M',type:'number',value:10,min:2.2,max:150,step:.1},
    {name:'lambdaMax',label:'Mino span',type:'number',value:16,min:1,max:80,step:1},
    {name:'samples',label:'Samples',type:'number',value:1000,min:200,max:4000,step:100}
  ],
  'solar-system-dynamics':[
    {name:'durationYears',label:'Duration (yr)',type:'number',value:30,min:.05,max:200,step:1},
    {name:'samples',label:'Samples',type:'number',value:900,min:100,max:5000,step:100},
    {name:'inclinationDeg',label:'Jupiter inclination',type:'number',value:10,min:0,max:60,step:1},
    {name:'saturnBackreaction',label:'Saturn backreaction',type:'checkbox',value:true},
    {name:'solar1pn',label:'Solar 1PN approximation',type:'checkbox',value:false},
    {name:'maxStepYears',label:'Max step (yr)',type:'number',value:.04,min:.001,max:.5,step:.005}
  ],
  'honeycomb-lattice':[
    {name:'nx',label:'Cells nx',type:'number',value:3,min:2,max:7,step:1},
    {name:'ny',label:'Cells ny',type:'number',value:3,min:2,max:7,step:1},
    {name:'layers',label:'Layers',type:'number',value:2,min:1,max:4,step:1},
    {name:'stacking',label:'Stacking',type:'select',value:'ABA',options:['AA','ABA','ABC']},
    {name:'strainX',label:'x strain',type:'number',value:0,min:-.2,max:.2,step:.01},
    {name:'driveAmplitude',label:'Drive amplitude',type:'number',value:.08,min:0,max:1,step:.01},
    {name:'driveFrequency',label:'Drive frequency',type:'number',value:1,min:.01,max:10,step:.05},
    {name:'duration',label:'Duration',type:'number',value:8,min:1,max:40,step:1}
  ],
  'kerr-shadow':[
    {name:'spin',label:'Spin a/M',type:'number',value:.9,min:0,max:.98,step:.01},
    {name:'inclinationDeg',label:'Inclination (deg)',type:'number',value:60,min:.5,max:90,step:1},
    {name:'curveSamples',label:'Curve samples',type:'number',value:320,min:120,max:1200,step:40}
  ],
  'undulator-spectrum':[
    {name:'periodMm',label:'Period λu (mm)',type:'number',value:50,min:1,max:1000,step:.5},
    {name:'gamma',label:'Lorentz γ',type:'number',value:6000,min:2,max:10000000,step:100},
    {name:'K',label:'Undulator K',type:'number',value:.7,min:0,max:20,step:.01},
    {name:'periods',label:'Periods',type:'number',value:20,min:2,max:500,step:1},
    {name:'harmonic',label:'Angular-map harmonic',type:'number',value:1,min:1,max:15,step:2},
    {name:'thetaMaxMrad',label:'θ max (mrad)',type:'number',value:1,min:.05,max:10,step:.05}
  ],
  'frequency-response':[
    {name:'omegaN',label:'Natural ωₙ',type:'number',value:2,min:.1,max:20,step:.05},
    {name:'zeta',label:'Damping ζ',type:'number',value:.05,min:0,max:1,step:.01},
    {name:'force',label:'Force amplitude',type:'number',value:1,min:0,max:20,step:.1},
    {name:'frequencyStart',label:'ω start',type:'number',value:.6,min:.05,max:20,step:.05},
    {name:'frequencyStop',label:'ω stop',type:'number',value:3.2,min:.1,max:30,step:.05},
    {name:'frequencyPoints',label:'Frequency points',type:'number',value:17,min:7,max:41,step:2}
  ]
});

const NATIVE_ADVANCED_PARAMETER_SCHEMAS = Object.freeze({
  'kerr-geodesics':[
    {name:'rtol',label:'Relative tolerance',type:'number',value:1e-9,min:1e-13,max:1e-5,step:1e-10},
    {name:'atol',label:'Absolute tolerance',type:'number',value:1e-11,min:1e-15,max:1e-7,step:1e-12},
    {name:'horizonPad',label:'Horizon guard pad',type:'number',value:1e-4,min:1e-8,max:.1,step:1e-4}
  ],
  'solar-system-dynamics':[
    {name:'saturnInclinationFactor',label:'Saturn inclination factor',type:'number',value:.25,min:0,max:1,step:.05},
    {name:'velocityCross',label:'Velocity-cross perturbation',type:'checkbox',value:false},
    {name:'radialDrag',label:'Radial drag perturbation',type:'checkbox',value:false},
    {name:'velocityCrossStrength',label:'Velocity-cross strength',type:'number',value:1e-4,min:0,max:1e-2,step:1e-5},
    {name:'radialDragStrength',label:'Radial drag strength',type:'number',value:1e-8,min:0,max:1e-5,step:1e-8},
    {name:'omegaZPerYear',label:'ωz / year',type:'number',value:.1,min:0,max:10,step:.05},
    {name:'rtol',label:'Relative tolerance',type:'number',value:1e-10,min:1e-13,max:1e-5,step:1e-11},
    {name:'atol',label:'Absolute tolerance',type:'number',value:1e-12,min:1e-15,max:1e-7,step:1e-13},
    {name:'ftleD0',label:'FTLE initial separation',type:'number',value:1e-8,min:1e-12,max:1e-3,step:1e-8},
    {name:'ftleSegmentYears',label:'FTLE segment (yr)',type:'number',value:2,min:.05,max:20,step:.25},
    {name:'ftleMaxYears',label:'FTLE max years',type:'number',value:30,min:.1,max:200,step:1}
  ],
  'honeycomb-lattice':[
    {name:'bondLength',label:'Bond length',type:'number',value:1,min:.05,max:20,step:.05},
    {name:'layerSpacing',label:'Layer spacing',type:'number',value:.35,min:.01,max:10,step:.01},
    {name:'mass',label:'Mass',type:'number',value:1,min:1e-6,max:1e6,step:.1},
    {name:'kIn',label:'In-plane stiffness',type:'number',value:10,min:1e-6,max:1e6,step:.1},
    {name:'alpha',label:'In-plane nonlinearity α',type:'number',value:2,min:0,max:10000,step:.1},
    {name:'kInter',label:'Interlayer stiffness',type:'number',value:3,min:1e-6,max:1e6,step:.1},
    {name:'betaInter',label:'Interlayer nonlinearity β',type:'number',value:1,min:0,max:10000,step:.1},
    {name:'interlayerDamping',label:'Interlayer damping',type:'number',value:.01,min:0,max:10,step:.01},
    {name:'defectMode',label:'Defect mode',type:'select',value:'none',options:['none','mass','weak-bond','line-weak-bond']},
    {name:'defectMassMultiplier',label:'Defect mass multiplier',type:'number',value:2,min:0,max:100,step:.1},
    {name:'defectBondScale',label:'Defect bond scale',type:'number',value:.4,min:0,max:10,step:.05},
    {name:'driveMode',label:'Drive mode',type:'select',value:'sin',options:['none','sin','pulse','beat','chirp']},
    {name:'uniformForceX',label:'Uniform force x',type:'number',value:0,min:-100,max:100,step:.01},
    {name:'stochasticMode',label:'Langevin stochastic mode',type:'checkbox',value:false},
    {name:'temperatureReduced',label:'Reduced temperature',type:'number',value:0,min:0,max:100,step:.01},
    {name:'seed',label:'Seed',type:'number',value:12345,min:0,max:2147483647,step:1},
    {name:'initialDisplacement',label:'Initial displacement',type:'number',value:.01,min:0,max:10,step:.01},
    {name:'samples',label:'Samples',type:'number',value:420,min:64,max:20000,step:20},
    {name:'rtol',label:'Relative tolerance',type:'number',value:1e-9,min:1e-13,max:1e-5,step:1e-10},
    {name:'atol',label:'Absolute tolerance',type:'number',value:1e-11,min:1e-15,max:1e-7,step:1e-12},
    {name:'maxStep',label:'Max step',type:'number',value:.03,min:.0001,max:1,step:.005},
    {name:'langevinDt',label:'Langevin dt',type:'number',value:.005,min:.00001,max:.2,step:.001},
    {name:'phononPointsPerSegment',label:'Phonon points/segment',type:'number',value:24,min:8,max:100,step:4},
    {name:'phononQGrid',label:'Phonon DOS q-grid',type:'number',value:12,min:4,max:80,step:2},
    {name:'phononBins',label:'Phonon DOS bins',type:'number',value:80,min:16,max:240,step:8}
  ],
  'undulator-spectrum':[
    {name:'angularPoints',label:'Angular map points',type:'number',value:61,min:21,max:181,step:10},
    {name:'relativeEnergySpreadRms',label:'Relative energy spread RMS',type:'number',value:.001,min:0,max:.2,step:.0001},
    {name:'angularDivergenceRmsMrad',label:'Angular divergence RMS (mrad)',type:'number',value:.05,min:0,max:10,step:.01},
    {name:'beamSamples',label:'Beam Monte Carlo samples',type:'number',value:12000,min:2000,max:200000,step:1000},
    {name:'beamSeed',label:'Beam seed',type:'number',value:20260911,min:0,max:2147483647,step:1},
    {name:'beamBins',label:'Beam histogram bins',type:'number',value:120,min:40,max:500,step:10}
  ],
  'frequency-response':[
    {name:'settleCycles',label:'Settle cycles',type:'number',value:16,min:4,max:120,step:1},
    {name:'observeCycles',label:'Observe cycles',type:'number',value:5,min:3,max:40,step:1},
    {name:'pointsPerCycle',label:'Points per cycle',type:'number',value:48,min:32,max:240,step:8},
    {name:'omega0',label:'Duffing ω0',type:'number',value:1,min:.1,max:20,step:.05},
    {name:'cubicStiffness',label:'Duffing cubic stiffness β',type:'number',value:1,min:0,max:50,step:.1}
  ]
});

const NATIVE_GLOBAL_TOOL_SPECS = Object.freeze([
  {id:'result-inspector',name:'Result Inspector',description:'Inspect the current structured result, schema inventory, and numerical sanity checks.'},
  {id:'bootstrap',name:'Bootstrap uncertainty',description:'Resample the first numeric result series and estimate uncertainty for the selected statistic.'},
  {id:'regression',name:'Linear regression diagnostics',description:'Fit and inspect an ordinary least-squares trend on the current numeric result series.'},
  {id:'robust-regression',name:'Robust Huber regression',description:'Fit a Huber robust trend that reduces the leverage of large residuals.'},
  {id:'convergence-diagnostics',name:'Convergence diagnostics',description:'Estimate a bounded convergence trend from the current numeric series; use explicit refinement tools when available.'},
  {id:'visualization-summary',name:'Visualization summary',description:'Build the original Visualization Studio numeric field summary from the current structured result.'},
  {id:'visualization-transform',name:'Normalize / transform results',description:'Apply z-score normalization to a copy of current numeric result fields for analysis and visualization.'},
  {id:'local-sensitivity',name:'Local sensitivity',description:'Compute finite-difference local sensitivity between varying result fields.'},
  {id:'elasticity-sensitivity',name:'Elasticity sensitivity',description:'Compute normalized local elasticity from the current finite result table.'},
  {id:'standardized-sensitivity',name:'Standardized sensitivity',description:'Rank standardized associations across varying numeric fields using the original Visual Analytics core.'},
  {id:'polynomial-regression',name:'Polynomial regression',description:'Fit the original bounded polynomial-regression core to varying fields in the current result.'},
  {id:'monte-carlo-propagation',name:'Monte Carlo propagation',description:'Run the original linear uncertainty-propagation core with explicit sampling assumptions.'},
  {id:'doe-design',name:'DOE design',description:'Generate a bounded Latin-hypercube design with the original Applied Analysis core.'},
  {id:'parameter-estimation',name:'Parameter estimation',description:'Fit the original bounded parameter-estimation core to current result fields.'},
  {id:'polynomial-cv',name:'Polynomial model selection',description:'Cross-validate polynomial families with the original Advanced Applied Analysis core.'},
  {id:'pca-svd',name:'PCA / SVD',description:'Run standardized PCA/SVD on varying current-result fields.'},
  {id:'conditioning-diagnostics',name:'Conditioning diagnostics',description:'Inspect rank, singular values and condition number of current-result variables.'},
  {id:'tikhonov',name:'Tikhonov inverse solve',description:'Run the original regularized linear inverse solver on current-result fields.'},
  {id:'tsvd',name:'Truncated-SVD inverse solve',description:'Run the original TSVD regularized inverse solver on current-result fields.'},
  {id:'correlation-matrix',name:'Correlation matrix',description:'Compute a Pearson correlation matrix across varying current-result fields.'},
  {id:'pareto-frontier',name:'Pareto frontier',description:'Compute a two-objective Pareto frontier without inventing a master score.'},
  {id:'robust-sensitivity',name:'Robust sensitivity summary',description:'Combine complementary sensitivity diagnostics without a synthetic ranking score.'},
  {id:'run-comparison',name:'Run comparison',description:'Compare finite numeric rows against a baseline using the original Research Orchestrator core.'},
  {id:'morris-design',name:'Morris screening design',description:'Generate a prospective Morris screening design with explicit bounds and no automatic execution.'}
]);

const NATIVE_TOOL_SPECS = Object.freeze({
  'kerr-geodesics':[
    {id:'refinement',name:'Numerical refinement',description:'Compare loose and tight integration settings and inspect residual sensitivity.'}
  ],
  'solar-system-dynamics':[
    {id:'refinement',name:'Numerical refinement',description:'Compare loose and tight orbital integrations.'},
    {id:'ftle',name:'Finite-time Lyapunov indicator',description:'Run the bounded Benettin-style phase-space divergence diagnostic.'}
  ],
  'honeycomb-lattice':[
    {id:'normal-modes',name:'Finite-cell normal modes',description:'Diagonalize the harmonic finite-cell dynamical matrix.'},
    {id:'phonon-dispersion',name:'Phonon dispersion',description:'Compute Bloch branches along the high-symmetry path.'},
    {id:'phonon-dos',name:'Phonon density of states',description:'Sample the reciprocal cell and build a normalized DOS.'}
  ],
  'undulator-spectrum':[
    {id:'angular-map',name:'Angular harmonic map',description:'Evaluate resonance-energy red shift across observation angle.'},
    {id:'beam-broadening',name:'Beam broadening',description:'Propagate energy spread and angular divergence through the resonance relation.'}
  ],
  'frequency-response':[
    {id:'duffing',name:'Duffing nonlinear sweep',description:'Forward/reverse continuation sweep with cubic stiffness and branch sensitivity.'}
  ]
});

let nativeExperimentResult = null;
let nativeExperimentToolResult = null;
let nativeExperimentVerificationResult = null;

function nativeParameterGroup(field){
  const name=String(field.name||'').toLowerCase();
  if(/seed|uncert|spread|divergence|stochastic|langevin|temperature/.test(name))return 'Stochastic / uncertainty';
  if(/rtol|atol|maxstep|samples|points|bins|grid|order|cycles|dt|duration|lambdamax|segment|maxyears/.test(name))return 'Numerical / solver';
  if(/drive|force|damping|zeta|omega|stiff|alpha|beta|drag|backreaction|1pn|strain/.test(name))return 'Driving / physics';
  return 'Model / geometry';
}

function nativeParameterUsesLogSlider(field){
  const min=Number(field.min),max=Number(field.max);
  return Number.isFinite(min)&&Number.isFinite(max)&&min>0&&max/min>=1000;
}

function nativeParameterHasSlider(field){
  if(field.type!=='number')return false;
  if(/seed/i.test(String(field.name||'')))return false;
  return Number.isFinite(Number(field.min))&&Number.isFinite(Number(field.max))&&Number(field.max)>Number(field.min);
}

function nativeParameterHtml(field){
  const name=uEsc(field.name),label=uEsc(field.label);
  if(field.type==='checkbox')return '<label class="native-check professional-check"><input data-native-param="'+name+'" type="checkbox" '+(field.value?'checked':'')+'><span>'+label+'</span></label>';
  if(field.type==='select')return '<label class="professional-param"><span class="param-label">'+label+'</span><select data-native-param="'+name+'">'+field.options.map(v=>'<option '+(String(v)===String(field.value)?'selected':'')+'>'+uEsc(v)+'</option>').join('')+'</select></label>';
  const hasSlider=nativeParameterHasSlider(field);
  const log=hasSlider&&nativeParameterUsesLogSlider(field);
  const slider=hasSlider
    ?('<input class="param-range" data-param-range="'+name+'" data-range-mode="'+(log?'log':'linear')+'" type="range" min="'+uEsc(log?Math.log10(Number(field.min)):field.min)+'" max="'+uEsc(log?Math.log10(Number(field.max)):field.max)+'" step="'+uEsc(log?.001:(field.step??'any'))+'" value="'+uEsc(log?Math.log10(Number(field.value)):field.value)+'">')
    :'';
  return '<label class="professional-param"><span class="param-label">'+label+'</span><div class="param-input-row"><input data-native-param="'+name+'" type="number" value="'+uEsc(field.value)+'" min="'+uEsc(field.min??'')+'" max="'+uEsc(field.max??'')+'" step="'+uEsc(field.step??'any')+'"><span class="param-value-tag">'+uEsc(field.value)+'</span></div>'+slider+'</label>';
}

function bindProfessionalParameterControls(){
  document.querySelectorAll('#nativeExperimentControls [data-native-param]').forEach(input=>{
    if(input.type!=='number')return;
    const key=input.dataset.nativeParam;
    const range=document.querySelector('#nativeExperimentControls [data-param-range="'+key+'"]');
    const tag=input.closest('.professional-param')?.querySelector('.param-value-tag');
    const updateTag=()=>{if(tag)tag.textContent=input.value};
    input.addEventListener('input',()=>{
      updateTag();
      if(!range)return;
      const value=Number(input.value);
      if(!Number.isFinite(value))return;
      if(range.dataset.rangeMode==='log'&&value>0)range.value=String(Math.log10(value));
      else range.value=String(value);
    });
    if(range){
      range.addEventListener('input',()=>{
        let value=Number(range.value);
        if(range.dataset.rangeMode==='log')value=10**value;
        const step=Number(input.step);
        if(Number.isFinite(step)&&step>0&&range.dataset.rangeMode!=='log'){
          const min=Number(input.min)||0;
          value=Math.round((value-min)/step)*step+min;
        }
        input.value=(Math.abs(value)>=1e5||Math.abs(value)<1e-5&&value!==0)?value.toExponential(8):String(Number(value.toPrecision(9)));
        updateTag();
      });
    }
    updateTag();
  });
}

function renderNativeParameterSections(fields){
  const order=['Model / geometry','Driving / physics','Numerical / solver','Stochastic / uncertainty'];
  const groups=new Map(order.map(x=>[x,[]]));
  fields.forEach(field=>groups.get(nativeParameterGroup(field))?.push(field));
  return order.filter(name=>groups.get(name).length).map((name,index)=>{
    const items=groups.get(name);
    return '<section class="parameter-section"><div class="parameter-section-heading"><span>'+String(index+1).padStart(2,'0')+'</span><div><strong>'+uEsc(name)+'</strong><small>'+items.length+' adjustable controls</small></div></div><div class="native-parameter-grid professional-control-grid">'+items.map(nativeParameterHtml).join('')+'</div></section>';
  }).join('');
}

function renderNativeExperimentControls(spec){
  const primary=NATIVE_PARAMETER_SCHEMAS[spec.id]||[];
  const advanced=NATIVE_ADVANCED_PARAMETER_SCHEMAS[spec.id]||[];
  const seen=new Set();
  const fields=[...primary,...advanced].filter(field=>{
    if(seen.has(field.name))return false;
    seen.add(field.name);return true;
  });
  uEl('nativeExperimentControls').innerHTML=renderNativeParameterSections(fields);
  uEl('nativeExperimentParameterCount').textContent=String(fields.length);
  bindProfessionalParameterControls();

  const tools=[...(NATIVE_TOOL_SPECS[spec.id]||[]),...NATIVE_GLOBAL_TOOL_SPECS];
  const toolGroups=[
    ['Experiment-specific',tools.filter(t=>(NATIVE_TOOL_SPECS[spec.id]||[]).some(x=>x.id===t.id))],
    ['Inspect & verify',tools.filter(t=>['result-inspector','convergence-diagnostics','visualization-summary'].includes(t.id))],
    ['Uncertainty & sensitivity',tools.filter(t=>['bootstrap','monte-carlo-propagation','local-sensitivity','elasticity-sensitivity','standardized-sensitivity','robust-sensitivity'].includes(t.id))],
    ['Fit & model selection',tools.filter(t=>['regression','robust-regression','polynomial-regression','parameter-estimation','polynomial-cv'].includes(t.id))],
    ['Experimental design',tools.filter(t=>['doe-design','morris-design'].includes(t.id))],
    ['Deep numerical analysis',tools.filter(t=>['pca-svd','conditioning-diagnostics','tikhonov','tsvd'].includes(t.id))],
    ['Compare & transform',tools.filter(t=>['visualization-transform','correlation-matrix','pareto-frontier','run-comparison'].includes(t.id))]
  ].filter(([,items])=>items.length);
  const toolHtml=toolGroups.map(([name,items],index)=>'<details class="native-tool-group" '+(index===0?'open':'')+'><summary><strong>'+uEsc(name)+'</strong><span>'+items.length+' tools</span></summary><div class="native-tool-list">'+items.map(t=>'<button type="button" class="native-tool-row" data-native-tool="'+uEsc(t.id)+'"><span><strong>'+uEsc(t.name)+'</strong><small>'+uEsc(t.description)+'</small></span><b>Run →</b></button>').join('')+'</div></details>').join('');
  const original='<div class="full-original-strip"><div><strong>Full Original Workspace</strong><span>Complete pre-redesign workbench remains available without removing any function.</span></div><button class="secondary" data-open-full-original="'+uEsc(spec.id)+'">Open original workspace</button></div>';
  uEl('nativeExperimentTools').innerHTML=toolHtml+original;
  document.querySelectorAll('[data-open-full-original]').forEach(b=>b.onclick=()=>openFullOriginalWorkspace(b.dataset.openFullOriginal));
  document.querySelectorAll('[data-native-tool]').forEach(b=>b.onclick=()=>runNativeExperimentTool(b.dataset.nativeTool));
  document.querySelectorAll('[data-native-verification-tool]').forEach(b=>b.onclick=()=>runNativeVerificationTool(b.dataset.nativeVerificationTool));
  if(uEl('nativeExperimentOpenOriginalVerification'))uEl('nativeExperimentOpenOriginalVerification').onclick=()=>activeNativeExperimentId&&openFullOriginalWorkspace(activeNativeExperimentId);

  uEl('nativeExperimentRunMode').value='safe';
  nativeExperimentResult=null;
  nativeExperimentToolResult=null;
  nativeExperimentVerificationResult=null;
  uEl('nativeExperimentMetrics').innerHTML='';
  uEl('nativeExperimentResultCharts').innerHTML='';
  uEl('nativeExperimentResultTables').innerHTML='';
  uEl('nativeExperimentToolMetrics').innerHTML='';
  uEl('nativeExperimentToolCharts').innerHTML='';
  uEl('nativeExperimentToolTables').innerHTML='';
  uEl('nativeExperimentVerificationMetrics').innerHTML='';
  uEl('nativeExperimentVerificationCharts').innerHTML='';
  uEl('nativeExperimentVerificationTables').innerHTML='';
  uEl('nativeExperimentToolBoundary').textContent='';
  uEl('nativeExperimentVerificationBoundary').textContent='';
  uEl('nativeExperimentResultBoundary').textContent='Run the experiment to view its model assumptions and scientific boundary.';
  uEl('nativeExperimentBackend').textContent='not run';
  uEl('nativeExperimentVerificationMode').textContent='not run';
  uEl('nativeExperimentVerificationParameters').textContent='—';
  uEl('nativeExperimentVerificationOutputs').textContent='—';
  uEl('nativeExperimentToolBackend').textContent='not run';
  uEl('nativeExperimentVerificationBackend').textContent='not run';
  if(uEl('nativeExperimentEmptyResults'))uEl('nativeExperimentEmptyResults').hidden=false;
  if(uEl('nativeExperimentToolEmpty'))uEl('nativeExperimentToolEmpty').hidden=false;
  if(uEl('nativeExperimentVerificationEmpty'))uEl('nativeExperimentVerificationEmpty').hidden=false;
}

function collectNativeExperimentParameters(){
  const values={};
  document.querySelectorAll('#nativeExperimentControls [data-native-param]').forEach(node=>{
    const key=node.dataset.nativeParam;
    if(node.type==='checkbox')values[key]=node.checked;
    else if(node.type==='number'){const v=Number(node.value);if(!Number.isFinite(v))throw new Error(key+' must be finite');values[key]=v}
    else values[key]=node.value;
  });
  return values;
}

function nativeMetricText(value){
  if(value===null||value===undefined)return '—';
  if(typeof value==='number'){
    if(!Number.isFinite(value))return '—';
    const a=Math.abs(value);
    return (a!==0&&(a>=1e5||a<1e-4))?value.toExponential(5):Number(value.toPrecision(7)).toString();
  }
  if(Array.isArray(value))return value.slice(0,5).map(nativeMetricText).join(', ')+(value.length>5?' …':'');
  if(typeof value==='object')return JSON.stringify(value);
  return String(value);
}

function renderNativePayload(payload,targets){
  const metrics=payload.metrics||{};
  const entries=Object.entries(metrics).filter(([,v])=>typeof v!=='object'||v===null||Array.isArray(v));
  uEl(targets.metrics).innerHTML=entries.length?entries.slice(0,24).map(([k,v])=>'<div class="native-result-metric"><span>'+uEsc(k.replace(/([A-Z])/g,' $1'))+'</span><strong>'+uEsc(nativeMetricText(v))+'</strong></div>').join(''):'<div class="empty-state compact-empty">No scalar metrics returned.</div>';
  const series=Array.isArray(payload.series)?payload.series:[];
  uEl(targets.charts).innerHTML=series.map((seriesRow,idx)=>{
    const points=(seriesRow.x||[]).map((x,i)=>({x:Number(x),y:Number((seriesRow.y||[])[i])})).filter(point=>Number.isFinite(point.x)&&Number.isFinite(point.y));
    const graph=seriesRow.chart==='scatter'?nativeScatterSvg([{label:seriesRow.label||seriesRow.id,points}],{xLabel:seriesRow.xLabel||'x',yLabel:seriesRow.yLabel||'y'}):utubeLineSvg([{label:seriesRow.label||seriesRow.id,points}],{xLabel:seriesRow.xLabel||'x',yLabel:seriesRow.yLabel||'y',height:280});
    return '<article class="native-viz-panel"><div class="native-viz-title"><span>'+uEsc(seriesRow.label||seriesRow.id||('Series '+(idx+1)))+'</span><small>'+uEsc(seriesRow.chart||'line')+'</small></div>'+graph+'</article>';
  }).join('');
  const tables=Array.isArray(payload.tables)?payload.tables:[];
  uEl(targets.tables).innerHTML=tables.map(table=>{
    const rows=Array.isArray(table.rows)?table.rows:[];if(!rows.length)return '';
    const keys=Object.keys(rows[0]).slice(0,14);
    return '<article class="native-table-panel"><div class="native-viz-title"><span>'+uEsc(table.label||table.id||'Result table')+'</span><small>'+rows.length+' rows</small></div><div class="table-wrap"><table class="research-table"><thead><tr>'+keys.map(k=>'<th>'+uEsc(k)+'</th>').join('')+'</tr></thead><tbody>'+rows.slice(0,160).map(row=>'<tr>'+keys.map(k=>'<td>'+uEsc(nativeMetricText(row[k]))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></article>';
  }).join('');
  if(targets.boundary)uEl(targets.boundary).textContent=payload.boundary||'';
  if(targets.backend)uEl(targets.backend).textContent=payload.backend||'scientific adapter';
  if(targets.empty)uEl(targets.empty).hidden=true;
}

function renderNativeExperimentResult(payload,parameters,mode){
  nativeExperimentResult=payload;
  renderNativePayload(payload,{metrics:'nativeExperimentMetrics',charts:'nativeExperimentResultCharts',tables:'nativeExperimentResultTables',empty:'nativeExperimentEmptyResults'});
  uEl('nativeExperimentResultBoundary').textContent=payload.boundary||'No explicit boundary returned.';
  uEl('nativeExperimentBackend').textContent=payload.backend||'scientific adapter';
  uEl('nativeExperimentVerificationMode').textContent=mode||'safe';
  uEl('nativeExperimentVerificationParameters').textContent=String(Object.keys(parameters||{}).length);
  const outputs=Object.keys(payload.metrics||{}).length+(payload.series||[]).length+(payload.tables||[]).length;
  uEl('nativeExperimentVerificationOutputs').textContent=String(outputs);
}

function renderNativeToolResult(payload){
  nativeExperimentToolResult=payload;
  renderNativePayload(payload,{metrics:'nativeExperimentToolMetrics',charts:'nativeExperimentToolCharts',tables:'nativeExperimentToolTables',boundary:'nativeExperimentToolBoundary',backend:'nativeExperimentToolBackend',empty:'nativeExperimentToolEmpty'});
}

function renderNativeVerificationResult(payload){
  nativeExperimentVerificationResult=payload;
  renderNativePayload(payload,{metrics:'nativeExperimentVerificationMetrics',charts:'nativeExperimentVerificationCharts',tables:'nativeExperimentVerificationTables',boundary:'nativeExperimentVerificationBoundary',backend:'nativeExperimentVerificationBackend',empty:'nativeExperimentVerificationEmpty'});
}

async function runNativeExperiment(){
  if(!activeNativeExperimentId||activeNativeExperimentId==='utube-studio')return;
  if(!invoke){toast('Experiment execution is available in the desktop build.',true);return}
  const button=uEl('nativeExperimentRun');
  try{
    button.disabled=true;button.textContent='Running…';
    uEl('nativeExperimentRunStatus').textContent='Running calculation…';
    const parameters=collectNativeExperimentParameters();
    const mode=uEl('nativeExperimentRunMode').value||'safe';
    const payload=await invoke('native_experiment_run',{experimentId:activeNativeExperimentId,parameters,mode});
    renderNativeExperimentResult(payload,parameters,mode);
    uEl('nativeExperimentRunStatus').textContent='Completed. Primary result saved in Results; analysis tools are ready.';
    document.querySelector('[data-native-exp-tab="results"]')?.click();
  }catch(e){
    uEl('nativeExperimentRunStatus').textContent=String(e);
    toast(String(e),true);
  }finally{
    button.disabled=false;button.textContent='Run Experiment';
  }
}

async function runNativeExperimentTool(tool){
  if(!activeNativeExperimentId||!invoke)return;
  const status=uEl('nativeExperimentToolStatus');
  try{
    status.textContent='Running '+tool+'…';
    const parameters=collectNativeExperimentParameters();
    parameters.__tool=tool;
    if(nativeExperimentResult)parameters.contextResult=nativeExperimentResult;
    const mode=uEl('nativeExperimentRunMode').value||'safe';
    const payload=await invoke('native_experiment_run',{experimentId:activeNativeExperimentId,parameters,mode});
    renderNativeToolResult(payload);
    status.textContent='Completed '+tool+'. Analysis output remains in Tools & Analysis.';
  }catch(e){
    status.textContent=String(e);
    toast(String(e),true);
  }
}

async function runNativeVerificationTool(tool){
  if(!activeNativeExperimentId||!invoke)return;
  const status=uEl('nativeExperimentStatus');
  try{
    status.textContent='Running verification tool '+tool+'…';
    const parameters=collectNativeExperimentParameters();
    parameters.__tool=tool;
    if(nativeExperimentResult)parameters.contextResult=nativeExperimentResult;
    const mode=uEl('nativeExperimentRunMode').value||'safe';
    const payload=await invoke('native_experiment_run',{experimentId:activeNativeExperimentId,parameters,mode});
    renderNativeVerificationResult(payload);
    status.textContent='Completed verification tool '+tool+'.';
  }catch(e){
    status.textContent=String(e);
    toast(String(e),true);
  }
}


const ENGINEERING_CAPABILITIES = Object.freeze([{"id":"utube-studio","label":"U-Tube Research Studio","category":"Experiments & Physics","description":"Rotating U-tube model, threshold maps, theory↔experiment comparison, uncertainty, robust design, digital twin and hysteresis.","launchMode":"route","profiles":[],"routeHint":"Project Workspace → U-Tube Research Studio"},{"id":"utube-physical","label":"U-Tube Physical Model & Data","category":"Experiments & Physics","description":"Physical view, threshold map, theory↔experiment comparison and DOE/sweep workflows.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"utube-uncertainty","label":"U-Tube Uncertainty","category":"Experiments & Physics","description":"Explicit model-input uncertainty and threshold sensitivity tools.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"utube-advanced","label":"U-Tube Advanced Engineering & Twin","category":"Experiments & Physics","description":"DIY data view, robust design, digital twin, hysteresis and verification-oriented tools.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"data-bridge","label":"Canonical Data Bridge","category":"Data & Measurement","description":"Promote parsed numeric tables into reusable canonical project datasets and inspect/export them.","launchMode":"route","profiles":[],"routeHint":"Project Workspace → Project Tools → Data & LabBridge → Data Bridge"},{"id":"measurement-registry","label":"Measurement & Calibration Registry","category":"Data & Measurement","description":"Project measurement/calibration records and their explicit provenance links.","launchMode":"route","profiles":[],"routeHint":".physlab Project / Evidence Center → Measurements & calibration"},{"id":"betterboard-discovery","label":"BetterBoard Discovery","category":"Data & Measurement","description":"Discover local BetterBoard measurement packages and connect real-world sensor evidence.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"betterboard-inbox","label":"BetterBoard Ingress / Inbox","category":"Data & Measurement","description":"Select, validate and explicitly ingest BetterBoard measurement packages without silent promotion.","launchMode":"route","profiles":[],"routeHint":"Project Workspace → Project Tools → Data & LabBridge → BetterBoard Discovery"},{"id":"labbridge","label":"LabBridge & Lab Journey","category":"Data & Measurement","description":"Promote measurements, preserve provenance and maintain the project lab journey.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"research-notebook","label":"Experiment Notebook & Annotations","category":"Data & Measurement","description":"Write project notebook entries, annotate evidence and browse preserved research records.","launchMode":"route","profiles":[],"routeHint":"Project Workspace → Project Tools → Data & LabBridge → LabBridge / Journey → Experiment Notebook"},{"id":"result-inspector","label":"Result Inspector","category":"Data & Measurement","description":"Inspect results, contracts, materialized datasets and execution environments.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"research-orchestrator","label":"Research Orchestrator","category":"Data & Measurement","description":"Reusable sweep, numeric table, comparison and convergence workflows.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"visualization-studio","label":"Visualization Studio","category":"Visualization & Analysis","description":"Build figures from project datasets with explicit visualization choices and provenance.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"visual-analytics","label":"Visual Analytics","category":"Visualization & Analysis","description":"Interactive uncertainty, selection, multi-run overlay and saved dashboard analysis.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"applied-analysis","label":"Applied Analysis","category":"Visualization & Analysis","description":"Core applied statistics, uncertainty and design-of-experiments analysis.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"advanced-applied-analysis","label":"Advanced Applied Analysis","category":"Visualization & Analysis","description":"Robust regression, model selection, screening and DOE-to-sweep workflows.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"deep-applied-math","label":"Deep Applied Math","category":"Visualization & Analysis","description":"Deeper numerical, linear-algebra and mathematical analysis workflows.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"sweep-design-bridge","label":"Sweep Design Bridge","category":"Visualization & Analysis","description":"Bridge statistical designs into bounded computational sweep jobs.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"science-analysis","label":"Science Analysis","category":"Visualization & Analysis","description":"Scientific semantics, sensitivity, response surfaces, comparison, correlation and Pareto analysis.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"science-protocol","label":"Science Protocol","category":"Visualization & Analysis","description":"Project-level analysis plan and protocol controls that preserve scientific interpretation boundaries.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"modelspec-diy","label":"ModelSpec DIY","category":"Modeling & Simulation","description":"Build bounded model controls without modifying source datasets.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"run-comparison","label":"Run Comparison","category":"Modeling & Simulation","description":"Visual parameter/metric deltas, comparability, UQ and environment/staleness provenance.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"model-coupling","label":"Model Coupling","category":"Modeling & Simulation","description":"Map canonical dataset values into explicit downstream model parameter packets.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"pipeline-dag","label":"Pipeline DAG","category":"Modeling & Simulation","description":"Build and inspect dependency graphs and workflow execution state.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"digital-twin","label":"Measurement Digital Twin","category":"Modeling & Simulation","description":"Measurement→calibration→model comparison→discrepancy and beam-statistics workspace.","launchMode":"direct","profiles":["radia-magnet-studio","radiation-platform","oscillation-integration"],"routeHint":"Available directly in RADIA Magnet Studio, Radiation Platform and Oscillation Integration profiles."},{"id":"engineering-decisions","label":"Engineering Decisions","category":"Engineering Decisions & Reliability","description":"Evidence-linked alternatives, explicit metrics/constraints and Pareto trade studies without a synthetic master score.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"operations-planning","label":"Operations Planning","category":"Engineering Decisions & Reliability","description":"Transparent finite-resource engineering task planning and dispatch-rule simulation.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"quality-reliability","label":"Quality & Reliability","category":"Engineering Decisions & Reliability","description":"Observed variation, DOE evidence and reliability-event analysis without qualification/certification claims.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"risk-economics","label":"Risk & Engineering Economics","category":"Engineering Decisions & Reliability","description":"Declared risk scenarios and time-valued cash flows without automatic risk acceptance or recommendations.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"requirements-verification","label":"Requirements & Verification","category":"Engineering Decisions & Reliability","description":"Traceable shall-statements, verification methods, evidence freshness and human review rationale.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"evidence-center","label":"Evidence Center","category":"Reproducibility & AI","description":"Credibility passport, claims, cross-checks, evidence graph, snapshots and evidence diffs.","launchMode":"direct","profiles":[],"routeHint":""},{"id":"reproducibility-pack","label":"Reproducibility Pack","category":"Reproducibility & AI","description":"Package project metadata, datasets, analysis artifacts, environments, provenance and reports into a portable ZIP.","launchMode":"route","profiles":[],"routeHint":"Project Workspace → Project Tools → Reproducibility"},{"id":"local-ai","label":"Local AI Physics Tutor","category":"Reproducibility & AI","description":"Read-only local OpenPenguin/Ollama explanation layer; it cannot change parameters, execute model-provided code or replace solvers.","launchMode":"profile","profiles":["numerical-methods","ising-monte-carlo","random-walk-monte-carlo","nonlinear-chaos","oscillation-integration","radia-magnet-studio","radiation-platform"],"routeHint":"Native Lab → Local AI Physics Tutor · OpenPenguin / Ollama"},{"id":"run-vault","label":"Run Vault","category":"Reproducibility & AI","description":"Persistent experiment snapshots for reproducibility, restoration, comparison, notes and bug reports.","launchMode":"profile","profiles":["numerical-methods","ising-monte-carlo","random-walk-monte-carlo","nonlinear-chaos","oscillation-integration","radia-magnet-studio","radiation-platform"],"routeHint":"Native Lab → Run Vault"},{"id":"openguin-advisory","label":"OpenPenguin Advisory Bridge","category":"Reproducibility & AI","description":"Review/import advisory records while preserving the boundary that suggestions do not execute measurements, solvers or parameter changes.","launchMode":"route","profiles":[],"routeHint":"Project Workspace → Project Tools → Data & LabBridge → LabBridge / Journey → OpenPenguin advisory"},{"id":"engineering-vvuq","label":"Engineering V&V / UQ Suite","category":"Engineering Decisions & Reliability","description":"Profile-native engineering verification, validation and uncertainty surfaces hosting deeper science/model workspaces.","launchMode":"profile","profiles":["numerical-methods","ising-monte-carlo","random-walk-monte-carlo","nonlinear-chaos","oscillation-integration","radia-magnet-studio","radiation-platform"],"routeHint":"Native Lab → Engineering V&V/UQ"},{"id":"kerr-geodesics","label":"Kerr Geodesic Dynamics","category":"Experiments & Physics","description":"Kerr geodesic dynamics workspace.","launchMode":"profile","profiles":["nonlinear-chaos"],"routeHint":"Nonlinear Chaos → Engineering V&V/UQ"},{"id":"kerr-platform","label":"Kerr Experiment / Compute Workflow","category":"Experiments & Physics","description":"Kerr experiment and compute workflow with preserved experiment identity.","launchMode":"profile","profiles":["nonlinear-chaos"],"routeHint":"Nonlinear Chaos → Engineering V&V/UQ"},{"id":"kerr-shadow","label":"Kerr Shadow Morphology","category":"Experiments & Physics","description":"Kerr shadow morphology sweep and analysis.","launchMode":"profile","profiles":["nonlinear-chaos"],"routeHint":"Nonlinear Chaos → Deep Science"},{"id":"solar-system","label":"Sun–Jupiter–Saturn Dynamics","category":"Experiments & Physics","description":"Solar-system dynamics and workflow tools.","launchMode":"profile","profiles":["nonlinear-chaos"],"routeHint":"Nonlinear Chaos → Engineering V&V/UQ"},{"id":"lattice-dynamics","label":"Multilayer Honeycomb Lattice","category":"Experiments & Physics","description":"Lattice dynamics, phonons and associated workflow controls.","launchMode":"profile","profiles":["oscillation-integration"],"routeHint":"Oscillation Integration → Engineering V&V/UQ"},{"id":"deep-science","label":"Deep Science Studio","category":"Experiments & Physics","description":"Advanced science analyses exposed by supported physics profiles.","launchMode":"profile","profiles":["nonlinear-chaos","oscillation-integration","numerical-methods"],"routeHint":"Supported physics profile → Engineering V&V/UQ"},{"id":"remaining-science","label":"Advanced Model Science","category":"Experiments & Physics","description":"Additional profile-specific science studies.","launchMode":"profile","profiles":["ising-monte-carlo","random-walk-monte-carlo","nonlinear-chaos","oscillation-integration"],"routeHint":"Supported physics profile → Engineering V&V/UQ"},{"id":"frequency-response","label":"Frequency Response Studio","category":"Experiments & Physics","description":"Frequency-response analysis for supported dynamic models.","launchMode":"profile","profiles":["nonlinear-chaos","oscillation-integration"],"routeHint":"Supported dynamics profile → Engineering V&V/UQ"},{"id":"new-model-refinement","label":"New Model Refinement Studio","category":"Modeling & Simulation","description":"Model-refinement investigations exposed in supported dynamics profiles.","launchMode":"profile","profiles":["nonlinear-chaos","oscillation-integration"],"routeHint":"Supported dynamics profile → Engineering V&V/UQ"},{"id":"model-depth","label":"Model Depth","category":"Modeling & Simulation","description":"Profile-specific deeper model diagnostics and analyses.","launchMode":"profile","profiles":["ising-monte-carlo","nonlinear-chaos","oscillation-integration","numerical-methods"],"routeHint":"Supported profile → Engineering V&V/UQ"},{"id":"undulator-spectrum","label":"Undulator Spectrum & Beam Broadening","category":"Experiments & Physics","description":"Undulator spectrum and beam-broadening analysis requiring the native radiation/RADIA namespace.","launchMode":"profile","profiles":["radia-magnet-studio","radiation-platform"],"routeHint":"RADIA Magnet Studio / Radiation Platform → Engineering V&V/UQ"},{"id":"radiation-stokes","label":"Trajectory Radiation & Stokes Map","category":"Experiments & Physics","description":"Trajectory-linked radiation and Stokes analysis requiring RADIA namespace state.","launchMode":"profile","profiles":["radia-magnet-studio"],"routeHint":"RADIA Magnet Studio → Engineering V&V/UQ"},{"id":"radiation-quality","label":"Radiation Quality Degradation","category":"Engineering Decisions & Reliability","description":"Manufacturing/radiation quality analysis requiring native RADIA state.","launchMode":"profile","profiles":["radia-magnet-studio"],"routeHint":"RADIA Magnet Studio → Engineering V&V/UQ"},{"id":"radiation-seed-compare","label":"Nominal vs Seed Radiation","category":"Experiments & Physics","description":"Nominal-versus-seed radiation comparison requiring native RADIA state.","launchMode":"profile","profiles":["radia-magnet-studio"],"routeHint":"RADIA Magnet Studio → Engineering V&V/UQ"},{"id":"radia-forward","label":"RADIA Measurement Adapter","category":"Modeling & Simulation","description":"Use the current Magnet Studio configuration as the real RADIA forward model against measurement coordinates.","launchMode":"profile","profiles":["radia-magnet-studio"],"routeHint":"RADIA Magnet Studio → Full mode → RADIA Measurement Adapter"},{"id":"radia-tolerance","label":"RADIA Nonlinear Tolerance Workspace","category":"Engineering Decisions & Reliability","description":"Profile-native nonlinear RADIA tolerance analysis using the current Magnet Studio namespace.","launchMode":"profile","profiles":["radia-magnet-studio"],"routeHint":"RADIA Magnet Studio → nonlinear RADIA tolerance workspace"},{"id":"radia-radiation-propagation","label":"RADIA → Radiation Tolerance Propagation","category":"Engineering Decisions & Reliability","description":"Propagate RADIA tolerance cases into radiation behavior without replacing native model provenance.","launchMode":"profile","profiles":["radia-magnet-studio"],"routeHint":"RADIA Magnet Studio → RADIA → Radiation tolerance propagation"}]);

let capabilityCategory = 'All';

function capabilityDefaultProfile(cap){
  if(cap.profiles&&cap.profiles.length)return cap.profiles[0];
  if(cap.id.startsWith('utube-'))return 'oscillation-integration';
  if(cap.id.includes('radia')||cap.id.startsWith('radiation-')||cap.id==='undulator-spectrum')return 'radia-magnet-studio';
  return 'numerical-methods';
}

const CAPABILITY_NATIVE_EXPERIMENT_MAP = Object.freeze({
  'utube-studio':'utube-studio',
  'kerr-geodesics':'kerr-geodesics',
  'kerr-shadow':'kerr-shadow',
  'solar-system':'solar-system-dynamics',
  'lattice-dynamics':'honeycomb-lattice',
  'frequency-response':'frequency-response',
  'undulator-spectrum':'undulator-spectrum'
});

const ACTION_NATIVE_VIEW_ROUTES = Object.freeze({
  'data-bridge':'data',
  'measurement-registry':'data',
  'betterboard-discovery':'data',
  'betterboard-inbox':'data',
  'labbridge':'data',
  'research-notebook':'workspaces',
  'run-comparison':'results',
  'reproducibility-pack':'results',
  'model-coupling':'pipelines',
  'pipeline-dag':'pipelines',
  'operations-planning':'campaigns',
  'evidence-center':'workspaces'
});

const ACTION_NATIVE_UTUBE_SURFACES = Object.freeze(new Set([
  'utube-studio','utube-physical','utube-uncertainty','utube-advanced','digital-twin'
]));

let activeActionRow=null;

const ACTION_NATIVE_UTUBE_TOOL_MAP = Object.freeze({
  'Run uncertainty propagation':'uncertainty',
  'Compute local uncertainty budget':'uncertainty-budget',
  'Solve inverse geometry':'inverse-geometry',
  'Evaluate design space':'design-space',
  'Fit calibration':'digital-twin-calibration',
  'Compare field series':'digital-twin-field',
  'Fit affine discrepancy':'digital-twin-field',
  'Analyze phase space':'beam-phase-space',
  'Rank remeasurement points':'digital-twin-field'
});

function actionRouteInfo(row){
  if(!row)return {kind:'unknown',label:'Unknown',detail:'No action selected.'};
  const nativeExperiment=CAPABILITY_NATIVE_EXPERIMENT_MAP[row.surface_id];
  if(nativeExperiment)return {kind:'native-experiment',label:'Native experiment',detail:'Runs in the Tauri experiment workspace.',experimentId:nativeExperiment};
  const utubeTool=ACTION_NATIVE_UTUBE_TOOL_MAP[row.label];
  if(utubeTool)return {kind:'native-utube-tool',label:'Native U-Tube tool',detail:'Runs the migrated U-Tube tool directly in the Tauri workspace.',toolId:utubeTool};
  if(ACTION_NATIVE_UTUBE_SURFACES.has(row.surface_id))return {kind:'native-utube',label:'Native U-Tube',detail:'Runs in the Tauri U-Tube workspace.'};
  if(ACTION_NATIVE_VIEW_ROUTES[row.surface_id])return {kind:'native-view',label:'Native application view',detail:'Opens a first-class Tauri project/data/results/pipeline view.',view:ACTION_NATIVE_VIEW_ROUTES[row.surface_id]};
  return {kind:'compatibility',label:'Compatibility-backed',detail:'The exact original action is preserved in its original Engineering Lab renderer and opened with an action deep-link.'};
}

function openActionWorkspace(row){
  activeActionRow=row;
  const route=actionRouteInfo(row);
  uEl('actionWorkspaceTitle').textContent=row.label;
  uEl('actionWorkspaceSubtitle').textContent=row.surface_label+' · '+row.control_type;
  uEl('actionWorkspaceMeta').innerHTML=[
    ['Capability',row.surface_label],
    ['Control type',row.control_type],
    ['Source module',row.module],
    ['Baseline',row.baseline_action?'pre-redesign':'current-only'],
    ['Current source',row.current_action?'present':'baseline only']
  ].map(([k,v])=>'<div class="native-result-metric"><span>'+uEsc(k)+'</span><strong>'+uEsc(v)+'</strong></div>').join('');
  uEl('actionWorkspaceRoute').innerHTML='<h3>'+uEsc(route.label)+'</h3><p>'+uEsc(route.detail)+'</p><p><b>Zero-loss rule:</b> this action remains directly discoverable even when its implementation has not yet been rewritten as a pure native control.</p>';
  uEl('actionWorkspaceStatus').textContent='Ready to open '+row.label+'.';
  showView('actionworkspace');
}

async function openSelectedActionExact(){
  const row=activeActionRow;if(!row)return;
  const route=actionRouteInfo(row);
  const status=uEl('actionWorkspaceStatus');
  status.textContent='Opening '+row.label+'…';
  if(route.kind==='native-experiment'){
    openNativeExperiment(route.experimentId);
    toast('Opened native experiment for: '+row.label);
    return;
  }
  if(route.kind==='native-utube-tool'){
    openNativeUtube();
    document.querySelector('[data-utube-tab="tools"]')?.click();
    const button=document.querySelector('[data-utube-tool="'+route.toolId+'"]');
    if(button){button.click();toast('Running native tool: '+row.label)}
    else toast('Native tool route exists but the tool button is unavailable: '+row.label,true);
    return;
  }
  if(route.kind==='native-utube'){
    openNativeUtube();
    document.querySelector('[data-utube-tab="tools"]')?.click();
    toast('Opened native U-Tube tools for: '+row.label);
    return;
  }
  if(route.kind==='native-view'){
    showView(route.view);
    toast('Opened native application view for: '+row.label);
    return;
  }
  await openCapabilitySurface(row.surface_id,row.label);
}


async function openCapabilitySurface(surfaceId, actionLabel=''){
  const cap=ENGINEERING_CAPABILITIES.find(x=>x.id===surfaceId);
  if(!cap)return;
  const nativeId=CAPABILITY_NATIVE_EXPERIMENT_MAP[surfaceId];
  if(nativeId){
    openNativeExperiment(nativeId);
    return;
  }
  const nativeViewRoutes={
    'data-bridge':'data',
    'measurement-registry':'data',
    'research-notebook':'workspaces',
    'run-comparison':'results',
    'reproducibility-pack':'results',
    'model-coupling':'pipelines',
    'pipeline-dag':'pipelines',
    'operations-planning':'campaigns',
    'evidence-center':'workspaces'
  };
  if(nativeViewRoutes[surfaceId]){
    showView(nativeViewRoutes[surfaceId]);
    if(actionLabel)toast('Opened workspace for: '+actionLabel);
    return;
  }
  if(['utube-physical','utube-uncertainty','utube-advanced','digital-twin'].includes(surfaceId)){
    openNativeUtube();
    document.querySelector('[data-utube-tab="tools"]')?.click();
    if(actionLabel)toast('Opened U-Tube tools for: '+actionLabel);
    return;
  }
    if(!invoke){toast('Capability opening is available in the desktop build.',true);return}
  const moduleId=capabilityDefaultProfile(cap);
  const m=modules.find(x=>x.id===moduleId);
  if(!m){toast('Required Lab profile is not installed in this build: '+moduleId,true);return}
  try{
    const status=statusFor(m);
    let requested=selectedModes[moduleId]||(status.fullReady?'full':'safe');
    if((surfaceId.startsWith('radia-')||surfaceId.startsWith('radiation-'))&&status.fullReady)requested='full';
    const info=await invoke('launch_module',{moduleId,mode:requested});
    activeModule=moduleId;
    activeMode=info.mode||requested;
    el('openLabTitle').textContent=cap.label+' · '+m.name;
    el('openLabUrl').textContent=info.url;
    const joiner=info.url.includes('?')?'&':'?';
    const actionQuery=actionLabel?'&pl_action='+encodeURIComponent(actionLabel):'';
    el('labFrame').src=info.url+joiner+'pl_surface='+encodeURIComponent(surfaceId)+actionQuery;
    showView('lab');
  }catch(e){toast(String(e),true)}
}

function capabilityCard(cap){
  const nativeViewIds=new Set(['data-bridge','measurement-registry','research-notebook','run-comparison','reproducibility-pack','model-coupling','pipeline-dag','operations-planning','evidence-center','utube-physical','utube-uncertainty','utube-advanced','digital-twin']);
  const access=(CAPABILITY_NATIVE_EXPERIMENT_MAP[cap.id]||nativeViewIds.has(cap.id))?'Native':'Original capability';
  const route=cap.routeHint?'<div class="capability-route">'+uEsc(cap.routeHint)+'</div>':'';
  return '<article class="module-card capability-card" data-capability-id="'+uEsc(cap.id)+'" data-search="'+uEsc((cap.label+' '+cap.category+' '+cap.description+' '+cap.id).toLowerCase())+'">'+
    '<div class="card-top"><div class="module-icon">◈</div><span class="status-pill ready">'+uEsc(access)+'</span></div>'+
    '<div class="category">'+uEsc(cap.category)+'</div><h4>'+uEsc(cap.label)+'</h4><p class="desc">'+uEsc(cap.description)+'</p>'+route+
    '<div class="card-actions"><button class="primary" data-open-capability="'+uEsc(cap.id)+'">Open capability</button></div></article>';
}

function renderCapabilityCatalog(){
  const grid=uEl('capabilityGrid'); if(!grid)return;
  const search=(uEl('capabilitySearch')?.value||'').trim().toLowerCase();
  const categories=['All',...new Set(ENGINEERING_CAPABILITIES.map(x=>x.category))];
  uEl('capabilityFilters').innerHTML=categories.map(c=>'<button class="filter '+(c===capabilityCategory?'active':'')+'" data-capability-category="'+uEsc(c)+'">'+uEsc(c)+'</button>').join('');
  const visible=ENGINEERING_CAPABILITIES.filter(cap=>(capabilityCategory==='All'||cap.category===capabilityCategory)&&(!search||(cap.label+' '+cap.category+' '+cap.description+' '+cap.id+' '+cap.routeHint).toLowerCase().includes(search)));
  uEl('capabilityCount').textContent=String(visible.length);
  grid.innerHTML=visible.map(capabilityCard).join('')||'<div class="empty-state">No capabilities match this search.</div>';
  document.querySelectorAll('[data-capability-category]').forEach(b=>b.onclick=()=>{capabilityCategory=b.dataset.capabilityCategory;renderCapabilityCatalog()});
  document.querySelectorAll('[data-open-capability]').forEach(b=>b.onclick=()=>openCapabilitySurface(b.dataset.openCapability));
}

let actionStageFilter='Experiments & Physics';

const ACTION_WORKFLOW_STAGES=Object.freeze([
  {id:'Experiments & Physics',index:'01',title:'Experiments & Physics',description:'Build, run and inspect physical experiments and model-specific tools.'},
  {id:'Data & Measurement',index:'02',title:'Data & Measurement',description:'Bring in measurements, calibrations, BetterBoard data and canonical datasets.'},
  {id:'Visualization & Analysis',index:'03',title:'Visualization & Analysis',description:'Inspect, visualize, compare, fit and analyze scientific results.'},
  {id:'Modeling & Simulation',index:'04',title:'Modeling & Simulation',description:'Define models, connect pipelines, design sweeps and orchestrate simulation workflows.'},
  {id:'Engineering Decisions & Reliability',index:'05',title:'Engineering Decisions & Reliability',description:'Verify requirements, evaluate quality, reliability, risk, economics and engineering decisions.'},
  {id:'Reproducibility & AI',index:'06',title:'Reproducibility & AI',description:'Capture evidence, reproduce runs, package results and use local advisory tools.'}
]);

function actionCatalogRows(){
  return Array.isArray(window.ENGINEERING_ACTION_CATALOG)?window.ENGINEERING_ACTION_CATALOG:[];
}

function capabilityById(id){
  return ENGINEERING_CAPABILITIES.find(x=>x.id===id)||null;
}

function actionStageForRow(row){
  return capabilityById(row.surface_id)?.category||'Visualization & Analysis';
}

function actionVerbWeight(row){
  const label=String(row.label||'').toLowerCase();
  const type=String(row.control_type||'');
  if(type==='button'||type==='download_button'||type==='form_submit_button')return 0;
  if(/run|open|inspect|compare|validate|check|analy|fit|compute|generate|export|save|register|queue|build|create/.test(label))return 1;
  if(type==='selectbox'||type==='radio'||type==='multiselect')return 2;
  if(type==='slider'||type==='number_input'||type==='text_input'||type==='checkbox'||type==='toggle')return 3;
  return 4;
}

function actionRowHtml(row){
  const route=actionRouteInfo(row);
  const routeClass=route.kind==='compatibility'?'compat':'native';
  return '<button class="action-row" type="button" data-open-action="'+uEsc(row.action_id)+'">'+
    '<span class="action-row-main"><strong>'+uEsc(row.label)+'</strong><small>'+uEsc(row.control_type.replaceAll('_',' '))+'</small></span>'+
    '<span class="action-route-badge '+routeClass+'">'+uEsc(route.label)+'</span>'+
    '<span class="action-arrow">→</span></button>';
}

function renderActionStageNav(rows,search){
  const nav=uEl('actionStageNav');if(!nav)return;
  nav.innerHTML=ACTION_WORKFLOW_STAGES.map(stage=>{
    const count=rows.filter(row=>actionStageForRow(row)===stage.id&&(!search||(row.label+' '+row.surface_label+' '+row.module+' '+row.control_type).toLowerCase().includes(search))).length;
    return '<button type="button" class="workflow-stage '+(stage.id===actionStageFilter?'active':'')+'" data-action-stage="'+uEsc(stage.id)+'">'+
      '<span>'+stage.index+'</span><strong>'+uEsc(stage.title)+'</strong><small>'+count+' actions</small></button>';
  }).join('');
  document.querySelectorAll('[data-action-stage]').forEach(button=>button.onclick=()=>{
    actionStageFilter=button.dataset.actionStage;
    if(uEl('actionSearch'))uEl('actionSearch').value='';
    renderActionCatalog();
  });
}

function renderActionCatalog(){
  const host=uEl('actionGroups');if(!host)return;
  const rows=actionCatalogRows();
  const search=(uEl('actionSearch')?.value||'').trim().toLowerCase();
  renderActionStageNav(rows,search);
  const stage=ACTION_WORKFLOW_STAGES.find(x=>x.id===actionStageFilter)||ACTION_WORKFLOW_STAGES[0];
  uEl('actionStageTitle').textContent=search?'Search across all workflow stages':stage.title;
  uEl('actionStageDescription').textContent=search?'Matching actions stay grouped by their real capability; no functions are moved or renamed.':stage.description;
  const scoped=rows.filter(row=>{
    const hay=(row.label+' '+row.surface_label+' '+row.module+' '+row.control_type).toLowerCase();
    return search?hay.includes(search):actionStageForRow(row)===actionStageFilter;
  });
  uEl('actionCount').textContent=String(rows.length);
  uEl('actionStageCount').textContent=search?(scoped.length+' matching actions'):(scoped.length+' actions in this stage');
  const parity=window.ENGINEERING_ACTION_PARITY||{};
  const missing=Array.isArray(parity.missing_from_current)?parity.missing_from_current.length:0;
  uEl('actionParityStatus').textContent=rows.length?('baseline '+(parity.baseline_action_count??'—')+' · current '+(parity.current_action_count??'—')+' · missing '+missing):'generated during desktop build';

  const grouped=new Map();
  scoped.forEach(row=>{
    if(!grouped.has(row.surface_id))grouped.set(row.surface_id,[]);
    grouped.get(row.surface_id).push(row);
  });
  const groups=[...grouped.entries()].sort((a,b)=>String(capabilityById(a[0])?.label||a[0]).localeCompare(String(capabilityById(b[0])?.label||b[0])));
  host.innerHTML=groups.length?groups.map(([surfaceId,items],groupIndex)=>{
    const cap=capabilityById(surfaceId);
    items.sort((a,b)=>actionVerbWeight(a)-actionVerbWeight(b)||String(a.label).localeCompare(String(b.label)));
    const nativeCount=items.filter(row=>actionRouteInfo(row).kind!=='compatibility').length;
    const open=search||groupIndex<2;
    return '<details class="action-capability-group" '+(open?'open':'')+'>'+
      '<summary><div class="action-group-title"><span class="action-group-index">'+String(groupIndex+1).padStart(2,'0')+'</span><div><strong>'+uEsc(cap?.label||items[0].surface_label)+'</strong><small>'+uEsc(cap?.description||items[0].module)+'</small></div></div>'+
      '<div class="action-group-stats"><span>'+items.length+' actions</span><span>'+nativeCount+' direct/native</span><b>⌄</b></div></summary>'+
      '<div class="action-list">'+items.map(actionRowHtml).join('')+'</div></details>';
  }).join(''):'<div class="empty-state">No preserved actions match this search.</div>';

  document.querySelectorAll('[data-open-action]').forEach(button=>button.onclick=()=>{
    const row=rows.find(x=>x.action_id===button.dataset.openAction);
    if(row)openActionWorkspace(row);
  });
  if(uEl('actionSearch')&&!uEl('actionSearch').dataset.bound){
    uEl('actionSearch').dataset.bound='1';
    uEl('actionSearch').addEventListener('input',renderActionCatalog);
    uEl('actionClearSearch').onclick=()=>{uEl('actionSearch').value='';renderActionCatalog();uEl('actionSearch').focus()};
  }
  if(uEl('backFromActionWorkspace')&&!uEl('backFromActionWorkspace').dataset.bound){
    uEl('backFromActionWorkspace').dataset.bound='1';
    uEl('backFromActionWorkspace').onclick=()=>showView('actions');
    uEl('actionWorkspaceOpen').onclick=()=>openSelectedActionExact();
    uEl('actionWorkspaceOpenCapability').onclick=()=>activeActionRow&&openCapabilitySurface(activeActionRow.surface_id,activeActionRow.label);
  }
}

