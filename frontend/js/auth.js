const ROTULOS_PAPEL = {
  super_admin: "Super Admin",
  admin_empresa: "Administrador",
  funcionario: "Funcionário",
  cliente: "Cliente",
  parceiro: "Parceiro",
  motorista: "Motorista",
};

function exigirLogin() {
  const auth = obterAuth();
  if (!auth) {
    window.location.href = "/index.html";
    return null;
  }
  return auth;
}

function exigirPapel(...papeisPermitidos) {
  const auth = exigirLogin();
  if (!auth) return null;
  if (!papeisPermitidos.includes(auth.role)) {
    window.location.href = "/pages/dashboard.html";
    return null;
  }
  return auth;
}

function sair() {
  limparAuth();
  window.location.href = "/index.html";
}

function linksPorPapel(role) {
  const base = [{ href: "/pages/dashboard.html", label: "Início" }];
  if (role === "super_admin") {
    return [
      ...base,
      { href: "/pages/empresas.html", label: "Empresas" },
      { href: "/pages/planos.html", label: "Planos" },
      { href: "/pages/interline.html", label: "Interline" },
      { href: "/pages/plataforma.html", label: "Plataforma" },
    ];
  }
  if (role === "admin_empresa") {
    return [
      ...base,
      { href: "/pages/viagens.html", label: "Viagens", modulo: "passagens", grupo: "Vendas" },
      { href: "/pages/cupons.html", label: "Cupons", modulo: "passagens", grupo: "Vendas" },
      { href: "/pages/checkin.html", label: "Check-in", modulo: "passagens", grupo: "Vendas" },
      { href: "/pages/onibus.html", label: "Ônibus", grupo: "Frota" },
      { href: "/pages/motoristas.html", label: "Motoristas", modulo: "motorista", grupo: "Frota" },
      { href: "/pages/rotas.html", label: "Rotas", modulo: "passagens", grupo: "Frota" },
      { href: "/pages/fretamentos.html", label: "Fretamentos", modulo: "fretamento", grupo: "Fretamento e frete" },
      { href: "/pages/fretes.html", label: "Fretes", modulo: "frete", grupo: "Fretamento e frete" },
      { href: "/pages/locais.html", label: "Locais", modulo: "eventos", grupo: "Eventos" },
      { href: "/pages/sessoes.html", label: "Sessões", modulo: "eventos", grupo: "Eventos" },
      { href: "/pages/checkin-eventos.html", label: "Check-in eventos", modulo: "eventos", grupo: "Eventos" },
      { href: "/pages/turmas.html", label: "Turmas", modulo: "academia", grupo: "Academia" },
      { href: "/pages/ocorrencias-turma.html", label: "Agenda", modulo: "academia", grupo: "Academia" },
      { href: "/pages/matriculas.html", label: "Matrículas", modulo: "academia", grupo: "Academia" },
      { href: "/pages/checkin-academia.html", label: "Check-in academia", modulo: "academia", grupo: "Academia" },
      { href: "/pages/relatorios.html", label: "Relatórios", grupo: "Financeiro" },
      { href: "/pages/dre.html", label: "DRE", modulo: "dre", grupo: "Financeiro" },
      { href: "/pages/minhas-faturas.html", label: "Faturas", grupo: "Financeiro" },
      { href: "/pages/acertos-interline.html", label: "Acertos interline", grupo: "Financeiro" },
      { href: "/pages/funcionarios.html", label: "Funcionários", grupo: "Equipe" },
      { href: "/pages/parceiros.html", label: "Parceiros", grupo: "Equipe" },
      { href: "/pages/avaliacoes.html", label: "Avaliações", grupo: "Equipe" },
      { href: "/pages/auditoria.html", label: "Auditoria", grupo: "Equipe" },
      { href: "/pages/configuracoes.html", label: "Configurações" },
    ];
  }
  if (role === "parceiro") {
    return [
      ...base,
      { href: "/pages/parceiro-vendas.html", label: "Minhas vendas" },
    ];
  }
  if (role === "motorista") {
    return [
      ...base,
      { href: "/pages/motorista-app.html", label: "Minha jornada" },
    ];
  }
  if (role === "funcionario") {
    return [
      ...base,
      { href: "/pages/viagens.html", label: "Viagens", modulo: "passagens", grupo: "Vendas" },
      { href: "/pages/checkin.html", label: "Check-in", modulo: "passagens", grupo: "Vendas" },
      { href: "/pages/fretamentos.html", label: "Fretamentos", modulo: "fretamento", grupo: "Fretamento e frete" },
      { href: "/pages/fretes.html", label: "Fretes", modulo: "frete", grupo: "Fretamento e frete" },
      { href: "/pages/locais.html", label: "Locais", modulo: "eventos", grupo: "Eventos" },
      { href: "/pages/sessoes.html", label: "Sessões", modulo: "eventos", grupo: "Eventos" },
      { href: "/pages/checkin-eventos.html", label: "Check-in eventos", modulo: "eventos", grupo: "Eventos" },
      { href: "/pages/turmas.html", label: "Turmas", modulo: "academia", grupo: "Academia" },
      { href: "/pages/ocorrencias-turma.html", label: "Agenda", modulo: "academia", grupo: "Academia" },
      { href: "/pages/matriculas.html", label: "Matrículas", modulo: "academia", grupo: "Academia" },
      { href: "/pages/checkin-academia.html", label: "Check-in academia", modulo: "academia", grupo: "Academia" },
      { href: "/pages/avaliacoes.html", label: "Avaliações" },
    ];
  }
  if (role === "cliente") {
    return [
      ...base,
      { href: "/pages/busca.html", label: "Buscar viagem" },
      { href: "/pages/minhas-passagens.html", label: "Minhas passagens" },
    ];
  }
  return base;
}

