self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
  console.log("Service worker installed");
});

self.addEventListener("activate", (event) => {
  console.log("Service worker activating...");
  event.waitUntil(
    self.clients.claim().then(() => {
      console.log("Service Worker is now controlling pages");
    }),
  );
});

self.addEventListener("fetch", (event) => {
  // Handle all requests to domains other than the current origin
  if (new URL(event.request.url).origin !== location.origin) {
    console.log("Service Worker intercepting:", event.request.url);
    event.respondWith(
      fetch(event.request.url, { mode: "no-cors" })
        .then((response) => {
          // Clone the response as we can only read it once
          const originalResponse = response.clone();

          // Create new headers
          const newHeaders = new Headers(originalResponse.headers);
          newHeaders.set("Cross-Origin-Resource-Policy", "cross-origin");

          debugger;

          // Create new response with modified headers
          return new Response(originalResponse.body, {
            status: originalResponse.status,
            statusText: originalResponse.statusText,
            headers: newHeaders,
          });
        })
        .catch((error) => {
          console.error("Service Worker fetch error:", error);
        }),
    );
  }
});
