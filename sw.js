const CACHE = 'cc4ej-v11';
const PRECACHE = [
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

self.addEventListener('install', e => {
  // skipWaiting() first — don't wait for caching to finish before taking over.
  // This minimises the window where the old SW (without geojson bypass) is
  // still intercepting fetches after the page has the updated HTML.
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .catch(() => {}) // never let cache-cleanup failure block clients.claim()
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Mapbox — network-first, fall back to cache
  if (url.hostname.includes('mapbox') || url.hostname.includes('tiles')) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }

  // GeoJSON data files — bypass SW entirely, let browser HTTP cache handle it
  if (url.pathname.endsWith('.geojson')) {
    return;
  }

  // HTML / JSON — network-first, cache on success, fall back only if cached
  const isDataFile = url.pathname === '/'
    || url.pathname.endsWith('.html')
    || url.pathname.endsWith('.json');
  if (isDataFile) {
    e.respondWith(
      fetch(e.request).then(resp => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      }).catch(() => caches.match(e.request).then(cached => {
        if (cached) return cached;
        // No cache — surface a real error rather than returning undefined
        return new Response('{}', { status: 503, headers: { 'Content-Type': 'application/json' } });
      }))
    );
    return;
  }

  // Static assets — cache-first
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
      if (resp.ok && e.request.method === 'GET') {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return resp;
    }))
  );
});