function agruparLinks(links) {
  // Junta em blocos os links consecutivos que têm o mesmo `grupo`, na
  // ordem em que já vêm de linksPorPapel() — não reordena nada, só junta
  // pra desenhar o rótulo da seção uma vez só por bloco.
  const blocos = [];
  for (const link of links) {
    const ultimo = blocos[blocos.length - 1];
    if (ultimo && ultimo.grupo === (link.grupo || null)) {
      ultimo.links.push(link);
    } else {
      blocos.push({ grupo: link.grupo || null, links: [link] });
    }
  }
  return blocos;
}

const ICONE_MENU = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`;
const ICONE_FECHAR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>`;
const ICONE_SETA = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`;

function montarTopo(containerId) {
  const auth = obterAuth();
  const container = document.getElementById(containerId);
  if (!container) return;

  const links = auth ? linksPorPapel(auth.role) : [];
  const caminhoAtual = window.location.pathname;
  const blocos = agruparLinks(links);
  const navHtml = blocos
    .map((bloco) => {
      const linksDoBloco = bloco.links
        .map(
          (l) =>
            `<a href="${l.href}" class="link-nav${caminhoAtual === l.href ? " ativo" : ""}"${l.modulo ? ` data-modulo="${l.modulo}"` : ""}>${l.label}</a>`
        )
        .join("");
      if (!bloco.grupo) return linksDoBloco;
      const grupoAtivo = bloco.links.some((l) => caminhoAtual === l.href);
      return `<div class="nav-grupo${grupoAtivo ? " aberto" : ""}">
        <span class="nav-grupo-toggle${grupoAtivo ? " ativo" : ""}" tabindex="0">${bloco.grupo}${ICONE_SETA}</span>
        <div class="nav-dropdown">${linksDoBloco}</div>
      </div>`;
    })
    .join("");

  const usuarioHtml = auth
    ? `<div class="nav-usuario">
         <span class="nav-nome">${auth.nome} · ${ROTULOS_PAPEL[auth.role] || auth.role}</span>
         <a href="/pages/conta.html" class="link-nav${caminhoAtual === "/pages/conta.html" ? " ativo" : ""}">Minha conta</a>
         <a href="#" id="link-sair" class="link-nav">Sair</a>
       </div>`
    : "";

  container.innerHTML = `
    <header class="topo">
      <div class="topo-linha">
        <div class="marca">
          <img id="logo-empresa-topo" alt="" class="marca-logo escondido" />
          Go<span style="color:var(--acento)">Tur</span>
        </div>
        <button type="button" class="btn-menu-mobile" id="btn-menu-mobile" aria-label="Abrir menu" aria-expanded="false">${ICONE_MENU}</button>
      </div>
      <nav id="nav-principal">
        ${navHtml}
        <button type="button" id="btn-instalar-pwa" class="link-nav escondido" style="background:none;border:1px solid currentColor;padding:5px 10px;width:auto">Instalar app</button>
        ${links.length ? '<div class="nav-separador"></div>' : ""}
        ${usuarioHtml}
      </nav>
    </header>
  `;

  const linkSair = document.getElementById("link-sair");
  if (linkSair) {
    linkSair.addEventListener("click", (ev) => {
      ev.preventDefault();
      sair();
    });
  }

  const btnInstalar = document.getElementById("btn-instalar-pwa");
  if (btnInstalar && typeof pwaInstalavelAgora === "function") {
    const mostrarSeInstalavel = () => btnInstalar.classList.toggle("escondido", !pwaInstalavelAgora());
    mostrarSeInstalavel();
    document.addEventListener("gotur-pwa-instalavel", mostrarSeInstalavel);
    document.addEventListener("gotur-pwa-instalada", () => btnInstalar.classList.add("escondido"));
    btnInstalar.addEventListener("click", () => instalarPwaGoTur());
  }

  container.querySelectorAll(".nav-grupo-toggle").forEach((toggle) => {
    const alternar = () => {
      const grupo = toggle.closest(".nav-grupo");
      const abrindo = !grupo.classList.contains("aberto");
      container.querySelectorAll(".nav-grupo.aberto").forEach((g) => g.classList.remove("aberto"));
      grupo.classList.toggle("aberto", abrindo);
    };
    toggle.addEventListener("click", alternar);
    toggle.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        alternar();
      }
    });
  });

  const btnMenu = document.getElementById("btn-menu-mobile");
  const nav = document.getElementById("nav-principal");
  if (btnMenu && nav) {
    btnMenu.addEventListener("click", () => {
      const abrindo = !nav.classList.contains("aberto");
      nav.classList.toggle("aberto", abrindo);
      btnMenu.setAttribute("aria-expanded", String(abrindo));
      btnMenu.innerHTML = abrindo ? ICONE_FECHAR : ICONE_MENU;
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 860 && nav.classList.contains("aberto")) {
        nav.classList.remove("aberto");
        btnMenu.setAttribute("aria-expanded", "false");
        btnMenu.innerHTML = ICONE_MENU;
      }
    });
  }

  if (auth && (auth.role === "admin_empresa" || auth.role === "funcionario")) {
    fetch("/api/empresas/minha", { headers: { Authorization: `Bearer ${auth.access_token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((empresa) => {
        if (!empresa) return;
        const modulosHabilitados = {
          fretamento: empresa.fretamento_habilitado,
          passagens: empresa.passagens_habilitado,
          frete: empresa.frete_habilitado,
          motorista: empresa.motorista_habilitado,
          dre: empresa.dre_habilitado,
          eventos: empresa.eventos_habilitado,
          academia: empresa.academia_habilitado,
        };
        Object.entries(modulosHabilitados).forEach(([modulo, habilitado]) => {
          if (!habilitado) {
            container.querySelectorAll(`[data-modulo="${modulo}"]`).forEach((el) => el.classList.add("escondido"));
          }
        });
        container.querySelectorAll(".nav-grupo").forEach((grupoEl) => {
          const linksDoGrupo = grupoEl.querySelectorAll(".nav-dropdown .link-nav");
          if ([...linksDoGrupo].every((a) => a.classList.contains("escondido"))) {
            grupoEl.classList.add("escondido");
          }
        });
        if (empresa.logo_url) {
          const logo = document.getElementById("logo-empresa-topo");
          if (logo) {
            logo.src = empresa.logo_url;
            logo.classList.remove("escondido");
          }
        }
      })
      .catch(() => {});
  }
}
