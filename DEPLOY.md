# Deploy no PythonAnywhere

O PythonAnywhere hospeda aplicações via WSGI. O GoTur é uma API FastAPI
(ASGI), então usamos um adaptador ASGI→WSGI próprio
(`backend/app/wsgi_adapter.py`, referenciado por
`backend/pythonanywhere_wsgi.py`) para rodar sem mudar o código da
aplicação — testado e escolhido no lugar do pacote `a2wsgi` porque este
trava (deadlock) dentro do modelo de processo do uWSGI do PythonAnywhere.

## 1. Subir o código

Duas opções — escolha uma:

**A) Via Git (recomendado, facilita atualizar depois)**
1. Suba o projeto para um repositório no GitHub (pode ser privado).
2. No PythonAnywhere, abra um **Bash console** (aba *Consoles*) e rode:
   ```bash
   git clone https://github.com/SEU_USUARIO/SEU_REPO.git gotur
   ```

**B) Via upload de arquivos**
1. Compacte a pasta `gotur/` localmente (zip).
2. Na aba *Files* do PythonAnywhere, envie o zip e rode no console:
   ```bash
   unzip gotur.zip -d gotur
   ```

## 2. Criar o ambiente virtual e instalar dependências

No Bash console do PythonAnywhere:
```bash
cd ~/gotur/backend
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
nano .env
```
No mínimo, defina:
- `GOTUR_DEBUG=false`
- `GOTUR_JWT_SECRET=` uma string aleatória longa (ex: gere com `python3 -c "import secrets; print(secrets.token_hex(32))"`)

O arquivo `.env` **não** deve ser commitado (já está no `.gitignore`).

## 4. Rodar as migrações do banco

O schema é gerenciado via Alembic — **sempre rode isso antes de subir a
aplicação**, tanto na primeira vez quanto depois de puxar código novo:
```bash
alembic upgrade head
```
Isso cria as tabelas do zero (banco novo) ou aplica só as mudanças
pendentes (banco já existente) — sem apagar dados.

## 5. Popular o banco (opcional, cria super admin + empresa demo)

```bash
python seed.py
```
Ou pule este passo e crie o super admin manualmente depois — veja a seção 8.

## 6. Configurar a aba "Web"

1. Na aba **Web**, clique em **Add a new web app**.
2. Escolha **Manual configuration** (não escolha Flask/Django) e a versão de Python que você usou no venv (ex: 3.10).
3. Em **Virtualenv**, informe: `/home/SEU_USUARIO/gotur/backend/venv`
4. Em **Code → WSGI configuration file**, clique no link do arquivo e **substitua todo o conteúdo** por:
   ```python
   import sys
   path = '/home/SEU_USUARIO/gotur/backend'
   if path not in sys.path:
       sys.path.insert(0, path)

   from pythonanywhere_wsgi import application
   ```
5. Salve e clique em **Reload** (botão verde no topo da aba Web).

## 7. Acessar

Seu app estará em `https://SEU_USUARIO.pythonanywhere.com` (HTTPS já incluso).
O frontend (HTML/CSS/JS) é servido pela própria aplicação na raiz; a API fica em `/api`.

## 8. Criar o primeiro super admin (se não rodou o seed)

No Bash console, com o venv ativado (depois de rodar `alembic upgrade head`):
```bash
cd ~/gotur/backend
python -c "
from app.database import SessionLocal
from app.core.security import hash_senha
from app.models.usuario import Usuario
from app.models.enums import UserRole
db = SessionLocal()
db.add(Usuario(nome='Super Admin', email='seu-email@exemplo.com', senha_hash=hash_senha('TROQUE-ESTA-SENHA'), role=UserRole.SUPER_ADMIN))
db.commit()
print('Super admin criado')
"
```
Troque o e-mail e a senha antes de rodar, e troque a senha novamente após o primeiro login.

## Atualizando depois de mudanças no código

```bash
cd ~/gotur
git pull                     # se usou a opção A
cd backend && source venv/bin/activate
pip install -r requirements.txt   # se requirements.txt mudou
alembic upgrade head              # sempre rodar — aplica migrações pendentes
```
Depois volte na aba **Web** e clique **Reload**.

## Rodando os testes automatizados (opcional, mas recomendado antes de cada deploy)

```bash
cd ~/gotur/backend
pip install -r requirements-dev.txt
pytest
```

## Tarefa diária: backup + cobrança recorrente

Duas coisas precisam rodar sozinhas todo dia:

- **Backup do banco** (`backend/scripts/backup_db.py`) — copia o `gotur.db`
  pra `backend/backups/` com carimbo de data/hora, e apaga as cópias mais
  antigas (mantém as 14 mais recentes por padrão). Só cuida de SQLite — se
  `GOTUR_DATABASE_URL` apontar pra Postgres/MySQL, use o backup do próprio
  provedor em vez disso.
- **Cobrança recorrente** (`backend/scripts/gerar_faturas_mensais.py`) —
  gera a fatura de quem venceu o ciclo (30 dias desde a última, ou o fim do
  trial pra empresa nova) e atualiza quem ficou inadimplente/suspenso por
  atraso. Sem isso, é o super admin que precisa entrar no painel e gerar
  fatura na mão pra cada empresa. Ver `app/services/faturamento.py` pra
  entender a regra do ciclo.

