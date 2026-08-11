const SLUG = window.__LOJA_SLUG__;
let BRANDING = null;
let viagemAtual = null;
let poltronaSelecionadaId = null;
let retomarAposLogin = null;
let mapaFretamento, marcadorFretamento, linhaFretamento;
let mapaFrete, marcadorFrete, linhaFrete;

function escurecer(hex, fator) {
  const num = parseInt(hex.replace("#", ""), 16);
  const canal = (deslocamento) => Math.max(0, Math.min(255, Math.round(((num >> deslocamento) & 255) * fator)));
  return "#" + [16, 8, 0].map((d) => canal(d).toString(16).padStart(2, "0")).join("");
}

function clarear(hex, fator) {
  const num = parseInt(hex.replace("#", ""), 16);
  const canal = (deslocamento) => {
    const c = (num >> deslocamento) & 255;
    return Math.round(c + (255 - c) * fator)
      .toString(16)
      .padStart(2, "0");
  };
  return "#" + [16, 8, 0].map(canal).join("");
}

function aplicarTema(cor) {
  document.documentElement.style.setProperty("--azul", cor);
  document.documentElement.style.setProperty("--azul-escuro", escurecer(cor, 0.75));
  document.documentElement.style.setProperty("--azul-claro", clarear(cor, 0.92));
  document.getElementById("meta-theme-color").setAttribute("content", cor);
}

function iconeEmojiMapa(emoji) {
  return L.divIcon({
    html: `<div style="font-size:28px;line-height:1;transform:translate(-50%,-100%)">${emoji}</div>`,
    className: "",
    iconSize: [0, 0],
  });
}

function mostrarAlerta(mensagem, tipo = "erro", alvo = "alerta") {
  document.getElementById(alvo).innerHTML = `<div class="alerta ${tipo}">${mensagem}</div>`;
  if (tipo === "sucesso") setTimeout(() => (document.getElementById(alvo).innerHTML = ""), 4000);
}

function trocarVista(nome) {
  document.querySelectorAll(".loja-vista").forEach((v) => v.classList.remove("ativa"));
  document.getElementById(`vista-${nome}`).classList.add("ativa");
  document.querySelectorAll(".loja-nav-item").forEach((b) => b.classList.toggle("ativo", b.dataset.vista === nome));
  if (nome === "minhas") carregarMinhasViagens();
  if (nome === "conta") renderizarConta();
}

// ---------- Busca ----------

async function configurarCidadesBusca() {
  let cidades = [];
  try {
    cidades = await fetch(`/api/viagens/loja/${SLUG}/cidades`).then((r) => (r.ok ? r.json() : []));
  } catch (e) {
    return;
  }
  // Sem rotas cadastradas ainda (ou só uma cidade) — mantém os campos de
  // texto livre, não vale a pena forçar um select com uma opção só.
  if (cidades.length < 2) return;

  const opcoes = `<option value="">Selecione...</option>` + cidades.map((c) => `<option value="${c}">${c}</option>`).join("");

  const campoOrigem = document.getElementById("busca-origem");
  const selectOrigem = document.createElement("select");
  selectOrigem.id = "busca-origem";
  selectOrigem.required = true;
  selectOrigem.innerHTML = opcoes;
  campoOrigem.replaceWith(selectOrigem);

  const campoDestino = document.getElementById("busca-destino");
  const selectDestino = document.createElement("select");
  selectDestino.id = "busca-destino";
  selectDestino.required = true;
  selectDestino.innerHTML = opcoes;
  campoDestino.replaceWith(selectDestino);
}

