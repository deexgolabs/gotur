function _garantirDialogJornada() {
  if (document.getElementById("dialog-jornada")) return;
  const dialog = document.createElement("dialog");
  dialog.id = "dialog-jornada";
  dialog.style.cssText = "border:none;border-radius:8px;padding:24px;max-width:480px;width:100%";
  dialog.innerHTML = `
    <h2 style="margin-top:0" id="titulo-dialog-jornada">Jornada do motorista</h2>
    <div id="conteudo-jornada"></div>
    <div class="linha-acoes">
      <button type="button" class="secundario" id="btn-fechar-jornada">Fechar</button>
    </div>
  `;
  document.body.appendChild(dialog);
  dialog.querySelector("#btn-fechar-jornada").addEventListener("click", () => dialog.close());
}

function _formatarHoraJornada(iso) {
  return iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "-";
}

async function abrirDialogJornada(tipoViagem, referenciaId, motoristaNome) {
  _garantirDialogJornada();
  const dialog = document.getElementById("dialog-jornada");
  const titulo = document.getElementById("titulo-dialog-jornada");
  const conteudo = document.getElementById("conteudo-jornada");
  titulo.textContent = `Jornada — ${motoristaNome || "sem motorista definido"}`;

  if (!motoristaNome) {
    conteudo.innerHTML = `<p class="vazio">Defina o nome do motorista antes de controlar a jornada.</p>`;
    dialog.showModal();
    return;
  }

  conteudo.innerHTML = "Carregando...";
  dialog.showModal();

  try {
    const [jornadas, resumo] = await Promise.all([
      api("GET", `/jornadas?tipo_viagem=${tipoViagem}&referencia_id=${referenciaId}`),
      api("GET", `/jornadas/resumo?motorista_nome=${encodeURIComponent(motoristaNome)}`),
    ]);

    const aberta = jornadas.find((j) => j.fim === null);

    const avisoLimite = resumo.acima_do_limite
      ? `<p class="alerta erro" style="margin:0 0 12px">${motoristaNome} já soma ${resumo.horas_ultimas_24h}h nas últimas 24h — acima do limite de referência (8h) da Lei do Motorista.</p>`
      : `<p class="rodape-form" style="text-align:left">Horas nas últimas 24h: ${resumo.horas_ultimas_24h}h</p>`;

    const linhasHistorico = jornadas
      .map(
        (j) => `
      <tr>
        <td>${_formatarHoraJornada(j.inicio)}</td>
        <td>${j.fim ? _formatarHoraJornada(j.fim) : "Em andamento"}</td>
        <td>${j.horas}h</td>
      </tr>`
      )
      .join("");

    conteudo.innerHTML = `
      ${avisoLimite}
      <div class="linha-acoes" style="margin:0 0 14px">
        ${aberta
          ? `<button type="button" id="btn-encerrar-jornada" data-id="${aberta.id}">Encerrar jornada</button>`
          : `<button type="button" id="btn-iniciar-jornada">Iniciar jornada</button>`}
      </div>
      <table>
        <thead><tr><th>Início</th><th>Fim</th><th>Horas</th></tr></thead>
        <tbody>${linhasHistorico || '<tr><td colspan="3">Nenhuma jornada registrada ainda.</td></tr>'}</tbody>
      </table>
    `;

    const btnIniciar = document.getElementById("btn-iniciar-jornada");
    if (btnIniciar) {
      btnIniciar.addEventListener("click", async () => {
        try {
          await api("POST", "/jornadas", { motorista_nome: motoristaNome, tipo_viagem: tipoViagem, referencia_id: referenciaId });
          abrirDialogJornada(tipoViagem, referenciaId, motoristaNome);
        } catch (erro) {
          alert(erro.message);
        }
      });
    }
    const btnEncerrar = document.getElementById("btn-encerrar-jornada");
    if (btnEncerrar) {
      btnEncerrar.addEventListener("click", async () => {
        try {
          await api("PATCH", `/jornadas/${btnEncerrar.dataset.id}/encerrar`);
          abrirDialogJornada(tipoViagem, referenciaId, motoristaNome);
        } catch (erro) {
          alert(erro.message);
        }
      });
    }
  } catch (erro) {
    conteudo.innerHTML = `<p class="vazio">${erro.message}</p>`;
  }
}
