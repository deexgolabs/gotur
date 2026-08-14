function _pixParseDataUtc(valorIso) {
  // O backend manda datetime sem timezone (UTC "nu"); sem o "Z" o navegador
  // interpretaria como horário local e o cronômetro ficaria errado.
  return new Date(valorIso.endsWith("Z") ? valorIso : `${valorIso}Z`);
}

function _pixTempoRestante(expiraEm) {
  const ms = _pixParseDataUtc(expiraEm) - new Date();
  if (ms <= 0) return "expirado";

  // Pix expira em minutos, então minutos:segundos faz sentido; boleto
  // expira em dias, e o mesmo formato viraria algo tipo "4319:59" — ilegível.
  // Acima de 1h mostra dias/horas (mais grosseiro, mas legível); abaixo
  // disso mostra o cronômetro fino de sempre.
  const umaHoraEmMs = 60 * 60000;
  if (ms >= umaHoraEmMs) {
    const dias = Math.floor(ms / (24 * umaHoraEmMs));
    const horas = Math.floor((ms % (24 * umaHoraEmMs)) / umaHoraEmMs);
    if (dias > 0) return `${dias} dia${dias > 1 ? "s" : ""}${horas > 0 ? ` e ${horas}h` : ""}`;
    return `${horas}h`;
  }

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

  // Sem `forma_pagamento` (ex: passagem/pedido antigo) trata como Pix.
  const ehPix = !pedido.forma_pagamento || pedido.forma_pagamento === "pix";
  const ehBoleto = pedido.forma_pagamento === "boleto";
  const ehManualGenerico = !ehPix && !ehBoleto;

  // Controla se mostra o botão "Já paguei" — com um gateway real
  // configurado (mesmo em ambiente de teste do Mercado Pago), esse botão
  // só ia dar erro de "confirmação manual desabilitada", então nesse caso
  // só mostra que está esperando a confirmação automática. Vem de
  // `pedido.pagamento_simulado` (é assim que a API já manda), com
  // `opcoes.ehSimulado` como override explícito se precisar.
  const ehSimulado = opcoes.ehSimulado !== undefined ? opcoes.ehSimulado !== false : pedido.pagamento_simulado !== false;

  function _blocoConfirmarOuAguardar(rotulo) {
    if (ehSimulado) {
      return `<button type="button" id="pix-confirmar">Já paguei — confirmar pagamento</button>
        <p class="rodape-form">Ambiente simulado: nenhuma cobrança real é feita. Este botão simula a confirmação que um gateway de pagamento real enviaria automaticamente assim que o pagamento cair.</p>`;
    }
    return `<p class="rodape-form">Assim que o pagamento cair, a confirmação é automática — não precisa fazer nada além de pagar o ${rotulo} acima.</p>`;
  }

  function render() {
    if (ehPix) {
      container.innerHTML = `
      <div class="pix-caixa">
        <h3>Pagamento via Pix</h3>
        <p>Escaneie ou copie o código abaixo no app do seu banco. Valor: <strong>R$ ${Number(pedido.valor).toFixed(2)}</strong></p>
        <textarea readonly class="pix-codigo" id="pix-codigo">${pedido.pix_copia_cola}</textarea>
        <button type="button" class="secundario" id="pix-copiar">Copiar código</button>
        <p class="pix-tempo" id="pix-tempo">Expira em <span id="pix-timer">${_pixTempoRestante(pedido.expira_em)}</span></p>
        ${_blocoConfirmarOuAguardar("Pix")}
        <div id="pix-status"></div>
      </div>
    `;
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
    } else if (ehBoleto) {
      container.innerHTML = `
      <div class="pix-caixa">
        <h3>Pagamento via boleto</h3>
        <p>Valor: <strong>R$ ${Number(pedido.valor).toFixed(2)}</strong> — o boleto pode levar até 3 dias úteis pra compensar depois de pago.</p>
        ${pedido.boleto_codigo_barras ? `<textarea readonly class="pix-codigo" id="pix-codigo">${pedido.boleto_codigo_barras}</textarea>
        <button type="button" class="secundario" id="pix-copiar">Copiar linha digitável</button>` : ""}
        ${pedido.boleto_url ? `<p><a href="${pedido.boleto_url}" target="_blank" rel="noopener">Abrir/imprimir boleto</a></p>` : ""}
        <p class="pix-tempo" id="pix-tempo">Vence em <span id="pix-timer">${_pixTempoRestante(pedido.expira_em)}</span></p>
        ${_blocoConfirmarOuAguardar("boleto")}
        <div id="pix-status"></div>
      </div>
    `;
      const botaoCopiar = document.getElementById("pix-copiar");
      if (botaoCopiar) {
        botaoCopiar.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(pedido.boleto_codigo_barras);
            botaoCopiar.textContent = "Copiado!";
            setTimeout(() => (botaoCopiar.textContent = "Copiar linha digitável"), 2000);
          } catch (erro) {
            document.getElementById("pix-codigo").select();
          }
        });
      }
    } else if (ehManualGenerico) {
      container.innerHTML = `
      <div class="pix-caixa">
        <h3>Aguardando confirmação de pagamento</h3>
        <p>Esta empresa confirma o pagamento manualmente. Valor: <strong>R$ ${Number(pedido.valor).toFixed(2)}</strong></p>
        <p class="pix-tempo" id="pix-tempo">Expira em <span id="pix-timer">${_pixTempoRestante(pedido.expira_em)}</span></p>
        <button type="button" id="pix-confirmar">Confirmar pagamento recebido</button>
        <p class="rodape-form">Clique acima assim que receber o pagamento (dinheiro, maquininha própria etc.) pra liberar a venda.</p>
        <div id="pix-status"></div>
      </div>
    `;
    }

    const botaoConfirmar = document.getElementById("pix-confirmar");
    if (!botaoConfirmar) return;
    botaoConfirmar.addEventListener("click", async () => {
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
        const botaoConfirmar = document.getElementById("pix-confirmar");
        if (botaoConfirmar) botaoConfirmar.disabled = true;
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
