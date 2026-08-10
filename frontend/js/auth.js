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
      { href: "/pages/funcionarios.html", label: "Funcionários" },
      { href: "/pages/onibus.html", label: "Ônibus" },
      { href: "/pages/rotas.html", label: "Rotas" },
      { href: "/pages/viagens.html", label: "Viagens" },
      { href: "/pages/fretamentos.html", label: "Fretamentos" },
      { href: "/pages/checkin.html", label: "Check-in" },
      { href: "/pages/relatorios.html", label: "Relatórios" },
      { href: "/pages/auditoria.html", label: "Auditoria" },
      { href: "/pages/minhas-faturas.html", label: "Faturas" },
      { href: "/pages/configuracoes.html", label: "Configurações" },
    ];
  }
  if (role === "funcionario") {
    return [
      ...base,
      { href: "/pages/viagens.html", label: "Viagens" },
      { href: "/pages/fretamentos.html", label: "Fretamentos" },
      { href: "/pages/checkin.html", label: "Check-in" },
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

const ICONE_MENU = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`;
const ICONE_FECHAR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>`;

function montarTopo(containerId) {
  const auth = obterAuth();
  const container = document.getElementById(containerId);
  if (!container) return;

  const links = auth ? linksPorPapel(auth.role) : [];
  const caminhoAtual = window.location.pathname;
  const linksHtml = links
    .map((l) => `<a href="${l.href}" class="link-nav${caminhoAtual === l.href ? " ativo" : ""}">${l.label}</a>`)
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
        <div class="marca">Go<span style="color:#4fd1a5">Tur</span></div>
        <button type="button" class="btn-menu-mobile" id="btn-menu-mobile" aria-label="Abrir menu" aria-expanded="false">${ICONE_MENU}</button>
      </div>
      <nav id="nav-principal">
        ${linksHtml}
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
}
