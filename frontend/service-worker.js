const CACHE_NAME = "gotur-shell-v1";
const SHELL_URLS = [
  "/",
  "/index.html",
  "/manifest.json",
  "/css/style.css",
  "/js/api.js",
  "/js/auth.js",
  "/js/pagamento-pix.js",
  "/js/pwa.js",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL_URLS))
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((chaves) => Promise.all(chaves.filter((chave) => chave !== CACHE_NAME).map((chave) => caches.delete(chave))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (evento) => {
  const { request } = evento;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    // Nunca cacheia a API nem terceiros (ex: tiles do mapa): preço,
    // disponibilidade de poltrona e posição do GPS precisam ser sempre em
    // tempo real, e cachear indevidamente causaria dados errados.
    return;
  }

  evento.respondWith(
    fetch(request)
      .then((resposta) => {
        const copia = resposta.clone();
        caches
          .open(CACHE_NAME)
          .then((cache) => cache.put(request, copia))
          .catch(() => {});
        return resposta;
      })
      .catch(() => caches.match(request).then((resposta) => resposta || caches.match("/index.html")))
  );
});

// Push notification real (Web Push) — usado no rastreio de fretamento e
// frete pra avisar quando o status muda, sem precisar do app aberto.
self.addEventListener("push", (evento) => {
  let dados = { title: "GoTur", body: "Você tem uma atualização.", url: "/" };
  try {
    if (evento.data) dados = { ...dados, ...evento.data.json() };
  } catch (e) {
    // payload inesperado — usa o texto puro como corpo
    if (evento.data) dados.body = evento.data.text();
  }

  evento.waitUntil(
    self.registration.showNotification(dados.title, {
      body: dados.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: dados.url },
    })
  );
});

self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  const url = (evento.notification.data && evento.notification.data.url) || "/";
  evento.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((janelas) => {
      for (const janela of janelas) {
        if (janela.url === url && "focus" in janela) return janela.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
