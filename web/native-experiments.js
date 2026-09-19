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
let nativeExperimentResult = null;

function nativeParameterHtml(field){
  const name=uEsc(field.name),label=uEsc(field.label);
  if(field.type==='checkbox')return '<label class="native-check"><input data-native-param="'+name+'" type="checkbox" '+(field.value?'checked':'')+'><span>'+label+'</span></label>';
  if(field.type==='select')return '<label>'+label+'<select data-native-param="'+name+'">'+field.options.map(v=>'<option '+(String(v)===String(field.value)?'selected':'')+'>'+uEsc(v)+'</option>').join('')+'</select></label>';
  return '<label>'+label+'<input data-native-param="'+name+'" type="number" value="'+uEsc(field.value)+'" min="'+uEsc(field.min??'')+'" max="'+uEsc(field.max??'')+'" step="'+uEsc(field.step??'any')+'"></label>';
}
function renderNativeExperimentControls(spec){
  const schema=NATIVE_PARAMETER_SCHEMAS[spec.id]||[];
  uEl('nativeExperimentControls').innerHTML=schema.map(nativeParameterHtml).join('');
  uEl('nativeExperimentRunMode').value='safe';
  nativeExperimentResult=null;
  uEl('nativeExperimentMetrics').innerHTML='';
  uEl('nativeExperimentResultCharts').innerHTML='';
  uEl('nativeExperimentResultTables').innerHTML='';
  uEl('nativeExperimentResultBoundary').textContent='Run the experiment to view its model assumptions and scientific boundary.';
  if(uEl('nativeExperimentEmptyResults'))uEl('nativeExperimentEmptyResults').hidden=false;
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
function renderNativeExperimentResult(payload){
  nativeExperimentResult=payload;
  const metrics=payload.metrics||{};
  const entries=Object.entries(metrics).filter(([,v])=>typeof v!=='object'||v===null||Array.isArray(v));
  uEl('nativeExperimentMetrics').innerHTML=entries.length?entries.slice(0,16).map(([k,v])=>'<div class="native-result-metric"><span>'+uEsc(k.replace(/([A-Z])/g,' $1'))+'</span><strong>'+uEsc(nativeMetricText(v))+'</strong></div>').join(''):'<div class="empty-state compact-empty">No scalar metrics returned.</div>';
  const series=Array.isArray(payload.series)?payload.series:[];
  uEl('nativeExperimentResultCharts').innerHTML=series.map((s,idx)=>{
    const points=(s.x||[]).map((x,i)=>({x:Number(x),y:Number((s.y||[])[i])})).filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));
    const graph=s.chart==='scatter'?nativeScatterSvg([{label:s.label||s.id,points}],{xLabel:s.xLabel||'x',yLabel:s.yLabel||'y'}):utubeLineSvg([{label:s.label||s.id,points}],{xLabel:s.xLabel||'x',yLabel:s.yLabel||'y',height:280});
    return '<article class="native-viz-panel"><div class="native-viz-title"><span>'+uEsc(s.label||s.id||('Series '+(idx+1)))+'</span><small>'+uEsc(s.chart||'line')+'</small></div>'+graph+'</article>';
  }).join('');
  const tables=Array.isArray(payload.tables)?payload.tables:[];
  uEl('nativeExperimentResultTables').innerHTML=tables.map(t=>{
    const rows=Array.isArray(t.rows)?t.rows:[];if(!rows.length)return '';
    const keys=Object.keys(rows[0]).slice(0,12);
    return '<article class="native-table-panel"><div class="native-viz-title"><span>'+uEsc(t.label||t.id||'Result table')+'</span><small>'+rows.length+' rows</small></div><div class="table-wrap"><table class="research-table"><thead><tr>'+keys.map(k=>'<th>'+uEsc(k)+'</th>').join('')+'</tr></thead><tbody>'+rows.slice(0,120).map(row=>'<tr>'+keys.map(k=>'<td>'+uEsc(nativeMetricText(row[k]))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></article>';
  }).join('');
  uEl('nativeExperimentResultBoundary').textContent=payload.boundary||'';
  if(uEl('nativeExperimentBackend'))uEl('nativeExperimentBackend').textContent=payload.backend||'scientific adapter';
  if(uEl('nativeExperimentEmptyResults'))uEl('nativeExperimentEmptyResults').hidden=true;
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
    renderNativeExperimentResult(payload);
    uEl('nativeExperimentRunStatus').textContent='Completed.';
    document.querySelector('[data-native-exp-tab="results"]')?.click();
  }catch(e){
    uEl('nativeExperimentRunStatus').textContent=String(e);
    toast(String(e),true);
  }finally{
    button.disabled=false;button.textContent='Run Experiment';
  }
}
