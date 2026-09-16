(() => {
  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return;

  const GENERIC_HOSTS = ['numerical-methods', 'oscillation-integration', 'nonlinear-chaos'];
  const UTUBE_PRIORITY = ['utube-studio','utube-physical','utube-uncertainty','utube-advanced','utube-robust','utube-hysteresis'];
  const FULL_MODE_SURFACES = new Set(['radia-forward','radia-tolerance','radia-radiation-propagation','radiation-stokes','radiation-quality','radiation-seed-compare','radiation-interactions','radiation-response-surface']);
  const descriptions = {
    'utube-studio':'Coordinated rotating U-tube research hub connecting model, experiment, uncertainty and engineering studies.',
    'utube-physical':'Physical model and data views: operating point, threshold map, theory ↔ experiment, convergence and free energy.',
    'utube-uncertainty':'U-tube uncertainty studies and explicit numerical/experimental uncertainty views.',
    'utube-advanced':'Advanced physics and engineering, including inverse design, experiment planning and DIY data views.',
    'utube-robust':'Robust design, adaptive experiments, verification and U-tube digital-twin workflows.',
    'utube-hysteresis':'Dynamic threshold and measured ramp hysteresis fitting with rate-envelope prediction.',
    'data-bridge':'Promote parsed numeric tables into reusable canonical project datasets.',
    'measurement-registry':'Project measurement/calibration records and explicit provenance links.',
    'project-workspace':'Canonical project home connecting data, analysis, modeling and reproducibility.',
    'radiation-interactions':'Pairwise manufacturing-error non-additivity screening.',
    'radiation-response-surface':'Bounded two-factor radiation response-surface exploration.'
  };

  let surfaces = Array.isArray(window.__PHYSICAL_LAB_SURFACES__) ? window.__PHYSICAL_LAB_SURFACES__ : [];
  let statuses = new Map(), activeCategory = 'All', query = '', busySurface = '';
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const byId = id => document.getElementById(id);
  const sortSurfacesForWorkbench = rows => [...rows].sort((a,b)=>{
    const ai=UTUBE_PRIORITY.indexOf(a.id), bi=UTUBE_PRIORITY.indexOf(b.id);
    if(ai!==bi && (ai>=0 || bi>=0)) return ai<0?1:bi<0?-1:ai-bi;
    return String(a.category||'').localeCompare(String(b.category||'')) || String(a.label||a.id||'').localeCompare(String(b.label||b.id||''));
  });

  function ensureWorkbenchChrome(){
    if(!document.querySelector('[data-view="capabilities"]')){
      const nav=document.querySelector('.nav'), labs=nav?.querySelector('[data-view="labs"]'), button=document.createElement('button');
      button.className='nav-item'; button.dataset.view='capabilities'; button.innerHTML='<span>⌘</span>Workbench';
      if(nav) nav.insertBefore(button,labs?.nextSibling||nav.children[1]||null);
    }
    if(!byId('capabilitiesView')){
      const main=document.querySelector('main.main'), firstView=main?.querySelector('.view'), section=document.createElement('section');
      section.id='capabilitiesView'; section.className='view'; section.innerHTML=`
        <div class="research-hero workbench-hero"><div><div class="eyebrow">EVERY USER-FACING CAPABILITY • ONE FRONT DOOR</div><h2>Engineering Workbench</h2><p>Discover and open every registered workspace and previously embedded child tool without knowing its hidden Lab route.</p></div><div class="research-badge">Native reachability</div></div>
        <section class="family-feature"><div class="family-feature-head"><div><div class="eyebrow">FEATURED EXPERIMENT FAMILY</div><h3>Rotating U-Tube Research</h3><p>Main model, new experiments and engineering follow-ons stay together and directly launchable.</p></div><span id="utubeFamilyCount" class="family-count">0 / ${UTUBE_PRIORITY.length}</span></div><div id="utubeFamilyGrid" class="utube-family-grid"></div></section>
        <div id="capabilitySummary" class="stats capability-summary"></div>
        <div class="workbench-toolbar"><div class="search-wrap workbench-search"><span>⌕</span><input id="capabilitySearch" placeholder="Search all capabilities, profiles and routes" /></div><div id="capabilityFilters" class="filters capability-filters"></div></div>
        <div id="capabilityGrid" class="capability-grid"></div>`;
      if(main) main.insertBefore(section,firstView||null);
    }
    if(!byId('workbenchNativeStyles')){
      const style=document.createElement('style'); style.id='workbenchNativeStyles'; style.textContent=`
        .family-feature{margin:18px 0 20px;padding:18px;border:1px solid var(--border,#30384a);background:rgba(74,111,220,.08);border-radius:20px}.family-feature-head{display:flex;justify-content:space-between;gap:16px;margin-bottom:14px}.family-feature-head h3{margin:3px 0 5px;font-size:22px}.family-feature-head p{margin:0;opacity:.72}.family-count{border:1px solid var(--border,#30384a);border-radius:999px;padding:7px 10px;font-size:12px;white-space:nowrap}.utube-family-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.utube-family-card{border:1px solid var(--border,#30384a);background:rgba(15,20,30,.58);border-radius:14px;padding:14px;display:flex;flex-direction:column;gap:8px;min-height:185px}.utube-family-card h4{margin:0;font-size:15px}.utube-family-card p{margin:0;opacity:.7;line-height:1.4;font-size:13px;flex:1}.family-step{font-size:11px;opacity:.6;text-transform:uppercase}.workbench-toolbar{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin:18px 0 20px}.workbench-search{min-width:320px;flex:1;max-width:620px}.capability-filters{display:flex;gap:8px;flex-wrap:wrap}.filter-chip{border:1px solid var(--border,#30384a);background:var(--panel,#171d29);color:inherit;border-radius:999px;padding:8px 12px;cursor:pointer}.filter-chip.active{background:rgba(95,134,255,.18)}.capability-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px;padding-bottom:28px}.capability-card{border:1px solid var(--border,#30384a);background:var(--panel,#171d29);border-radius:18px;padding:18px;display:flex;flex-direction:column;gap:10px;min-height:260px}.capability-card h3{margin:0}.capability-card p{margin:0;opacity:.78;line-height:1.45;flex:1}.capability-card-head,.capability-meta{display:flex;gap:7px;flex-wrap:wrap}.capability-card-head span,.capability-meta span,.capability-profiles{font-size:12px}.capability-category,.capability-access,.capability-meta span{border:1px solid var(--border,#30384a);border-radius:999px;padding:5px 8px}.capability-access,.capability-profiles{opacity:.7}.capability-card .primary,.utube-family-card .primary{align-self:flex-start}@media(max-width:900px){.capability-grid,.utube-family-grid{grid-template-columns:1fr}.workbench-search{min-width:100%}.family-feature-head{flex-direction:column}}`;
      document.head.appendChild(style);
    }
  }

  function showWorkbench(){ensureWorkbenchChrome();document.querySelectorAll('.view').forEach(v=>v.classList.remove('active-view'));document.querySelectorAll('.nav-item').forEach(i=>i.classList.toggle('active',i.dataset.view==='capabilities'));byId('capabilitiesView')?.classList.add('active-view');if(byId('viewTitle'))byId('viewTitle').textContent='Engineering Workbench';if(byId('viewSubtitle'))byId('viewSubtitle').textContent='Every user-facing Engineering Lab capability, reachable from the native desktop.';loadCatalog();}
  function candidateHosts(s){const p=Array.isArray(s.profiles)?s.profiles.filter(Boolean):[];return p.length?p:GENERIC_HOSTS;}
  function hostResolution(s){const c=candidateHosts(s), mode=FULL_MODE_SURFACES.has(s.id)?'full':'safe', key=mode==='full'?'fullReady':'safeReady', ready=c.find(id=>statuses.get(id)?.[key]);if(ready)return{host:ready,mode,ready:true};const installed=c.find(id=>statuses.get(id)?.installed);return{host:installed||c[0]||'numerical-methods',mode,ready:false};}
  function accessLabel(s){return s.kind==='embedded'?'Child workspace':s.launchMode==='profile'?'Profile-scoped':s.launchMode==='route'?'Project route':'Direct';}

  function renderUtubeFamily(){
    const grid=byId('utubeFamilyGrid'); if(!grid)return;
    const rows=UTUBE_PRIORITY.map(id=>surfaces.find(s=>s.id===id)).filter(Boolean), count=byId('utubeFamilyCount');
    if(count)count.textContent=`${rows.length} / ${UTUBE_PRIORITY.length} connected`;
    grid.innerHTML=rows.map((s,i)=>{const launch=hostResolution(s), state=statuses.get(launch.host)?.state||'Not checked', disabled=busySurface===s.id?'disabled':'';return `<article class="utube-family-card"><div class="family-step">${i+1} / ${UTUBE_PRIORITY.length} · ${esc(accessLabel(s))}</div><h4>${esc(s.label)}</h4><p>${esc(descriptions[s.id]||s.routeHint||'Rotating U-Tube workspace.')}</p><div class="capability-meta"><span>${esc(launch.host)}</span><span>${esc(state)}</span></div><button class="primary" data-surface-open="${esc(s.id)}" ${disabled}>${busySurface===s.id?'Preparing…':'Open experiment'}</button></article>`;}).join('');
  }
  function renderSummary(filtered){const e=byId('capabilitySummary');if(!e)return;const cats=new Set(surfaces.map(s=>s.category));e.innerHTML=`<div class="stat-card"><b>${surfaces.length}</b><span>Desktop capabilities</span></div><div class="stat-card"><b>${cats.size}</b><span>Categories</span></div><div class="stat-card"><b>${surfaces.filter(s=>s.kind==='embedded').length}</b><span>Exposed child tools</span></div><div class="stat-card"><b>${filtered.length}</b><span>Visible now</span></div>`;}
  function renderFilters(){const e=byId('capabilityFilters');if(!e)return;const cats=['All',...new Set(surfaces.map(s=>s.category))];e.innerHTML=cats.map(c=>`<button class="filter-chip ${c===activeCategory?'active':''}" data-surface-category="${esc(c)}">${esc(c)}</button>`).join('');}
  function render(){
    const grid=byId('capabilityGrid'); if(!grid)return; renderUtubeFamily(); const needle=query.trim().toLowerCase();
    const filtered=sortSurfacesForWorkbench(surfaces.filter(s=>(activeCategory==='All'||s.category===activeCategory)&&(!needle||[s.label,s.id,s.category,s.routeHint,descriptions[s.id],...(s.profiles||[])].join(' ').toLowerCase().includes(needle))));
    renderSummary(filtered);renderFilters();if(!filtered.length){grid.innerHTML='<div class="empty-state">No capabilities match this search/filter.</div>';return;}
    grid.innerHTML=filtered.map(s=>{const launch=hostResolution(s), state=statuses.get(launch.host)?.state||'Not checked', full=FULL_MODE_SURFACES.has(s.id), disabled=busySurface===s.id?'disabled':'';return `<article class="capability-card"><div class="capability-card-head"><span class="capability-category">${esc(s.category)}</span><span class="capability-access">${esc(accessLabel(s))}</span></div><h3>${esc(s.label)}</h3><p>${esc(descriptions[s.id]||s.routeHint||'Engineering Lab interactive workspace.')}</p><div class="capability-meta"><span>Host · ${esc(launch.host)}</span><span>${full?'Full mode':'Safe mode'}</span><span>${esc(state)}</span></div>${s.profiles?.length?`<div class="capability-profiles">Profiles: ${esc(s.profiles.join(', '))}</div>`:''}<button class="primary" data-surface-open="${esc(s.id)}" ${disabled}>${busySurface===s.id?'Preparing…':'Prepare & Open'}</button></article>`;}).join('');
  }

  async function refreshStatuses(){try{const rows=await invoke('module_statuses');statuses=new Map((rows||[]).map(r=>[r.id,r]));}catch(e){console.warn('Workbench host status unavailable',e);statuses=new Map();}}
  async function loadCatalog(){ensureWorkbenchChrome();surfaces=Array.isArray(window.__PHYSICAL_LAB_SURFACES__)?sortSurfacesForWorkbench(window.__PHYSICAL_LAB_SURFACES__):surfaces;await refreshStatuses();render();}
  function withSurfaceQuery(url,id){return `${url}${String(url).includes('?')?'&':'?'}surface=${encodeURIComponent(id)}`;}
  async function prepareAndOpen(id){const s=surfaces.find(x=>x.id===id);if(!s)return;busySurface=id;render();try{await refreshStatuses();let launch=hostResolution(s),status=statuses.get(launch.host);if(!status?.installed||!(launch.mode==='full'?status.fullReady:status.safeReady)){await invoke('install_module',{moduleId:launch.host});await refreshStatuses();launch=hostResolution(s);status=statuses.get(launch.host);}const ready=launch.mode==='full'?status?.fullReady:status?.safeReady;if(!ready&&launch.mode==='full')throw new Error(`${s.label} needs ${launch.host} Full mode. Repair its fragile scientific dependencies in Dependency Center, then open it again.`);if(!ready)throw new Error(`${launch.host} is not ready after preparation.`);const info=await invoke('launch_module',{moduleId:launch.host,mode:launch.mode});window.__physicalLabSurfaceHost=launch.host;if(byId('openLabTitle'))byId('openLabTitle').textContent=s.label;if(byId('openLabUrl'))byId('openLabUrl').textContent=`${launch.host} · ${launch.mode.toUpperCase()} · ${s.id}`;if(byId('labFrame'))byId('labFrame').src=withSurfaceQuery(info.url,s.id);if(typeof showView==='function')showView('lab');}catch(e){alert(`Could not open ${s.label}: ${e}`);}finally{busySurface='';render();}}
  async function stopWorkbenchHost(){const host=window.__physicalLabSurfaceHost;if(!host)return;window.__physicalLabSurfaceHost='';try{await invoke('stop_module',{moduleId:host});}catch(_){}}

  document.addEventListener('click',e=>{const c=e.target.closest('[data-surface-category]');if(c){activeCategory=c.dataset.surfaceCategory;render();return;}const open=e.target.closest('[data-surface-open]');if(open)prepareAndOpen(open.dataset.surfaceOpen);});
  document.addEventListener('DOMContentLoaded',()=>{ensureWorkbenchChrome();const input=byId('capabilitySearch');if(input)input.addEventListener('input',e=>{query=e.target.value||'';render();});const nav=document.querySelector('[data-view="capabilities"]');if(nav)nav.addEventListener('click',e=>{e.preventDefault();showWorkbench();});const back=byId('backFromLab');if(back)back.addEventListener('click',()=>{stopWorkbenchHost();},true);loadCatalog();});
  window.PhysicalLabWorkbench={loadCatalog,prepareAndOpen,showWorkbench};
})();