function configurarBusca() {
  const hoje = new Date().toISOString().slice(0, 10);
  const campoData = document.getElementById("busca-data");
  campoData.value = hoje;
  campoData.min = hoje;

  document.getElementById("form-busca").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const origem = document.getElementById("busca-origem").value.trim();
    const destino = document.getElementById("busca-destino").value.trim();
    const data = campoData.value;
    const resultados = document.getElementById("resultados-busca");
    resultados.innerHTML = `<p class="loja-selo-vazio">Buscando...</p>`;
    try {
      const viagens = await fetch(
        `/api/viagens/buscar?origem=${encodeURIComponent(origem)}&destino=${encodeURIComponent(destino)}&data=${data}&tenant_id=${BRANDING.id}`
      ).then((r) => (r.ok ? r.json() : Promise.reject(new Error("Erro ao buscar"))));

      if (!viagens.length) {
        resultados.innerHTML = `<p class="loja-selo-vazio">Nenhuma viagem encontrada pra essa data.<br>Tente outra data ou confira o nome das cidades.</p>`;
        return;
      }
      resultados.innerHTML = viagens
        .map(
          (v, i) => `
        <div class="loja-card loja-card-viagem" data-indice="${i}">
          <div>
            <div class="trecho">${v.origem} → ${v.destino}</div>
            <div class="info">${new Date(v.data_hora_partida).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} · ${v.poltronas_livres} vagas</div>
          </div>
          <div class="preco">R$ ${Number(v.preco).toFixed(2)}</div>
        </div>`
        )
        .join("");

      resultados.querySelectorAll(".loja-card-viagem").forEach((card) => {
        card.addEventListener("click", () => abrirCompra(viagens[parseInt(card.dataset.indice, 10)]));
      });
    } catch (e) {
      resultados.innerHTML = `<p class="loja-selo-vazio">Erro ao buscar. Tente de novo.</p>`;
    }
  });
}

// ---------- Compra ----------

function abrirCompra(viagem) {
  viagemAtual = viagem;
  poltronaSelecionadaId = null;
  document.getElementById("alerta-compra").innerHTML = "";
  document.getElementById("compra-titulo").textContent = `${viagem.origem} → ${viagem.destino}`;
  document.getElementById("card-form-compra").classList.add("escondido");
  document.getElementById("area-pix-loja").classList.add("escondido");
  document.getElementById("form-compra-loja").classList.remove("escondido");

  document.querySelectorAll(".loja-vista").forEach((v) => v.classList.remove("ativa"));
  document.getElementById("vista-compra").classList.add("ativa");

  carregarMapaLoja();
}

function queryTrechoAtual() {
  return `?origem_parada_id=${viagemAtual.parada_origem_id}&destino_parada_id=${viagemAtual.parada_destino_id}`;
}

async function carregarMapaLoja() {
  const poltronas = await fetch(`/api/viagens/${viagemAtual.id}/poltronas${queryTrechoAtual()}`).then((r) => r.json());
  const porFileira = {};
  poltronas.forEach((p) => {
    porFileira[p.fileira] = porFileira[p.fileira] || [];
    porFileira[p.fileira].push(p);
  });

  const container = document.getElementById("mapa-onibus");
  container.innerHTML = Object.keys(porFileira)
    .sort((a, b) => a - b)
    .map((fileira) => {
      const assentos = porFileira[fileira].sort((a, b) => a.coluna - b.coluna);
      const celulas = [];
      assentos.forEach((p) => {
        if (p.coluna === 3) celulas.push('<div class="poltrona corredor"></div>');
        const classes = ["poltrona", p.status];
        if (p.poltrona_viagem_id === poltronaSelecionadaId) classes.push("selecionada");
        celulas.push(
          `<div class="${classes.join(" ")}" data-id="${p.poltrona_viagem_id}" data-status="${p.status}" data-numero="${p.numero}" data-preco="${p.preco}">${p.numero}</div>`
        );
      });
      return `<div class="fileira-poltronas">${celulas.join("")}</div>`;
    })
    .join("");

  container.querySelectorAll(".poltrona[data-id]").forEach((el) => {
    el.addEventListener("click", () => onClicarPoltronaLoja(el));
  });
}

async function onClicarPoltronaLoja(el) {
  if (el.dataset.status !== "livre") {
    mostrarAlerta("Essa poltrona não está disponível.", "erro", "alerta-compra");
    return;
  }
  if (!obterAuth()) {
    retomarAposLogin = { tipo: "poltrona", numero: el.dataset.numero, id: el.dataset.id };
    mostrarAlerta("Crie uma conta ou faça login pra escolher sua poltrona — é rápido.", "erro", "alerta-compra");
    trocarVista("conta");
    return;
  }

  try {
    await api("POST", `/viagens/${viagemAtual.id}/poltronas/${el.dataset.id}/hold${queryTrechoAtual()}`);
  } catch (erro) {
    mostrarAlerta(erro.message, "erro", "alerta-compra");
    carregarMapaLoja();
    return;
  }

  document.getElementById("alerta-compra").innerHTML = "";
  poltronaSelecionadaId = parseInt(el.dataset.id, 10);
  document.getElementById("compra-numero-selecionada").textContent = el.dataset.numero;
  document.getElementById("compra-preco-selecionada").textContent = `R$ ${Number(el.dataset.preco).toFixed(2)}`;
  const auth = obterAuth();
  if (auth && !document.getElementById("compra-nome").value) {
    document.getElementById("compra-nome").value = auth.nome || "";
  }
  document.getElementById("card-form-compra").classList.remove("escondido");
  carregarMapaLoja();
}