O plano gratuito do PythonAnywhere só dá **1 tarefa agendada** — por isso
existe `backend/scripts/tarefas_diarias.py`, que roda as duas em sequência.
Pra ativar:
1. Aba **Tasks**.
2. Em **Scheduled Tasks**, escolha um horário (ex: 03:00) e cole:
   ```bash
   /home/SEU_USUARIO/gotur/backend/venv/bin/python /home/SEU_USUARIO/gotur/backend/scripts/tarefas_diarias.py --base-url https://SEU_USUARIO.pythonanywhere.com
   ```
   Troque `--base-url` pelo domínio real — é o que entra no link de
   pagamento mandado por e-mail/WhatsApp quando uma fatura é gerada.
3. Salve. A partir daí roda todo dia sem precisar mexer em nada.

Se você estiver num plano pago do PythonAnywhere (mais de 1 tarefa
agendada) ou fora do PythonAnywhere, pode preferir agendar
`backup_db.py` e `gerar_faturas_mensais.py` como duas tarefas separadas em
horários diferentes — os dois continuam funcionando sozinhos também.

## Gateway de pagamento real (Mercado Pago, opcional)

Sem nada configurado, o sistema roda em modo simulado: Pix gera um código
de mentira e cartão/dinheiro/outro são aprovados na hora — ótimo para
testar o fluxo, mas não cobra ninguém de verdade. Pra ativar o Mercado
Pago de verdade (Pix real):
1. Crie uma aplicação em [mercadopago.com.br/developers](https://www.mercadopago.com.br/developers/panel/app) e pegue o **Access Token de produção**.
2. No `.env` do servidor, adicione:
   ```
   GOTUR_GATEWAY_API_KEY=APP_USR-SEU-ACCESS-TOKEN
   ```
3. Reload na aba Web. A partir daí, toda compra por Pix gera uma cobrança
   de verdade no Mercado Pago (código copia-e-cola real).

Cartão de crédito **ainda não** funciona com o gateway real — o Mercado
Pago exige tokenizar o cartão no navegador do cliente (Card Payment Brick)
antes de cobrar, o que precisa de uma tela de checkout própria. Com a
chave configurada, escolher "Cartão" na compra dá erro; sem a chave
(modo simulado), continua aprovando na hora como antes. Ver
`backend/app/services/pagamento_provider.py` para o ponto exato de
extensão quando for implementar.

## Nota fiscal de serviço eletrônica (NFS-e, terreno pronto)

NFS-e não tem uma API nacional única — cada prefeitura tem seu próprio
webservice. O caminho realista é contratar um agregador (Focus NFe, NFE.io,
PlugNotas, etc.) que fala com as prefeituras por você. Isso **ainda não
está implementado** — o botão "Emitir NFS-e" (na tela de uma viagem) já
existe e funciona, mas sem um agregador configurado ele só registra no log
("emissão simulada"), sem gerar nota nenhuma.

Pra implementar de verdade quando for contratar um agregador:
1. Configure `GOTUR_NFSE_PROVIDER_URL` e `GOTUR_NFSE_PROVIDER_TOKEN` no `.env`.
2. Implemente `NfseProviderReal.emitir()` em `backend/app/services/nfse_provider.py`, chamando o endpoint de emissão do agregador escolhido (o payload varia por provedor).
3. Nenhum outro ponto do sistema precisa mudar.

## Monitoramento de erro (Sentry, opcional)

Sem nada configurado, erros só aparecem nos logs do PythonAnywhere (aba
**Web → Log files**). Pra receber alerta automático de erro em produção:
1. Crie uma conta grátis em [sentry.io](https://sentry.io) e um projeto Python/FastAPI.
2. Copie o DSN do projeto.
3. No `.env` do servidor, adicione:
   ```
   GOTUR_SENTRY_DSN=https://SUACHAVE@oNNNN.ingest.sentry.io/NNNN
   ```
4. Reload na aba Web. Pronto — erros não tratados passam a aparecer no painel do Sentry automaticamente.

## Push notification real (Web Push, opcional)

Sem nada configurado, quem acompanha um fretamento/frete pela tela de
rastreio não vê o botão funcionar de verdade (some com um aviso). Pra
ativar notificações reais do navegador quando o status muda:

1. Gere o par de chaves VAPID:
   ```bash
   cd ~/gotur/backend
   venv/bin/python scripts/gerar_chaves_vapid.py
   ```
2. Copie as três linhas impressas pro `.env` do servidor:
   ```
   GOTUR_VAPID_PUBLIC_KEY=...
   GOTUR_VAPID_PRIVATE_KEY=...
   GOTUR_VAPID_CLAIMS_EMAIL=seuemail@suaempresa.com
   ```
3. Reload na aba Web. O botão "Ativar notificações" nas telas de rastreio
   (e na loja white-label) passa a funcionar de verdade — sem depender de
   Firebase ou qualquer serviço pago.

## Checklist de segurança antes de ir ao ar

- [ ] `GOTUR_DEBUG=false` e `GOTUR_JWT_SECRET` configurado com valor forte e único
- [ ] Senha do super admin trocada (não deixe a do seed em produção)
- [ ] `GOTUR_CORS_ORIGINS` restrito ao(s) domínio(s) real(is), se o front for servido por fora do PythonAnywhere
- [ ] Considerar migrar de SQLite para Postgres/MySQL se esperar tráfego alto (`GOTUR_DATABASE_URL` — drivers `psycopg2`/`pymysql` já inclusos no requirements.txt)
- [ ] Backup automático configurado (ver seção "Backup automático do banco" acima)
- [ ] Sentry (ou similar) configurado pra saber quando algo quebrar em produção (ver seção acima)
- [ ] Rodar `pytest` antes de cada deploy para pegar regressões
