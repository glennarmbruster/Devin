const prefix = 'all-about-devin-' + encodeURIComponent(self.registration.scope) + ':';
const cacheName = prefix + edition;
const localURL = path => new URL(path, self.registration.scope).href;
const assets = files.map(localURL);

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(cacheName);
    for (let start = 0; start < assets.length; start += 16) {
      const batch = assets.slice(start, start + 16);
      await cache.addAll(batch.map(url => new Request(url, {cache:'reload'})));
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith(prefix) && name !== cacheName) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('message', event => {
  const request = event.data;
  if (request !== 'verify' && request?.type !== 'verify-edition') return;
  event.waitUntil((async () => {
    const cache = await caches.open(cacheName);
    const stored = await cache.keys();
    const saved = new Set(stored.map(asset => asset.url));
    const matches = request === 'verify' || request.edition === edition;
    event.ports[0]?.postMessage(matches && assets.every(asset => saved.has(asset)));
  })());
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  url.search = '';
  url.hash = '';
  const target = url.href === self.registration.scope ? localURL('index.html') : url.href;
  if (!assets.includes(target)) return;
  event.respondWith((async () => {
    const cached = await (await caches.open(cacheName)).match(target);
    return cached || fetch(event.request);
  })());
});
