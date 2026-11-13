# SafeWalk API — Rotas mais seguras para quem anda a pé em São Paulo

**Global Solution FIAP 2026.2 · CitizenTech · Engenharia de Software (3ESPG) · Disciplina: Arquitetura Orientada a Serviços (SOA) e Web Services**

## Integrantes

| Nome | RM |
|---|---|
| Gustavo Alves | 557876 |
| Gabriel Dias | 556830 |
| Leonardo Taschin | 554583 |
| Gabriel Galerani | 557421 |
| Enzo Dias | 558225 |

## Ficha da CitizenTech

| Campo | Resposta |
|---|---|
| **Nome** | SafeWalk |
| **Cidade e bairro** | São Paulo — Av. Paulista / Consolação (região da FIAP Paulista) |
| **Cidadão beneficiado** | Pedestres da capital, com foco em quem anda à noite, mulheres, idosos, PCD e crianças, e nas pessoas que os acompanham à distância |
| **Problema, em uma frase** | Os apps de mapa escolhem o caminho mais curto, mas nenhum escolhe o mais seguro para quem anda a pé em São Paulo |
| **Como funciona** | O pedestre compara a rota rápida com a segura (com o motivo do risco), é acompanhado por contatos via link, tem SOS escalonado (pergunta → contatos → GCM) e colabora com relatos que alimentam o score e o painel da Prefeitura |
| **O que cada parte faz** | **Esta API (SOA):** regras de negócio, persistência, segurança e contratos REST · App mobile: jornada do cidadão · ML: score de risco · IoT: dispositivo/sensor · Cyber: LGPD, PIN, antiabuso |
| **Repositório** | https://github.com/G4T14H/safewalk-api |
| **Indicador de impacto** | (1) % de redução de risco da rota segura vs. rápida (`risk_reduction_pct` em `/routes/compare`); (2) nº de relatos confirmados; (3) tempo até a escalada do SOS; (4) chamados SP156 gerados pelos relatos |
| **ODS conectados** | **ODS 11** (cidades seguras e acessíveis — caminhabilidade e segurança urbana), **ODS 3** (saúde e bem-estar — redução de mortes no trânsito e violência), **ODS 10** (redução das desigualdades — perfis idoso/PCD), **ODS 9** (infraestrutura e inovação — integração de dados públicos), **ODS 13** (alagamentos entram no risco da rota) |

## O que esta entrega contém (mapeamento com a rubrica)

| Critério (pontos) | Onde está |
|---|---|
| **Estruturação do domínio (3,0)** | `app/domain/` (enums + 10 entidades com relacionamentos e regras), `app/services/` (regras puras: risco, rotas, anomalias, relatos, SOS), `app/routers/` (camada REST), `app/schemas.py` (contratos). Separação em camadas, sem regra de negócio nos controllers. |
| **Conexão com banco de dados (3,0)** | SQLAlchemy 2.0 (`app/database.py`). SQLite por padrão e **PostgreSQL** via `DATABASE_URL` (`docker-compose.yml`). Sessão por requisição (`get_db`), FKs com `ON DELETE`, índices, `UNIQUE` (ex.: uma confirmação por usuário/relato). |
| **Migrações (1,5)** | Alembic: `alembic/versions/0001_tabelas_iniciais_do_dominio.py` (10 tabelas) e `0002_reputacao_do_usuario.py` (evolução do domínio). `alembic check` sem divergências; upgrade e downgrade testados. |
| **Documentação automática (1,5)** | Swagger UI em **`/docs`**, ReDoc em `/redoc`, OpenAPI em `/openapi.json` (cópia em `docs/openapi.json`: 25 paths / 31 operações, todos com resumo e esquemas). Botão **Authorize** funcional (OAuth2 + JWT). |
| **Testes automatizados (1,0)** | `pytest` — **47 testes** (`tests/`, **96% de cobertura** do código da API), banco SQLite em memória isolado por teste. Inclui teste de migração (upgrade/downgrade). |

## Arquitetura