function configurarCompra() {
  document.getElementById("btn-voltar-busca").addEventListener("click", () => trocarVista("buscar"));

  document.getElementById("form-compra-loja").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!poltronaSelecionadaId) return;
    try {
      const resposta = await api("POST", `/viagens/${viagemAtual.id}/passagens`, {
        poltrona_viagem_id: poltronaSelecionadaId,
        cliente_nome: document.getElementById("compra-nome").value.trim(),
        cliente_documento: document.getElementById("compra-documento").value.trim(),
        forma_pagamento: document.getElementById("compra-forma").value,
        parada_origem_id: viagemAtual.parada_origem_id,
        parada_destino_id: viagemAtual.parada_destino_id,
        codigo_cupom: document.getElementById("compra-cupom").value.trim() || null,
      });

      if (resposta.pedido_pagamento) {
        document.getElementById("form-compra-loja").classList.add("escondido");
        const areaPix = document.getElementById("area-pix-loja");
        areaPix.classList.remove("escondido");
        renderizarPagamentoPix(areaPix, resposta.pedido_pagamento, {
          aoConfirmar: (passagem) => {
            mostrarAlerta(
              passagem ? `Compra confirmada! Localizador: ${passagem.localizador}` : "Compra confirmada!",
              "sucesso",
              "alerta-compra"
            );
            setTimeout(() => trocarVista("minhas"), 1200);
          },
        });
        return;
      }

      mostrarAlerta(`Compra confirmada! Localizador: ${resposta.passagem.localizador}`, "sucesso", "alerta-compra");
      setTimeout(() => trocarVista("minhas"), 1200);
    } catch (erro) {
      mostrarAlerta(erro.message, "erro", "alerta-compra");
    }
  });
}

// ---------- Minhas viagens ----------

function estrelasHtml(nota) {
  return "★".repeat(nota) + "☆".repeat(5 - nota);
}

