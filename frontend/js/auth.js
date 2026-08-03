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
    return [...base, { href: "/pages/empresas.html", label: "Empresas" }];
  }
  if (role === "admin_empresa") {
    return [
      ...base,
      { href: "/pages/funcionarios.html", label: "Funcionários" },
      { href: "/pages/onibus.html", label: "Ônibus" },
      { href: "/pages/rotas.html", label: "Rotas" },
      { href: "/pages/viagens.html", label: "Viagens" },
      { href: "/pages/checkin.html", label: "Check-in" },
      { href: "/pages/relatorios.html", label: "Relatórios" },
    ];
  }
  if (role === "funcionario") {
    return [
      ...base,
      { href: "/pages/viagens.html", label: "Viagens" },
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

function montarTopo(containerId) {
  const auth = obterAuth();
  const container = document.getElementById(containerId);
  if (!container) return;

  const links = auth ? linksPorPapel(auth.role) : [];
  const linksHtml = links.map((l) => `<a href="${l.href}">${l.label}</a>`).join("");
  const nomeHtml = auth
    ? `<span style="margin-left:18px;opacity:.85;font-size:.88rem">${auth.nome} · ${ROTULOS_PAPEL[auth.role] || auth.role}</span>
       <a href="#" id="link-sair">Sair</a>`
    : "";

  container.innerHTML = `
    <header class="topo">
      <div class="marca">Go<span style="color:#4fd1a5">Tur</span></div>
      <nav>${linksHtml}${nomeHtml}</nav>
    </header>
  `;

  const linkSair = document.getElementById("link-sair");
  if (linkSair) {
    linkSair.addEventListener("click", (ev) => {
      ev.preventDefault();
      sair();
    });
  }
}
