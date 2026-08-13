let _eventoInstalacaoPwa = null;

window.addEventListener("beforeinstallprompt", (evento) => {
  evento.preventDefault();
  _eventoInstalacaoPwa = evento;
  document.dispatchEvent(new CustomEvent("gotur-pwa-instalavel"));
});

window.addEventListener("appinstalled", () => {
  _eventoInstalacaoPwa = null;
  document.dispatchEvent(new CustomEvent("gotur-pwa-instalada"));
});

function pwaInstalavelAgora() {
  return _eventoInstalacaoPwa !== null;
}

async function instalarPwaVion() {
  if (!_eventoInstalacaoPwa) return false;
  _eventoInstalacaoPwa.prompt();
  const escolha = await _eventoInstalacaoPwa.userChoice;
  _eventoInstalacaoPwa = null;
  return escolha.outcome === "accepted";
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  });
}