async function carregarMinhasViagens() {
  const container = document.getElementById("minhas-conteudo");
  const auth = obterAuth();
  if (!auth) {
    container.innerHTML = `<p class="loja-selo-vazio">Faça login pra ver suas viagens.</p>`;
    return;
  }
  container.innerHTML = `<p class="loja-selo-vazio">Carregando...</p>`;
  try {
    const lista = await api("GET", `/passagens/minhas?tenant_id=${BRANDING.id}`);
    if (!lista.length) {
      container.innerHTML = `<p class="loja-selo-vazio">Você ainda não comprou nenhuma passagem aqui.</p>`;
      return;
    }
    container.innerHTML = lista
      .map(
        (p) => `
      <div class="loja-card">
        <div class="trecho">${p.origem} → ${p.destino}</div>
        <div class="info">${new Date(p.data_hora_partida).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} · Poltrona ${p.numero_poltrona}</div>
        <div class="info">Localizador: <strong>${p.localizador}</strong></div>
        <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center">
          <span class="selo ${p.status}">${p.status === "confirmada" ? "Confirmada" : "Cancelada"}</span>
          <span style="font-weight:700">R$ ${Number(p.preco).toFixed(2)}</span>
        </div>
        ${p.nota_avaliacao ? `<div class="avaliacao-nota" style="margin-top:8px">${estrelasHtml(p.nota_avaliacao)}</div>` : ""}
        ${p.pode_avaliar ? `<button class="secundario" data-avaliar="${p.id}" style="margin-top:10px;width:100%">Avaliar viagem</button>` : ""}
        ${p.pode_avaliar ? `
        <div class="escondido" id="form-avaliar-${p.id}" style="margin-top:10px">
          <div class="estrelas" data-estrelas="${p.id}">
            ${[1, 2, 3, 4, 5].map((n) => `<button type="button" class="estrela" data-nota="${n}">★</button>`).join("")}
          </div>
          <button type="button" data-enviar-avaliacao="${p.id}" style="margin-top:8px;width:100%">Enviar avaliação</button>
        </div>` : ""}
      </div>`
      )
      .join("");

    container.querySelectorAll("button[data-avaliar]").forEach((btn) => {
      btn.addEventListener("click", () => document.getElementById(`form-avaliar-${btn.dataset.avaliar}`).classList.toggle("escondido"));
    });
    container.querySelectorAll(".estrelas").forEach((grupo) => {
      grupo.querySelectorAll(".estrela").forEach((estrela) => {
        estrela.addEventListener("click", () => {
          const nota = parseInt(estrela.dataset.nota, 10);
          grupo.dataset.notaEscolhida = nota;
          grupo.querySelectorAll(".estrela").forEach((e) => e.classList.toggle("ativa", parseInt(e.dataset.nota, 10) <= nota));
        });
      });
    });
    container.querySelectorAll("button[data-enviar-avaliacao]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const passagemId = btn.dataset.enviarAvaliacao;
        const grupo = document.querySelector(`.estrelas[data-estrelas="${passagemId}"]`);
        const nota = parseInt(grupo.dataset.notaEscolhida || "0", 10);
        if (!nota) {
          mostrarAlerta("Escolha uma nota de 1 a 5 estrelas.");
          return;
        }
        try {
          await api("POST", `/passagens/${passagemId}/avaliar`, { nota });
          mostrarAlerta("Obrigado pela avaliação!", "sucesso");
          carregarMinhasViagens();
        } catch (erro) {
          mostrarAlerta(erro.message);
        }
      });
    });
  } catch (erro) {
    container.innerHTML = `<p class="loja-selo-vazio">Erro ao carregar suas viagens.</p>`;
  }
}

// ---------- Fretamento ----------

function trocarAbaFretamento(nome) {
  document.querySelectorAll("[data-aba-fretamento]").forEach((b) => b.classList.toggle("ativa", b.dataset.abaFretamento === nome));
  document.getElementById("fretamento-solicitar").classList.toggle("escondido", nome !== "solicitar");
  document.getElementById("fretamento-acompanhar").classList.toggle("escondido", nome !== "acompanhar");
}

function abrirAcompanharFretamento(codigo) {
  trocarVista("fretamento");
  trocarAbaFretamento("acompanhar");
  document.getElementById("fret-codigo").value = codigo;
  rastrearFretamentoLoja();
}

