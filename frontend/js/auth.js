const ROTULOS_PAPEL = {
  super_admin: "Super Admin",
  admin_empresa: "Administrador",
  funcionario: "Funcionário",
  cliente: "Cliente",
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
      { href: "/pages/rotas.html", label: "Rotas", modulo: "passagens", grupo: "Frota" },
      { href: "/pages/fretamentos.html", label: "Fretamentos", modulo: "fretamento", grupo: "Fretamento e frete" },
      { href: "/pages/fretes.html", label: "Fretes", modulo: "frete", grupo: "Fretamento e frete" },
      { href: "/pages/relatorios.html", label: "Relatórios", grupo: "Financeiro" },
      { href: "/pages/dre.html", label: "DRE", grupo: "Financeiro" },
      { href: "/pages/minhas-faturas.html", label: "Faturas", grupo: "Financeiro" },
      { href: "/pages/funcionarios.html", label: "Funcionários", grupo: "Equipe" },
      { href: "/pages/avaliacoes.html", label: "Avaliações", grupo: "Equipe" },
      { href: "/pages/auditoria.html", label: "Auditoria", grupo: "Equipe" },
      { href: "/pages/configuracoes.html", label: "Configurações" },
    ];
  }
  if (role === "funcionario") {
    return [
      ...base,
      { href: "/pages/viagens.html", label: "Viagens", modulo: "passagens", grupo: "Vendas" },
      { href: "/pages/checkin.html", label: "Check-in", modulo: "passagens", grupo: "Vendas" },
      { href: "/pages/fretamentos.html", label: "Fretamentos", modulo: "fretamento", grupo: "Fretamento e frete" },
      { href: "/pages/fretes.html", label: "Fretes", modulo: "frete", grupo: "Fretamento e frete" },
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

function montarTopo(containerId) {
  const auth = obterAuth();
  const container = document.getElementById(containerId);
  if (!container) return;

  const links = auth ? linksPorPapel(auth.role) : [];
  const caminhoAtual = window.location.pathname;
  const blocos = agruparLinks(links);
  const navHtml = blocos
    .map((bloco, indice) => {
      const rotulo = bloco.grupo ? `<span class="nav-rotulo-grupo">${bloco.grupo}</span>` : "";
      const linksDoBloco = bloco.links
        .map(
          (l) =>
            `<a href="${l.href}" class="link-nav${caminhoAtual === l.href ? " ativo" : ""}"${l.modulo ? ` data-modulo="${l.modulo}"` : ""}>${l.label}</a>`
        )
        .join("");
      const separador = indice > 0 ? '<div class="nav-separador"></div>' : "";
      return `${separador}<div class="nav-grupo">${rotulo}${linksDoBloco}</div>`;
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
          Go<span style="color:#4fd1a5">Tur</span>
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
        if (!empresa.fretamento_habilitado) {
          container.querySelectorAll('[data-modulo="fretamento"]').forEach((el) => el.classList.add("escondido"));
        }
        if (!empresa.passagens_habilitado) {
          container.querySelectorAll('[data-modulo="passagens"]').forEach((el) => el.classList.add("escondido"));
        }
        if (!empresa.frete_habilitado) {
          container.querySelectorAll('[data-modulo="frete"]').forEach((el) => el.classList.add("escondido"));
        }
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
