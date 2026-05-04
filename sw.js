// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2024-2026 Claymont Coalition for Environmental Justice. See LICENSE.md.

const CACHE = 'cc4ej-v22';
// Mobile audit fix #20 — separate, size-bounded cache for Mapbox tiles.
// Network-first stays the rule for app data; tiles use cache-first with a
// soft cap so offline / spotty cellular doesn't blank the basemap.
const TILE_CACHE = 'cc4ej-tiles-v1';
const TILE_CACHE_MAX = 220; // ~25 MB at typical raster tile sizes

// No blocking precache — install completes instantly so the new SW always activates.
// Data files are cached on first network-first fetch below.
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE && k !== TILE_CACHE).map(k => caches.delete(k))
      ))
      .catch(() => {})
      .then(() => self.clients.claim())
  );
});

// Trim TILE_CACHE down to TILE_CACHE_MAX entries (FIFO).
// Called after each cache.put — async, never blocks the response.
async function trimTileCache() {
  try {
    const cache = await caches.open(TILE_CACHE);
    const keys = await cache.keys();
    const overflow = keys.length - TILE_CACHE_MAX;
    if (overflow > 0) {
      for (let i = 0; i < overflow; i++) await cache.delete(keys[i]);
    }
  } catch (_) {}
}

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Open-Meteo weather/AQI — always network, never cache (must stay live)
  if (url.hostname.includes('open-meteo.com')) {
    return;
  }

  // Mobile audit fix #20 — Mapbox style/tiles: cache-first with size cap.
  // Style.json + sprites + glyphs + raster + vector tiles all live under
  // api.mapbox.com or *.tiles.mapbox.com. Cache-first means the basemap
  // shows offline for areas the user has already visited; size cap keeps
  // the cache from ballooning. GET requests only.
  if (url.hostname.includes('mapbox') || url.hostname.includes('tiles')) {
    if (e.request.method !== 'GET') return;
    e.respondWith(
      caches.open(TILE_CACHE).then(cache =>
        cache.match(e.request).then(hit => {
          if (hit) {
            // Refresh in background so cached tiles don't go stale forever.
            fetch(e.request).then(r => {
              if (r && r.ok) cache.put(e.request, r.clone()).then(trimTileCache);
            }).catch(() => {});
            return hit;
          }
          return fetch(e.request).then(r => {
            if (r && r.ok) cache.put(e.request, r.clone()).then(trimTileCache);
            return r;
          }).catch(() => Response.error());
        })
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
        if (resp.ok && e.request.method === 'GET') {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone)).catch(() => {});
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
          caches.open(CACHE).then(c => c.put(e.request, clone)).catch(() => {});
        }
        return resp;
      })
    )
  );
});