function configurarFretamento() {
  document.querySelectorAll("[data-aba-fretamento]").forEach((btn) => {
    btn.addEventListener("click", () => trocarAbaFretamento(btn.dataset.abaFretamento));
  });

  document.getElementById("form-fretamento").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const resposta = await fetch(`/api/fretamentos/loja/${SLUG}/solicitar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cliente_nome: document.getElementById("fret-nome").value.trim(),
          cliente_contato: document.getElementById("fret-contato").value.trim(),
          origem: document.getElementById("fret-origem").value.trim(),
          destino: document.getElementById("fret-destino").value.trim(),
          data_hora_saida: document.getElementById("fret-data").value,
          observacoes: document.getElementById("fret-obs").value.trim() || null,
        }),
      });
      if (!resposta.ok) {
        const erro = await resposta.json().catch(() => ({}));
        throw new Error(erro.detail || "Não foi possível enviar a solicitação.");
      }
      const dados = await resposta.json();
      document.getElementById("form-fretamento").reset();
      mostrarAlerta("Solicitação enviada! Acompanhe o andamento a qualquer momento por aqui.", "sucesso");
      abrirAcompanharFretamento(dados.codigo_rastreio);
    } catch (erro) {
      mostrarAlerta(erro.message);
    }
  });

  document.getElementById("btn-rastrear-fretamento").addEventListener("click", rastrearFretamentoLoja);
}

async function rastrearFretamentoLoja() {
  const codigo = document.getElementById("fret-codigo").value.trim().toUpperCase();
  const resultado = document.getElementById("fretamento-resultado");
  if (!codigo) return;
  resultado.innerHTML = `<p class="loja-selo-vazio">Buscando...</p>`;
  try {
    const dados = await fetch(`/api/fretamentos/rastrear/${codigo}`).then((r) => {
      if (!r.ok) throw new Error("Código não encontrado");
      return r.json();
    });

    history.replaceState(null, "", `/loja/${SLUG}?codigo=${codigo}`);

    const ROTULOS = { orcamento: "Orçamento", confirmado: "Confirmado", em_andamento: "Em andamento", concluido: "Concluído", cancelado: "Cancelado" };
    resultado.innerHTML = `
      <div class="loja-card">
        <div class="trecho">${dados.origem} → ${dados.destino}</div>
        <div class="info">Saída: ${new Date(dados.data_hora_saida).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</div>
        <div style="margin-top:8px"><span class="selo hold">${ROTULOS[dados.status] || dados.status}</span></div>
        ${dados.status === "em_andamento" ? '<div id="mapa-fretamento-loja" style="height:260px;border-radius:10px;margin-top:12px"></div>' : ""}
        <button type="button" class="secundario" id="btn-copiar-link-fretamento" style="margin-top:12px;width:100%">Copiar link pra acompanhar</button>
        <button type="button" class="secundario" id="btn-ativar-push-fretamento" style="margin-top:8px;width:100%">Ativar notificações</button>
      </div>`;

    document.getElementById("btn-copiar-link-fretamento").addEventListener("click", async () => {
      const link = `${window.location.origin}/loja/${SLUG}?codigo=${codigo}`;
      try {
        await navigator.clipboard.writeText(link);
        mostrarAlerta("Link copiado! Envie pra quem quiser acompanhar.", "sucesso");
      } catch (e) {
        mostrarAlerta(`Copie manualmente: ${link}`);
      }
    });

    document.getElementById("btn-ativar-push-fretamento").addEventListener("click", async (ev) => {
      ev.target.disabled = true;
      try {
        await ativarPushRastreio(`/api/fretamentos/rastrear/${codigo}/push`, `/loja/${SLUG}/`);
        ev.target.textContent = "Notificações ativadas!";
      } catch (erro) {
        mostrarAlerta(erro.message);
        ev.target.disabled = false;
      }
    });

    if (dados.status === "em_andamento" && dados.trajeto.length) {
      if (!mapaFretamento) {
        mapaFretamento = L.map("mapa-fretamento-loja");
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap", maxZoom: 19 }).addTo(mapaFretamento);
        linhaFretamento = L.polyline([], { color: BRANDING.cor_primaria, weight: 4 }).addTo(mapaFretamento);
      }
      const pontos = dados.trajeto.map((p) => [p.latitude, p.longitude]);
      linhaFretamento.setLatLngs(pontos);
      const ultimo = pontos[pontos.length - 1];
      if (marcadorFretamento) marcadorFretamento.setLatLng(ultimo);
      else marcadorFretamento = L.marker(ultimo, { icon: iconeEmojiMapa(dados.icone_mapa || "🚌") }).addTo(mapaFretamento);
      mapaFretamento.fitBounds(linhaFretamento.getBounds(), { maxZoom: 15, padding: [20, 20] });
    }
  } catch (erro) {
    resultado.innerHTML = `<p class="loja-selo-vazio">${erro.message}</p>`;
  }
}

// ---------- Frete ----------

function trocarAbaFrete(nome) {
  document.querySelectorAll("[data-aba-frete]").forEach((b) => b.classList.toggle("ativa", b.dataset.abaFrete === nome));
  document.getElementById("frete-solicitar").classList.toggle("escondido", nome !== "solicitar");
  document.getElementById("frete-acompanhar").classList.toggle("escondido", nome !== "acompanhar");
}

function abrirAcompanharFrete(codigo) {
  trocarVista("frete");
  trocarAbaFrete("acompanhar");
  document.getElementById("frete-codigo").value = codigo;
  rastrearFreteLoja();
}

function configurarFrete() {
  document.querySelectorAll("[data-aba-frete]").forEach((btn) => {
    btn.addEventListener("click", () => trocarAbaFrete(btn.dataset.abaFrete));
  });

  document.getElementById("form-frete").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const resposta = await fetch(`/api/fretes/loja/${SLUG}/solicitar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          remetente_nome: document.getElementById("frete-remetente-nome").value.trim(),
          remetente_contato: document.getElementById("frete-remetente-contato").value.trim(),
          destinatario_nome: document.getElementById("frete-destinatario-nome").value.trim(),
          destinatario_contato: document.getElementById("frete-destinatario-contato").value.trim() || null,
          descricao_carga: document.getElementById("frete-descricao-carga").value.trim() || null,
          origem: document.getElementById("frete-origem").value.trim(),
          destino: document.getElementById("frete-destino").value.trim(),
          data_hora_coleta: document.getElementById("frete-data-coleta").value,
          observacoes: document.getElementById("frete-obs").value.trim() || null,
        }),
      });
      if (!resposta.ok) {
        const erro = await resposta.json().catch(() => ({}));
        throw new Error(erro.detail || "Não foi possível enviar a solicitação.");
      }
      const dados = await resposta.json();
      document.getElementById("form-frete").reset();
      mostrarAlerta("Solicitação enviada! Acompanhe o andamento a qualquer momento por aqui.", "sucesso");
      abrirAcompanharFrete(dados.codigo_rastreio);
    } catch (erro) {
      mostrarAlerta(erro.message);
    }
  });

  document.getElementById("btn-rastrear-frete").addEventListener("click", rastrearFreteLoja);
}

