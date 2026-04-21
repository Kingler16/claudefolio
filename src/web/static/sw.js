/* Velora Service Worker — PWA Foundation (Phase 0)
 *
 * Strategie:
 *  - PRECACHE: kritische Shell-Assets beim install
 *  - RUNTIME:  NetworkFirst für HTML/API, CacheFirst für /static/
 *  - OFFLINE:  fallback auf /offline für nicht gecachte HTML
 *
 * Push-Handler folgt in Phase 3.
 */

const VERSION = 'velora-0.1.0';
const STATIC_CACHE = `velora-static-${VERSION}`;
const RUNTIME_CACHE = `velora-runtime-${VERSION}`;

const PRECACHE = [
  '/',
  '/offline',
  '/static/css/design-system.css',
  '/static/css/background.css',
  '/static/css/components.css',
  '/static/css/main.css',
  '/static/vendor/htmx.min.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE).catch(() => null))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => !k.endsWith(VERSION))
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // SSE-Stream (Chat) niemals cachen
  if (url.pathname.startsWith('/api/chat/threads/') && url.pathname.endsWith('/message')) {
    return;
  }
  // Share-Target-POST wird durch method:GET filter schon rausgefiltert, aber defensiv:
  if (url.pathname === '/api/share/trade') return;
  // Cache-Status ist hoch-dynamisch
  if (url.pathname === '/api/cache/status') return;

  // Manifest + Service-Worker selbst nie cachen
  if (url.pathname === '/manifest.webmanifest' || url.pathname === '/sw.js') return;

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(req));
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(req, { fallbackToCache: true }));
    return;
  }

  // HTML-Seiten: Network-First, Offline-Fallback
  if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirst(req, { fallbackToCache: true, offlinePage: '/offline' }));
    return;
  }
});

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(req, res.clone());
    }
    return res;
  } catch (err) {
    if (cached) return cached;
    throw err;
  }
}

async function networkFirst(req, { fallbackToCache = false, offlinePage = null } = {}) {
  try {
    const res = await fetch(req);
    if (res.ok && req.method === 'GET') {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(req, res.clone()).catch(() => null);
    }
    return res;
  } catch (err) {
    if (fallbackToCache) {
      const cached = await caches.match(req);
      if (cached) return cached;
    }
    if (offlinePage) {
      const offline = await caches.match(offlinePage);
      if (offline) return offline;
    }
    throw err;
  }
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
