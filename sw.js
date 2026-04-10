const CACHE = 'cc4ej-v7';
const PRECACHE = [
  './',
  './index.html',
  './manifest.json',
  './facilities.json?v=2',
  './communities.json?v=2',
  './de_blockgroups.geojson?v=2',
  './efa_splits.geojson?v=2',
  './addicks_estates_memo.html',
  './icon-192.png?v=9',
  './icon-512.png?v=9',
  './icon-apple.png?v=9',
  './cc4ej-logo.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Mapbox tiles — network-first
  if (url.hostname.includes('mapbox') || url.hostname.includes('tiles')) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }

  // HTML and app data — network-first so updates always show immediately
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
      }).catch(() => caches.match(e.request))
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