async function rastrearFreteLoja() {
  const codigo = document.getElementById("frete-codigo").value.trim().toUpperCase();
  const resultado = document.getElementById("frete-resultado");
  if (!codigo) return;
  resultado.innerHTML = `<p class="loja-selo-vazio">Buscando...</p>`;
  try {
    const dados = await fetch(`/api/fretes/rastrear/${codigo}`).then((r) => {
      if (!r.ok) throw new Error("Código não encontrado");
      return r.json();
    });

    history.replaceState(null, "", `/loja/${SLUG}?frete=${codigo}`);

    const ROTULOS = { solicitado: "Solicitado", confirmado: "Confirmado", em_transito: "Em trânsito", entregue: "Entregue", cancelado: "Cancelado" };
    resultado.innerHTML = `
      <div class="loja-card">
        <div class="trecho">${dados.origem} → ${dados.destino}</div>
        <div class="info">Coleta: ${new Date(dados.data_hora_coleta).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</div>
        <div class="info">${dados.remetente_nome} → ${dados.destinatario_nome}</div>
        <div style="margin-top:8px"><span class="selo hold">${ROTULOS[dados.status] || dados.status}</span></div>
        ${dados.status === "em_transito" ? '<div id="mapa-frete-loja" style="height:260px;border-radius:10px;margin-top:12px"></div>' : ""}
        <button type="button" class="secundario" id="btn-copiar-link-frete" style="margin-top:12px;width:100%">Copiar link pra acompanhar</button>
        <button type="button" class="secundario" id="btn-ativar-push-frete" style="margin-top:8px;width:100%">Ativar notificações</button>
      </div>`;

    document.getElementById("btn-copiar-link-frete").addEventListener("click", async () => {
      const link = `${window.location.origin}/loja/${SLUG}?frete=${codigo}`;
      try {
        await navigator.clipboard.writeText(link);
        mostrarAlerta("Link copiado! Envie pra quem quiser acompanhar.", "sucesso");
      } catch (e) {
        mostrarAlerta(`Copie manualmente: ${link}`);
      }
    });

    document.getElementById("btn-ativar-push-frete").addEventListener("click", async (ev) => {
      ev.target.disabled = true;
      try {
        await ativarPushRastreio(`/api/fretes/rastrear/${codigo}/push`, `/loja/${SLUG}/`);
        ev.target.textContent = "Notificações ativadas!";
      } catch (erro) {
        mostrarAlerta(erro.message);
        ev.target.disabled = false;
      }
    });

    if (dados.status === "em_transito" && dados.trajeto.length) {
      if (!mapaFrete) {
        mapaFrete = L.map("mapa-frete-loja");
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap", maxZoom: 19 }).addTo(mapaFrete);
        linhaFrete = L.polyline([], { color: BRANDING.cor_primaria, weight: 4 }).addTo(mapaFrete);
      }
      const pontos = dados.trajeto.map((p) => [p.latitude, p.longitude]);
      linhaFrete.setLatLngs(pontos);
      const ultimo = pontos[pontos.length - 1];
      if (marcadorFrete) marcadorFrete.setLatLng(ultimo);
      else marcadorFrete = L.marker(ultimo, { icon: iconeEmojiMapa(dados.icone_mapa || "🚚") }).addTo(mapaFrete);
      mapaFrete.fitBounds(linhaFrete.getBounds(), { maxZoom: 15, padding: [20, 20] });
    }
  } catch (erro) {
    resultado.innerHTML = `<p class="loja-selo-vazio">${erro.message}</p>`;
  }
}

