(() => {
  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return;

  const GENERIC_HOSTS = ['numerical-methods', 'oscillation-integration', 'nonlinear-chaos'];
  const FULL_MODE_SURFACES = new Set([
    'radia-forward', 'radia-tolerance', 'radia-radiation-propagation',
    'radiation-stokes', 'radiation-quality', 'radiation-seed-compare',
    'radiation-interactions', 'radiation-response-surface'
  ]);

  let statuses = new Map();
  let activeHost = '';
  let busySurface = '';
  const listeners = new Set();

  const allSurfaces = () => Array.isArray(window.__PHYSICAL_LAB_SURFACES__) ? window.__PHYSICAL_LAB_SURFACES__ : [];
  const surfaceById = id => allSurfaces().find(row => row.id === id) || null;
  const candidateHosts = surface => {
    const preferred = Array.isArray(surface?.preferredProfiles) ? surface.preferredProfiles.filter(Boolean) : [];
    const legal = Array.isArray(surface?.profiles) ? surface.profiles.filter(Boolean) : [];
    return [...new Set([...preferred, ...legal, ...(preferred.length || legal.length ? [] : GENERIC_HOSTS)])];
  };
  const modeFor = surface => FULL_MODE_SURFACES.has(surface?.id) ? 'full' : 'safe';
  const statusForHost = host => statuses.get(host) || null;
  const notify = () => listeners.forEach(fn => { try { fn({busySurface, activeHost}); } catch (_) {} });

  async function refreshStatuses() {
    try {
      const rows = await invoke('module_statuses');
      statuses = new Map((rows || []).map(row => [row.id, row]));
    } catch (error) {
      console.warn('Capability launcher host status unavailable', error);
      statuses = new Map();
    }
    notify();
    return statuses;
  }

  function resolveHost(surface) {
    if (!surface) return {host:'', mode:'safe', ready:false, status:null};
    const candidates = candidateHosts(surface);
    const mode = modeFor(surface);
    const readinessKey = mode === 'full' ? 'fullReady' : 'safeReady';
    const readyHost = candidates.find(id => statuses.get(id)?.[readinessKey]);
    if (readyHost) return {host:readyHost, mode, ready:true, status:statuses.get(readyHost)};
    const installedHost = candidates.find(id => statuses.get(id)?.installed);
    const host = installedHost || candidates[0] || '';
    return {host, mode, ready:false, status:statuses.get(host) || null};
  }

  function withSurfaceQuery(url, id) {
    return `${url}${String(url).includes('?') ? '&' : '?'}surface=${encodeURIComponent(id)}`;
  }

  async function prepareAndOpen(surfaceId) {
    const surface = surfaceById(surfaceId);
    if (!surface) throw new Error(`Unknown Engineering Lab capability: ${surfaceId}`);
    busySurface = surfaceId;
    notify();
    try {
      await refreshStatuses();
      let launch = resolveHost(surface);
      if (!launch.host) throw new Error(`${surface.label || surface.id} has no legal host profile.`);
      let status = statusForHost(launch.host);
      const readyNow = launch.mode === 'full' ? status?.fullReady : status?.safeReady;
      if (!status?.installed || !readyNow) {
        await invoke('install_module', {moduleId: launch.host});
        await refreshStatuses();
        launch = resolveHost(surface);
        status = statusForHost(launch.host);
      }
      const ready = launch.mode === 'full' ? status?.fullReady : status?.safeReady;
      if (!ready && launch.mode === 'full') {
        throw new Error(`${surface.label} needs ${launch.host} Full mode. Repair its fragile scientific dependencies in Dependency Center, then open it again.`);
      }
      if (!ready) throw new Error(`${launch.host} is not ready after preparation.`);

      const info = await invoke('launch_module', {moduleId: launch.host, mode: launch.mode});
      activeHost = launch.host;
      window.__physicalLabSurfaceHost = launch.host;
      const title = document.getElementById('openLabTitle');
      const url = document.getElementById('openLabUrl');
      const frame = document.getElementById('labFrame');
      if (title) title.textContent = surface.label || surface.id;
      if (url) url.textContent = `${launch.host} · ${launch.mode.toUpperCase()} · ${surface.id}`;
      if (frame) frame.src = withSurfaceQuery(info.url, surface.id);
      if (typeof showView === 'function') showView('lab');
      try { localStorage.setItem('physicalLab.recentCapability', surface.id); } catch (_) {}
      return {surface, launch, info};
    } finally {
      busySurface = '';
      notify();
    }
  }

  async function stopActiveHost() {
    const host = activeHost || window.__physicalLabSurfaceHost || '';
    activeHost = '';
    window.__physicalLabSurfaceHost = '';
    if (!host) return;
    try { await invoke('stop_module', {moduleId: host}); } catch (_) {}
    notify();
  }

  function subscribe(fn) {
    if (typeof fn !== 'function') return () => {};
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  window.PhysicalLabCapabilityLauncher = {
    allSurfaces,
    surfaceById,
    refreshStatuses,
    statusForHost,
    resolveHost,
    modeFor,
    prepareAndOpen,
    stopActiveHost,
    subscribe,
    get busySurface(){ return busySurface; },
    get activeHost(){ return activeHost; }
  };

  document.addEventListener('DOMContentLoaded', () => {
    const back = document.getElementById('backFromLab');
    if (back) back.addEventListener('click', () => { stopActiveHost(); }, true);
  });
})();
