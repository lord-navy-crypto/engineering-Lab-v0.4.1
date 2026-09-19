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
  renderNativeMigrationViz(spec);
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