// ---------- Conta ----------

function configurarConta() {
  renderizarConta();
}

function renderizarConta() {
  const container = document.getElementById("conta-conteudo");
  const auth = obterAuth();

  if (auth) {
    container.innerHTML = `
      <div class="loja-card">
        <div style="font-weight:700;font-size:1.1rem">${auth.nome}</div>
        <div class="info" style="color:var(--cinza)">${auth.role === "cliente" ? "Cliente" : auth.role}</div>
        <div class="linha-acoes" style="margin-top:14px">
          <button type="button" class="secundario" id="btn-sair-loja">Sair</button>
        </div>
      </div>`;
    document.getElementById("btn-sair-loja").addEventListener("click", () => {
      limparAuth();
      renderizarConta();
      mostrarAlerta("Você saiu da sua conta.", "sucesso");
    });
    return;
  }

  container.innerHTML = `
    <div class="loja-abas">
      <button type="button" class="loja-aba ativa" data-aba-conta="login">Entrar</button>
      <button type="button" class="loja-aba" data-aba-conta="registrar">Criar conta</button>
    </div>
    <form class="loja-card loja-form escondido" id="form-login-loja">
      <label for="login-email">E-mail</label>
      <input id="login-email" type="email" required />
      <label for="login-senha">Senha</label>
      <input id="login-senha" type="password" required />
      <button type="submit">Entrar</button>
    </form>
    <form class="loja-card loja-form" id="form-registrar-loja">
      <label for="registrar-nome">Nome</label>
      <input id="registrar-nome" required />
      <label for="registrar-email">E-mail</label>
      <input id="registrar-email" type="email" required />
      <label for="registrar-documento">CPF</label>
      <input id="registrar-documento" required />
      <label for="registrar-senha">Senha</label>
      <input id="registrar-senha" type="password" required minlength="6" />
      <p class="rodape-form" style="text-align:left">
        Ao criar sua conta, você concorda com os
        <a href="/termos-de-uso.html" target="_blank">Termos de Uso</a> e a
        <a href="/politica-privacidade.html" target="_blank">Política de Privacidade</a>.
      </p>
      <button type="submit">Criar conta</button>
    </form>`;

  const formLogin = document.getElementById("form-login-loja");
  const formRegistrar = document.getElementById("form-registrar-loja");

  document.querySelectorAll("[data-aba-conta]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-aba-conta]").forEach((b) => b.classList.remove("ativa"));
      btn.classList.add("ativa");
      const login = btn.dataset.abaConta === "login";
      formLogin.classList.toggle("escondido", !login);
      formRegistrar.classList.toggle("escondido", login);
    });
  });

  formLogin.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const dados = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: document.getElementById("login-email").value.trim(),
          senha: document.getElementById("login-senha").value,
        }),
      }).then((r) => {
        if (!r.ok) throw new Error("E-mail ou senha inválidos");
        return r.json();
      });
      salvarAuth(dados);
      aposLogin();
    } catch (erro) {
      mostrarAlerta(erro.message);
    }
  });

  formRegistrar.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const dados = await fetch("/api/auth/registrar-cliente", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nome: document.getElementById("registrar-nome").value.trim(),
          email: document.getElementById("registrar-email").value.trim(),
          documento: document.getElementById("registrar-documento").value.trim(),
          senha: document.getElementById("registrar-senha").value,
        }),
      }).then((r) => {
        if (!r.ok) return r.json().then((e) => Promise.reject(new Error(e.detail || "Não foi possível criar a conta")));
        return r.json();
      });
      salvarAuth(dados);
      aposLogin();
    } catch (erro) {
      mostrarAlerta(erro.message);
    }
  });
}

