"""Popula o banco com dados de demonstração (idempotente).

Os hotspots são dados SIMULADOS, inspirados nas categorias das bases oficiais
(SSP-SP, Infosiga, GeoSampa) para a região Bela Vista/Consolação. Sem dados pessoais.
"""
from sqlalchemy import select

from app.database import SessionLocal
from app.domain.enums import CameraSource, UserRole
from app.domain.models import Camera, RiskHotspot, User
from app.security import hash_secret

# nome, lat, lng, raio_m, risco_base, iluminação_ok, fonte
HOTSPOTS = [
    ("R. Augusta x Av. Paulista", -23.5560, -46.6600, 250, 0.70, True, "SSP-SP (simulado)"),
    ("R. Augusta, 900-1300", -23.5547, -46.6585, 220, 0.65, True, "SSP-SP (simulado)"),
    ("R. da Consolação, 1500", -23.5530, -46.6610, 200, 0.55, False, "SSP-SP/GeoSampa (simulado)"),
    ("R. Frei Caneca, 300-600", -23.5540, -46.6540, 200, 0.40, False, "GeoSampa (simulado)"),
    ("Av. Paulista x R. Pamplona", -23.5640, -46.6520, 180, 0.35, True, "Infosiga (simulado)"),
    ("R. Peixoto Gomide", -23.5575, -46.6575, 180, 0.45, False, "GeoSampa (simulado)"),
]
CAMERAS = [  # Smart Sampa (mock)
    ("Câmera Av. Paulista 1106", -23.5646, -46.6528, CameraSource.public),
    ("Câmera Av. Paulista x Augusta", -23.5565, -46.6595, CameraSource.public),
    ("Câmera Consolação 2000", -23.5535, -46.6600, CameraSource.private),
    ("Câmera Frei Caneca 569", -23.5530, -46.6525, CameraSource.private),
    ("Câmera Peixoto Gomide", -23.5580, -46.6570, CameraSource.public),
]


def run() -> None:
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.email == "operador@safewalk.dev")):
            db.add(User(name="Operador Prefeitura", email="operador@safewalk.dev",
                        password_hash=hash_secret("Operador@123"), role=UserRole.operator))
        if not db.scalar(select(User).where(User.email == "leo@safewalk.dev")):
            db.add(User(name="Leo Demo", email="leo@safewalk.dev", password_hash=hash_secret("Cidadao@123")))
        if not db.scalar(select(RiskHotspot)):
            db.add_all(RiskHotspot(name=n, lat=la, lng=ln, radius_m=r, base_risk=b, lighting_ok=li, source=s)
                       for n, la, ln, r, b, li, s in HOTSPOTS)
        if not db.scalar(select(Camera)):
            db.add_all(Camera(name=n, lat=la, lng=ln, source=s) for n, la, ln, s in CAMERAS)
        db.commit()
    print("Seed concluído. Operador: operador@safewalk.dev / Operador@123 | Cidadão: leo@safewalk.dev / Cidadao@123")


if __name__ == "__main__":
    run()
