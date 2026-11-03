"""API REST da plataforma CLYVO VET (FastAPI) + servidor do painel web.

Execute:  python run.py     (ou: uvicorn app.main:create_app --factory --reload)
Documentação interativa (Swagger) em http://localhost:8000/docs
"""
import logging
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, Settings, get_settings
from .database import Database, utcnow
from .schemas import ChatIn, TelemetryIn
from .services.chat_agent import TutorChatAgent
from .services.copilot import ClinicalCopilot
from .services.knowledge_base import KnowledgeBase
from .services.llm_client import LLMClient
from .services.pipeline import SCENARIOS, MonitoringPipeline
from .services.risk_model import RiskModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

PRIORITY_ORDER = {2: 0, 1: 1, 0: 2}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    db = Database(settings.db_path)
    risk_model = RiskModel(settings.model_path, settings.dataset_path)
    kb = KnowledgeBase(settings.knowledge_dir)
    llm = LLMClient(settings.llm_provider, settings.llm_model)
    pipeline = MonitoringPipeline(db, risk_model, ClinicalCopilot(llm, kb), TutorChatAgent(llm, kb), settings.alert_cooldown_minutes)

    app = FastAPI(title="CLYVO VET — IoT & IA Generativa (Sprint 4)", version="4.0.0",
                  description="Telemetria da coleira inteligente, classificação de risco por ML, copiloto clínico (LLM + RAG) e assistente do tutor.")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.state.db, app.state.pipeline, app.state.llm = db, pipeline, llm

    def pet_or_404(pet_id: int) -> dict:
        pet = db.get_pet(pet_id)
        if not pet:
            raise HTTPException(404, f"Pet {pet_id} não encontrado")
        return pet

    @app.get("/api/health", tags=["sistema"])
    def health():
        return {"status": "ok", "llm_mode": llm.mode, "llm_model": llm.model if llm.online else None,
                "risk_model": risk_model.metrics["selected_model"], "model_version": risk_model.metrics["model_version"],
                "knowledge_chunks": len(kb.chunks), "server_time": utcnow().isoformat(timespec="seconds")}

    @app.get("/api/model/metrics", tags=["sistema"])
    def model_metrics():
        return risk_model.metrics

    # ------------------------------------------------------------------ pets
    @app.get("/api/pets", tags=["pets"])
    def list_pets():
        pets = db.list_pets()
        for pet in pets:
            pet["latest"] = db.latest_telemetry(pet["id"])
        return pets

    @app.get("/api/pets/{pet_id}", tags=["pets"])
    def get_pet(pet_id: int):
        pet = pet_or_404(pet_id)
        return {**pet, "records": db.get_records(pet_id), "latest": db.latest_telemetry(pet_id)}

    @app.get("/api/pets/{pet_id}/telemetry", tags=["pets"])
    def pet_telemetry(pet_id: int, limit: int = Query(60, ge=1, le=500)):
        pet_or_404(pet_id)
        return db.get_telemetry(pet_id, limit)

    @app.get("/api/pets/{pet_id}/summary", tags=["ia"])
    def pet_summary(pet_id: int, hours: int = Query(24, ge=1, le=168)):
        pet = pet_or_404(pet_id)
        since = utcnow() - timedelta(hours=hours)
        readings = db.get_telemetry_since(pet_id, since)
        alerts = [a for a in db.list_alerts(pet_id) if a["created_at"] >= since.isoformat(timespec="seconds")]
        return pipeline.copilot.daily_summary(pet, db.get_records(pet_id), readings, alerts)

    # ------------------------------------------------------------- telemetry
    @app.post("/api/telemetry", tags=["iot"], status_code=201)
    def ingest_telemetry(payload: TelemetryIn):
        pet = db.get_pet_by_device(payload.device_id) if payload.device_id else None
        if pet is None and payload.pet_id:
            pet = db.get_pet(payload.pet_id)
        if pet is None:
            raise HTTPException(404, "Dispositivo/pet não cadastrado")
        return pipeline.process_reading(pet, payload.to_reading())

    @app.post("/api/simulate/{scenario}", tags=["iot"], status_code=201)
    def simulate(scenario: str, pet_id: int = 1):
        if scenario not in SCENARIOS:
            raise HTTPException(400, f"Cenário inválido. Opções: {', '.join(SCENARIOS)}")
        return pipeline.simulate(pet_or_404(pet_id), scenario)

    # ---------------------------------------------------------------- triage
    @app.get("/api/triage", tags=["clinica"])
    def triage_queue():
        queue = []
        for pet in db.list_pets():
            latest = db.latest_telemetry(pet["id"])
            open_alerts = [a for a in db.list_alerts(pet["id"], limit=20) if a["status"] == "ABERTO"]
            level = max([latest["risk_level"] if latest else 0] + [a["risk_level"] for a in open_alerts])
            queue.append({"pet": pet, "latest": latest, "level": level, "open_alerts": len(open_alerts),
                          "last_alert": open_alerts[0] if open_alerts else None})
        return sorted(queue, key=lambda q: (PRIORITY_ORDER[q["level"]], -(q["latest"]["id"] if q["latest"] else 0)))

    @app.get("/api/alerts", tags=["clinica"])
    def list_alerts(pet_id: int | None = None, limit: int = Query(50, ge=1, le=200)):
        return db.list_alerts(pet_id, limit)

    @app.patch("/api/alerts/{alert_id}/ack", tags=["clinica"])
    def acknowledge(alert_id: int):
        if not db.get_alert(alert_id):
            raise HTTPException(404, "Alerta não encontrado")
        return db.acknowledge_alert(alert_id)

    @app.get("/api/notifications", tags=["clinica"])
    def notifications(limit: int = Query(30, ge=1, le=200)):
        return db.list_notifications(limit)

    # ------------------------------------------------------------------ chat
    @app.get("/api/pets/{pet_id}/chat", tags=["ia"])
    def chat_history(pet_id: int):
        pet_or_404(pet_id)
        return db.get_chat(pet_id)

    @app.post("/api/pets/{pet_id}/chat", tags=["ia"])
    def chat(pet_id: int, body: ChatIn):
        return pipeline.chat_message(pet_or_404(pet_id), body.message)

    frontend = Path(BASE_DIR / "frontend")
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app

