function _garantirDialogChecklist() {
  if (document.getElementById("dialog-checklist")) return;
  const dialog = document.createElement("dialog");
  dialog.id = "dialog-checklist";
  dialog.style.cssText = "border:none;border-radius:8px;padding:24px;max-width:480px;width:100%";
  dialog.innerHTML = `
    <h2 style="margin-top:0" id="titulo-dialog-checklist">Checklist pré-viagem</h2>
    <div id="conteudo-checklist"></div>
    <div class="linha-acoes">
      <button type="button" class="secundario" id="btn-fechar-checklist">Fechar</button>
    </div>
  `;
  document.body.appendChild(dialog);
  dialog.querySelector("#btn-fechar-checklist").addEventListener("click", () => dialog.close());
}

function _formatarHoraChecklist(iso) {
  return iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "-";
}

async function abrirDialogChecklist(tipoViagem, referenciaId, motoristaNome) {
  _garantirDialogChecklist();
  const dialog = document.getElementById("dialog-checklist");
  const titulo = document.getElementById("titulo-dialog-checklist");
  const conteudo = document.getElementById("conteudo-checklist");
  titulo.textContent = `Checklist pré-viagem — ${motoristaNome || "sem motorista definido"}`;

  if (!motoristaNome) {
    conteudo.innerHTML = `<p class="vazio">Defina o nome do motorista antes de preencher o checklist.</p>`;
    dialog.showModal();
    return;
  }

  conteudo.innerHTML = "Carregando...";
  dialog.showModal();

  try {
    const checklists = await api("GET", `/checklists?tipo_viagem=${tipoViagem}&referencia_id=${referenciaId}`);

    const linhasHistorico = checklists
      .map(
        (c) => `
      <tr>
        <td>${_formatarHoraChecklist(c.criado_em)}</td>
        <td>${c.pneus_ok ? "✅" : "❌"}</td>
        <td>${c.oleo_ok ? "✅" : "❌"}</td>
        <td>${c.combustivel_ok ? "✅" : "❌"}</td>
      </tr>`
      )
      .join("");

    conteudo.innerHTML = `
      <form id="form-checklist" style="margin-bottom:16px">
        <label style="display:flex;align-items:center;gap:8px;font-weight:400;margin-bottom:8px">
          <input type="checkbox" id="chk-pneus" style="width:auto" />
          Pneus (calibragem e estado)
        </label>
        <label style="display:flex;align-items:center;gap:8px;font-weight:400;margin-bottom:8px">
          <input type="checkbox" id="chk-oleo" style="width:auto" />
          Nível de óleo
        </label>
        <label style="display:flex;align-items:center;gap:8px;font-weight:400;margin-bottom:8px">
          <input type="checkbox" id="chk-combustivel" style="width:auto" />
          Combustível suficiente
        </label>
        <label for="chk-observacoes">Observações (opcional)</label>
        <input id="chk-observacoes" placeholder="Ex: pneu dianteiro direito baixo" />
        <div class="linha-acoes" style="margin:12px 0 0">
          <button type="submit">Registrar checklist</button>
        </div>
      </form>
      <table>
        <thead><tr><th>Quando</th><th>Pneus</th><th>Óleo</th><th>Combustível</th></tr></thead>
        <tbody>${linhasHistorico || '<tr><td colspan="4">Nenhum checklist registrado ainda.</td></tr>'}</tbody>
      </table>
    `;

    document.getElementById("form-checklist").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        await api("POST", "/checklists", {
          motorista_nome: motoristaNome,
          tipo_viagem: tipoViagem,
          referencia_id: referenciaId,
          pneus_ok: document.getElementById("chk-pneus").checked,
          oleo_ok: document.getElementById("chk-oleo").checked,
          combustivel_ok: document.getElementById("chk-combustivel").checked,
          observacoes: document.getElementById("chk-observacoes").value.trim() || null,
        });
        abrirDialogChecklist(tipoViagem, referenciaId, motoristaNome);
      } catch (erro) {
        alert(erro.message);
      }
    });
  } catch (erro) {
    conteudo.innerHTML = `<p class="vazio">${erro.message}</p>`;
  }
}
