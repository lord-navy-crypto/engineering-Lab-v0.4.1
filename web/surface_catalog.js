(() => {
  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return;

  const GENERIC_HOSTS = ['numerical-methods', 'oscillation-integration', 'nonlinear-chaos'];
  const FULL_MODE_SURFACES = new Set([
    'radia-forward', 'radia-tolerance', 'radia-radiation-propagation',
    'radiation-stokes', 'radiation-quality', 'radiation-seed-compare',
    'radiation-interactions', 'radiation-response-surface'
  ]);
  const descriptions = {
    'utube-studio': 'Rotating U-tube model, uncertainty, robust design, digital twin and hysteresis.',
    'data-bridge': 'Promote parsed numeric tables into reusable canonical project datasets.',
    'measurement-registry': 'Project measurement/calibration records and explicit provenance links.',
    'project-workspace': 'Canonical project home connecting data, analysis, modeling and reproducibility.',
    'utube-robust': 'Robust design, adaptive experiments, verification and U-Tube digital twin.',
    'utube-hysteresis': 'Measured ramp hysteresis fitting and rate-envelope prediction.',
    'radiation-interactions': 'Pairwise manufacturing-error non-additivity screening.',
    'radiation-response-surface': 'Bounded two-factor radiation response-surface exploration.'
  };

  let surfaces = Array.isArray(window.__PHYSICAL_LAB_SURFACES__) ? window.__PHYSICAL_LAB_SURFACES__ : [];
  let statuses = new Map();
  let activeCategory = 'All';
  let query = '';
  let busySurface = '';

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const byId = (id) => document.getElementById(id);

  function ensureWorkbenchChrome() {
    if (!document.querySelector('[data-view="capabilities"]')) {
      const nav = document.querySelector('.nav');
      const labs = nav?.querySelector('[data-view="labs"]');
      const button = document.createElement('button');
      button.className = 'nav-item';
      button.dataset.view = 'capabilities';
      button.innerHTML = '<span>⌘</span>Workbench';
      if (nav) nav.insertBefore(button, labs?.nextSibling || nav.children[1] || null);
    }
    if (!byId('capabilitiesView')) {
      const main = document.querySelector('main.main');
      const firstView = main?.querySelector('.view');
      const section = document.createElement('section');
      section.id = 'capabilitiesView';
      section.className = 'view';
      section.innerHTML = `
        <div class="research-hero workbench-hero">
          <div><div class="eyebrow">EVERY USER-FACING CAPABILITY • ONE FRONT DOOR</div><h2>Engineering Workbench</h2>
          <p>Discover and open every registered workspace and previously embedded child tool without knowing its hidden Lab route.</p></div>
          <div class="research-badge">Native reachability</div>
        </div>
        <div id="capabilitySummary" class="stats capability-summary"></div>
        <div class="workbench-toolbar">
          <div class="search-wrap workbench-search"><span>⌕</span><input id="capabilitySearch" placeholder="Search all capabilities, profiles and routes" /></div>
          <div id="capabilityFilters" class="filters capability-filters"></div>
        </div>
        <div id="capabilityGrid" class="capability-grid"><div class="empty-state">Open Workbench to load the capability catalog.</div></div>`;
      if (main) main.insertBefore(section, firstView || null);
    }
    if (!byId('workbenchNativeStyles')) {
      const style = document.createElement('style');
      style.id = 'workbenchNativeStyles';
      style.textContent = `
        .workbench-toolbar{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin:18px 0 20px}
        .workbench-search{min-width:320px;flex:1;max-width:620px}.capability-filters{display:flex;gap:8px;flex-wrap:wrap}
        .filter-chip{border:1px solid var(--border,#30384a);background:var(--panel,#171d29);color:inherit;border-radius:999px;padding:8px 12px;cursor:pointer}
        .filter-chip.active{background:rgba(95,134,255,.18);border-color:rgba(120,154,255,.8)}
        .capability-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px;padding-bottom:28px}
        .capability-card{border:1px solid var(--border,#30384a);background:var(--panel,#171d29);border-radius:18px;padding:18px;display:flex;flex-direction:column;gap:10px;min-height:260px}
        .capability-card h3{margin:0;font-size:18px}.capability-card p{margin:0;opacity:.78;line-height:1.45;flex:1}
        .capability-card-head,.capability-meta{display:flex;gap:7px;flex-wrap:wrap}.capability-card-head span,.capability-meta span,.capability-profiles{font-size:12px}
        .capability-category,.capability-access,.capability-meta span{border:1px solid var(--border,#30384a);border-radius:999px;padding:5px 8px}
        .capability-access{opacity:.75}.capability-profiles{opacity:.65;line-height:1.4}.capability-card .primary{align-self:flex-start;margin-top:4px}
        .capability-summary .stat-card span{display:block;opacity:.68;margin-top:4px}
        @media(max-width:900px){.capability-grid{grid-template-columns:1fr}.workbench-search{min-width:100%;max-width:none}}
      `;
      document.head.appendChild(style);
    }
  }

  function showWorkbench() {
    ensureWorkbenchChrome();
    document.querySelectorAll('.view').forEach((view) => view.classList.remove('active-view'));
    document.querySelectorAll('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.view === 'capabilities'));
    byId('capabilitiesView')?.classList.add('active-view');
    if (byId('viewTitle')) byId('viewTitle').textContent = 'Engineering Workbench';
    if (byId('viewSubtitle')) byId('viewSubtitle').textContent = 'Every user-facing Engineering Lab capability, reachable from the native desktop.';
    loadCatalog();
  }

  function candidateHosts(surface) {
    const declared = Array.isArray(surface.profiles) ? surface.profiles.filter(Boolean) : [];
    return declared.length ? declared : GENERIC_HOSTS;
  }

  function hostResolution(surface) {
    const candidates = candidateHosts(surface);
    const mode = FULL_MODE_SURFACES.has(surface.id) ? 'full' : 'safe';
    const readyKey = mode === 'full' ? 'fullReady' : 'safeReady';
    const ready = candidates.find((id) => statuses.get(id)?.[readyKey]);
    if (ready) return {host: ready, mode, ready: true};
    const installed = candidates.find((id) => statuses.get(id)?.installed);
    if (installed) return {host: installed, mode, ready: false};
    return {host: candidates[0] || 'numerical-methods', mode, ready: false};
  }

  function accessLabel(surface) {
    if (surface.kind === 'embedded') return 'Child workspace';
    if (surface.launchMode === 'profile') return 'Profile-scoped';
    if (surface.launchMode === 'route') return 'Project route';
    return 'Direct';
  }

  function renderSummary(filtered) {
    const el = byId('capabilitySummary');
    if (!el) return;
    const categories = new Set(surfaces.map((s) => s.category));
    el.innerHTML = `
      <div class="stat-card"><b>${surfaces.length}</b><span>Desktop capabilities</span></div>
      <div class="stat-card"><b>${categories.size}</b><span>Categories</span></div>
      <div class="stat-card"><b>${surfaces.filter(s => s.kind === 'embedded').length}</b><span>Exposed child tools</span></div>
      <div class="stat-card"><b>${filtered.length}</b><span>Visible now</span></div>`;
  }

  function renderFilters() {
    const el = byId('capabilityFilters');
    if (!el) return;
    const categories = ['All', ...new Set(surfaces.map((s) => s.category))];
    el.innerHTML = categories.map((cat) => `<button class="filter-chip ${cat === activeCategory ? 'active' : ''}" data-surface-category="${esc(cat)}">${esc(cat)}</button>`).join('');
  }

  function render() {
    const grid = byId('capabilityGrid');
    if (!grid) return;
    const needle = query.trim().toLowerCase();
    const filtered = surfaces.filter((surface) => {
      if (activeCategory !== 'All' && surface.category !== activeCategory) return false;
      if (!needle) return true;
      const text = [surface.label, surface.id, surface.category, surface.routeHint, descriptions[surface.id], ...(surface.profiles || [])].join(' ').toLowerCase();
      return text.includes(needle);
    });
    renderSummary(filtered);
    renderFilters();
    if (!filtered.length) {
      grid.innerHTML = '<div class="empty-state">No capabilities match this search/filter.</div>';
      return;
    }
    grid.innerHTML = filtered.map((surface) => {
      const launch = hostResolution(surface);
      const status = statuses.get(launch.host);
      const hostState = status ? status.state : 'Not checked';
      const full = FULL_MODE_SURFACES.has(surface.id);
      const disabled = busySurface === surface.id ? 'disabled' : '';
      return `<article class="capability-card">
        <div class="capability-card-head"><span class="capability-category">${esc(surface.category)}</span><span class="capability-access">${esc(accessLabel(surface))}</span></div>
        <h3>${esc(surface.label)}</h3>
        <p>${esc(descriptions[surface.id] || surface.routeHint || 'Engineering Lab interactive workspace.')}</p>
        <div class="capability-meta"><span>Host · ${esc(launch.host)}</span><span>${full ? 'Full mode' : 'Safe mode'}</span><span>${esc(hostState)}</span></div>
        ${surface.profiles?.length ? `<div class="capability-profiles">Profiles: ${esc(surface.profiles.join(', '))}</div>` : ''}
        <button class="primary" data-surface-open="${esc(surface.id)}" ${disabled}>${busySurface === surface.id ? 'Preparing…' : 'Prepare & Open'}</button>
      </article>`;
    }).join('');
  }

  async function refreshStatuses() {
    try {
      const rows = await invoke('module_statuses');
      statuses = new Map((rows || []).map((row) => [row.id, row]));
    } catch (error) {
      console.warn('Workbench host status unavailable', error);
      statuses = new Map();
    }
  }

  async function loadCatalog() {
    ensureWorkbenchChrome();
    surfaces = Array.isArray(window.__PHYSICAL_LAB_SURFACES__) ? window.__PHYSICAL_LAB_SURFACES__ : surfaces;
    await refreshStatuses();
    render();
  }

  function withSurfaceQuery(url, surfaceId) {
    const joiner = String(url).includes('?') ? '&' : '?';
    return `${url}${joiner}surface=${encodeURIComponent(surfaceId)}`;
  }

  async function prepareAndOpen(surfaceId) {
    const surface = surfaces.find((s) => s.id === surfaceId);
    if (!surface) return;
    busySurface = surfaceId;
    render();
    try {
      await refreshStatuses();
      let launch = hostResolution(surface);
      let status = statuses.get(launch.host);
      if (!status?.installed || !(launch.mode === 'full' ? status.fullReady : status.safeReady)) {
        await invoke('install_module', {moduleId: launch.host});
        await refreshStatuses();
        launch = hostResolution(surface);
        status = statuses.get(launch.host);
      }
      const ready = launch.mode === 'full' ? status?.fullReady : status?.safeReady;
      if (!ready && launch.mode === 'full') throw new Error(`${surface.label} needs ${launch.host} Full mode. Repair its fragile scientific dependencies in Dependency Center, then open it again.`);
      if (!ready) throw new Error(`${launch.host} is not ready after preparation.`);

      const info = await invoke('launch_module', {moduleId: launch.host, mode: launch.mode});
      window.__physicalLabSurfaceHost = launch.host;
      const title = byId('openLabTitle');
      const url = byId('openLabUrl');
      const frame = byId('labFrame');
      const deepLink = withSurfaceQuery(info.url, surface.id);
      if (title) title.textContent = surface.label;
      if (url) url.textContent = `${launch.host} · ${launch.mode.toUpperCase()} · ${surface.id}`;
      if (frame) frame.src = deepLink;
      if (typeof showView === 'function') showView('lab');
    } catch (error) {
      alert(`Could not open ${surface.label}: ${error}`);
    } finally {
      busySurface = '';
      render();
    }
  }

  async function stopWorkbenchHost() {
    const host = window.__physicalLabSurfaceHost;
    if (!host) return;
    window.__physicalLabSurfaceHost = '';
    try { await invoke('stop_module', {moduleId: host}); } catch (_) {}
  }

  document.addEventListener('click', (event) => {
    const category = event.target.closest('[data-surface-category]');
    if (category) { activeCategory = category.dataset.surfaceCategory; render(); return; }
    const open = event.target.closest('[data-surface-open]');
    if (open) prepareAndOpen(open.dataset.surfaceOpen);
  });

  document.addEventListener('DOMContentLoaded', () => {
    ensureWorkbenchChrome();
    const input = byId('capabilitySearch');
    if (input) input.addEventListener('input', (event) => { query = event.target.value || ''; render(); });
    const nav = document.querySelector('[data-view="capabilities"]');
    if (nav) nav.addEventListener('click', (event) => { event.preventDefault(); showWorkbench(); });
    const back = byId('backFromLab');
    if (back) back.addEventListener('click', () => { stopWorkbenchHost(); }, true);
    loadCatalog();
  });

  window.PhysicalLabWorkbench = {loadCatalog, prepareAndOpen, showWorkbench};
})();
