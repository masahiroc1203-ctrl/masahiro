// オフライン用サービスワーカー
// ファイルを変更したら VERSION を上げるとキャッシュが更新される
const VERSION = 'v4';
const CACHE = `hiit-weekly-${VERSION}`;
const ASSETS = [
  './',
  'index.html',
  'manifest.webmanifest',
  'css/app.css',
  'js/app.js',
  'js/audio.js',
  'js/engine.js',
  'js/figure.js',
  'js/player.js',
  'js/pose.js',
  'js/store.js',
  'js/ui.js',
  'js/video.js',
  'js/data/exercises.js',
  'js/data/menus.js',
  'js/data/parts.js',
  'js/views/exercises.js',
  'js/views/history.js',
  'js/views/home.js',
  'js/views/menus.js',
  'icons/icon.svg',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('hiit-weekly-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// 同じオリジンのファイルは「キャッシュを返しつつ裏で更新」。外部（YouTube等）は素通し
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(req, { ignoreSearch: true });
      const network = fetch(req)
        .then((res) => {
          if (res.ok) cache.put(req, res.clone());
          return res;
        })
        .catch(() => cached || Response.error());
      return cached || network;
    }),
  );
});
