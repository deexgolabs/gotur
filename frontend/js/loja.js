const SLUG = window.__LOJA_SLUG__;
let BRANDING = null;
let viagemAtual = null;
let poltronaSelecionadaId = null;
let precoSelecionadoLoja = null;
let retomarAposLogin = null;
let interlineOpcaoAtual = null;
let interlineEtapa = 1; // 1 = escolhendo poltrona da perna A, 2 = da perna B
let interlinePoltronaA = null;
let interlinePoltronaB = null;
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
  document.documentElement.style.setProperty("--roxo", cor);
  document.documentElement.style.setProperty("--roxo-escuro", escurecer(cor, 0.75));
  document.documentElement.style.setProperty("--roxo-claro", clarear(cor, 0.92));
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

function entrarEmModoVitrine(mensagem) {
  document.body.classList.add("modo-vitrine");
  document.getElementById("vitrine-topo-texto").textContent = mensagem;
  document.getElementById("vitrine-topo").classList.remove("escondido");
}

function sairDoModoVitrine() {
  document.body.classList.remove("modo-vitrine");
  document.getElementById("vitrine-topo").classList.add("escondido");
}

async function abrirLandingEvento(sessaoId) {
  try {
    const lista = await fetch(`/api/sessoes/loja/${SLUG}`).then((r) => (r.ok ? r.json() : []));
    const sessao = lista.find((s) => s.id === sessaoId);
    if (!sessao) {
      mostrarAlerta("Esse evento não está mais disponível.");
      sairDoModoVitrine();
      trocarVista("eventos");
      return;
    }
    abrirCompraEvento(sessao);
  } catch (erro) {
    sairDoModoVitrine();
    trocarVista("eventos");
  }
}

async function abrirLandingAula(ocorrenciaId) {
  document.querySelectorAll(".loja-vista").forEach((v) => v.classList.remove("ativa"));
  document.getElementById("vista-academia").classList.add("ativa");
  await carregarAcademia();
  const ocorrencia = ocorrenciasAcademiaCache.find((o) => o.id === ocorrenciaId);
  if (!ocorrencia) {
    mostrarAlerta("Essa aula não está mais disponível.");
    return;
  }
  reservarAula(ocorrencia);
}

