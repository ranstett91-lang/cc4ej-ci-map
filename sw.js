// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.

const CACHE = 'cc4ej-v20';

// No blocking precache — install completes instantly so v14 always activates.
// Data files are cached on first network-first fetch below.
self.addEventListener('install', () => {
  self.skipWaiting();
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

  // Open-Meteo weather/AQI — always network, never cache (must stay live)
  if (url.hostname.includes('open-meteo.com')) {
    return;
  }

  // Mapbox — network-first, fall back to cache
  if (url.hostname.includes('mapbox') || url.hostname.includes('tiles')) {
    e.respondWith(
      fetch(e.request).catch(() =>
        caches.match(e.request).then(r => r || Response.error())
      )
    );
    return;
  }

  // App data (HTML, JSON, GeoJSON) — network-first, cache on success.
  // GeoJSON must use explicit respondWith() — a bare return without
  // respondWith() causes iOS Safari to throw "The string did not match
  // the expected pattern" instead of falling through to the network.
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
