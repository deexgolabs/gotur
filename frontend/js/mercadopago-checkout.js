/**
 * Card Payment Brick do Mercado Pago — carrega o SDK deles sob demanda e
 * monta o formulário de cartão dentro de um container. O Brick cuida de
 * validar e tokenizar o cartão direto no navegador do cliente (o número
 * do cartão nunca passa pelo nosso backend, só o token que ele gera).
 *
 * Segue o contrato oficial documentado em
 * https://www.mercadopago.com.br/developers/pt/docs/checkout-bricks/card-payment-brick/introduction
 */

function _carregarSdkMercadoPago() {
  if (window.MercadoPago) return Promise.resolve();
  if (window._mpSdkPromise) return window._mpSdkPromise;
  window._mpSdkPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://sdk.mercadopago.com/js/v2";
    script.onload = resolve;
    script.onerror = () => reject(new Error("Não foi possível carregar o Mercado Pago. Verifique sua conexão."));
    document.head.appendChild(script);
  });
  return window._mpSdkPromise;
}

let _brickCartaoAtual = null;

/**
 * `opcoes.publicKey`: Public Key da empresa (ou null — nesse caso mostra
 * um aviso em vez de montar o Brick).
 * `opcoes.valor`: valor total a cobrar, em reais.
 * `opcoes.onPagar(dadosCartao)`: chamado quando o cliente confirma o
 * pagamento dentro do Brick — `dadosCartao` é
 * `{token, payment_method_id, installments, payer_email}`. Deve devolver
 * uma Promise: resolve se a cobrança deu certo no nosso backend (o Brick
 * mostra sucesso), rejeita com uma mensagem se falhou (o Brick mostra o
 * erro e deixa o cliente tentar de novo).
 */
async function montarCheckoutCartaoMP(containerId, { publicKey, valor, onPagar }) {
  const container = document.getElementById(containerId);
  if (!publicKey) {
    container.innerHTML = '<p class="vazio">Pagamento com cartão indisponível — esta empresa ainda não configurou o Mercado Pago.</p>';
    return;
  }

  container.innerHTML = "";
  desmontarCheckoutCartaoMP();

  try {
    await _carregarSdkMercadoPago();
  } catch (erro) {
    container.innerHTML = `<p class="vazio">${erro.message}</p>`;
    return;
  }

  const mp = new MercadoPago(publicKey, { locale: "pt-BR" });
  const bricksBuilder = mp.bricks();

  _brickCartaoAtual = await bricksBuilder.create("cardPayment", containerId, {
    initialization: { amount: valor },
    customization: { visual: { style: { theme: "default" } } },
    callbacks: {
      onReady: () => {},
      onSubmit: (formData) =>
        new Promise((resolve, reject) => {
          onPagar({
            token: formData.token,
            payment_method_id: formData.payment_method_id,
            installments: formData.installments,
            payer_email: formData.payer && formData.payer.email,
          })
            .then(resolve)
            .catch((erro) => reject(erro));
        }),
      onError: (erro) => {
        console.error("Erro no Card Payment Brick:", erro);
      },
    },
  });
}

function desmontarCheckoutCartaoMP() {
  if (_brickCartaoAtual) {
    try {
      _brickCartaoAtual.unmount();
    } catch (e) {
      // brick já desmontado — ignora
    }
    _brickCartaoAtual = null;
  }
}
