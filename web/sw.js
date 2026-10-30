// Mind & Routine service worker: works offline, shows notifications.
// The page's data never passes through here -- it stays in the browser.
const CACHE = "mind-v1";
const FILES = ["./", "index.html", "manifest.webmanifest", "icon-192.png", "icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Network first (so updates arrive), cache when offline.
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(fetch(e.request).then(r => {
    const copy = r.clone();
    caches.open(CACHE).then(c => c.put(e.request, copy));
    return r;
  }).catch(() => caches.match(e.request).then(r => r || caches.match("index.html"))));
});

// Background reminder when the app is closed (Chrome decides how often).
self.addEventListener("periodicsync", e => {
  if (e.tag === "mind-checkin") {
    e.waitUntil(self.registration.showNotification("Mind & Routine",
      {body: "Time for a check-in?", tag: "mind-checkin", icon: "icon-192.png"}));
  }
});

// Tapping a notification opens (or focuses) the app.
self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({type: "window"}).then(list => {
    for (const c of list) if ("focus" in c) return c.focus();
    return self.clients.openWindow("./");
  }));
});
