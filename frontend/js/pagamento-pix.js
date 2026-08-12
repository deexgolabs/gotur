function _pixParseDataUtc(valorIso) {
  // O backend manda datetime sem timezone (UTC "nu"); sem o "Z" o navegador
  // interpretaria como horário local e o cronômetro ficaria errado.
  return new Date(valorIso.endsWith("Z") ? valorIso : `${valorIso}Z`);
}

function _pixTempoRestante(expiraEm) {
  const ms = _pixParseDataUtc(expiraEm) - new Date();
  if (ms <= 0) return "expirado";
  const min = Math.floor(ms / 60000);
  const seg = Math.floor((ms % 60000) / 1000);
  return `${min}:${String(seg).padStart(2, "0")}`;
}

/**
 * Renderiza a tela de pagamento Pix (ambiente simulado) dentro de `container`
 * e (opcionalmente) faz polling do status. Chama `opcoes.aoConfirmar(resultadoOuNull)`
 * quando é confirmado — `resultadoOuNull` vem do próprio botão quando é ele
 * quem confirma, ou `null` quando veio do polling (confirmado em outra aba,
 * ou por um webhook de gateway real no futuro).
 *
 * Por padrão usa os endpoints de compra de passagem
 * (`/pedidos-pagamento/{id}/...`); passe `opcoes.endpointConfirmar` (e,
 * se quiser polling, `opcoes.endpointConsultar` + `opcoes.valoresConfirmado`
 * / `opcoes.valoresExpirado`) para reaproveitar em outro fluxo (ex: fatura
 * da assinatura).
 */
function renderizarPagamentoPix(container, pedido, opcoes = {}) {
  const endpointConfirmar = opcoes.endpointConfirmar || `/pedidos-pagamento/${pedido.id}/confirmar-simulado`;
  const endpointConsultar = opcoes.endpointConsultar || (opcoes.semPolling ? null : `/pedidos-pagamento/${pedido.id}`);
  const campoStatus = opcoes.campoStatus || "status";
  const valoresConfirmado = opcoes.valoresConfirmado || ["confirmado"];
  const valoresExpirado = opcoes.valoresExpirado || ["expirado", "cancelado"];
  let intervalo = null;

  function pararPolling() {
    if (intervalo) clearInterval(intervalo);
    intervalo = null;
  }

  // Sem `forma_pagamento` (ex: fatura da assinatura, que reaproveita este
  // mesmo componente) trata como Pix — é o único meio que a fatura usa.
  const ehPix = !pedido.forma_pagamento || pedido.forma_pagamento === "pix";

  function render() {
    container.innerHTML = ehPix
      ? `
      <div class="pix-caixa">
        <h3>Pagamento via Pix</h3>
        <p>Escaneie ou copie o código abaixo no app do seu banco. Valor: <strong>R$ ${Number(pedido.valor).toFixed(2)}</strong></p>
        <textarea readonly class="pix-codigo" id="pix-codigo">${pedido.pix_copia_cola}</textarea>
        <button type="button" class="secundario" id="pix-copiar">Copiar código</button>
        <p class="pix-tempo" id="pix-tempo">Expira em <span id="pix-timer">${_pixTempoRestante(pedido.expira_em)}</span></p>
        <button type="button" id="pix-confirmar">Já paguei — confirmar pagamento</button>
        <p class="rodape-form">Ambiente simulado: nenhuma cobrança real é feita. Este botão simula a confirmação que um gateway de pagamento real enviaria automaticamente assim que o Pix cair na conta.</p>
        <div id="pix-status"></div>
      </div>
    `
      : `
      <div class="pix-caixa">
        <h3>Aguardando confirmação de pagamento</h3>
        <p>Esta empresa confirma o pagamento manualmente. Valor: <strong>R$ ${Number(pedido.valor).toFixed(2)}</strong></p>
        <p class="pix-tempo" id="pix-tempo">Expira em <span id="pix-timer">${_pixTempoRestante(pedido.expira_em)}</span></p>
        <button type="button" id="pix-confirmar">Confirmar pagamento recebido</button>
        <p class="rodape-form">Clique acima assim que receber o pagamento (dinheiro, maquininha própria etc.) pra liberar a venda.</p>
        <div id="pix-status"></div>
      </div>
    `;

    if (ehPix) {
      document.getElementById("pix-copiar").addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(pedido.pix_copia_cola);
          const botao = document.getElementById("pix-copiar");
          botao.textContent = "Copiado!";
          setTimeout(() => (botao.textContent = "Copiar código"), 2000);
        } catch (erro) {
          document.getElementById("pix-codigo").select();
        }
      });
    }

    document.getElementById("pix-confirmar").addEventListener("click", async () => {
      const botao = document.getElementById("pix-confirmar");
      botao.disabled = true;
      try {
        const resultado = await api("POST", endpointConfirmar);
        pararPolling();
        if (opcoes.aoConfirmar) opcoes.aoConfirmar(resultado);
      } catch (erro) {
        botao.disabled = false;
        document.getElementById("pix-status").innerHTML = `<div class="alerta erro">${erro.message}</div>`;
      }
    });
  }

  render();

  if (endpointConsultar) {
    intervalo = setInterval(async () => {
      let atualizado;
      try {
        atualizado = await api("GET", endpointConsultar);
      } catch (erro) {
        return;
      }
      const statusAtual = atualizado[campoStatus];
      if (valoresConfirmado.includes(statusAtual)) {
        pararPolling();
        if (opcoes.aoConfirmar) opcoes.aoConfirmar(null);
      } else if (valoresExpirado.includes(statusAtual)) {
        pararPolling();
        document.getElementById("pix-status").innerHTML = ehPix
          ? '<div class="alerta erro">Pix expirado sem pagamento. Tente novamente.</div>'
          : '<div class="alerta erro">Prazo esgotado sem confirmação. Tente novamente.</div>';
        document.getElementById("pix-confirmar").disabled = true;
      } else {
        const span = document.getElementById("pix-timer");
        const linha = document.getElementById("pix-tempo");
        if (span) span.textContent = _pixTempoRestante(pedido.expira_em);
        if (linha && _pixParseDataUtc(pedido.expira_em) - new Date() < 60000) linha.classList.add("expirando");
      }
    }, 4000);
  }

  return { pararPolling };
}
