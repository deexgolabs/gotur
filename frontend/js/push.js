// Ativa push notification real (Web Push) numa tela de rastreio pública —
// funciona sem login, a inscrição fica vinculada só ao código de rastreio.

function urlBase64ParaUint8Array(base64) {
  const preenchimento = "=".repeat((4 - (base64.length % 4)) % 4);
  const base64Seguro = (base64 + preenchimento).replace(/-/g, "+").replace(/_/g, "/");
  const bruto = window.atob(base64Seguro);
  const saida = new Uint8Array(bruto.length);
  for (let i = 0; i < bruto.length; i++) saida[i] = bruto.charCodeAt(i);
  return saida;
}

async function ativarPushRastreio(caminhoInscricaoApi, swScope) {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    throw new Error("Seu navegador não suporta notificações push.");
  }

  const resposta = await fetch("/api/push/chave-publica");
  const { chave_publica } = await resposta.json();
  if (!chave_publica) {
    throw new Error("Notificações push ainda não foram ativadas por essa empresa.");
  }

  const permissao = await Notification.requestPermission();
  if (permissao !== "granted") {
    throw new Error("Permissão de notificações negada.");
  }

  const registro = await navigator.serviceWorker.register(swScope ? `${swScope}service-worker.js` : "/service-worker.js");
  await navigator.serviceWorker.ready;

  let inscricao = await registro.pushManager.getSubscription();
  if (!inscricao) {
    inscricao = await registro.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ParaUint8Array(chave_publica),
    });
  }

  const dadosInscricao = inscricao.toJSON();
  await fetch(caminhoInscricaoApi, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint: dadosInscricao.endpoint, keys: dadosInscricao.keys }),
  });
}
