#!/usr/bin/env bash
# Sobe o SafeWalk localmente com UM comando: ./run.sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
alembic upgrade head
python -m app.seed
echo ""
echo "API:     http://localhost:8000"
echo "Swagger: http://localhost:8000/docs"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
