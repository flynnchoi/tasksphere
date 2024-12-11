// Cache version
const CACHE_NAME = 'tasksphere-cache-v1';

// Files to cache
const urlsToCache = [
  '/',
  '/static/icons/tasksphere_icon_128.png',
  '/static/icons/tasksphere_icon_256.png',
  '/static/icons/tasksphere_icon_512.png',
  // Add other static assets or routes you want to cache
];

// Install event
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

// Activate event
self.addEventListener('activate', event => {
  // Cleanup old caches if necessary
});

// Fetch event
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached response or fetch from network
        return response || fetch(event.request);
      })
  );
});