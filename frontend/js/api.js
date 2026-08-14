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
  let dados = null;
  if (texto) {
    try {
      dados = JSON.parse(texto);
    } catch (e) {
      if (!resposta.ok) throw new Error("O servidor teve um problema inesperado. Tente novamente em instantes.");
      throw new Error("Resposta inesperada do servidor.");
    }
  }

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

function baixarCsv(nomeArquivo, cabecalhos, linhas) {
  const escapar = (valor) => {
    const texto = valor === null || valor === undefined ? "" : String(valor);
    return /[",\n;]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
  };
  const conteudo = [cabecalhos, ...linhas].map((linha) => linha.map(escapar).join(";")).join("\r\n");
  const blob = new Blob(["﻿" + conteudo], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeArquivo;
  link.click();
  URL.revokeObjectURL(url);
}

async function abrirArquivoAutenticado(caminho, nomeJanela) {
  const auth = obterAuth();
  const resposta = await fetch(`${API_BASE}${caminho}`, {
    headers: auth && auth.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {},
  });
  if (!resposta.ok) {
    throw new Error("Não foi possível abrir o arquivo.");
  }
  const blob = await resposta.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, nomeJanela || "_blank");
}
