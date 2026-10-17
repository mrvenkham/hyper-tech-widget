// COSMO service worker. Lets the JARVIS page install as an app and still open
// (with an "offline" banner) when the COSMO server isn't running.
// Never caches /api/*: COSMO's answers, news and your data always come live.
const SHELL = "cosmo-shell-v1";
const FILES = ["/", "/countries.json", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== SHELL).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin || url.pathname.startsWith("/api/") || e.request.method !== "GET") return;
  if (url.pathname === "/" || url.pathname === "/index.html") {
    // Page: always try the server first so updates show up; fall back to the saved copy.
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(SHELL).then(c => c.put("/", copy)); return r; })
      .catch(() => caches.match("/")));
    return;
  }
  // Map, icons, manifest: saved copy first (they rarely change).
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request)));
});