function aposLogin() {
  renderizarConta();
  mostrarAlerta("Login realizado!", "sucesso");
  if (retomarAposLogin && viagemAtual) {
    retomarAposLogin = null;
    document.querySelectorAll(".loja-vista").forEach((v) => v.classList.remove("ativa"));
    document.getElementById("vista-compra").classList.add("ativa");
    carregarMapaLoja();
  } else {
    retomarAposLogin = null;
    trocarVista("buscar");
  }
}

// ---------- Bootstrap ----------

function chaveCacheMarca() {
  return `gotur_marca_${SLUG}`;
}

function aplicarSplash(marca) {
  if (!marca) return;
  document.getElementById("splash-nome").textContent = marca.nome || "";
  if (marca.logo_url) {
    const img = document.getElementById("splash-logo");
    img.src = marca.logo_url;
    img.classList.remove("escondido");
  }
}

async function iniciar() {
  // Numa visita anterior já vimos o logo/nome dessa loja — mostra na hora
  // (splash instantâneo, estilo app nativo) enquanto busca os dados
  // frescos, em vez de deixar a tela em branco/genérica até a rede
  // responder.
  try {
    const cache = JSON.parse(localStorage.getItem(chaveCacheMarca()) || "null");
    aplicarSplash(cache);
  } catch (e) {
    // cache corrompido — ignora e segue com a tela padrão
  }

  try {
    const resposta = await fetch(`/api/empresas/loja/${SLUG}`);
    if (!resposta.ok) throw new Error("not found");
    BRANDING = await resposta.json();
    localStorage.setItem(chaveCacheMarca(), JSON.stringify({ nome: BRANDING.nome, logo_url: BRANDING.logo_url }));
  } catch (e) {
    document.getElementById("splash-spinner").classList.add("escondido");
    const erro = document.createElement("p");
    erro.className = "erro-splash";
    erro.textContent = "Essa loja não foi encontrada. Confira o link com a viação.";
    document.getElementById("tela-carregando").appendChild(erro);
    return;
  }

  document.title = `${BRANDING.nome} — GoTur`;
  document.getElementById("loja-nome").textContent = BRANDING.nome;
  if (BRANDING.logo_url) {
    const img = document.getElementById("loja-logo");
    img.src = BRANDING.logo_url;
    img.classList.remove("escondido");
  }
  aplicarTema(BRANDING.cor_primaria);
  document.getElementById("link-apple-icon").setAttribute("href", BRANDING.logo_url || "/icons/apple-touch-icon.png");

  document.getElementById("tela-carregando").classList.add("escondido");
  document.getElementById("app").classList.remove("escondido");

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(`/loja/${SLUG}/service-worker.js`).catch(() => {});
  }

  document.querySelectorAll(".loja-nav-item").forEach((btn) => {
    btn.addEventListener("click", () => trocarVista(btn.dataset.vista));
  });

  // Essa empresa pode ter desligado algum dos módulos (ver
  // Configurações → Módulos) — some com a aba correspondente.
  if (!BRANDING.passagens_habilitado) {
    document.querySelector('.loja-nav-item[data-vista="buscar"]').classList.add("escondido");
  }
  if (!BRANDING.fretamento_habilitado) {
    document.querySelector('.loja-nav-item[data-vista="fretamento"]').classList.add("escondido");
  }
  if (!BRANDING.frete_habilitado) {
    document.querySelector('.loja-nav-item[data-vista="frete"]').classList.add("escondido");
  }
  if (!BRANDING.passagens_habilitado && (BRANDING.fretamento_habilitado || BRANDING.frete_habilitado)) {
    trocarVista(BRANDING.fretamento_habilitado ? "fretamento" : "frete");
  }

  configurarBusca();
  if (BRANDING.passagens_habilitado) {
    configurarCidadesBusca();
  }
  configurarCompra();
  configurarFretamento();
  configurarFrete();
  configurarConta();

  // Link direto de acompanhamento (ex: compartilhado por WhatsApp), no
  // formato /loja/{slug}?codigo=XXXX (fretamento) ou ?frete=XXXX — abre já
  // na aba de rastreio correspondente.
  const params = new URLSearchParams(window.location.search);
  const codigoNaUrl = params.get("codigo");
  const freteNaUrl = params.get("frete");
  if (codigoNaUrl) {
    abrirAcompanharFretamento(codigoNaUrl.toUpperCase());
  } else if (freteNaUrl) {
    abrirAcompanharFrete(freteNaUrl.toUpperCase());
  }
}

iniciar();