```
 App mobile (React Native) ─┐
 Link do contato (web)  ────┼──►  FastAPI (routers)  ──►  services (regras)  ──►  SQLAlchemy  ──►  SQLite / PostgreSQL
 Painel da Prefeitura (web) ┘            │                     │
                                         │ JWT/RBAC            ├─ risk_service    (score por ponto/horário, rota rápida × segura)
                                         │ rate limit          ├─ anomaly_service (parada, desvio, movimento brusco)
                                         ▼                     ├─ report_service  (peso progressivo, validade, antiabuso)
                                   Swagger /docs               └─ sos_service     (escalada por etapas)

 Smart Sampa / GCM / SP156: integrações SIMULADAS (câmeras e chamados fictícios em banco)
```

### Regras de negócio implementadas

- **Score de risco (0–1)** = histórico oficial × fator de horário + relatos ativos (peso progressivo) + penalidade de iluminação − redução por câmeras próximas. Perfis (`elderly_pcd`, `child`, `night`) mudam os pesos.
- **Rota rápida × segura**: a rápida é a linha reta; a segura é o candidato de menor risco entre desvios laterais, limitado a 1,6× o tempo da rápida. A resposta traz o **motivo do risco**, a diferença de tempo e a redução de risco (%).
- **Acompanhamento**: o contato só recebe link depois de **aceitar o convite**; o link é público (sem login), mostra só o último ponto e **expira** quando o trajeto termina (janela de 10 min só para a confirmação de chegada → depois `410 Gone`).
- **Anomalias**: parada ≥ 60 s no mesmo ponto, desvio > 150 m da rota, velocidade > 8 m/s.
- **SOS**: botão → contatos na hora; gatilho automático → pergunta "Tudo bem?" por 30 s → contatos → após 120 s, **central da GCM** (protocolo simulado). **Só o PIN cancela** (hash PBKDF2).
- **Relatos**: entram com peso baixo (depende da reputação do autor) e ganham +0,15 por confirmação; expiram por tipo (crimes 6 h, alagamento 12 h, infraestrutura até o SP156 resolver); autor nunca é exposto; antiduplicidade (100 m / 30 min) e limite de spam (5 / 10 min); operador pode marcar como falso (reduz reputação).
- **Segurança**: JWT, RBAC (`citizen` / `operator`), rate limit nos endpoints de auth, validação Pydantic, sem imagens nem biometria (câmeras = só posição).

## Como executar

### Opção A — um comando (SQLite, sem nada para configurar)

```bash
./run.sh          # Windows: run.bat
```

Cria o ambiente virtual, instala as dependências, aplica as migrações, popula o seed e sobe a API.
Abra **http://localhost:8000/docs**.

### Opção A2 — passo a passo

```bash
python -m venv .venv && source .venv/bin/activate      # Windows (PowerShell): .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head          # aplica as migrações
python -m app.seed            # dados de demonstração (hotspots, câmeras, usuários)
uvicorn app.main:app --reload
```

Abra **http://localhost:8000/docs**.

### Opção B — Docker + PostgreSQL (migrações também validadas em PostgreSQL 16)

```bash
docker compose up --build
```

### Testes

```bash
pytest -v
```

Versões exatas usadas nos testes: `requirements.lock.txt` (`pip install -r requirements.lock.txt` reproduz o ambiente).

### Usuários de demonstração (criados pelo seed)

| Perfil | E-mail | Senha |
|---|---|---|
| Cidadão | `leo@safewalk.dev` | `Cidadao@123` |
| Operador (Prefeitura/GCM) | `operador@safewalk.dev` | `Operador@123` |

No Swagger: **Authorize** → `username` = e-mail, `password` = senha.

## Endpoints

