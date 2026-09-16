(() => {
  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return;

  const GENERIC_HOSTS = ['numerical-methods', 'oscillation-integration', 'nonlinear-chaos'];
  const FULL_MODE_SURFACES = new Set([
    'radia-forward', 'radia-tolerance', 'radia-radiation-propagation',
    'radiation-stokes', 'radiation-quality', 'radiation-seed-compare',
    'radiation-interactions', 'radiation-response-surface', 'undulator-spectrum'
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

  let surfaces = [];
  let statuses = new Map();
  let activeCategory = 'All';
  let query = '';
  let busySurface = '';

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const byId = (id) => document.getElementById(id);

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
        <div class="capability-card-head">
          <span class="capability-category">${esc(surface.category)}</span>
          <span class="capability-access">${esc(accessLabel(surface))}</span>
        </div>
        <h3>${esc(surface.label)}</h3>
        <p>${esc(descriptions[surface.id] || surface.routeHint || 'Engineering Lab interactive workspace.')}</p>
        <div class="capability-meta">
          <span>Host · ${esc(launch.host)}</span>
          <span>${full ? 'Full mode' : 'Safe mode'}</span>
          <span>${esc(hostState)}</span>
        </div>
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
    try {
      surfaces = await invoke('list_surface_catalog');
      await refreshStatuses();
      render();
    } catch (error) {
      const grid = byId('capabilityGrid');
      if (grid) grid.innerHTML = `<div class="empty-state">Workbench catalog could not load: ${esc(error)}</div>`;
    }
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
      if (!ready && launch.mode === 'full') {
        throw new Error(`${surface.label} needs ${launch.host} Full mode and its fragile scientific dependencies are not ready. Open Dependency Center to repair them.`);
      }
      if (!ready) throw new Error(`${launch.host} is not ready after preparation.`);

      const info = await invoke('launch_module', {moduleId: launch.host, mode: launch.mode, surfaceId: surface.id});
      window.__physicalLabSurfaceHost = launch.host;
      const title = byId('openLabTitle');
      const url = byId('openLabUrl');
      const frame = byId('labFrame');
      if (title) title.textContent = surface.label;
      if (url) url.textContent = `${launch.host} · ${launch.mode.toUpperCase()} · ${info.url}`;
      if (frame) frame.src = info.url;
      if (typeof window.showView === 'function') window.showView('lab');
      else if (typeof showView === 'function') showView('lab');
    } catch (error) {
      alert(`Could not open ${surface.label}: ${error}`);
    } finally {
      busySurface = '';
      render();
    }
  }

  document.addEventListener('click', (event) => {
    const category = event.target.closest('[data-surface-category]');
    if (category) {
      activeCategory = category.dataset.surfaceCategory;
      render();
      return;
    }
    const open = event.target.closest('[data-surface-open]');
    if (open) prepareAndOpen(open.dataset.surfaceOpen);
  });

  document.addEventListener('DOMContentLoaded', () => {
    const input = byId('capabilitySearch');
    if (input) input.addEventListener('input', (event) => { query = event.target.value || ''; render(); });
    const nav = document.querySelector('[data-view="capabilities"]');
    if (nav) nav.addEventListener('click', () => loadCatalog());
    const close = byId('closeLab');
    if (close) close.addEventListener('click', async () => {
      const host = window.__physicalLabSurfaceHost;
      if (!host) return;
      window.__physicalLabSurfaceHost = '';
      try { await invoke('stop_module', {moduleId: host}); } catch (_) {}
    }, true);
  });

  window.PhysicalLabWorkbench = {loadCatalog, prepareAndOpen};
})();
