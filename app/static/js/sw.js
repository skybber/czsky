// Minimal service worker that makes CzSky installable as a PWA.
// It does not cache anything; it only shows a simple offline page when navigation fails.

const OFFLINE_HTML =
    '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<title>CzSky - offline</title></head>' +
    '<body style="background:#0b1020;color:#d8e0ff;font-family:sans-serif;text-align:center;padding-top:30vh">' +
    '<p>No network connection.</p>' +
    '<p><a href="" style="color:#d8e0ff" onclick="location.reload();return false;">Retry</a></p>' +
    '</body></html>';

self.addEventListener('install', function () {
    self.skipWaiting();
});

self.addEventListener('activate', function (event) {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function (event) {
    if (event.request.mode !== 'navigate') {
        return;
    }
    event.respondWith(
        fetch(event.request).catch(function () {
            return new Response(OFFLINE_HTML, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
        })
    );
});
