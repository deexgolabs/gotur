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

## Backup automático do banco

O script `backend/scripts/backup_db.py` copia o `gotur.db` pra
`backend/backups/`, com um carimbo de data/hora, e apaga automaticamente
as cópias mais antigas (mantém as 14 mais recentes por padrão).

Pra rodar todo dia sozinho no PythonAnywhere:
1. Aba **Tasks**.
2. Em **Scheduled Tasks**, escolha um horário (ex: 03:00) e cole:
   ```bash
   /home/SEU_USUARIO/gotur/backend/venv/bin/python /home/SEU_USUARIO/gotur/backend/scripts/backup_db.py
   ```
3. Salve. A partir daí roda todo dia sem precisar mexer em nada.

O plano gratuito do PythonAnywhere dá 1 tarefa agendada por dia — suficiente
pra esse backup diário. Se estiver usando Postgres/MySQL (não SQLite), esse
script não se aplica: use o backup do próprio provedor do banco.

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

## Checklist de segurança antes de ir ao ar

- [ ] `GOTUR_DEBUG=false` e `GOTUR_JWT_SECRET` configurado com valor forte e único
- [ ] Senha do super admin trocada (não deixe a do seed em produção)
- [ ] `GOTUR_CORS_ORIGINS` restrito ao(s) domínio(s) real(is), se o front for servido por fora do PythonAnywhere
- [ ] Considerar migrar de SQLite para Postgres/MySQL se esperar tráfego alto (`GOTUR_DATABASE_URL` — drivers `psycopg2`/`pymysql` já inclusos no requirements.txt)
- [ ] Backup automático configurado (ver seção "Backup automático do banco" acima)
- [ ] Sentry (ou similar) configurado pra saber quando algo quebrar em produção (ver seção acima)
- [ ] Rodar `pytest` antes de cada deploy para pegar regressões
