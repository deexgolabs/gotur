const SLUG = window.__LOJA_SLUG__;
let BRANDING = null;
let viagemAtual = null;
let poltronaSelecionadaId = null;
let retomarAposLogin = null;
let mapaFretamento, marcadorFretamento, linhaFretamento;

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

function configurarFretamento() {
  document.querySelectorAll("[data-aba-fretamento]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-aba-fretamento]").forEach((b) => b.classList.remove("ativa"));
      btn.classList.add("ativa");
      const solicitar = btn.dataset.abaFretamento === "solicitar";
      document.getElementById("fretamento-solicitar").classList.toggle("escondido", !solicitar);
      document.getElementById("fretamento-acompanhar").classList.toggle("escondido", solicitar);
    });
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
      mostrarAlerta(`Solicitação enviada! Guarde o código ${dados.codigo_rastreio} pra acompanhar.`, "sucesso");
      document.getElementById("form-fretamento").reset();
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

    const ROTULOS = { orcamento: "Orçamento", confirmado: "Confirmado", em_andamento: "Em andamento", concluido: "Concluído", cancelado: "Cancelado" };
    resultado.innerHTML = `
      <div class="loja-card">
        <div class="trecho">${dados.origem} → ${dados.destino}</div>
        <div class="info">Saída: ${new Date(dados.data_hora_saida).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</div>
        <div style="margin-top:8px"><span class="selo hold">${ROTULOS[dados.status] || dados.status}</span></div>
        ${dados.status === "em_andamento" ? '<div id="mapa-fretamento-loja" style="height:260px;border-radius:10px;margin-top:12px"></div>' : ""}
      </div>`;

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
      else marcadorFretamento = L.marker(ultimo).addTo(mapaFretamento);
      mapaFretamento.fitBounds(linhaFretamento.getBounds(), { maxZoom: 15, padding: [20, 20] });
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

async function iniciar() {
  try {
    const resposta = await fetch(`/api/empresas/loja/${SLUG}`);
    if (!resposta.ok) throw new Error("not found");
    BRANDING = await resposta.json();
  } catch (e) {
    document.getElementById("tela-carregando").textContent = "Essa loja não foi encontrada. Confira o link com a viação.";
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

  configurarBusca();
  configurarCompra();
  configurarFretamento();
  configurarConta();
}

iniciar();
