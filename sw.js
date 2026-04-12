const CACHE = 'cc4ej-v13';

// Small critical files only — must all succeed for install to complete.
// Large GeoJSON files (1.4 MB total) are cached opportunistically so a slow
// mobile connection never prevents the new SW from installing and activating.
const PRECACHE_CRITICAL = [
  './',
  './index.html',
  './manifest.json',
  './facilities.json?v=2',
  './communities.json?v=2',
  './addicks_estates_memo.html',
  './icon-192.png?v=10',
  './icon-apple-2.png',
  './cc4ej-logo.png',
];

const PRECACHE_OPTIONAL = [
  './de_blockgroups.geojson?v=2',
  './efa_splits.geojson?v=2',
];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c =>
      c.addAll(PRECACHE_CRITICAL).then(() =>
        // Best-effort: don't block install if large files are slow/unavailable
        Promise.all(PRECACHE_OPTIONAL.map(url => c.add(url).catch(() => {})))
      )
    )
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .catch(() => {})
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Mapbox — network-first, fall back to cache
  if (url.hostname.includes('mapbox') || url.hostname.includes('tiles')) {
    e.respondWith(
      fetch(e.request).catch(() =>
        caches.match(e.request).then(r => r || Response.error())
      )
    );
    return;
  }

  // App data (HTML, JSON, GeoJSON) — network-first, cache on success, fall
  // back to cache.  GeoJSON is intentionally included here — a bare `return`
  // without calling respondWith() causes iOS Safari to throw
  // "The string did not match the expected pattern" instead of falling
  // through to the network.  Explicit respondWith() is required on iOS.
  const isDataFile = url.pathname === '/'
    || url.pathname.endsWith('.html')
    || url.pathname.endsWith('.json')
    || url.pathname.endsWith('.geojson');
  if (isDataFile) {
    e.respondWith(
      fetch(e.request).then(resp => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      }).catch(() =>
        caches.match(e.request).then(r => r || Response.error())
      )
    );
    return;
  }

  // Static assets — cache-first
  e.respondWith(
    caches.match(e.request).then(r =>
      r || fetch(e.request).then(resp => {
        if (resp.ok && e.request.method === 'GET') {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      })
    )
  );
});
