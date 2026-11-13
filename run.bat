@echo off
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
alembic upgrade head
python -m app.seed
echo.
echo API:     http://localhost:8000
echo Swagger: http://localhost:8000/docs
uvicorn app.main:app --host 0.0.0.0 --port 8000
