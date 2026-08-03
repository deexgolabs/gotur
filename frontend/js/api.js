const API_BASE = "/api";

function obterAuth() {
  const bruto = localStorage.getItem("gotur_auth");
  return bruto ? JSON.parse(bruto) : null;
}

function salvarAuth(dados) {
  localStorage.setItem("gotur_auth", JSON.stringify(dados));
}

function limparAuth() {
  localStorage.removeItem("gotur_auth");
}

async function api(metodo, caminho, corpo) {
  const auth = obterAuth();
  const cabecalhos = { "Content-Type": "application/json" };
  if (auth && auth.access_token) {
    cabecalhos["Authorization"] = `Bearer ${auth.access_token}`;
  }

  const resposta = await fetch(`${API_BASE}${caminho}`, {
    method: metodo,
    headers: cabecalhos,
    body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
  });

  const texto = await resposta.text();
  const dados = texto ? JSON.parse(texto) : null;

  if (resposta.status === 401 && auth && auth.access_token) {
    limparAuth();
    window.location.href = "/index.html";
    throw new Error("Sessão expirada, faça login novamente.");
  }

  if (!resposta.ok) {
    const detalhe = dados && dados.detail ? dados.detail : "Erro inesperado ao comunicar com o servidor";
    throw new Error(typeof detalhe === "string" ? detalhe : JSON.stringify(detalhe));
  }
  return dados;
}
