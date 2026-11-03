// Minimal service worker: makes the dashboard installable on phone ("Add to Home screen"). API calls always go to the network.
const C = "sc-v1", SHELL = ["/", "/styles.css", "/app.js", "/demo.js", "/fcsim.js", "/manifest.webmanifest", "/icon-192.png"];
self.addEventListener("install", e => e.waitUntil(caches.open(C).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (u.pathname.startsWith("/api") || u.pathname.startsWith("/media")) return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