| Método | Rota | Descrição | Acesso |
|---|---|---|---|
| POST | `/auth/register` · `/auth/login` | Cadastro e login (JWT) | público |
| GET/PATCH | `/users/me` | Perfil e perfil de caminhada | cidadão |
| PUT | `/users/me/pin` | Define o PIN do SOS | cidadão |
| POST/GET/DELETE | `/contacts`, `/contacts/{id}` | Convida / lista / remove contatos | cidadão |
| POST | `/contacts/accept/{invite_token}` | Contato aceita o convite | público (link do convite) |
| POST | `/routes/compare` | Rota rápida × segura, com motivos | cidadão |
| GET | `/risk/score` | Score de risco de um ponto/horário | cidadão |
| POST/GET | `/trips`, `/trips/{id}` | Inicia / consulta trajeto | cidadão |
| POST | `/trips/{id}/locations` | Envia posição (detecta anomalia) | cidadão |
| POST | `/trips/{id}/complete` | Finaliza (check-in de chegada) | cidadão |
| GET | `/public/track/{token}` | Página do contato (ao vivo) | público (token) |
| POST/GET | `/reports` | Cria / lista relatos num raio | cidadão |
| POST | `/reports/{id}/confirm` | Confirma relato de outro usuário | cidadão |
| DELETE | `/reports/{id}` | Apaga o próprio relato | autor |
| PATCH | `/reports/{id}/resolve` | Encerra (SP156) ou marca como falso | operador |
| POST/GET | `/sos`, `/sos/{id}` | Dispara / consulta SOS (escalada por tempo) | cidadão |
| POST | `/sos/{id}/escalate` · `/sos/{id}/cancel` | Escala agora / cancela com PIN | cidadão |
| GET/POST | `/cameras` | Câmeras (mock Smart Sampa) | cidadão / operador |
| GET | `/dashboard/overview` | Painel da Prefeitura | operador |
| GET | `/health` | Healthcheck | público |

## Evidências da aplicação (`docs/`)

| Arquivo | Conteúdo |
|---|---|
| `docs/evidencias/01_migracoes_e_seed.txt` | Migrações (downgrade base → upgrade head), seed e `alembic check` executados em **PostgreSQL 16 real**, com a listagem das 10 tabelas do domínio (+ `alembic_version`, controle do Alembic) |
| `docs/evidencias/02_testes_pytest.txt` | Saída do `pytest -v`: 47 testes passando |
| `docs/evidencias/03_fluxo_completo_http.txt` | Fluxo real via HTTP contra a API sobre PostgreSQL: cadastro → contato (pendente bloqueado, depois aceito) → relato confirmado por outro usuário → score → comparação de rotas → trajeto → link público → desvio → SOS (PIN errado/correto) → chegada → painel (403 para cidadão) |
| `docs/evidencias/fluxo_http.sh` | Script que reproduz esse fluxo: `bash docs/evidencias/fluxo_http.sh` com a API no ar |
| `docs/openapi.json` | Especificação OpenAPI gerada automaticamente |


## Estrutura do repositório

```
app/
  main.py  config.py  database.py  security.py  deps.py  schemas.py  seed.py
  domain/    enums.py  models.py
  services/  geo.py  timeutil.py  risk_service.py  anomaly_service.py  report_service.py  sos_service.py
  routers/   auth.py  contacts.py  routes.py  trips.py  reports.py  sos.py  city.py
alembic/versions/   0001_...  0002_...
tests/              conftest.py  test_auth.py  test_risk_routes.py  test_reports.py  test_trips_sos.py  test_city_migrations.py  test_time_and_misc.py
docs/               openapi.json  evidencias/
Dockerfile  docker-compose.yml  requirements.txt  requirements.lock.txt  alembic.ini  pytest.ini  run.sh  run.bat
```

## Decisões e limitações (honestidade técnica)

- **Roteamento simulado**: sem motor de ruas (OSRM/Google). As rotas candidatas são geométricas (linha reta + desvios laterais). Em produção, o `risk_service` pontuaria as arestas do grafo viário.
- **Dados simulados**: os *hotspots* e câmeras do seed são fictícios, inspirados nas categorias de SSP-SP, Infosiga, GeoSampa e Smart Sampa. A ingestão dos dados reais fica para a disciplina de ML.
- **Integrações simuladas**: Smart Sampa, GCM e SP156 (protocolos fictícios gerados pela API).
- **Consultas geográficas em Python** (haversine). Em produção: PostgreSQL + PostGIS com índice espacial.
- **Rate limit em memória**: suficiente para uma instância; em produção usar Redis/API gateway.
- **Escalada do SOS por tempo é calculada sob demanda** (ao consultar o alerta); em produção, um *worker* agendado dispararia as notificações reais (push/SMS).
- **Chave JWT**: o valor padrão de `SECRET_KEY` é só para desenvolvimento. Em produção, defina `SECRET_KEY` (ver `.env.example`).
- **Fusos**: horários recebidos com fuso (ex.: `-03:00`, `Z`) são convertidos para UTC; `depart_at` com fuso é convertido para o horário de São Paulo.
- Nenhum dado pessoal real é usado.
