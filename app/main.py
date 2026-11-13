"""SafeWalk API — Global Solution FIAP 2026 (SOA e Web Services)."""
from fastapi import FastAPI

from app.routers import auth, city, contacts, reports, routes, sos, trips

DESCRIPTION = """
Backend do **SafeWalk**: rotas mais seguras para quem anda a pé em São Paulo.

* **Rotas**: compara a rota mais rápida com a mais segura e explica o risco de cada trecho.
* **Acompanhamento**: contatos veem a localização por link (com consentimento), sem instalar nada.
* **SOS**: escalada por etapas (pergunta → contatos → central da GCM); só o PIN cancela.
* **Relatos colaborativos**: peso progressivo, validade por tipo e antiabuso.
* **Painel da Prefeitura**: visão B2G de relatos, SOS e chamados SP156.

Integrações Smart Sampa, GCM e SP156 são **simuladas** nesta entrega.
Use **Authorize** (e-mail como `username`) para testar os endpoints protegidos.
"""

app = FastAPI(title="SafeWalk API", version="1.0.0", description=DESCRIPTION,
              contact={"name": "Equipe SafeWalk — FIAP 3ESR"})

for module in (auth, contacts, routes, trips, reports, sos, city):
    app.include_router(module.router)


@app.get("/health", tags=["Infra"], summary="Healthcheck")
def health():
    return {"status": "ok", "service": "safewalk-api"}
