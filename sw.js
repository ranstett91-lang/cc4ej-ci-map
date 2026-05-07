// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2024-2026 Claymont Coalition for Environmental Justice. See LICENSE.md.

const CACHE = 'cc4ej-v24';
// Mobile audit fix #20 — separate, size-bounded cache for Mapbox tiles.
// Network-first stays the rule for app data; tiles use cache-first with a
// soft cap so offline / spotty cellular doesn't blank the basemap.
const TILE_CACHE = 'cc4ej-tiles-v1';
const TILE_CACHE_MAX = 220; // ~25 MB at typical raster tile sizes

// Single-source-of-truth set of caches we want to keep on activate. If you
// bump CACHE or TILE_CACHE versions, add the OLD name here only if you want
// to preserve it; otherwise the activate handler will sweep it. Defensive
// against the prior pattern where the deletion filter referenced two
// constants directly — adding a new cache without updating both would have
// silently orphaned it.
const KEEP_CACHES = new Set([CACHE, TILE_CACHE]);

// No blocking precache — install completes instantly so the new SW always activates.
// Data files are cached on first network-first fetch below.
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => !KEEP_CACHES.has(k)).map(k => caches.delete(k))
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

  // Open-Meteo weather/AQI — always network, never cache (must stay live).
  // Use explicit respondWith() for the GET case rather than a bare `return`.
  // iOS Safari has a documented quirk where a bare-return inside a fetch
  // handler that's intercepting a content-shaped response can raise "The
  // string did not match the expected pattern" (the GeoJSON branch below
  // was added to work around exactly that). The non-GET bare-return is
  // intentional and safe — it tells the SW we don't want to handle the
  // request at all, and the iOS quirk only fires when we partially handle.
  if (url.hostname.includes('open-meteo.com')) {
    if (e.request.method !== 'GET') return;
    e.respondWith(fetch(e.request));
    return;
  }

  // Mobile audit fix #20 — Mapbox style/tiles + NOAA SLR raster tiles:
  // cache-first with size cap. Style.json + sprites + glyphs + raster +
  // vector tiles all live under api.mapbox.com or *.tiles.mapbox.com.
  // NOAA SLR rasters live under *.coast.noaa.gov. Cache-first means the
  // basemap shows offline for areas the user has already visited; the
  // size cap keeps the cache from ballooning. GET requests only.
  // (The original `includes('tiles')` check was too broad — any third-
  // party host with "tiles" in the name would also land here, and any
  // other tile host would silently fall through to the unbounded static
  // cache, defeating the size cap.)
  const isMapTile = (
       url.hostname === 'api.mapbox.com'
    || url.hostname.endsWith('.tiles.mapbox.com')
    || url.hostname === 'maps.coast.noaa.gov'
    || url.hostname === 'maps2.coast.noaa.gov'
  );
  if (isMapTile) {
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
  //
  // Fallback strategy:
  //   - Network 2xx       : return network, populate cache
  //   - Network 5xx       : return cached if available, otherwise the 5xx
  //                         (audit fix 3.3 — Vercel deploy windows
  //                         shouldn't break users who already have the
  //                         site cached). 4xx is NOT cache-fallback'd
  //                         because a 404 means the resource genuinely
  //                         doesn't exist anymore and showing a stale
  //                         cached copy would be misleading.
  //   - Network exception : return cached if available, otherwise
  //                         Response.error() so the page sees a proper
  //                         failure
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
          return resp;
        }
        if (resp.status >= 500 && resp.status < 600) {
          return caches.match(e.request).then(cached => cached || resp);
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
