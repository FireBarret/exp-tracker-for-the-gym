// Service worker. The point here isn't offline support -- it's that the host is
// slow to answer, so anything that can be served from disk should be.
//
//  * static assets  -> cache-first, and they never change under a given URL
//                      because the app fingerprints them (?v=<hash>)
//  * pages          -> network-first with a cached fallback, so you always see
//                      current data but a dropped signal still renders something
//
// The version below is derived from the asset hashes, so a deploy that changes
// any file evicts the old caches automatically.

const VERSION = "{{ version }}";
const STATIC_CACHE = "gym-static-" + VERSION;
const PAGE_CACHE = "gym-pages-" + VERSION;

// Fingerprinted URLs, baked in at render time. When any asset changes this file
// changes too, which is what makes the browser install a fresh worker.
const PRECACHE = {{ precache | tojson }};

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((c) => c.addAll(PRECACHE))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== STATIC_CACHE && k !== PAGE_CACHE)
            .map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

function isStatic(url) {
  return url.pathname.startsWith("/static/");
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;                 // never cache writes

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === "/export.csv") return;       // always fetch fresh

  if (isStatic(url)) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(STATIC_CACHE).then((c) => c.put(req, copy));
        }
        return res;
      }))
    );
    return;
  }

  // Pages: go to the network, fall back to whatever was last seen.
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(PAGE_CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match("/splits")))
  );
});