function trocarVista(nome) {
  document.querySelectorAll(".loja-vista").forEach((v) => v.classList.remove("ativa"));
  document.getElementById(`vista-${nome}`).classList.add("ativa");
  document.querySelectorAll(".loja-nav-item").forEach((b) => b.classList.toggle("ativo", b.dataset.vista === nome));
  if (nome === "minhas") carregarMinhasViagens();
  if (nome === "conta") renderizarConta();
  if (nome === "eventos") carregarEventos();
  if (nome === "meus-ingressos") carregarMeusIngressos();
  if (nome === "academia") carregarAcademia();
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
    buscarInterline(origem, destino, data); // em paralelo — não deixa o "return" abaixo pular essa busca
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

async function buscarInterline(origem, destino, data) {
  const container = document.getElementById("resultados-interline");
  container.innerHTML = "";
  let opcoes = [];
  try {
    opcoes = await fetch(
      `/api/interline/buscar?origem=${encodeURIComponent(origem)}&destino=${encodeURIComponent(destino)}&data=${data}`
    ).then((r) => (r.ok ? r.json() : []));
  } catch (e) {
    return;
  }
  if (!opcoes.length) return;

  container.innerHTML =
    `<div class="loja-titulo-vista" style="font-size:1rem;margin-top:16px">Com conexão</div>` +
    opcoes
      .map(
        (o, i) => `
      <div class="loja-card loja-card-viagem" data-indice-interline="${i}">
        <div>
          <div class="trecho">${BRANDING.nome} → ${o.empresa_b_nome}, via ${o.parada_conexao_nome}</div>
          <div class="info">${new Date(o.data_hora_partida_a).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} · baldeia ${new Date(o.data_hora_partida_b).toLocaleString("pt-BR", { timeStyle: "short" })}</div>
        </div>
        <div class="preco">R$ ${Number(o.valor_total).toFixed(2)}</div>
      </div>`
      )
      .join("");

  container.querySelectorAll(".loja-card-viagem").forEach((card) => {
    card.addEventListener("click", () => abrirCompraInterline(opcoes[parseInt(card.dataset.indiceInterline, 10)]));
  });
}

// ---------- Compra interline (duas pernas, empresas diferentes) ----------

function abrirCompraInterline(opcao) {
  interlineOpcaoAtual = opcao;
  interlineEtapa = 1;
  interlinePoltronaA = null;
  interlinePoltronaB = null;
  document.getElementById("alerta-compra-interline").innerHTML = "";
  document.getElementById("interline-titulo").textContent = `${BRANDING.nome} → ${opcao.empresa_b_nome}`;
  document.getElementById("card-form-compra-interline").classList.add("escondido");
  document.getElementById("area-pix-interline").classList.add("escondido");
  document.getElementById("form-compra-interline").classList.remove("escondido");

  document.querySelectorAll(".loja-vista").forEach((v) => v.classList.remove("ativa"));
  document.getElementById("vista-compra-interline").classList.add("ativa");

  carregarMapaInterline();
}

function viagemIdEtapaAtual() {
  return interlineEtapa === 1 ? interlineOpcaoAtual.viagem_perna_a_id : interlineOpcaoAtual.viagem_perna_b_id;
}

async function carregarMapaInterline() {
  document.getElementById("interline-etapa-label").textContent =
    interlineEtapa === 1
      ? `Etapa 1 de 2 — escolha a poltrona com ${BRANDING.nome}`
      : `Etapa 2 de 2 — escolha a poltrona com ${interlineOpcaoAtual.empresa_b_nome}`;

  const poltronas = await fetch(`/api/viagens/${viagemIdEtapaAtual()}/poltronas`).then((r) => r.json());
  const porFileira = {};
  poltronas.forEach((p) => {
    porFileira[p.fileira] = porFileira[p.fileira] || [];
    porFileira[p.fileira].push(p);
  });

  const poltronaSelecionadaEtapa = interlineEtapa === 1 ? interlinePoltronaA : interlinePoltronaB;
  const container = document.getElementById("mapa-onibus-interline");
  container.innerHTML = Object.keys(porFileira)
    .sort((a, b) => a - b)
    .map((fileira) => {
      const assentos = porFileira[fileira].sort((a, b) => a.coluna - b.coluna);
      const celulas = [];
      assentos.forEach((p) => {
        if (p.coluna === 3) celulas.push('<div class="poltrona corredor"></div>');
        const classes = ["poltrona", p.status];
        if (poltronaSelecionadaEtapa && p.poltrona_viagem_id === poltronaSelecionadaEtapa.id) classes.push("selecionada");
        celulas.push(
          `<div class="${classes.join(" ")}" data-id="${p.poltrona_viagem_id}" data-status="${p.status}" data-numero="${p.numero}" data-preco="${p.preco}">${p.numero}</div>`
        );
      });
      return `<div class="fileira-poltronas">${celulas.join("")}</div>`;
    })
    .join("");

  container.querySelectorAll(".poltrona[data-id]").forEach((el) => {
    el.addEventListener("click", () => onClicarPoltronaInterline(el));
  });
}

async function onClicarPoltronaInterline(el) {
  if (el.dataset.status !== "livre") {
    mostrarAlerta("Essa poltrona não está disponível.", "erro", "alerta-compra-interline");
    return;
  }
  if (!obterAuth()) {
    mostrarAlerta("Crie uma conta ou faça login pra escolher sua poltrona — é rápido.", "erro", "alerta-compra-interline");
    trocarVista("conta");
    return;
  }

  try {
    await api("POST", `/viagens/${viagemIdEtapaAtual()}/poltronas/${el.dataset.id}/hold`);
  } catch (erro) {
    mostrarAlerta(erro.message, "erro", "alerta-compra-interline");
    carregarMapaInterline();
    return;
  }

  const poltronaEscolhida = { id: parseInt(el.dataset.id, 10), numero: el.dataset.numero, preco: Number(el.dataset.preco) };
  if (interlineEtapa === 1) {
    interlinePoltronaA = poltronaEscolhida;
    interlineEtapa = 2;
    document.getElementById("alerta-compra-interline").innerHTML = "";
    carregarMapaInterline();
    return;
  }

  interlinePoltronaB = poltronaEscolhida;
  document.getElementById("alerta-compra-interline").innerHTML = "";
  document.getElementById("interline-numero-a").textContent = `Nº ${interlinePoltronaA.numero} (${BRANDING.nome})`;
  document.getElementById("interline-numero-b").textContent = `Nº ${interlinePoltronaB.numero} (${interlineOpcaoAtual.empresa_b_nome})`;
  document.getElementById("interline-preco-total").textContent = `R$ ${(interlinePoltronaA.preco + interlinePoltronaB.preco).toFixed(2)}`;
  const auth = obterAuth();
  if (auth && !document.getElementById("interline-nome").value) {
    document.getElementById("interline-nome").value = auth.nome || "";
  }
  document.getElementById("card-form-compra-interline").classList.remove("escondido");
  atualizarFormaPagamentoInterline();
  carregarMapaInterline();
}

function dadosBaseCompraInterline(formaPagamento) {
  return {
    conexao_id: interlineOpcaoAtual.conexao_id,
    viagem_perna_a_id: interlineOpcaoAtual.viagem_perna_a_id,
    poltrona_perna_a_id: interlinePoltronaA.id,
    viagem_perna_b_id: interlineOpcaoAtual.viagem_perna_b_id,
    poltrona_perna_b_id: interlinePoltronaB.id,
    cliente_nome: document.getElementById("interline-nome").value.trim(),
    cliente_documento: document.getElementById("interline-documento").value.trim(),
    forma_pagamento: formaPagamento,
  };
}

function pedidoNormalizadoDoInterline(pedido) {
  return {
    id: pedido.id,
    valor: pedido.valor_total,
    pix_copia_cola: pedido.pix_copia_cola,
    expira_em: pedido.pix_expira_em,
    pagamento_simulado: pedido.pagamento_simulado,
  };
}

function tratarRespostaCompraInterline(resposta) {
  if (resposta.pedido_interline) {
    document.getElementById("form-compra-interline").classList.add("escondido");
    document.getElementById("area-cartao-interline").classList.add("escondido");
    const areaPix = document.getElementById("area-pix-interline");
    areaPix.classList.remove("escondido");
    renderizarPagamentoPix(areaPix, pedidoNormalizadoDoInterline(resposta.pedido_interline), {
      endpointConfirmar: `/interline/pedidos/${resposta.pedido_interline.id}/confirmar-simulado`,
      semPolling: true,
      aoConfirmar: () => {
        mostrarAlerta("Compra confirmada!", "sucesso", "alerta-compra-interline");
        setTimeout(() => trocarVista("minhas"), 1200);
      },
    });
    return;
  }

  mostrarAlerta(
    `Compra confirmada! Localizadores: ${resposta.localizador_perna_a} e ${resposta.localizador_perna_b}`,
    "sucesso",
    "alerta-compra-interline"
  );
  setTimeout(() => trocarVista("minhas"), 1200);
}

function atualizarFormaPagamentoInterline() {
  const forma = document.getElementById("interline-forma").value;
  const btnConfirmar = document.getElementById("btn-confirmar-compra-interline");
  const areaCartao = document.getElementById("area-cartao-interline");

  if (forma !== "cartao") {
    desmontarCheckoutCartaoMP();
    areaCartao.classList.add("escondido");
    btnConfirmar.classList.remove("escondido");
    return;
  }

  btnConfirmar.classList.add("escondido");
  areaCartao.classList.remove("escondido");

  montarCheckoutCartaoMP("area-cartao-interline", {
    publicKey: BRANDING.mercadopago_public_key,
    valor: interlinePoltronaA.preco + interlinePoltronaB.preco,
    onPagar: (dadosCartao) =>
      api("POST", "/interline/pedidos", {
        ...dadosBaseCompraInterline("cartao"),
        mp_token: dadosCartao.token,
        mp_payment_method_id: dadosCartao.payment_method_id,
        mp_installments: dadosCartao.installments,
        mp_payer_email: dadosCartao.payer_email,
      }).then((resposta) => tratarRespostaCompraInterline(resposta)),
  });
}

function configurarCompraInterline() {
  document.getElementById("btn-voltar-busca-interline").addEventListener("click", () => trocarVista("buscar"));
  document.getElementById("interline-forma").addEventListener("change", atualizarFormaPagamentoInterline);

  document.getElementById("form-compra-interline").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const forma = document.getElementById("interline-forma").value;
    if (forma === "cartao") return; // o próprio Brick tem o botão de pagar

    try {
      const resposta = await api("POST", "/interline/pedidos", dadosBaseCompraInterline(forma));
      tratarRespostaCompraInterline(resposta);
    } catch (erro) {
      mostrarAlerta(erro.message, "erro", "alerta-compra-interline");
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
  precoSelecionadoLoja = Number(el.dataset.preco);
  document.getElementById("compra-numero-selecionada").textContent = el.dataset.numero;
  document.getElementById("compra-preco-selecionada").textContent = `R$ ${precoSelecionadoLoja.toFixed(2)}`;
  const auth = obterAuth();
  if (auth && !document.getElementById("compra-nome").value) {
    document.getElementById("compra-nome").value = auth.nome || "";
  }
  document.getElementById("card-form-compra").classList.remove("escondido");
  atualizarFormaPagamentoLoja();
  carregarMapaLoja();
}

function tratarRespostaCompraLoja(resposta) {
  if (resposta.pedido_pagamento) {
    document.getElementById("form-compra-loja").classList.add("escondido");
    document.getElementById("area-cartao-loja").classList.add("escondido");
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
}

function dadosBaseCompraLoja(formaPagamento) {
  return {
    poltrona_viagem_id: poltronaSelecionadaId,
    cliente_nome: document.getElementById("compra-nome").value.trim(),
    cliente_documento: document.getElementById("compra-documento").value.trim(),
    forma_pagamento: formaPagamento,
    parada_origem_id: viagemAtual.parada_origem_id,
    parada_destino_id: viagemAtual.parada_destino_id,
    codigo_cupom: document.getElementById("compra-cupom").value.trim() || null,
  };
}

function atualizarFormaPagamentoLoja() {
  const forma = document.getElementById("compra-forma").value;
  const btnConfirmar = document.getElementById("btn-confirmar-compra");
  const areaCartao = document.getElementById("area-cartao-loja");

  if (forma !== "cartao") {
    desmontarCheckoutCartaoMP();
    areaCartao.classList.add("escondido");
    btnConfirmar.classList.remove("escondido");
    return;
  }

  btnConfirmar.classList.add("escondido");
  areaCartao.classList.remove("escondido");
  if (!poltronaSelecionadaId) return;

  montarCheckoutCartaoMP("area-cartao-loja", {
    publicKey: BRANDING.mercadopago_public_key,
    valor: precoSelecionadoLoja,
    onPagar: (dadosCartao) =>
      api("POST", `/viagens/${viagemAtual.id}/passagens`, {
        ...dadosBaseCompraLoja("cartao"),
        mp_token: dadosCartao.token,
        mp_payment_method_id: dadosCartao.payment_method_id,
        mp_installments: dadosCartao.installments,
        mp_payer_email: dadosCartao.payer_email,
      }).then((resposta) => {
        tratarRespostaCompraLoja(resposta);
      }),
  });
}

function configurarCompra() {
  document.getElementById("btn-voltar-busca").addEventListener("click", () => trocarVista("buscar"));

  document.getElementById("compra-forma").addEventListener("change", atualizarFormaPagamentoLoja);

  document.getElementById("form-compra-loja").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!poltronaSelecionadaId) return;
    const forma = document.getElementById("compra-forma").value;
    if (forma === "cartao") return; // o próprio Brick tem o botão de pagar

    try {
      const resposta = await api("POST", `/viagens/${viagemAtual.id}/passagens`, dadosBaseCompraLoja(forma));
      tratarRespostaCompraLoja(resposta);
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

    let cuponsHtml = "";
    try {
      const cupons = await api("GET", `/cupons/minhas?tenant_id=${BRANDING.id}`);
      if (cupons.length) {
        cuponsHtml = `
          <div class="loja-card" style="border-color:var(--verde)">
            <div class="trecho" style="margin-bottom:6px">Seus cupons de fidelidade</div>
            ${cupons
              .map(
                (c) => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0">
                <span><strong>${c.codigo}</strong> — ${c.valor}% off</span>
                <span class="selo ${c.usos_atuais < (c.max_usos || 1) ? "livre" : "bloqueada"}">${c.usos_atuais < (c.max_usos || 1) ? "Disponível" : "Usado"}</span>
              </div>`
              )
              .join("")}
          </div>`;
      }
    } catch (e) {
      // sem cupons — segue sem mostrar nada
    }

    if (!lista.length) {
      container.innerHTML = cuponsHtml || `<p class="loja-selo-vazio">Você ainda não comprou nenhuma passagem aqui.</p>`;
      return;
    }
    container.innerHTML = cuponsHtml + lista
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

// ---------- Eventos ----------

let sessaoAtual = null;
let assentoSelecionadoIdEvento = null;
let precoSelecionadoEvento = null;

async function carregarEventos() {
  const container = document.getElementById("eventos-lista");
  container.innerHTML = `<p class="loja-selo-vazio">Carregando...</p>`;
  try {
    const lista = await fetch(`/api/sessoes/loja/${SLUG}`).then((r) => (r.ok ? r.json() : []));
    if (!lista.length) {
      container.innerHTML = `<p class="loja-selo-vazio">Nenhum evento disponível no momento.</p>`;
      return;
    }
    container.innerHTML = lista
      .map(
        (s, i) => `
      <div class="loja-card loja-card-viagem" data-indice="${i}">
        <div>
          <div class="trecho">${s.nome_evento}</div>
          <div class="info">${s.local_nome} · ${new Date(s.data_hora).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} · ${s.assentos_livres} vagas</div>
        </div>
        <div class="preco">R$ ${Number(s.preco).toFixed(2)}</div>
      </div>`
      )
      .join("");
    container.querySelectorAll("[data-indice]").forEach((el) => {
      el.addEventListener("click", () => abrirCompraEvento(lista[parseInt(el.dataset.indice, 10)]));
    });
  } catch (erro) {
    container.innerHTML = `<p class="loja-selo-vazio">Erro ao carregar eventos.</p>`;
  }
}

function abrirCompraEvento(sessao) {
  sessaoAtual = sessao;
  assentoSelecionadoIdEvento = null;
  document.getElementById("alerta-compra-evento").innerHTML = "";
  document.getElementById("evento-titulo").textContent = `${sessao.nome_evento} — ${sessao.local_nome}`;
  document.getElementById("card-form-compra-evento").classList.add("escondido");
  document.getElementById("area-pix-evento").classList.add("escondido");
  document.getElementById("form-compra-evento").classList.remove("escondido");

  document.querySelectorAll(".loja-vista").forEach((v) => v.classList.remove("ativa"));
  document.getElementById("vista-compra-evento").classList.add("ativa");

  carregarMapaEvento();
}

async function carregarMapaEvento() {
  const assentos = await fetch(`/api/sessoes/${sessaoAtual.id}/assentos`).then((r) => r.json());
  const porFileira = {};
  assentos.forEach((a) => {
    porFileira[a.fileira] = porFileira[a.fileira] || [];
    porFileira[a.fileira].push(a);
  });

  const container = document.getElementById("mapa-assentos-evento");
  container.innerHTML = Object.keys(porFileira)
    .sort((a, b) => a - b)
    .map((fileira) => {
      const linha = porFileira[fileira].sort((a, b) => a.coluna - b.coluna);
      const celulas = [];
      linha.forEach((a) => {
        if (a.coluna === 3) celulas.push('<div class="poltrona corredor"></div>');
        const classes = ["poltrona", a.status];
        if (a.assento_sessao_id === assentoSelecionadoIdEvento) classes.push("selecionada");
        celulas.push(
          `<div class="${classes.join(" ")}" data-id="${a.assento_sessao_id}" data-status="${a.status}" data-numero="${a.numero}" data-preco="${a.preco}">${a.numero}</div>`
        );
      });
      return `<div class="fileira-poltronas">${celulas.join("")}</div>`;
    })
    .join("");

  container.querySelectorAll(".poltrona[data-id]").forEach((el) => {
    el.addEventListener("click", () => onClicarAssentoEvento(el));
  });
}

async function onClicarAssentoEvento(el) {
  if (el.dataset.status !== "livre") {
    mostrarAlerta("Esse assento não está disponível.", "erro", "alerta-compra-evento");
    return;
  }
  if (!obterAuth()) {
    mostrarAlerta("Crie uma conta ou faça login pra escolher seu assento — é rápido.", "erro", "alerta-compra-evento");
    trocarVista("conta");
    return;
  }

  try {
    await api("POST", `/sessoes/${sessaoAtual.id}/assentos/${el.dataset.id}/hold`);
  } catch (erro) {
    mostrarAlerta(erro.message, "erro", "alerta-compra-evento");
    carregarMapaEvento();
    return;
  }

  document.getElementById("alerta-compra-evento").innerHTML = "";
  assentoSelecionadoIdEvento = parseInt(el.dataset.id, 10);
  precoSelecionadoEvento = Number(el.dataset.preco);
  document.getElementById("evento-numero-selecionado").textContent = el.dataset.numero;
  document.getElementById("evento-preco-selecionado").textContent = `R$ ${precoSelecionadoEvento.toFixed(2)}`;
  const auth = obterAuth();
  if (auth && !document.getElementById("evento-nome").value) {
    document.getElementById("evento-nome").value = auth.nome || "";
  }
  document.getElementById("card-form-compra-evento").classList.remove("escondido");
  atualizarFormaPagamentoEvento();
  carregarMapaEvento();
}

function tratarRespostaCompraEvento(resposta) {
  if (resposta.pedido_ingresso) {
    document.getElementById("form-compra-evento").classList.add("escondido");
    document.getElementById("area-cartao-evento").classList.add("escondido");
    const areaPix = document.getElementById("area-pix-evento");
    areaPix.classList.remove("escondido");
    renderizarPagamentoPix(areaPix, resposta.pedido_ingresso, {
      endpointConfirmar: `/pedidos-ingresso/${resposta.pedido_ingresso.id}/confirmar-simulado`,
      endpointConsultar: `/pedidos-ingresso/${resposta.pedido_ingresso.id}`,
      aoConfirmar: (corpo) => {
        const codigo = corpo && corpo.ingresso ? corpo.ingresso.codigo : null;
        mostrarAlerta(codigo ? `Compra confirmada! Código: ${codigo}` : "Compra confirmada!", "sucesso", "alerta-compra-evento");
        setTimeout(() => trocarVista("meus-ingressos"), 1200);
      },
    });
    return;
  }

  mostrarAlerta(`Compra confirmada! Código: ${resposta.ingresso.codigo}`, "sucesso", "alerta-compra-evento");
  setTimeout(() => trocarVista("meus-ingressos"), 1200);
}

function dadosBaseCompraEvento(formaPagamento) {
  return {
    assento_sessao_id: assentoSelecionadoIdEvento,
    cliente_nome: document.getElementById("evento-nome").value.trim(),
    cliente_documento: document.getElementById("evento-documento").value.trim(),
    forma_pagamento: formaPagamento,
  };
}

function atualizarFormaPagamentoEvento() {
  const forma = document.getElementById("evento-forma").value;
  const btnConfirmar = document.getElementById("btn-confirmar-compra-evento");
  const areaCartao = document.getElementById("area-cartao-evento");

  if (forma !== "cartao") {
    desmontarCheckoutCartaoMP();
    areaCartao.classList.add("escondido");
    btnConfirmar.classList.remove("escondido");
    return;
  }

  btnConfirmar.classList.add("escondido");
  areaCartao.classList.remove("escondido");
  if (!assentoSelecionadoIdEvento) return;

  montarCheckoutCartaoMP("area-cartao-evento", {
    publicKey: BRANDING.mercadopago_public_key,
    valor: precoSelecionadoEvento,
    onPagar: (dadosCartao) =>
      api("POST", `/sessoes/${sessaoAtual.id}/ingressos`, {
        ...dadosBaseCompraEvento("cartao"),
        mp_token: dadosCartao.token,
        mp_payment_method_id: dadosCartao.payment_method_id,
        mp_installments: dadosCartao.installments,
        mp_payer_email: dadosCartao.payer_email,
      }).then((resposta) => {
        tratarRespostaCompraEvento(resposta);
      }),
  });
}

function configurarCompraEvento() {
  document.getElementById("btn-voltar-eventos").addEventListener("click", () => {
    sairDoModoVitrine();
    trocarVista("eventos");
  });

  document.getElementById("evento-forma").addEventListener("change", atualizarFormaPagamentoEvento);

  document.getElementById("form-compra-evento").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!assentoSelecionadoIdEvento) return;
    const forma = document.getElementById("evento-forma").value;
    if (forma === "cartao") return; // o próprio Brick tem o botão de pagar

    try {
      const resposta = await api("POST", `/sessoes/${sessaoAtual.id}/ingressos`, dadosBaseCompraEvento(forma));
      tratarRespostaCompraEvento(resposta);
    } catch (erro) {
      mostrarAlerta(erro.message, "erro", "alerta-compra-evento");
    }
  });
}

async function carregarMeusIngressos() {
  const container = document.getElementById("meus-ingressos-conteudo");
  const auth = obterAuth();
  if (!auth) {
    container.innerHTML = `<p class="loja-selo-vazio">Faça login pra ver seus ingressos.</p>`;
    return;
  }
  container.innerHTML = `<p class="loja-selo-vazio">Carregando...</p>`;
  try {
    const lista = await api("GET", "/ingressos/minhas");
    if (!lista.length) {
      container.innerHTML = `<p class="loja-selo-vazio">Você ainda não comprou nenhum ingresso aqui.</p>`;
      return;
    }
    container.innerHTML = lista
      .map(
        (i) => `
      <div class="loja-card">
        <div class="trecho">${i.nome_evento || "-"}</div>
        <div class="info">${i.local_nome || ""} ${i.data_hora ? "· " + new Date(i.data_hora).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : ""} · Assento ${i.numero_assento || "-"}</div>
        <div class="info">Código: <strong>${i.codigo}</strong></div>
        <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center">
          <span class="selo ${i.status}">${i.status === "confirmada" ? "Confirmado" : "Cancelado"}</span>
          <span style="font-weight:700">R$ ${Number(i.preco).toFixed(2)}</span>
        </div>
      </div>`
      )
      .join("");
  } catch (erro) {
    container.innerHTML = `<p class="loja-selo-vazio">Erro ao carregar seus ingressos.</p>`;
  }
}

// ---------- Academia ----------

let minhasMatriculasAcademia = [];
let ocorrenciasAcademiaCache = [];
let ocorrenciaAvulsaAtual = null;

const ROTULOS_STATUS_MATRICULA = {
  pendente: "Pendente de pagamento",
  ativa: "Ativa",
  inadimplente: "Inadimplente",
  suspensa: "Suspensa",
  cancelada: "Cancelada",
};

function pedidoNormalizadoDaFaturaMatricula(fatura) {
  return {
    id: fatura.id,
    valor: fatura.valor,
    forma_pagamento: fatura.forma_pagamento,
    pix_copia_cola: fatura.pix_copia_cola,
    expira_em: fatura.pix_expira_em,
    pagamento_simulado: fatura.pagamento_simulado,
  };
}

function mostrarPagamentoMatricula(fatura, container) {
  container.classList.remove("escondido");
  renderizarPagamentoPix(container, pedidoNormalizadoDaFaturaMatricula(fatura), {
    endpointConfirmar: `/faturas-matricula/${fatura.id}/confirmar-simulado`,
    semPolling: true,
    aoConfirmar: () => {
      mostrarAlerta("Matrícula ativada! Bem-vindo(a).", "sucesso");
      carregarAcademia();
    },
  });
}

async function iniciarPagamentoMatricula(fatura, container) {
  // Fatura recém-criada ainda não tem Pix gerado — o código Pix só nasce
  // quando alguém chama POST .../pagar (mesmo padrão de FaturaEmpresa em
  // minhas-faturas.html). Autoatendimento sempre gera via Pix.
  let faturaAtualizada = fatura;
  if (fatura.status === "pendente" && !fatura.pix_copia_cola) {
    try {
      faturaAtualizada = await api("POST", `/faturas-matricula/${fatura.id}/pagar`, { forma_pagamento: "pix" });
    } catch (erro) {
      mostrarAlerta(erro.message);
      return;
    }
  }
  mostrarPagamentoMatricula(faturaAtualizada, container);
}

async function carregarStatusMatricula() {
  const container = document.getElementById("academia-status-matricula");
  document.getElementById("academia-form-matricula").classList.add("escondido");

  if (!obterAuth()) {
    container.innerHTML = `<p class="loja-selo-vazio">Faça login pra se matricular ou reservar aulas.</p>`;
    minhasMatriculasAcademia = [];
    return;
  }

  try {
    minhasMatriculasAcademia = await api("GET", "/matriculas/minhas");
  } catch (erro) {
    minhasMatriculasAcademia = [];
  }

  const ativa = minhasMatriculasAcademia.find((m) => m.status === "ativa" || m.status === "inadimplente");
  const pendente = minhasMatriculasAcademia.find((m) => m.status === "pendente");

  if (ativa) {
    const avisoInadimplente =
      ativa.status === "inadimplente"
        ? `<p style="color:#c0392b;margin-top:6px">Sua mensalidade está atrasada — pague pra não perder o acesso.</p>`
        : "";
    container.innerHTML = `
      <div class="loja-card">
        <div style="font-weight:700">Matrícula ${ROTULOS_STATUS_MATRICULA[ativa.status]}</div>
        <div class="info">${
          ativa.tipo === "pacote_aulas"
            ? `${ativa.aulas_utilizadas_ciclo_atual} / ${ativa.aulas_por_ciclo} aulas usadas neste ciclo`
            : "Mensal ilimitado"
        }</div>
        ${avisoInadimplente}
      </div>`;
    return;
  }

  if (pendente) {
    container.innerHTML = `
      <div class="loja-card">
        <div style="font-weight:700">Matrícula pendente de pagamento</div>
        <div id="area-pix-matricula-pendente" style="margin-top:10px"></div>
      </div>`;
    try {
      const faturas = await api("GET", "/faturas-matricula/minhas");
      const fatura = faturas.find((f) => f.matricula_id === pendente.id && f.status === "pendente");
      if (fatura) iniciarPagamentoMatricula(fatura, document.getElementById("area-pix-matricula-pendente"));
    } catch (erro) {
      // sem fatura pra mostrar — segue sem o widget de pagamento
    }
    return;
  }

  if (!BRANDING.preco_padrao_mensalidade_academia) {
    container.innerHTML = `<p class="loja-selo-vazio">Essa academia ainda não abriu matrícula por aqui — fale com a recepção.</p>`;
    return;
  }

  const precoFormatado = Number(BRANDING.preco_padrao_mensalidade_academia).toFixed(2);
  container.innerHTML = `
    <p class="loja-selo-vazio">Você ainda não é aluno.</p>
    <p class="info" style="margin-bottom:10px">Mensalidade: R$ ${precoFormatado}</p>
    <button type="button" id="btn-abrir-matricula">Quero me matricular</button>`;
  document.getElementById("btn-abrir-matricula").addEventListener("click", () => {
    document.getElementById("academia-form-matricula").classList.remove("escondido");
  });
}

async function carregarAulasAcademia() {
  const container = document.getElementById("academia-lista-aulas");
  container.innerHTML = `<p class="loja-selo-vazio">Carregando...</p>`;
  try {
    const lista = await fetch(`/api/ocorrencias-turma/loja/${SLUG}`).then((r) => (r.ok ? r.json() : []));
    ocorrenciasAcademiaCache = lista;
    if (!lista.length) {
      container.innerHTML = `<p class="loja-selo-vazio">Nenhuma aula disponível no momento.</p>`;
      return;
    }
    container.innerHTML = lista
      .map((o, i) => {
        const vagas = o.capacidade_vagas - o.vagas_ocupadas;
        return `
      <div class="loja-card loja-card-viagem" data-indice-aula="${i}">
        <div>
          <div class="trecho">${o.nome_turma}</div>
          <div class="info">${new Date(o.data_hora_inicio).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} · ${vagas} vaga${vagas === 1 ? "" : "s"}</div>
        </div>
        <div class="preco">${o.preco_avulso != null ? `R$ ${Number(o.preco_avulso).toFixed(2)}` : ""}</div>
      </div>`;
      })
      .join("");
    container.querySelectorAll("[data-indice-aula]").forEach((el) => {
      el.addEventListener("click", () => reservarAula(lista[parseInt(el.dataset.indiceAula, 10)]));
    });
  } catch (erro) {
    container.innerHTML = `<p class="loja-selo-vazio">Erro ao carregar aulas.</p>`;
  }
}

async function reservarAula(ocorrencia) {
  if (!obterAuth()) {
    mostrarAlerta("Crie uma conta ou faça login pra reservar — é rápido.");
    trocarVista("conta");
    return;
  }

  document.getElementById("academia-form-avulsa").classList.add("escondido");

  const matriculaAtiva = minhasMatriculasAcademia.find((m) => m.status === "ativa" || m.status === "inadimplente");
  if (matriculaAtiva) {
    try {
      await api("POST", `/ocorrencias-turma/${ocorrencia.id}/reservas`, { matricula_id: matriculaAtiva.id });
      mostrarAlerta("Aula reservada!", "sucesso");
      carregarAulasAcademia();
      carregarMinhasAulasAcademia();
    } catch (erro) {
      mostrarAlerta(erro.message);
    }
    return;
  }

  if (!ocorrencia.preco_avulso) {
    mostrarAlerta("Essa turma é só pra aluno matriculado. Matricule-se pra reservar.");
    return;
  }

  abrirFormAvulsa(ocorrencia);
}

function abrirFormAvulsa(ocorrencia) {
  ocorrenciaAvulsaAtual = ocorrencia;
  document.getElementById("academia-avulsa-titulo").textContent =
    `${ocorrencia.nome_turma} — ${new Date(ocorrencia.data_hora_inicio).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} — R$ ${Number(ocorrencia.preco_avulso).toFixed(2)}`;
  document.getElementById("form-avulsa-academia").classList.remove("escondido");
  document.getElementById("area-cartao-avulsa").classList.add("escondido");
  const auth = obterAuth();
  if (auth && !document.getElementById("avulsa-nome").value) {
    document.getElementById("avulsa-nome").value = auth.nome || "";
  }
  document.getElementById("academia-form-avulsa").classList.remove("escondido");
  atualizarFormaPagamentoAvulsa();
  document.getElementById("academia-form-avulsa").scrollIntoView({ behavior: "smooth", block: "center" });
}

function dadosBaseAvulsaAcademia(formaPagamento) {
  return {
    cliente_nome: document.getElementById("avulsa-nome").value.trim(),
    cliente_documento: document.getElementById("avulsa-documento").value.trim(),
    forma_pagamento: formaPagamento,
  };
}

function tratarRespostaAvulsaAcademia() {
  mostrarAlerta("Aula reservada!", "sucesso");
  document.getElementById("form-avulsa-academia").reset();
  document.getElementById("academia-form-avulsa").classList.add("escondido");
  carregarAulasAcademia();
  carregarMinhasAulasAcademia();
}

function atualizarFormaPagamentoAvulsa() {
  const forma = document.getElementById("avulsa-forma").value;
  const btnConfirmar = document.getElementById("btn-confirmar-avulsa");
  const areaCartao = document.getElementById("area-cartao-avulsa");

  if (forma !== "cartao") {
    desmontarCheckoutCartaoMP();
    areaCartao.classList.add("escondido");
    btnConfirmar.classList.remove("escondido");
    return;
  }

  btnConfirmar.classList.add("escondido");
  areaCartao.classList.remove("escondido");
  if (!ocorrenciaAvulsaAtual) return;

  montarCheckoutCartaoMP("area-cartao-avulsa", {
    publicKey: BRANDING.mercadopago_public_key,
    valor: Number(ocorrenciaAvulsaAtual.preco_avulso),
    onPagar: (dadosCartao) =>
      api("POST", `/ocorrencias-turma/${ocorrenciaAvulsaAtual.id}/reservas`, {
        ...dadosBaseAvulsaAcademia("cartao"),
        mp_token: dadosCartao.token,
        mp_payment_method_id: dadosCartao.payment_method_id,
        mp_installments: dadosCartao.installments,
        mp_payer_email: dadosCartao.payer_email,
      }).then(() => tratarRespostaAvulsaAcademia()),
  });
}

async function carregarMinhasAulasAcademia() {
  const container = document.getElementById("academia-minhas-aulas");
  if (!obterAuth()) {
    container.innerHTML = "";
    return;
  }
  try {
    const lista = await api("GET", "/reservas/minhas");
    if (!lista.length) {
      container.innerHTML = `<p class="loja-selo-vazio">Você ainda não reservou nenhuma aula.</p>`;
      return;
    }
    container.innerHTML = lista
      .map(
        (r) => `
      <div class="loja-card">
        <div class="trecho">${r.nome_turma || "-"}</div>
        <div class="info">${r.data_hora_inicio ? new Date(r.data_hora_inicio).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : ""} · Código ${r.codigo}</div>
        <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center">
          <span class="selo ${r.status}">${r.status === "confirmada" ? "Confirmada" : "Cancelada"}</span>
          ${r.status === "confirmada" ? `<button class="secundario" data-cancelar-reserva="${r.id}">Cancelar</button>` : ""}
        </div>
      </div>`
      )
      .join("");

    container.querySelectorAll("button[data-cancelar-reserva]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Cancelar esta reserva?")) return;
        try {
          await api("POST", `/reservas/${btn.dataset.cancelarReserva}/cancelar`);
          mostrarAlerta("Reserva cancelada.", "sucesso");
          carregarAulasAcademia();
          carregarMinhasAulasAcademia();
        } catch (erro) {
          mostrarAlerta(erro.message);
        }
      });
    });
  } catch (erro) {
    container.innerHTML = `<p class="loja-selo-vazio">Erro ao carregar suas aulas.</p>`;
  }
}

async function carregarAcademia() {
  await Promise.all([carregarStatusMatricula(), carregarAulasAcademia(), carregarMinhasAulasAcademia()]);
}

function configurarAcademia() {
  document.getElementById("matricula-tipo").addEventListener("change", (ev) => {
    document.getElementById("matricula-campo-aulas").classList.toggle("escondido", ev.target.value !== "pacote_aulas");
  });

  document.getElementById("form-matricula-loja").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const tipo = document.getElementById("matricula-tipo").value;
      const payload = { tipo };
      if (tipo === "pacote_aulas") {
        payload.aulas_por_ciclo = parseInt(document.getElementById("matricula-aulas-por-ciclo").value, 10);
      }
      const matricula = await api("POST", `/matriculas/loja/${SLUG}`, payload);
      const faturas = await api("GET", "/faturas-matricula/minhas");
      const fatura = faturas.find((f) => f.matricula_id === matricula.id);
      document.getElementById("form-matricula-loja").classList.add("escondido");
      if (fatura) iniciarPagamentoMatricula(fatura, document.getElementById("area-pix-matricula"));
    } catch (erro) {
      mostrarAlerta(erro.message);
    }
  });

  document.getElementById("avulsa-forma").addEventListener("change", atualizarFormaPagamentoAvulsa);

  document.getElementById("form-avulsa-academia").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!ocorrenciaAvulsaAtual) return;
    const forma = document.getElementById("avulsa-forma").value;
    if (forma === "cartao") return; // o próprio Brick tem o botão de pagar

    try {
      await api("POST", `/ocorrencias-turma/${ocorrenciaAvulsaAtual.id}/reservas`, dadosBaseAvulsaAcademia(forma));
      tratarRespostaAvulsaAcademia();
    } catch (erro) {
      mostrarAlerta(erro.message);
    }
  });
}

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
          ${BRANDING.eventos_habilitado ? `<button type="button" class="secundario" id="btn-meus-ingressos-loja">Meus ingressos</button>` : ""}
          <button type="button" class="secundario" id="btn-sair-loja">Sair</button>
        </div>
      </div>`;
    const btnMeusIngressos = document.getElementById("btn-meus-ingressos-loja");
    if (btnMeusIngressos) {
      btnMeusIngressos.addEventListener("click", () => trocarVista("meus-ingressos"));
    }
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
  return `kivo_marca_${SLUG}`;
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

  document.title = `${BRANDING.nome} — Kivo`;
  document.getElementById("loja-nome").textContent = BRANDING.nome;
  if (BRANDING.logo_url) {
    const img = document.getElementById("loja-logo");
    img.src = BRANDING.logo_url;
    img.classList.remove("escondido");
  }
  aplicarTema(BRANDING.cor_primaria);
  document.getElementById("link-apple-icon").setAttribute("href", BRANDING.logo_url || "/icons/apple-touch-icon.png");

  if (BRANDING.telefone_contato || BRANDING.texto_loja) {
    const info = document.getElementById("loja-info");
    const partes = [];
    if (BRANDING.texto_loja) {
      partes.push(`<div>${BRANDING.texto_loja.replace(/\n/g, "<br>")}</div>`);
    }
    if (BRANDING.telefone_contato) {
      const digitos = BRANDING.telefone_contato.replace(/\D/g, "");
      const numeroWhats = digitos.length <= 11 ? `55${digitos}` : digitos;
      partes.push(
        `<div style="margin-top:${BRANDING.texto_loja ? "8px" : "0"}"><a href="https://wa.me/${numeroWhats}" target="_blank" rel="noopener">${BRANDING.telefone_contato}</a></div>`
      );
    }
    info.innerHTML = partes.join("");
    info.classList.remove("escondido");
  }

  document.getElementById("tela-carregando").classList.add("escondido");
  document.getElementById("app").classList.remove("escondido");

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(`/loja/${SLUG}/service-worker.js`).catch(() => {});
  }

  document.querySelectorAll(".loja-nav-item").forEach((btn) => {
    btn.addEventListener("click", () => trocarVista(btn.dataset.vista));
  });

  document.getElementById("link-sair-vitrine").addEventListener("click", (ev) => {
    ev.preventDefault();
    sairDoModoVitrine();
  });

  // Essa empresa pode ter desligado algum dos módulos (ver
  // Configurações → Módulos) — some com a aba correspondente.
  if (!BRANDING.passagens_habilitado) {
    document.querySelector('.loja-nav-item[data-vista="buscar"]').classList.add("escondido");
    document.querySelector('.loja-nav-item[data-vista="minhas"]').classList.add("escondido");
  }
  if (!BRANDING.fretamento_habilitado) {
    document.querySelector('.loja-nav-item[data-vista="fretamento"]').classList.add("escondido");
  }
  if (!BRANDING.frete_habilitado) {
    document.querySelector('.loja-nav-item[data-vista="frete"]').classList.add("escondido");
  }
  if (!BRANDING.eventos_habilitado) {
    document.querySelector('.loja-nav-item[data-vista="eventos"]').classList.add("escondido");
  }
  if (!BRANDING.academia_habilitado) {
    document.querySelector('.loja-nav-item[data-vista="academia"]').classList.add("escondido");
  }
  if (
    !BRANDING.passagens_habilitado &&
    (BRANDING.fretamento_habilitado || BRANDING.frete_habilitado || BRANDING.eventos_habilitado || BRANDING.academia_habilitado)
  ) {
    trocarVista(BRANDING.fretamento_habilitado ? "fretamento" : BRANDING.frete_habilitado ? "frete" : BRANDING.eventos_habilitado ? "eventos" : "academia");
  }

  configurarBusca();
  if (BRANDING.passagens_habilitado) {
    configurarCidadesBusca();
  }
  configurarCompra();
  configurarCompraInterline();
  configurarFretamento();
  configurarFrete();
  configurarCompraEvento();
  configurarAcademia();
  configurarConta();

  // Link direto de acompanhamento (ex: compartilhado por WhatsApp), no
  // formato /loja/{slug}?codigo=XXXX (fretamento) ou ?frete=XXXX — abre já
  // na aba de rastreio correspondente.
  const params = new URLSearchParams(window.location.search);
  const codigoNaUrl = params.get("codigo");
  const freteNaUrl = params.get("frete");

  // Landing page compartilhável de um evento/aula específico, no formato
  // /loja/{slug}/eventos/{id} ou /loja/{slug}/aulas/{id} — abre direto
  // nesse item (sem passar pela lista) e some com o menu inferior, pra
  // quem clicou num link de divulgação não ficar se perguntando onde
  // caiu. "Ver loja completa" no topo volta ao app normal.
  const segmentosPath = window.location.pathname.replace(/\/+$/, "").split("/");
  const tipoDeepLink = segmentosPath[3];
  const idDeepLink = segmentosPath[4] ? parseInt(segmentosPath[4], 10) : null;

  if (tipoDeepLink === "eventos" && idDeepLink && BRANDING.eventos_habilitado) {
    entrarEmModoVitrine("Você está vendo um evento específico.");
    abrirLandingEvento(idDeepLink);
  } else if (tipoDeepLink === "aulas" && idDeepLink && BRANDING.academia_habilitado) {
    entrarEmModoVitrine("Você está vendo uma aula específica.");
    abrirLandingAula(idDeepLink);
  } else if (codigoNaUrl) {
    abrirAcompanharFretamento(codigoNaUrl.toUpperCase());
  } else if (freteNaUrl) {
    abrirAcompanharFrete(freteNaUrl.toUpperCase());
  }
}

iniciar();
