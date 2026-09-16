(() => {
  const launcher = window.PhysicalLabCapabilityLauncher;
  const layout = window.__PHYSICAL_LAB_HOME_LAYOUT__ || {};
  if (!launcher) return;

  const home = document.getElementById('homeView');
  const searchInput = document.getElementById('searchInput');
  const escHome = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const familyIcon = {experiment:'◌', measure:'⌁', model:'∑', analyze:'∿'};

  function surface(id){ return launcher.surfaceById(id); }
  function runningTaskCount(){ try { return [...tasks.values()].filter(t => !t.done).length; } catch (_) { return 0; } }
  function currentProject(){ try { return typeof activeWorkspace === 'function' ? activeWorkspace() : null; } catch (_) { return null; } }
  function recentCapability(){
    try { const id=localStorage.getItem('physicalLab.recentCapability')||''; return surface(id); } catch (_) { return null; }
  }
  function latestSnapshot(){
    try { return [...(runSnapshots||[])].sort((a,b)=>String(b.createdAt||'').localeCompare(String(a.createdAt||'')))[0] || null; } catch (_) { return null; }
  }

  function installHomeChrome(){
    if (!home) return;
    home.innerHTML = `
      <div class="home-first-hero">
        <div><div class="eyebrow">START WITH THE SCIENTIFIC TASK</div><h2>What are you trying to do?</h2><p>Choose the work first. Engineering Lab resolves the Lab, workspace, runtime and deeper tools behind it.</p></div>
        <button class="secondary" data-home-explore-all>Explore all capabilities</button>
      </div>
      <section class="home-layer"><div class="section-head"><div><h3>Start here</h3><p>Four first-principles paths into the complete engineering workflow.</p></div></div><div id="homeTaskGrid" class="home-task-grid"></div></section>
      <section class="home-layer"><div class="section-head"><div><h3>Continue</h3><p>Your current Project, recent capability, active work and latest saved result context.</p></div></div><div id="homeContinueContext" class="home-context-grid"></div></section>
      <section class="home-layer home-feature-layer"><div class="section-head"><div><div class="eyebrow">FEATURED EXPERIMENT FAMILY</div><h3>Rotating U-Tube Research</h3><p>Move from physical model and data through uncertainty, planning, robust design and hysteresis without hunting through nested tabs.</p></div></div><div id="homeFeaturedFamilies" class="home-feature-grid"></div></section>
      <section class="home-layer home-readiness-layer"><div class="section-head"><div><h3>Ready to work</h3><p>Only the status needed to decide your next action; detailed repair stays in Runtime and Dependency Center.</p></div><button class="secondary" data-home-explore-all>Explore all capabilities</button></div><div id="homeReadiness" class="home-readiness-grid"></div></section>
      <div class="home-legacy-compat" aria-hidden="true"><div id="stats"></div><div id="featuredGrid"></div></div>`;

    if (!document.getElementById('homeProgressiveStyles')) {
      const style = document.createElement('style');
      style.id = 'homeProgressiveStyles';
      style.textContent = `
        .home-first-hero{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding:28px 30px;border:1px solid var(--border,#30384a);border-radius:22px;background:linear-gradient(135deg,rgba(69,92,155,.12),rgba(20,26,38,.22));margin-bottom:24px}.home-first-hero h2{font-size:38px;line-height:1.08;margin:6px 0 10px}.home-first-hero p{max-width:760px;margin:0;opacity:.76;line-height:1.5}.home-layer{margin:0 0 28px}.home-task-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.home-task-card{border:1px solid var(--border,#30384a);border-radius:18px;background:var(--panel,#171d29);padding:18px;display:flex;flex-direction:column;min-width:0;gap:12px}.home-task-head{display:flex;gap:12px;align-items:flex-start}.home-task-icon{width:38px;height:38px;display:grid;place-items:center;border:1px solid var(--border,#30384a);border-radius:12px;font-size:20px;flex:0 0 auto}.home-task-card h4{margin:0 0 4px;font-size:17px}.home-task-card p{margin:0;opacity:.7;font-size:13px;line-height:1.45}.home-quick-actions{display:flex;flex-direction:column;gap:7px;flex:1}.home-quick-action{width:100%;text-align:left;border:1px solid var(--border,#30384a);background:rgba(255,255,255,.025);color:inherit;border-radius:11px;padding:9px 10px;cursor:pointer;min-height:40px}.home-task-footer{display:flex;gap:8px;flex-wrap:wrap}.home-context-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.home-context-card{border:1px solid var(--border,#30384a);border-radius:15px;padding:15px;background:rgba(20,25,35,.55);min-width:0}.home-context-card span{font-size:11px;letter-spacing:.04em;text-transform:uppercase;opacity:.55}.home-context-card strong{display:block;margin:7px 0 3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.home-context-card small{opacity:.62;line-height:1.35}.home-context-card button{margin-top:10px}.home-feature-layer{padding:20px;border:1px solid var(--border,#30384a);border-radius:20px;background:rgba(74,111,220,.06)}.home-feature-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.home-feature-card{border:1px solid var(--border,#30384a);border-radius:14px;padding:14px;background:rgba(15,20,30,.58);min-width:0}.home-feature-step{font-size:11px;opacity:.5;margin-bottom:6px}.home-feature-card h4{margin:0 0 8px;font-size:14px}.home-feature-card button{margin-top:4px}.home-readiness-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.home-ready-item{border-top:2px solid var(--border,#30384a);padding:10px 4px}.home-ready-item span{display:block;font-size:11px;opacity:.55;text-transform:uppercase}.home-ready-item strong{display:block;margin-top:6px}.home-legacy-compat{display:none!important}.unified-search-results{position:absolute;z-index:40;top:calc(100% + 8px);right:0;width:min(720px,75vw);max-height:460px;overflow:auto;border:1px solid var(--border,#30384a);border-radius:16px;background:var(--panel,#171d29);padding:8px;box-shadow:0 16px 45px rgba(0,0,0,.35)}.search-wrap{position:relative}.unified-search-results.hidden{display:none}.unified-search-row{width:100%;display:flex;align-items:center;gap:12px;text-align:left;border:0;background:transparent;color:inherit;border-radius:11px;padding:10px;cursor:pointer}.unified-search-row:hover,.unified-search-row:focus-visible{background:rgba(255,255,255,.055);outline:none}.unified-search-type{width:82px;flex:0 0 auto;font-size:10px;text-transform:uppercase;opacity:.55}.unified-search-copy{min-width:0}.unified-search-copy strong,.unified-search-copy small{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.unified-search-copy small{opacity:.55;margin-top:2px}@media(max-width:1180px){.home-task-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.home-context-grid,.home-readiness-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.home-first-hero{align-items:flex-start;flex-direction:column}.home-first-hero h2{font-size:30px}.home-task-grid,.home-context-grid,.home-feature-grid,.home-readiness-grid{grid-template-columns:1fr}.unified-search-results{width:min(92vw,620px);right:-8px}}`;
      document.head.appendChild(style);
    }
  }

  function taskCard(family){
    const quick=(family.featured||[]).map(surface).filter(Boolean).slice(0,3);
    return `<article class="home-task-card"><div class="home-task-head"><div class="home-task-icon">${familyIcon[family.id]||'⌘'}</div><div><h4>${escHome(family.label)}</h4><p>${escHome(family.description||'')}</p></div></div><div class="home-quick-actions">${quick.map(s=>`<button class="home-quick-action" data-home-surface="${escHome(s.id)}">${escHome(s.label)}</button>`).join('')}</div><div class="home-task-footer"><button class="primary small" data-home-family="${escHome(family.id)}">View all</button>${family.destination?`<button class="secondary small" data-home-destination="${escHome(family.destination)}">Open ${escHome(family.destination==='labs'?'Labs':'native tools')}</button>`:''}</div></article>`;
  }

  function renderContinue(){
    const node=document.getElementById('homeContinueContext'); if(!node)return;
    const project=currentProject(), recent=recentCapability(), running=runningTaskCount(), snapshot=latestSnapshot();
    const cards=[
      project ? {type:'Active Project',title:project.name,detail:`${project.datasets??0} datasets · ${project.runs??0} runs`,action:'workspaces',label:'Open Project'} : {type:'Active Project',title:'No Project selected',detail:'Create or select a .physlab Project when your work needs persistent data and evidence.',action:'workspaces',label:'Projects'},
      recent ? {type:'Recent Capability',title:recent.label,detail:recent.category||'Engineering workspace',surface:recent.id,label:'Reopen'} : {type:'Recent Capability',title:'Nothing opened yet',detail:'Your most recently opened Workbench capability will appear here.'},
      {type:'Active Work',title:running?`${running} task${running===1?'':'s'} running`:'No active tasks',detail:running?'Open Task Center for progress and logs.':'Builds, launches and long operations will surface here.',action:'tasks',label:'Task Center'},
      snapshot ? {type:'Latest Saved Result',title:snapshot.moduleId||snapshot.id||'Saved run',detail:snapshot.createdAt||'Saved in active Project',action:'results',label:'Results'} : {type:'Latest Saved Result',title:'No saved run yet',detail:'Saved run snapshots and result context will appear here.',action:'results',label:'Results'}
    ];
    node.innerHTML=cards.map(card=>`<article class="home-context-card"><span>${escHome(card.type)}</span><strong>${escHome(card.title)}</strong><small>${escHome(card.detail)}</small>${card.surface?`<button class="secondary small" data-home-surface="${escHome(card.surface)}">${escHome(card.label)}</button>`:card.action?`<button class="secondary small" data-home-destination="${escHome(card.action)}">${escHome(card.label)}</button>`:''}</article>`).join('');
  }

  function renderFeatured(){
    const node=document.getElementById('homeFeaturedFamilies'); if(!node)return;
    const family=(layout.featuredFamilies||[]).find(row=>row.id==='rotating-utube');
    const rows=(family?.surfaceIds||[]).map(surface).filter(Boolean);
    node.innerHTML=rows.map((s,i)=>`<article class="home-feature-card"><div class="home-feature-step">${i+1} / ${rows.length}</div><h4>${escHome(s.label)}</h4><button class="secondary small" data-home-surface="${escHome(s.id)}">Open experiment</button></article>`).join('');
  }

  function renderReadiness(){
    const node=document.getElementById('homeReadiness'); if(!node)return;
    const project=currentProject(), running=runningTaskCount();
    const nativeReady=[runtime?.radiaReady,runtime?.chronoReady,runtime?.vampireReady].filter(Boolean).length;
    const rows=[
      ['Python',runtime?.pythonReady?(runtime.pythonVersion||'Ready'):'Needs attention'],
      ['Native engines',`${nativeReady} optional engine${nativeReady===1?'':'s'} ready`],
      ['Project',project?project.name:'No active Project'],
      ['Tasks',running?`${running} running`:'Idle']
    ];
    node.innerHTML=rows.map(([label,value])=>`<div class="home-ready-item"><span>${escHome(label)}</span><strong>${escHome(value)}</strong></div>`).join('');
  }

  function renderProgressiveHome(){
    const taskGrid=document.getElementById('homeTaskGrid');
    if(taskGrid)taskGrid.innerHTML=(layout.taskFamilies||[]).map(taskCard).join('');
    renderContinue(); renderFeatured(); renderReadiness();
  }

  function familyById(id){ return (layout.taskFamilies||[]).find(row=>row.id===id); }
  function showWorkbenchForFamily(id){
    const family=familyById(id);
    if(window.PhysicalLabWorkbench?.showWorkbench) window.PhysicalLabWorkbench.showWorkbench({category:family?.filterCategory||'All'});
  }

  const nativeDestinations=[
    {id:'workspaces',label:'Projects',type:'Project / Data',keywords:'project workspace physlab evidence'},
    {id:'data',label:'Data Bridge',type:'Project / Data',keywords:'measurement import arduino serial dataset'},
    {id:'results',label:'Results Center',type:'Project / Data',keywords:'results validation statistics reproducibility'},
    {id:'runtime',label:'Runtime Center',type:'Runtime / Dependency',keywords:'runtime python radia chrono vampire'},
    {id:'dependencies',label:'Dependency Center',type:'Runtime / Dependency',keywords:'dependency repair full mode native engine'},
    {id:'integrity',label:'Integrity Center',type:'Destination',keywords:'compatibility smoke test integrity'},
    {id:'pipelines',label:'Physics Pipelines',type:'Destination',keywords:'pipeline handoff workflow'},
    {id:'campaigns',label:'Campaigns',type:'Destination',keywords:'parameter sweep queue campaign'}
  ];

  function unifiedSearchIndex(){
    const labRows=(modules||[]).filter(m=>m.kind==='lab').map(m=>({kind:'lab',type:'Lab',id:m.id,label:m.name,detail:m.category||'',haystack:[m.name,m.id,m.category,...(m.tags||[])].join(' ').toLowerCase()}));
    const surfaceRows=launcher.allSurfaces().map(s=>({kind:'surface',type:'Capability',id:s.id,label:s.label,detail:s.category||s.routeHint||'',haystack:[s.label,s.id,s.category,s.routeHint,...(s.profiles||[])].join(' ').toLowerCase()}));
    const destinationRows=nativeDestinations.map(d=>({kind:'destination',type:d.type,id:d.id,label:d.label,detail:d.keywords,haystack:[d.label,d.id,d.keywords].join(' ').toLowerCase()}));
    return [...labRows,...surfaceRows,...destinationRows];
  }

  function ensureSearchResults(){
    if(!searchInput)return null;
    let results=document.getElementById('unifiedSearchResults');
    if(!results){results=document.createElement('div');results.id='unifiedSearchResults';results.className='unified-search-results hidden';results.setAttribute('role','listbox');searchInput.closest('.search-wrap')?.appendChild(results);}
    return results;
  }

  function renderUnifiedSearch(rawQuery){
    const results=ensureSearchResults(); if(!results)return;
    const query=String(rawQuery??searchInput?.value??'').trim().toLowerCase();
    if(!query){results.classList.add('hidden');results.innerHTML='';return;}
    const matches=unifiedSearchIndex().filter(row=>row.haystack.includes(query)).slice(0,12);
    results.innerHTML=matches.length?matches.map(row=>`<button class="unified-search-row" role="option" data-search-kind="${escHome(row.kind)}" data-search-id="${escHome(row.id)}"><span class="unified-search-type">${escHome(row.type)}</span><span class="unified-search-copy"><strong>${escHome(row.label)}</strong><small>${escHome(row.detail)}</small></span></button>`).join(''):'<div class="empty-state">No Labs, capabilities or native destinations match.</div>';
    results.classList.remove('hidden');
  }

  async function openSearchResult(kind,id){
    if(kind==='surface'){await launcher.prepareAndOpen(id);return;}
    if(kind==='destination'){showView(id);return;}
    if(kind==='lab'){
      const module=modules.find(m=>m.id===id); if(!module)return;
      let state=statusFor(module);
      if(!state.safeReady&&!state.fullReady){await installModule(id);state=statusFor(module);}
      const mode=state.fullReady?'full':'safe';
      await openModule(id,mode);
    }
  }

  installHomeChrome();
  renderProgressiveHome();

  const baseRender = typeof render === 'function' ? render : null;
  if(baseRender){
    render = function(){ baseRender(); renderProgressiveHome(); };
  }

  document.addEventListener('click', event=>{
    const surfaceButton=event.target.closest('[data-home-surface]');
    if(surfaceButton){launcher.prepareAndOpen(surfaceButton.dataset.homeSurface).catch(error=>toast(String(error),true));return;}
    const familyButton=event.target.closest('[data-home-family]');
    if(familyButton){showWorkbenchForFamily(familyButton.dataset.homeFamily);return;}
    const destination=event.target.closest('[data-home-destination]');
    if(destination){showView(destination.dataset.homeDestination);return;}
    if(event.target.closest('[data-home-explore-all]')){window.PhysicalLabWorkbench?.showWorkbench?.();return;}
    const searchRow=event.target.closest('[data-search-kind]');
    if(searchRow){openSearchResult(searchRow.dataset.searchKind,searchRow.dataset.searchId).catch(error=>toast(String(error),true));ensureSearchResults()?.classList.add('hidden');return;}
    if(searchInput && !event.target.closest('.search-wrap')) ensureSearchResults()?.classList.add('hidden');
  });

  if(searchInput){
    searchInput.placeholder='Search Labs, experiments, tools, data and runtimes';
    searchInput.oninput=event=>renderUnifiedSearch(event.target.value);
    searchInput.onfocus=()=>{if(searchInput.value.trim())renderUnifiedSearch(searchInput.value)};
    searchInput.addEventListener('keydown',event=>{if(event.key==='Escape')ensureSearchResults()?.classList.add('hidden')});
  }

  launcher.subscribe(()=>renderProgressiveHome());
  window.PhysicalLabHome={render:renderProgressiveHome,renderUnifiedSearch,showWorkbenchForFamily};
})();
